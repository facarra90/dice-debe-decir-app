import streamlit as st

st.title("DICE DEBE DECIR - Aplicación Web")

st.write("Descarga el ejecutable haciendo clic en el botón de abajo:")

# Enlace directo al archivo en Google Drive
google_drive_link = "https://drive.google.com/uc?id=1sIIBrZl9Jm22kTpPAAyr_pACF5tenDHr"

# Botón de descarga
st.markdown(f'<a href="{google_drive_link}" download target="_blank"><button style="padding:10px; font-size:16px;">📥 Descargar Ejecutable</button></a>', unsafe_allow_html=True)
