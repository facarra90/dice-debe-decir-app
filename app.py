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
