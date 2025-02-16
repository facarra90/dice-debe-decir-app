import streamlit as st
import pandas as pd

# Configurar la página para usar el ancho completo
st.set_page_config(page_title="Gasto Real no Ajustado", layout="wide")

# Inicializar la variable de estado para mantener visible la planilla
if "planilla_generada" not in st.session_state:
    st.session_state.planilla_generada = False

@st.cache_data
def load_base_data():
    # Cargar la base de datos desde un archivo Excel
    return pd.read_excel("BASE DE DATOS.xlsx")

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
        
        # Aplicar el formato de "Miles de Pesos" sin decimales (se usa Pandas Styler para la visualización)
        df_styled = df_final.style.format(format_miles_pesos)
        
        st.table(df_styled)

if __name__ == '__main__':
    main()
