import streamlit as st
import pandas as pd

# Función para cargar la base de datos (archivo Excel)
@st.cache_data
def load_base_data():
    return pd.read_excel("BASE DE DATOS.xlsx")

# Función para filtrar y preparar los datos, agrupándolos por "ITEMS"
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

    # Eliminar espacios en los nombres de columnas
    df_filtered.columns = [str(col).strip() for col in df_filtered.columns]
    # Seleccionar columnas que representan años (suponiendo que están entre 2011 y 2024)
    expense_cols = [col for col in df_filtered.columns if col.isdigit() and 2011 <= int(col) <= 2024]
    # Agrupar por "ITEMS" y sumar los gastos de los años
    df_grouped = df_filtered.groupby("ITEMS")[expense_cols].sum().reset_index()

    # Determinar el primer año en que se registra gasto
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

    # Crear la lista de años a partir del año inicial hasta el año de término
    global_years = list(range(start_year, anio_termino + 1))
    # Forzar que la columna 2025 esté presente, incluso si no está en el rango
    if 2025 not in global_years:
        global_years.append(2025)
        global_years.sort()

    # Asegurar que el DataFrame tenga una columna para cada año de la lista
    cols = [str(y) for y in global_years]
    for col in cols:
        if col not in df_grouped.columns:
            df_grouped[col] = 0

    # Reordenar las columnas: "ITEMS" seguido de los años ordenados
    df_grouped = df_grouped[["ITEMS"] + cols].sort_values("ITEMS")
    # Convertir las columnas de año a numérico
    for col in df_grouped.columns:
        if col.isdigit():
            df_grouped[col] = pd.to_numeric(df_grouped[col], errors="coerce").fillna(0)
    return df_grouped, global_years, df_filtered

# Función para validar que los datos editados sean correctos
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

# Función principal
def main():
    st.title("Gasto Real no Ajustado Cuadro Completo")
    df_base = load_base_data()
    
    # Filtros en la barra lateral: selección de CODIGO BIP, ETAPA y AÑO DE TERMINO
    st.sidebar.header("Filtrar Datos")
    codigo_bip_list = sorted(df_base["CODIGO BIP"].dropna().unique().tolist())
    selected_codigo_bip = st.sidebar.selectbox("Seleccione el CODIGO BIP:", codigo_bip_list)
    etapa_list = sorted(df_base["ETAPA"].dropna().unique().tolist())
    selected_etapa = st.sidebar.selectbox("Seleccione la ETAPA:", etapa_list)
    anio_termino = st.sidebar.number_input("Ingrese el AÑO DE TERMINO del proyecto:",
                                           min_value=2011, max_value=2100, value=2024, step=1)
    
    if st.sidebar.button("Generar Planilla"):
        df_grouped, global_years, _ = get_filtered_data(df_base, selected_codigo_bip, selected_etapa, anio_termino)
        if df_grouped is None:
            return
        
        st.markdown("### Gasto Real no Ajustado Cuadro Completo")
        # Configurar las columnas para el editor: se permiten editar los valores numéricos y se bloquea la columna "ITEMS"
        col_config = {}
        for y in global_years:
            col = str(y)
            if col in df_grouped.columns:
                col_config[col] = st.column_config.NumberColumn(min_value=0)
        col_config["ITEMS"] = st.column_config.TextColumn(disabled=True)
        
        # Desplegar la tabla editable
        if hasattr(st, "data_editor"):
            edited_df = st.data_editor(df_grouped, key="final_editor", column_config=col_config)
        else:
            edited_df = st.experimental_data_editor(df_grouped, key="final_editor", column_config=col_config)
        
        # Validar y actualizar los datos editados
        validated_df = validate_edited_data(edited_df, global_years)
        if validated_df is None:
            return
        
        # Se muestra solo la tabla editable sin la fila de totales

if __name__ == '__main__':
    main()
