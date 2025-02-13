import streamlit as st
import pandas as pd
import datetime
import csv
from io import BytesIO
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

# ---------- FUNCIONES DE FORMATEO ----------
def format_currency(value, prefix="$", decimals=0):
    fmt = f"{{:,.{decimals}f}}"
    s = fmt.format(value)
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{prefix} {s}" if prefix else s

def parse_int_currency(s):
    s = s.replace("$", "").replace("M$", "").replace(" ", "").replace(".", "")
    try:
        return int(s) if s != "" else 0
    except:
        return 0

# ---------- CARGA DE FACTORES DE CONVERSIÓN ----------
def load_conversion_factors():
    conversion = {}
    try:
        with open("factores_conversion.csv", newline='', encoding="latin-1") as csvfile:
            reader = csv.reader(csvfile, delimiter="\t")
            headers = next(reader)
            # Los encabezados (excepto el primero) son los años destino
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
    except Exception as e:
        st.error(f"Error al cargar factores de conversión: {e}")
    return conversion

conversion_factors = load_conversion_factors()

# ---------- CARGA DE LA BASE DE DATOS ----------
try:
    df_base = pd.read_excel("BASE DE DATOS.xlsx")
    df_base["CODIGO BIP"] = df_base["CODIGO BIP"].astype(str).str.strip().str.upper()
except Exception as e:
    st.error(f"No se pudo cargar la Base de Datos: {e}")
    st.stop()

# ---------- BARRA LATERAL: SELECCIÓN DE PARÁMETROS ----------
st.sidebar.header("Parámetros de Filtro")
codigo_bip_list = sorted(df_base["CODIGO BIP"].dropna().unique().tolist())
selected_codigo_bip = st.sidebar.selectbox("Seleccione el CODIGO BIP", codigo_bip_list)
selected_etapa = st.sidebar.selectbox("Seleccione la ETAPA", ["DISEÑO", "EJECUCION", "PREFACTIBILIDAD"])
selected_year_termino = st.sidebar.number_input("Ingrese el AÑO DE TERMINO del proyecto", value=2024, step=1)

# ---------- FILTRAR BASE DE DATOS ----------
df_filtrado = df_base[
    (df_base["CODIGO BIP"] == selected_codigo_bip) &
    (df_base["ETAPA"].str.upper() == selected_etapa)
]
if df_filtrado.empty:
    st.error("No se encontraron datos para el CODIGO BIP y ETAPA seleccionados.")
    st.stop()

nombre_proyecto = df_filtrado["NOMBRE"].iloc[0]
st.title(f'Proyecto "{nombre_proyecto}", Etapa {selected_etapa}, Código BIP: {selected_codigo_bip}')

# ---------- OBTENCIÓN DE LOS DATOS DE GASTO ----------
# Se consideran columnas numéricas (ej. años entre 2011 y 2024)
expense_cols = [col for col in df_filtrado.columns if str(col).isdigit() and 2011 <= int(col) <= 2024]
df_grouped = df_filtrado.groupby("ITEMS")[expense_cols].sum()

# Determinar el año de inicio: el primer año con gasto > 0
sorted_years = sorted(expense_cols, key=lambda y: int(y))
start_year = None
for year in sorted_years:
    if df_grouped[year].sum() > 0:
        start_year = int(year)
        break
if start_year is None:
    st.error("No se encontró gasto inicial en los datos.")
    st.stop()

if selected_year_termino < start_year:
    st.error("El AÑO DE TERMINO debe ser mayor o igual al año de inicio del gasto.")
    st.stop()

global_years = list(range(start_year, selected_year_termino + 1))
global_items = list(df_grouped.index)

# ---------- TABLA ORIGINAL: GASTO REAL NO AJUSTADO ----------
st.header("Tabla Original: Gasto Real no Ajustado")
# Crear un DataFrame con ítems y años
df_original = pd.DataFrame(index=global_items, columns=global_years).fillna(0)
for item in global_items:
    for year in global_years:
        # Si existe la columna (como string o int) en df_grouped, tomar el valor; sino 0
        if str(year) in df_grouped.columns:
            df_original.loc[item, year] = df_grouped.loc[item, str(year)]
        elif year in df_grouped.columns:
            df_original.loc[item, year] = df_grouped.loc[item, year]

df_original = df_original.astype(int)

st.markdown("**Edite los valores si es necesario:**")
# Usamos el data editor de Streamlit para permitir edición
edited_df = st.experimental_data_editor(df_original, num_rows="dynamic", key="original")

# Cálculos de totales
edited_df["Total"] = edited_df.sum(axis=1)
col_totals = edited_df.sum(axis=0)
grand_total = edited_df.drop("Total", axis=1).sum().sum()

st.markdown("**Totales por ítem:**")
st.dataframe(edited_df)
st.markdown("**Totales por año:**")
st.dataframe(pd.DataFrame(col_totals.drop("Total"), columns=["Total"]))
st.markdown("**Gran Total:**")
st.write(grand_total)

# ---------- TABLA DE CONVERSIÓN ----------
st.header("Tabla de Conversión: Anualización Moneda Pesos (M$)")
conversion_target_year = st.number_input("Convertir a año:", value=2024, step=1, key="conversion_year")

# Se crea una copia para aplicar la conversión
df_conversion = edited_df.copy().drop("Total", axis=1).astype(float)
for col in df_conversion.columns:
    nuevos_valores = []
    for val in df_conversion[col]:
        # Seleccionar la clave base para obtener el factor
        if col in conversion_factors:
            base_key = col
        else:
            base_key = max(conversion_factors.keys())
        available_years = sorted(conversion_factors[base_key].keys())
        target_year_use = conversion_target_year if conversion_target_year <= available_years[-1] else available_years[-1]
        factor = conversion_factors[base_key][target_year_use]
        nuevos_valores.append((val * factor) / 1000.0)
    df_conversion[col] = nuevos_valores
df_conversion["Total"] = df_conversion.sum(axis=1)
col_totals_conv = df_conversion.drop("Total", axis=1).sum()
grand_total_conv = df_conversion.drop("Total", axis=1).sum().sum()

st.dataframe(df_conversion)
st.markdown("**Totales (Conversión):**")
st.write("Total por ítem:")
st.dataframe(df_conversion)
st.write("Total por año:")
st.dataframe(pd.DataFrame(col_totals_conv, columns=["Total"]))
st.write("Gran Total:")
st.write(grand_total_conv)

# ---------- CUADRO EXTRA ----------
st.header("Cuadro Extra")
current_year = datetime.datetime.now().year

pagado, sol2025, sol_siguientes, costo_total = [], [], [], []
for item in global_items:
    # Extraer la fila convertida para el ítem
    row_conv = df_conversion.loc[item]
    total_pagado = row_conv[[year for year in global_years if year <= (current_year - 1)]].sum()
    total_sol2025 = row_conv[current_year] if current_year in global_years else 0
    total_siguientes = row_conv[[year for year in global_years if year > current_year]].sum()
    total_costo = total_pagado + total_sol2025 + total_siguientes
    pagado.append(total_pagado)
    sol2025.append(total_sol2025)
    sol_siguientes.append(total_siguientes)
    costo_total.append(total_costo)

df_extra = pd.DataFrame({
    "ITEM": global_items,
    "Pagado al 31/12/2024": pagado,
    "Solicitado para el año 2025": sol2025,
    "Solicitado años siguientes": sol_siguientes,
    "Costo Total": costo_total
})
st.dataframe(df_extra)

# ---------- CUADRO FINAL: PROGRAMACIÓN EN MONEDA ORIGINAL ----------
st.header("Cuadro Final: Programación en Moneda Original")
programacion_target_year = st.number_input("Convertir a año (Programación):", value=start_year-1, step=1, key="programacion_year")
if programacion_target_year >= start_year:
    st.error("El año de conversión para la Programación debe ser menor que el año de inicio.")
else:
    df_programacion = edited_df.copy().drop("Total", axis=1).astype(float)
    for col in df_programacion.columns:
        nuevos_valores = []
        for val in df_programacion[col]:
            if col in conversion_factors:
                base_key = col
            else:
                base_key = max(conversion_factors.keys())
            available_years = sorted(conversion_factors[base_key].keys())
            target_use = available_years[0] if programacion_target_year < available_years[0] else programacion_target_year
            factor = conversion_factors[base_key][target_use]
            nuevos_valores.append((val * factor) / 1000.0)
        df_programacion[col] = nuevos_valores
    df_programacion["Total"] = df_programacion.sum(axis=1)
    st.dataframe(df_programacion)

# ---------- EXPORTAR A EXCEL ----------
st.header("Exportar a Excel")

def export_to_excel():
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Exportar cada sección en una hoja
        df_original.to_excel(writer, sheet_name="Gasto Real", startrow=2)
        df_conversion.to_excel(writer, sheet_name="Conversión", startrow=2)
        df_extra.to_excel(writer, sheet_name="Cuadro Extra", index=False, startrow=2)
        if programacion_target_year < start_year:
            df_programacion.to_excel(writer, sheet_name="Programación", startrow=2)
        
        workbook = writer.book
        title_font = Font(bold=True, size=14)
        center_alignment = Alignment(horizontal="center")
        sheets = {
            "Gasto Real": df_original,
            "Conversión": df_conversion,
            "Cuadro Extra": df_extra,
        }
        if programacion_target_year < start_year:
            sheets["Programación"] = df_programacion
        for sheet_name, df in sheets.items():
            worksheet = writer.sheets[sheet_name]
            ncols = df.shape[1] + 1
            last_col_letter = get_column_letter(ncols)
            worksheet.merge_cells(f"A1:{last_col_letter}1")
            title_text = f"Proyecto: {selected_codigo_bip}"
            worksheet["A1"].value = title_text
            worksheet["A1"].font = title_font
            worksheet["A1"].alignment = center_alignment
            # Ajuste de ancho de columnas
            for col in worksheet.columns:
                max_length = 0
                col_letter = col[0].column_letter
                for cell in col:
                    try:
                        if cell.value:
                            max_length = max(max_length, len(str(cell.value)))
                    except:
                        pass
                adjusted_width = (max_length + 2)
                worksheet.column_dimensions[col_letter].width = adjusted_width
        writer.save()
    processed_data = output.getvalue()
    return processed_data

excel_data = export_to_excel()
st.download_button(
    label="Descargar Excel",
    data=excel_data,
    file_name="exported_data.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


