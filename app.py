import streamlit as st
import pandas as pd
import os

def cargar_base_datos():
    """Carga el archivo de la base de datos si está disponible."""
    if os.path.exists("BASE DE DATOS.xlsx"):
        return pd.read_excel("BASE DE DATOS.xlsx")
    else:
        st.error("No se encontró el archivo 'BASE DE DATOS.xlsx'. Súbelo para continuar.")
        return None

def cargar_factores_conversion():
    """Carga los factores de conversión desde un archivo CSV."""
    if os.path.exists("factores_conversion.csv"):
        return pd.read_csv("factores_conversion.csv", delimiter="\t", encoding="latin-1")
    else:
        st.error("No se encontró el archivo 'factores_conversion.csv'. Súbelo para continuar.")
        return None

def exportar_a_excel(df, nombre_archivo):
    """Exporta los datos a un archivo Excel descargable."""
    df.to_excel(nombre_archivo, index=False)
    with open(nombre_archivo, "rb") as file:
        st.download_button(
            label="📥 Descargar Excel",
            data=file,
            file_name=nombre_archivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

def main():
    st.title("DICE DEBE DECIR - Aplicación Web")
    st.write("Cargue los datos y seleccione las opciones para calcular los valores.")
    
    # Cargar archivos
    uploaded_db = st.file_uploader("Sube la BASE DE DATOS.xlsx", type=["xlsx"])
    uploaded_factors = st.file_uploader("Sube los FACTORES DE CONVERSIÓN.csv", type=["csv"])
    
    if uploaded_db:
        df_base = pd.read_excel(uploaded_db)
        st.session_state["df_base"] = df_base
    elif "df_base" in st.session_state:
        df_base = st.session_state["df_base"]
    else:
        df_base = None
    
    if uploaded_factors:
        df_factors = pd.read_csv(uploaded_factors, delimiter="\t", encoding="latin-1")
        st.session_state["df_factors"] = df_factors
    elif "df_factors" in st.session_state:
        df_factors = st.session_state["df_factors"]
    else:
        df_factors = None
    
    if df_base is not None:
        st.write("Vista previa de la base de datos:")
        st.dataframe(df_base.head())
    
    if df_factors is not None:
        st.write("Vista previa de los factores de conversión:")
        st.dataframe(df_factors.head())
    
    if df_base is not None and df_factors is not None:
        # Selección de Código BIP
        codigos_bip = df_base["CODIGO BIP"].astype(str).unique()
        selected_codigo_bip = st.selectbox("Seleccione un Código BIP", codigos_bip)
        
        # Selección de Etapa
        etapas = df_base["ETAPA"].astype(str).unique()
        selected_etapa = st.selectbox("Seleccione una Etapa", etapas)
        
        # Filtros y generación de datos
        df_filtrado = df_base[(df_base["CODIGO BIP"] == selected_codigo_bip) & 
                              (df_base["ETAPA"] == selected_etapa)]
        
        if df_filtrado.empty:
            st.error("No se encontraron datos para el Código BIP y Etapa seleccionados.")
        else:
            st.write("Datos filtrados:")
            st.dataframe(df_filtrado)
            
            if st.button("Exportar a Excel"):
                exportar_a_excel(df_filtrado, "datos_filtrados.xlsx")

if __name__ == "__main__":
    main()

