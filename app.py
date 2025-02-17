import streamlit as st
import pandas as pd
import csv
from datetime import datetime

# Configurar la página para que use el ancho completo y establecer título e ícono (opcional)
st.set_page_config(layout="wide", page_title="Cuadro Completo", page_icon="🌐")

# Inyección de CSS para adaptar la tipografía e identidad visual según el Manual de Normas Gráficas
st.markdown("""
<style>
/* Tipografía institucional: Gill Sans */
body, .css-18ni7ap, .css-1d391kg {
    font-family: 'Gill Sans', sans-serif;
}

/* Encabezados con color institucional (Pantone 2935 U) */
h1, h2, h3, h4, h5, h6 {
    color: #0072CE;
}

/* Estilo para enlaces */
a {
    color: #0072CE;
}

/* Estilo para la tabla para que tenga un aspecto limpio y corporativo */
table {
    border-collapse: collapse;
    width: 100%;
}
table, th, td {
    border: 1px solid #ddd;
}
th, td {
    padding: 8px;
    text-align: left;
}
/* Se ha eliminado el estilo de bandas de colores alternadas */

/* Estilos para la barra lateral: fondo Pantone 290 U (#D1E8FF) y letras Pantone 2935 U (#0072CE) */
[data-testid="stSidebar"] > div:first-child {
    background-color: #D1E8FF;
    color: #0072CE;
}
[data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
    color: #0072CE;
}
</style>
""", unsafe_allow_html=True)

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
    2. Lee el archivo usando csv.reader con delimiter="\t" (los campos están separados por tabulaciones).
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
        with open("factores_conversion.csv", newline='', encoding="latin-1") as csvfile:
            reader = csv.reader(csvfile, delimiter="\t")
            header = next(reader)
            destination_years = [col.strip() for col in header[1:]]
            for row in reader:
                if not row:
                    continue
                try:
                    base_year = int(row[0].strip())
                except Exception as e:
                    st.error(f"Error al convertir el año base '{row[0]}' a entero: {e}")
                    return None
                subdict = {}
                for i, val in enumerate(row[1:], start=1):
                    val_clean = val.strip().replace(",", ".")
                    try:
                        factor = float(val_clean)
                    except Exception as e:
                        st.error(f"Error al convertir el valor '{val}' en la fila con año base {base_year}: {e}")
                        return None
                    subdict[destination_years[i-1]] = factor
                factors[base_year] = subdict
    except Exception as e:
        st.error(f"Error al leer 'factores_conversion.csv': {e}")
        return None

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
    codigo_bip_norm = str(codigo_bip).strip().upper()
    etapa_norm = str(etapa).strip().upper()
    df_filtered = df_base[
        (df_base["CODIGO BIP"].astype(str).str.strip().str.upper() == codigo_bip_norm) &
        (df_base["ETAPA"].astype(str).str.strip().str.upper() == etapa_norm)
    ]
    if df_filtered.empty:
        st.error("No se encontraron datos para el CODIGO BIP y ETAPA seleccionados.")
        return None, None, None

    df_filtered.columns = [str(col).strip() for col in df_filtered.columns]
    expense_cols = [col for col in df_filtered.columns if col.isdigit() and 2011 <= int(col) <= 2024]
    df_grouped = df_filtered.groupby("ITEMS")[expense_cols].sum().reset_index()

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

    global_years = list(range(start_year, anio_termino + 1))
    if 2025 not in global_years:
        global_years.append(2025)
        global_years.sort()

    cols = [str(y) for y in global_years]
    for col in cols:
        if col not in df_grouped.columns:
            df_grouped[col] = 0

    df_grouped = df_grouped[["ITEMS"] + cols].sort_values("ITEMS")
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
    year_cols = [col for col in df_conv.columns if col.isdigit()]
    data = []
    for idx, row in df_conv.iterrows():
        if str(row["ITEMS"]).strip().upper() == "TOTAL":
            continue
        pagado = sum(row[col] for col in year_cols if int(col) < 2025)
        solicitado_2025 = row["2025"] if "2025" in row and pd.notnull(row["2025"]) else 0
        solicitado_siguientes = sum(row[col] for col in year_cols if int(col) > 2025)
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
    # Cambiamos el encabezado de la barra lateral
    st.sidebar.header("Seleccionar Proyecto FNDR")
    
    df_base = load_base_data()
    
    # Construir la lista de opciones para el selectbox combinando "CODIGO BIP" y "NOMBRE(s)"
    unique_codes = df_base["CODIGO BIP"].dropna().unique().tolist()
    code_options = []
    for code in unique_codes:
        nombres = df_base[
            df_base["CODIGO BIP"].astype(str).str.strip().str.upper() == str(code).strip().upper()
        ]["NOMBRE"].unique().tolist()
        nombres_str = ", ".join(nombres)
        code_options.append(f"{code} – {nombres_str}")
    code_options = sorted(code_options)
    
    # Mostrar el selectbox con las opciones combinadas
    selected_option = st.sidebar.selectbox("Seleccione el CODIGO BIP:", code_options)
    selected_codigo_bip = selected_option.split(" – ")[0]
    
    # Selección de ETAPA
    etapa_list = sorted(df_base["ETAPA"].dropna().unique().tolist())
    selected_etapa = st.sidebar.selectbox("Seleccione la ETAPA:", etapa_list)
    
    anio_termino = st.sidebar.number_input("Ingrese el AÑO DE TERMINO del proyecto:",
                                           min_value=2011, max_value=2100, value=2024, step=1)
    
    if st.sidebar.button("Generar Planilla"):
        st.session_state.planilla_generada = True

    if st.session_state.planilla_generada:
        try:
            project_name = df_base[
                df_base["CODIGO BIP"].astype(str).str.strip().str.upper() == str(selected_codigo_bip).strip().upper()
            ]["NOMBRE"].iloc[0]
        except Exception as e:
            st.error(f"No se pudo obtener el nombre del proyecto para el CODIGO BIP {selected_codigo_bip}: {e}")
            return
        
        st.header(f"Proyecto: {project_name} | Código BIP: {selected_codigo_bip} | Etapa: {selected_etapa}")
        
        df_grouped, global_years, _ = get_filtered_data(df_base, selected_codigo_bip, selected_etapa, anio_termino)
        if df_grouped is None:
            return
        
        st.markdown("### Gasto Real no Ajustado")
        
        # Configuración para edición de la tabla
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
        
        html_table = df_formatted.to_html(index=False)
        st.markdown(html_table, unsafe_allow_html=True)
        
        conversion_factors = load_conversion_factors()
        if conversion_factors is None:
            return
        
        available_moneda = sorted(conversion_factors.columns, key=lambda x: int(x))
        current_year = str(datetime.now().year)
        default_index = available_moneda.index(current_year) if current_year in available_moneda else 0
        dest_moneda = st.sidebar.selectbox(
            "Seleccione la moneda de destino (año de conversión):", 
            available_moneda, 
            index=default_index
        )
        
        df_converted = convert_expense_dataframe(validated_df, int(dest_moneda), conversion_factors)
        df_converted_final = append_totals_with_column(df_converted)
        df_converted_formatted = df_converted_final.copy()
        for col in df_converted_formatted.columns:
            if col.isdigit() or col == "Total":
                df_converted_formatted[col] = df_converted_formatted[col].apply(format_miles_pesos)
        
        st.markdown(f"### Anualizacion en Moneda {dest_moneda} (M$)")
        html_table_conv = df_converted_formatted.to_html(index=False)
        st.markdown(html_table_conv, unsafe_allow_html=True)
        
        st.markdown("### SOLICITUD DE FINANCIAMIENTO")
        df_solicitud = create_solicitud_financiamiento(df_converted)
        for col in ["Pagado al 31/12/2024", "Solicitado para el año 2025", "Solicitado años siguientes", "Costo Total"]:
            df_solicitud[col] = df_solicitud[col].apply(format_miles_pesos)
        html_solicitud = df_solicitud.to_html(index=False)
        st.markdown(html_solicitud, unsafe_allow_html=True)

if __name__ == '__main__':
    main()
