import streamlit as st
import pandas as pd

# Configurar la página para que use todo el ancho disponible
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
    Carga la tabla de factores de conversión desde un archivo CSV.
    Se espera que el CSV tenga la siguiente estructura:
      - La primera columna (index) corresponde al año base.
      - Las columnas restantes corresponden a los años de destino.
    El resultado es un diccionario anidado con la forma:
      { año_base: { año_destino: factor, ... }, ... }
    Se intenta leer probando diferentes codificaciones y separadores.
    """
    encodings = ["utf-8-sig", "latin1"]
    separators = [",", ";"]
    for enc in encodings:
        for sep in separators:
            try:
                df_factors = pd.read_csv(
                    "factores_conversion.csv",
                    index_col=0,
                    encoding=enc,
                    sep=sep,
                    on_bad_lines='skip'
                )
                # Convertir índice y columnas a enteros
                df_factors.index = df_factors.index.astype(int)
                df_factors.columns = df_factors.columns.astype(int)
                return df_factors.to_dict(orient="index")
            except Exception:
                pass
    st.error("Error al leer el archivo factores_conversion.csv. Por favor, verifica su formato.")
    return {}

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
    # Identificar las columnas de años (números)
    numeric_cols = [col for col in df_copy.columns if col.isdigit()]
    # Agregar columna "Total" (suma de los valores de las columnas numéricas)
    df_copy["Total"] = df_copy[numeric_cols].sum(axis=1)
    
    # Crear una fila con los totales de cada columna numérica y de la columna "Total"
    totals = {}
    for col in df_copy.columns:
        if col in numeric_cols or col == "Total":
            totals[col] = df_copy[col].sum()
        else:
            totals[col] = ""
    totals["ITEMS"] = "Total"
    totals_df = pd.DataFrame([totals])
    # Concatenar la fila de totales al DataFrame original
    combined = pd.concat([df_copy, totals_df], ignore_index=True)
    return combined

def convert_table(df, conversion_year, conversion_factors):
    """
    Genera un nuevo DataFrame con los valores convertidos a la moneda del año indicado.
    Para cada columna de año:
      - Se obtiene el factor de conversión para el par (año de la columna, año de destino).
      - Si el año base no existe o no tiene factor para el año destino, se utiliza el factor
        del máximo año disponible.
      - Se aplica la conversión: (valor * factor) / 1000.
    Se recalcula la columna "Total" como la suma de los años convertidos y se formatea la salida.
    """
    df_conv = df.copy()
    # Identificar las columnas de años (cadenas que representan dígitos)
    year_cols = [col for col in df_conv.columns if col.isdigit()]
    
    for col in year_cols:
        base_year = int(col)
        # Buscar el factor correspondiente en la tabla cargada
        if base_year in conversion_factors:
            factor = conversion_factors[base_year].get(conversion_year)
            if factor is None:
                # Si no se encuentra el factor para el año de destino, usar el factor del máximo año destino disponible
                max_target = max(conversion_factors[base_year].keys())
                factor = conversion_factors[base_year][max_target]
        else:
            # Si el año de la columna no está en la tabla, usar el factor del máximo año base disponible
            max_base = max(conversion_factors.keys())
            factor = conversion_factors[max_base].get(conversion_year)
            if factor is None:
                max_target = max(conversion_factors[max_base].keys())
                factor = conversion_factors[max_base][max_target]
        # Convertir la columna: (valor * factor) / 1000
        df_conv[col] = pd.to_numeric(df_conv[col], errors="coerce").fillna(0)
        df_conv[col] = (df_conv[col] * factor) / 1000
        df_conv[col] = df_conv[col].round(0).astype(int)
    
    # Recalcular la columna "Total" como la suma de las columnas de año convertidas
    if "Total" in df_conv.columns:
        df_conv["Total"] = df_conv[year_cols].sum(axis=1)
        df_conv["Total"] = df_conv["Total"].round(0).astype(int)
    
    # Aplicar el formato de "Miles de Pesos" a las columnas numéricas
    for col in year_cols + (["Total"] if "Total" in df_conv.columns else []):
        df_conv[col] = df_conv[col].apply(format_miles_pesos)
    
    return df_conv

def main():
    st.title("Gasto Real no Ajustado Cuadro Completo")
    df_base = load_base_data()
    conversion_factors = load_conversion_factors()  # Cargar factores desde el CSV
    
    # Filtros en la barra lateral
    st.sidebar.header("Filtrar Datos")
    codigo_bip_list = sorted(df_base["CODIGO BIP"].dropna().unique().tolist())
    selected_codigo_bip = st.sidebar.selectbox("Seleccione el CODIGO BIP:", codigo_bip_list)
    etapa_list = sorted(df_base["ETAPA"].dropna().unique().tolist())
    selected_etapa = st.sidebar.selectbox("Seleccione la ETAPA:", etapa_list)
    anio_termino = st.sidebar.number_input("Ingrese el AÑO DE TERMINO del proyecto:",
                                           min_value=2011, max_value=2100, value=2024, step=1)
    
    # Seleccionar el año para la conversión de moneda
    conversion_year = st.sidebar.selectbox("Seleccione el año para la conversión:", list(range(2011, 2025)))
    
    if st.sidebar.button("Generar Planilla"):
        st.session_state.planilla_generada = True
        
    if st.session_state.planilla_generada:
        df_grouped, global_years, _ = get_filtered_data(df_base, selected_codigo_bip, selected_etapa, anio_termino)
        if df_grouped is None:
            return
        
        st.markdown("### Gasto Real no Ajustado Cuadro Completo")
        # Configuración para el editor: se permite editar las columnas numéricas y se bloquea "ITEMS"
        col_config = {}
        for y in global_years:
            col = str(y)
            if col in df_grouped.columns:
                col_config[col] = st.column_config.NumberColumn(min_value=0)
        col_config["ITEMS"] = st.column_config.TextColumn(disabled=True)
        
        # Mostrar la tabla editable
        if hasattr(st, "data_editor"):
            edited_df = st.data_editor(df_grouped, key="final_editor", column_config=col_config)
        else:
            edited_df = st.experimental_data_editor(df_grouped, key="final_editor", column_config=col_config)
        
        validated_df = validate_edited_data(edited_df, global_years)
        if validated_df is None:
            return
        
        # Agregar columna "Total" a cada fila y la fila de totales final
        df_final = append_totals_with_column(validated_df)
        
        # Mostrar la tabla original (sin conversión) utilizando todo el ancho disponible
        df_formatted = df_final.copy()
        # Aplicar formato de miles de pesos a las columnas numéricas
        for col in [c for c in df_formatted.columns if c.isdigit()] + (["Total"] if "Total" in df_formatted.columns else []):
            df_formatted[col] = df_formatted[col].apply(format_miles_pesos)
        st.dataframe(df_formatted, use_container_width=True)
        
        # Generar la tabla convertida a la moneda del año seleccionado
        df_converted = convert_table(df_final, conversion_year, conversion_factors)
        st.markdown(f"### Gasto Real Ajustado a la moneda del año {conversion_year}")
        st.dataframe(df_converted, use_container_width=True)

if __name__ == '__main__':
    main()
