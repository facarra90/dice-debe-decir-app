import streamlit as st
import pandas as pd
import csv

# Configurar la página para que use el ancho completo
st.set_page_config(layout="wide")

# Inicializar la variable de estado para mantener visible la planilla
if "planilla_generada" not in st.session_state:
    st.session_state.planilla_generada = False

@st.cache_data
def load_base_data():
    # Cargar la base de datos desde un archivo Excel
    return pd.read_excel("BASE DE DATOS.xlsx")

@st.cache_data
def load_conversion_factors():
    """
    Carga y procesa el archivo 'factores_conversion.csv' siguiendo estos pasos:
    
    1. Abre el archivo usando open() con newline='' y encoding="latin-1".
    2. Lee el archivo usando csv.reader con delimiter="\t" (según el error, los campos están separados por tabulaciones).
    3. La primera fila es la cabecera:
         - La primera celda es un encabezado descriptivo (ej.: "AÑO Base").
         - Las siguientes celdas son los años de destino.
    4. Itera sobre las filas de datos:
         - Convierte el primer elemento (año base) a entero.
         - Para cada valor de las columnas siguientes, elimina espacios, reemplaza la coma decimal por punto y convierte a float.
    5. Construye un diccionario y luego lo convierte a DataFrame.
    """
    factors = {}
    try:
        # Cambia el delimitador a "\t" porque los errores indican que se usan tabulaciones
        with open("factores_conversion.csv", newline='', encoding="latin-1") as csvfile:
            reader = csv.reader(csvfile, delimiter="\t")
            # Leer la cabecera (no se convierte a números)
            header = next(reader)
            # La primera celda es descriptiva; las siguientes son los años de destino.
            destination_years = [col.strip() for col in header[1:]]
            for row in reader:
                if not row:
                    continue  # omitir filas vacías
                # El primer elemento debe ser el año base: eliminar espacios y convertir a entero.
                try:
                    base_year = int(row[0].strip())
                except Exception as e:
                    st.error(f"Error al convertir el año base '{row[0]}' a entero: {e}")
                    return None
                subdict = {}
                for i, val in enumerate(row[1:], start=1):
                    # Eliminar espacios y reemplazar coma por punto
                    val_clean = val.strip().replace(",", ".")
                    try:
                        factor = float(val_clean)
                    except Exception as e:
                        st.error(f"Error al convertir el valor '{val}' en la fila con año base {base_year}: {e}")
                        return None
                    # Asignar el factor al año de destino correspondiente
                    subdict[destination_years[i-1]] = factor
                factors[base_year] = subdict
    except Exception as e:
        st.error(f"Error al leer 'factores_conversion.csv': {e}")
        return None

    # Convertir el diccionario a DataFrame
    df_factors = pd.DataFrame.from_dict(factors, orient="index")
    df_factors.index.name = header[0].strip()
    return df_factors

def format_miles_pesos(x):
    """
    Formatea el número redondeándolo a entero y separando los miles con punto.
    Ejemplo: 1234567.89 -> "1.234.568"
    """
    try:
        return f"{int(round(x)):,}".replace(",", ".")
    except Exception:
        return x

def get_filtered_data(df_base, codigo_bip, etapa, anio_termino):
    # Normalizar los filtros
    codigo_bip_norm = str(codigo_bip).strip().upper()
    etapa_norm = str(etapa).strip().upper()
    df_filtered = df_base[
        (df_base["CODIGO BIP"].astype(str).str.strip().str.upper() == codigo_bip_norm) &
        (df_base["ETAPA"].astype(str).str.strip().str.upper() == etapa_norm)
    ]
    if df_filtered.empty:
        st.error("No se encontraron datos para el CODIGO BIP y ETAPA seleccionados.")
        return None, None, None

    # Quitar espacios en los nombres de columnas
    df_filtered.columns = [str(col).strip() for col in df_filtered.columns]
    # Seleccionar columnas que representan años (2011 a 2024)
    expense_cols = [col for col in df_filtered.columns if col.isdigit() and 2011 <= int(col) <= 2024]
    # Agrupar por "ITEMS" y sumar los gastos de cada año
    df_grouped = df_filtered.groupby("ITEMS")[expense_cols].sum().reset_index()

    # Determinar el primer año en el que se registra gasto
    sorted_years = sorted([int(col) for col in expense_cols])
    start_year = None
    for y in sorted_years:
        if str(y) in df_grouped.columns and df_grouped[str(y)].sum() > 0:
            start_year = y
            break
    if start_year is None:
        st.error("No se encontró gasto inicial en los datos.")
        return None, None, None
    if anio_termino < start_year:
        st.error("El AÑO DE TERMINO debe ser mayor o igual al año de inicio del gasto.")
        return None, None, None

    # Crear la lista de años desde el inicio hasta el AÑO DE TERMINO
    global_years = list(range(start_year, anio_termino + 1))
    # Forzar la inclusión del año 2025
    if 2025 not in global_years:
        global_years.append(2025)
        global_years.sort()

    # Asegurar que exista una columna para cada año en la lista
    cols = [str(y) for y in global_years]
    for col in cols:
        if col not in df_grouped.columns:
            df_grouped[col] = 0

    # Reordenar las columnas: "ITEMS" seguido de los años en orden
    df_grouped = df_grouped[["ITEMS"] + cols].sort_values("ITEMS")
    # Convertir las columnas de año a valores numéricos
    for col in df_grouped.columns:
        if col.isdigit():
            df_grouped[col] = pd.to_numeric(df_grouped[col], errors="coerce").fillna(0)
    return df_grouped, global_years, df_filtered

def validate_edited_data(df, global_years):
    if df.empty:
        st.error("La tabla no puede estar vacía.")
        return None
    if "ITEMS" not in df.columns:
        st.error("La columna 'ITEMS' es obligatoria y no puede ser eliminada.")
        return None
    for y in global_years:
        col = str(y)
        if col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            except Exception as e:
                st.error(f"Error al convertir la columna {col}: {e}")
                return None
    return df

def append_totals_with_column(df):
    """
    Agrega una columna "Total" a cada fila con la suma de los valores numéricos (años),
    y luego añade una fila de totales que sume cada columna, incluida la columna "Total".
    """
    df_copy = df.copy()
    numeric_cols = [col for col in df_copy.columns if col.isdigit()]
    df_copy["Total"] = df_copy[numeric_cols].sum(axis=1)
    
    totals = {}
    for col in df_copy.columns:
        if col in numeric_cols or col == "Total":
            totals[col] = df_copy[col].sum()
        else:
            totals[col] = ""
    totals["ITEMS"] = "Total"
    totals_df = pd.DataFrame([totals])
    combined = pd.concat([df_copy, totals_df], ignore_index=True)
    return combined

def convert_expense_dataframe(df, dest_year, conversion_factors):
    """
    Convierte los valores de gasto en el DataFrame original al año (o escala) destino indicado, 
    utilizando los factores de conversión.
    
    Para cada columna (año de origen) se aplica:
       Valor convertido = (Valor original * Factor de conversión) / 1000

    Si el año de origen no se encuentra en conversion_factors, se usa el máximo año base disponible.
    Si el año destino no existe en la tabla, se utiliza el factor correspondiente al máximo año destino.
    """
    converted_df = df.copy()
    
    for col in df.columns:
        if col.isdigit():
            origin_year = int(col)
            if origin_year not in conversion_factors.index:
                origin_year = conversion_factors.index.max()
            if str(dest_year) not in conversion_factors.columns:
                dest_year_str = max(conversion_factors.columns, key=lambda x: int(x))
            else:
                dest_year_str = str(dest_year)
            factor = conversion_factors.loc[origin_year, dest_year_str]
            converted_df[col] = df[col] * factor / 1000
    return converted_df

def create_solicitud_financiamiento(df_conv):
    """
    A partir del DataFrame de la inversión anualizada en moneda (df_conv), genera la tabla
    SOLICITUD DE FINANCIAMIENTO con las siguientes columnas:
    
      - Fuente: siempre "F.N.D.R."
      - Asignación Presupuestaria (Item): contenido de "ITEMS"
      - Moneda: siempre "M$"
      - Pagado al 31/12/2024: suma de los años anteriores a 2025 (los años < 2025)
      - Solicitado para el año 2025: valor de la columna "2025"
      - Solicitado años siguientes: suma de los años mayores a 2025 (años > 2025)
      - Costo Total: suma de las tres columnas anteriores.
    
    Además, agrega una fila total al final que sume los campos numéricos.
    """
    # Seleccionar solo las columnas que sean años (en formato dígito) y la columna "ITEMS"
    year_cols = [col for col in df_conv.columns if col.isdigit()]
    
    # Se crea la tabla base usando la información de cada fila
    data = []
    for idx, row in df_conv.iterrows():
        # Si la fila es la fila total (por ejemplo, si "ITEMS" es "Total"), se procesará al final.
        if str(row["ITEMS"]).strip().upper() == "TOTAL":
            continue
        # Sumar los años anteriores a 2025
        pagado = sum(row[col] for col in year_cols if int(col) < 2025)
        # Valor para 2025
        solicitado_2025 = row["2025"] if "2025" in row and pd.notnull(row["2025"]) else 0
        # Sumar los años siguientes a 2025
        solicitado_siguientes = sum(row[col] for col in year_cols if int(col) > 2025)
        # Costo Total
        costo_total = pagado + solicitado_2025 + solicitado_siguientes
        data.append({
            "Fuente": "F.N.D.R.",
            "Asignación Presupuestaria (Item)": row["ITEMS"],
            "Moneda": "M$",
            "Pagado al 31/12/2024": pagado,
            "Solicitado para el año 2025": solicitado_2025,
            "Solicitado años siguientes": solicitado_siguientes,
            "Costo Total": costo_total
        })
        
    df_solicitud = pd.DataFrame(data)
    
    # Calcular la fila de totales para las columnas numéricas
    total_row = {
        "Fuente": "",
        "Asignación Presupuestaria (Item)": "Total",
        "Moneda": ""
    }
    for col in ["Pagado al 31/12/2024", "Solicitado para el año 2025", "Solicitado años siguientes", "Costo Total"]:
        total_row[col] = df_solicitud[col].sum()
    df_solicitud = pd.concat([df_solicitud, pd.DataFrame([total_row])], ignore_index=True)
    return df_solicitud

def main():
    st.title("Gasto Real no Ajustado Cuadro Completo")
    df_base = load_base_data()
    
    # Filtros en la barra lateral
    st.sidebar.header("Filtrar Datos")
    codigo_bip_list = sorted(df_base["CODIGO BIP"].dropna().unique().tolist())
    selected_codigo_bip = st.sidebar.selectbox("Seleccione el CODIGO BIP:", codigo_bip_list)
    etapa_list = sorted(df_base["ETAPA"].dropna().unique().tolist())
    selected_etapa = st.sidebar.selectbox("Seleccione la ETAPA:", etapa_list)
    anio_termino = st.sidebar.number_input("Ingrese el AÑO DE TERMINO del proyecto:",
                                           min_value=2011, max_value=2100, value=2024, step=1)
    
    if st.sidebar.button("Generar Planilla"):
        st.session_state.planilla_generada = True
        
    if st.session_state.planilla_generada:
        df_grouped, global_years, _ = get_filtered_data(df_base, selected_codigo_bip, selected_etapa, anio_termino)
        if df_grouped is None:
            return
        
        st.markdown("### Gasto Real no Ajustado Cuadro Completo (Valores Originales)")
        col_config = {}
        for y in global_years:
            col = str(y)
            if col in df_grouped.columns:
                col_config[col] = st.column_config.NumberColumn(min_value=0)
        col_config["ITEMS"] = st.column_config.TextColumn(disabled=True)
        
        if hasattr(st, "data_editor"):
            edited_df = st.data_editor(df_grouped, key="final_editor", column_config=col_config)
        else:
            edited_df = st.experimental_data_editor(df_grouped, key="final_editor", column_config=col_config)
        
        validated_df = validate_edited_data(edited_df, global_years)
        if validated_df is None:
            return
        
        df_final = append_totals_with_column(validated_df)
        df_formatted = df_final.copy()
        for col in df_formatted.columns:
            if col.isdigit() or col == "Total":
                df_formatted[col] = df_formatted[col].apply(format_miles_pesos)
        
        st.dataframe(df_formatted, use_container_width=True)
        
        st.markdown("### Gasto Convertido a la Moneda Seleccionada")
        conversion_factors = load_conversion_factors()
        if conversion_factors is None:
            return
        
        available_moneda = sorted(conversion_factors.columns, key=lambda x: int(x))
        dest_moneda = st.sidebar.selectbox("Seleccione la moneda de destino (año de conversión):", available_moneda)
        
        df_converted = convert_expense_dataframe(validated_df, int(dest_moneda), conversion_factors)
        df_converted_final = append_totals_with_column(df_converted)
        df_converted_formatted = df_converted_final.copy()
        for col in df_converted_formatted.columns:
            if col.isdigit() or col == "Total":
                df_converted_formatted[col] = df_converted_formatted[col].apply(format_miles_pesos)
        
        st.dataframe(df_converted_formatted, use_container_width=True)
        
        # Nueva tabla: SOLICITUD DE FINANCIAMIENTO
        st.markdown("### SOLICITUD DE FINANCIAMIENTO")
        # Se genera la tabla a partir del DataFrame convertido (sin la fila total, para evitar duplicados)
        # Se toma df_converted ya que contiene los valores en moneda convertida (M$)
        df_solicitud = create_solicitud_financiamiento(df_converted)
        # Opcional: formatear los números de la nueva tabla
        for col in ["Pagado al 31/12/2024", "Solicitado para el año 2025", "Solicitado años siguientes", "Costo Total"]:
            df_solicitud[col] = df_solicitud[col].apply(format_miles_pesos)
        st.dataframe(df_solicitud, use_container_width=True)

if __name__ == '__main__':
    main()
