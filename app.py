import streamlit as st
from pathlib import Path

from modules.extractor import (
    EmptyPDFException,
    InvalidJSONResponse,
    MissingAPIKeyError,
    extract_bando_data,
    extract_text_from_pdf,
)
from modules.log_utils import log_error, log_prompt_run
from modules.validator import fields_status, validate_bando

st.set_page_config(page_title="Bandi Scanner", layout="wide")
st.title("Bandi Scanner — Estrazione bandi")

ROOT = Path(__file__).resolve().parent
TEMP_DIR = ROOT / "temp"
TEMP_DIR.mkdir(exist_ok=True)

uploaded_file = st.file_uploader("Carica un bando PDF", type=["pdf"])

if uploaded_file:
    safe_name = Path(uploaded_file.name).name
    file_path = TEMP_DIR / safe_name
    file_bytes = uploaded_file.getvalue()

    try:
        with open(file_path, "wb") as f:
            f.write(file_bytes)
    except OSError as exc:
        st.error(f"Impossibile salvare il file: {exc}")
        log_error(f"Salvataggio PDF fallito: {exc}")
        st.stop()

    st.success(f"File caricato: {safe_name}")
    st.info(f"Dimensione: {len(file_bytes) / 1024:.2f} KB")

    try:
        text = extract_text_from_pdf(str(file_path))
        st.success("Testo estratto correttamente dal PDF (nessun costo API)")
        with st.expander("Anteprima testo estratto (primi 1000 caratteri)"):
            st.text(text[:1000])

        st.divider()
        st.markdown(
            "**Estrazione JSON con AI** — consuma crediti Anthropic "
            "(circa pochi centesimi per PDF, dipende dalla lunghezza). "
            "Caricare il file **non** chiama l'API: clicca il pulsante solo quando serve."
        )

        if st.button("Estrai dati bando con AI", type="primary"):
            with st.spinner("Chiamata a Claude in corso…"):
                try:
                    raw_data = extract_bando_data(text)
                    result = validate_bando(raw_data, raw_text=text)
                    data = result["data"]

                    st.subheader("Dati bando estratti")
                    st.json(data)

                    for w in result.get("warnings", []):
                        st.info(w)

                    if result["errors"]:
                        st.error("Errori di validazione:")
                        for err in result["errors"]:
                            st.markdown(f"- {err}")

                    if result["needs_manual_review"]:
                        st.warning(
                            "Da revisionare manualmente — oltre il 50% dei campi "
                            f"è vuoto o nullo ({result['null_percentage']:.0f}%)."
                        )

                    if not result["errors"] and not result["needs_manual_review"]:
                        st.success("Validazione completata senza errori")

                    ok_fields, null_fields = fields_status(data)
                    log_prompt_run(
                        filename=safe_name,
                        fields_ok=ok_fields,
                        fields_null=null_fields,
                        notes=(
                            f"Validazione: {len(result['errors'])} errori, "
                            f"{result['null_percentage']:.0f}% campi vuoti"
                        ),
                    )

                except MissingAPIKeyError as exc:
                    st.error(str(exc))
                    log_error(str(exc))
                except InvalidJSONResponse as exc:
                    st.error(str(exc))
                    log_error(f"JSON invalido per {safe_name}: {exc}")
                except Exception as exc:
                    st.error(f"Errore durante l'estrazione AI: {exc}")
                    log_error(f"Estrazione AI fallita per {safe_name}: {exc}")

    except EmptyPDFException as exc:
        st.error(
            "PDF vuoto o illeggibile — impossibile estrarre testo sufficiente. "
            "Verifica che il PDF contenga testo selezionabile (non solo immagini)."
        )
        log_error(f"PDF illeggibile {safe_name}: {exc}")
