import streamlit as st
import pandas as pd
import csv
from st_aggrid import AgGrid, GridOptionsBuilder

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
    Carga y procesa el archivo 'factores_conversion.csv' con el siguiente formato:
    
    - Delimitador: punto y coma (;)
    - Codificación: latin-1 (ISO-8859-1)
    
    Estructura:
      * Primera fila (cabecera):
          - La primera celda contiene un encabezado descriptivo (ej.: "AÑO Base")
          - Las siguientes celdas contienen los años de destino (ej.: 2015, 2016, ..., 2025)
      * Filas siguientes:
          - Primera columna: Año base (número entero sin espacios, ej.: 2011, 2012, ..., 2024)
          - Columnas siguientes: Factores de conversión correspondientes a cada año de destino,
            con valores numéricos que pueden usar coma (,) como separador decimal.
    
    Se construye un diccionario de factores con la siguiente estructura:
       { año_base: { año_destino: factor, ... }, ... }
    
    Finalmente, se convierte a un DataFrame donde el índice es el año base y las columnas
    son los años de destino.
    """
    factors = {}
    try:
        # Abrir el archivo con el delimitador correcto
        with open("factores_conversion.csv", newline='', encoding="latin-1") as csvfile:
            reader = csv.reader(csvfile, delimiter=";")
            # Leer la cabecera (no se convierte a números)
            header = next(reader)
            # La primera celda es descriptiva; las siguientes son los años de destino.
            destination_years = [col.strip() for col in header[1:]]
            for row in reader:
                if not row:
                    continue  # omitir filas vacías
                try:
                    base_year = int(row[0].strip())
                except Exception as e:
                    st.error(f"Error al convertir el año base '{row[0]}' a entero: {e}")
                    return None
                subdict = {}
                for i, val in enumerate(row[1:], start=1):
                    # Eliminar espacios y reemplazar la coma por punto
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
        totals[col] = df_copy[col].sum() if col in numeric_cols or col == "Total" else ""
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

def main():
    st.title("Gasto Real no Ajustado Cuadro Completo")
    df_base = load_base_data()
    
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
        # Visualizamos la tabla original usando AgGrid para autoajuste de columnas.
        gb_original = GridOptionsBuilder.from_dataframe(df_grouped)
        gb_original.configure_default_column(autoWidth=True, wrapText=True)
        gridOptions_original = gb_original.build()
        AgGrid(df_grouped, gridOptions=gridOptions_original, fit_columns_on_grid_load=True)
        
        if hasattr(st, "data_editor"):
            edited_df = st.data_editor(df_grouped, key="final_editor")
        else:
            edited_df = st.experimental_data_editor(df_grouped, key="final_editor")
        
        validated_df = validate_edited_data(edited_df, global_years)
        if validated_df is None:
            return
        
        df_final = append_totals_with_column(validated_df)
        # Visualizamos la tabla validada con totales usando AgGrid
        gb_final = GridOptionsBuilder.from_dataframe(df_final)
        gb_final.configure_default_column(autoWidth=True, wrapText=True)
        gridOptions_final = gb_final.build()
        st.markdown("### Planilla Final con Totales")
        AgGrid(df_final, gridOptions=gridOptions_final, fit_columns_on_grid_load=True)
        
        st.markdown("### Gasto Convertido a la Moneda Seleccionada")
        conversion_factors = load_conversion_factors()
        if conversion_factors is None:
            return
        
        available_moneda = sorted(conversion_factors.columns, key=lambda x: int(x))
        dest_moneda = st.sidebar.selectbox("Seleccione la moneda de destino (año de conversión):", available_moneda)
        
        df_converted = convert_expense_dataframe(validated_df, int(dest_moneda), conversion_factors)
        df_converted_final = append_totals_with_column(df_converted)
        
        # Visualizamos la tabla convertida usando AgGrid con autoajuste de columnas
        gb_converted = GridOptionsBuilder.from_dataframe(df_converted_final)
        gb_converted.configure_default_column(autoWidth=True, wrapText=True)
        gridOptions_converted = gb_converted.build()
        AgGrid(df_converted_final, gridOptions=gridOptions_converted, fit_columns_on_grid_load=True)

if __name__ == '__main__':
    main()
