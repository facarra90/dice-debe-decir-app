import streamlit as st
import pandas as pd
import datetime
import io
import csv
from openpyxl.utils import get_column_letter

st.set_page_config(layout="wide", page_title="Dice debe Decir - Aplicación de Gasto")

@st.cache_data
def load_base_data():
    return pd.read_excel("BASE DE DATOS.xlsx")

@st.cache_data
def load_conversion_factors():
    conversion = {}
    with open("factores_conversion.csv", newline='', encoding="latin-1") as csvfile:
        reader = csv.reader(csvfile, delimiter="\t")
        headers = next(reader)
        year_headers = [int(h.strip()) for h in headers[1:]]
        for row in reader:
            base_year = int(row[0].strip())
            conversion[base_year] = {}
            for idx, cell in enumerate(row[1:]):
                try:
                    value = float(cell.strip().replace(",", "."))
                except ValueError:
                    value = None
                conversion[base_year][year_headers[idx]] = value
    return conversion

def format_number_custom(x):
    try:
        return f"{int(round(x)):,}".replace(",", ".")
    except Exception:
        return x

def style_df_contabilidad(df):
    styler = df.style.format(lambda x: format_number_custom(x) if isinstance(x, (int, float)) else x)
    styler = styler.set_properties(**{'text-align': 'left'})
    styler = styler.set_table_styles([
        {'selector': 'th.col_heading.level0', 'props': [('text-align', 'left')]},
        {'selector': 'th.row_heading', 'props': [('text-align', 'left')]},
        {'selector': 'th.index_name', 'props': [('text-align', 'left')]},
        {'selector': 'td', 'props': [('text-align', 'left')]}  # Alinea todas las celdas, incluidas las de Total
    ])
    return styler

def append_totals(df):
    df = df.copy()
    numeric_cols = df.select_dtypes(include=["number"]).columns
    df["Total"] = df[numeric_cols].sum(axis=1)
    total_row = df[numeric_cols].sum(axis=0)
    total_row["Total"] = total_row.sum()
    for col in df.columns.difference(numeric_cols):
        total_row[col] = ""
    total_row.name = "Total"
    df = pd.concat([df, total_row.to_frame().T])
    return df

def main():
    st.title("Dice debe Decir - Aplicación de Gasto")
    df_base = load_base_data()
    conversion_factors = load_conversion_factors()

    st.sidebar.header("Filtrar Datos")
    codigo_bip_list = sorted(df_base["CODIGO BIP"].dropna().unique().tolist())
    selected_codigo_bip = st.sidebar.selectbox("Seleccione el CODIGO BIP:", codigo_bip_list)
    etapa_list = sorted(df_base["ETAPA"].dropna().unique().tolist())
    selected_etapa = st.sidebar.selectbox("Seleccione la ETAPA:", etapa_list)
    anio_termino = st.sidebar.number_input("Ingrese el AÑO DE TERMINO del proyecto:",
                                           min_value=2011, max_value=2100, value=2024, step=1)

    if st.sidebar.button("Generar Planilla"):
        df_grouped, global_years, df_filtered = get_filtered_data(df_base, selected_codigo_bip, selected_etapa, anio_termino)
        if df_grouped is None:
            return

        st.markdown("### Gasto Real no Ajustado")
        st.write("Edite los valores según corresponda:")
        edited_original_df = st.data_editor(df_grouped, key="original_editor")

        st.markdown("### Anualizacion de la Inversion")
        original_df_totals = append_totals(edited_original_df)
        st.table(style_df_contabilidad(original_df_totals))

if __name__ == '__main__':
    main()
