import streamlit as st
from pathlib import Path

from modules.extractor import (
    extract_text_from_pdf,
    EmptyPDFException,
    extract_bando_data
)

st.title("Bandi Scanner MVP")

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

uploaded_file = st.file_uploader("Carica un bando PDF", type=["pdf"])

if uploaded_file:
    file_path = TEMP_DIR / uploaded_file.name
    file_bytes = uploaded_file.getvalue()

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    st.success(f"File caricato: {uploaded_file.name}")
    st.info(f"Dimensione: {len(file_bytes) / 1024:.2f} KB")

    try:
        text = extract_text_from_pdf(str(file_path))

        st.success("TESTO ESTRATTO CORRETTAMENTE")
        st.write(text[:1000])

        st.subheader("JSON estratto da Claude")

        try:
            data = extract_bando_data(text)
            st.json(data)

        except Exception as e:
            st.error(f"Errore Claude: {e}")

    except EmptyPDFException:
        st.error("PDF vuoto o non leggibile")