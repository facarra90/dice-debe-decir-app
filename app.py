import streamlit as st
import pandas as pd
import numpy as np
import io

# Función para formatear números sin decimales y con separador de miles (puntos)
def format_miles_pesos(x):
    try:
        # Se redondea y se formatea usando coma, luego se reemplaza por punto
        return f"{int(round(x)):,}".replace(",", ".")
    except Exception:
        return x

# Cargar los factores de conversión desde un archivo CSV.
# Se asume que el archivo "factores_conversion.csv" tiene las columnas "Año" y "Factor"
@st.cache_data
def load_conversion_factors():
    try:
        df_factors = pd.read_csv("factores_conversion.csv")
    except Exception as e:
        st.error(f"Error al cargar los factores de conversión: {e}")
        return {}
    
    # Convertir el DataFrame a un diccionario: clave = año (como cadena), valor = factor
    factor_dict = {}
    for index, row in df_factors.iterrows():
        year = str(row["Año"]).strip()
        try:
            factor = float(row["Factor"])
        except Exception as e:
            st.error(f"Error al convertir el factor para el año {year}: {e}")
            factor = 1  # Valor por defecto en caso de error
        factor_dict[year] = factor
    return factor_dict

# Función para convertir los valores del DataFrame original a Pesos (M$)
def convert_values_to_pesos(df_original, conversion_factors, target_year):
    """
    Recibe:
      - df_original: DataFrame con columnas de años y la columna "ITEMS".
      - conversion_factors: diccionario con factores de conversión (clave: año, valor: factor).
      - target_year: año objetivo para la conversión.
    
    Para cada columna de año, se realiza la conversión:
      valor_convertido = (valor_original * (factor_target / factor_año)) / 1000
    """
    target_year_str = str(target_year)
    if target_year_str not in conversion_factors:
        st.error(f"No se encontró el factor de conversión para el año objetivo {target_year}.")
        return None

    factor_target = conversion_factors[target_year_str]
    df_converted = df_original.copy()

    # Identificar las columnas que representan años (se asume que son dígitos y existen en el diccionario de factores)
    year_columns = [col for col in df_converted.columns if col.isdigit() and col in conversion_factors]

    for col in year_columns:
        try:
            # Asegurar que la columna sea numérica
            df_converted[col] = pd.to_numeric(df_converted[col], errors='coerce').fillna(0)
            factor_year = conversion_factors[col]
            # Aplicar la fórmula de conversión
            df_converted[col] = df_converted[col] * (factor_target / factor_year) / 1000
        except Exception as e:
            st.error(f"Error al convertir la columna {col}: {e}")
            return None
    return df_converted

def main():
    st.title("Aplicación de Conversión a Moneda Pesos (M$)")
    
    # ============================
    # 1. Tabla "Gasto Real no Ajustado"
    # ============================
    st.markdown("### Gasto Real no Ajustado")
    
    # Para fines de demostración se crea un DataFrame de ejemplo.
    # En una aplicación real, se cargarían los datos desde un archivo o base de datos.
    years = [str(y) for y in range(2011, 2025)]
    data = {
        "ITEMS": ["Item A", "Item B", "Item C"]
    }
    for year in years:
        data[year] = np.random.randint(1000, 10000, size=3)
    df_gasto = pd.DataFrame(data)
    
    # Permitir que el usuario edite la tabla utilizando st.data_editor (o st.experimental_data_editor)
    if hasattr(st, "data_editor"):
        edited_df = st.data_editor(df_gasto, key="gasto_editor")
    else:
        edited_df = st.experimental_data_editor(df_gasto, key="gasto_editor")
    
    # ============================
    # 2. Tabla "Conversión a Moneda Pesos (M$)"
    # ============================
    st.markdown("### Conversión a Moneda Pesos (M$)")
    
    # Cargar los factores de conversión desde el CSV
    conversion_factors = load_conversion_factors()
    if not conversion_factors:
        st.error("No se pudieron cargar los factores de conversión. Verifica el archivo CSV.")
        return
    
    # Permitir al usuario ingresar el año objetivo para la conversión.
    # Se asume que el año objetivo debe estar entre los años disponibles en los factores.
    available_years = [int(y) for y in conversion_factors.keys() if y.isdigit()]
    if not available_years:
        st.error("No se encontraron años válidos en los factores de conversión.")
        return
    
    target_year = st.number_input("Ingrese el año objetivo para la conversión:",
                                  min_value=min(available_years),
                                  max_value=max(available_years),
                                  value=max(available_years),
                                  step=1)
    
    # Botón para ejecutar la conversión
    if st.button("Convertir a Pesos (M$)"):
        df_converted = convert_values_to_pesos(edited_df, conversion_factors, target_year)
        if df_converted is not None:
            # Aplicar formato a los números: sin decimales y con separador de miles
            df_styled = df_converted.style.format(format_miles_pesos)
            st.table(df_styled)
            
            # ============================
            # 3. Opción para exportar a Excel
            # ============================
            output = io.BytesIO()
            try:
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_converted.to_excel(writer, index=False, sheet_name="Conversion")
                    writer.save()
                st.download_button(
                    label="Exportar a Excel",
                    data=output.getvalue(),
                    file_name="conversion_pesos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"Error al exportar a Excel: {e}")

if __name__ == '__main__':
    main()
