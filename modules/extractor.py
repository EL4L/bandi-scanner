import pymupdf
import os
import json

from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

client = Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)


class EmptyPDFException(Exception):
    pass


class InvalidJSONResponse(Exception):
    pass


# 1. ESTRAZIONE TESTO PDF
def extract_text_from_pdf(pdf_path: str) -> str:
    doc = pymupdf.open(pdf_path)

    text = ""

    for page in doc:
        text += page.get_text()

    if len(text.strip()) < 100:
        raise EmptyPDFException("PDF vuoto o non leggibile")

    return text


# 2. CHIAMATA CLAUDE
def extract_bando_data(raw_text: str) -> dict:

    prompt = f"""
Sei un sistema di estrazione dati da bandi pubblici italiani.

Restituisci SOLO JSON valido.

Testo:
{raw_text}

Schema:
{{
  "titolo": "",
  "ente": "",
  "data_scadenza": "",
  "codici_ateco": [],
  "ateco_aperto_a_tutti": false,
  "regioni": [],
  "dimensione_impresa": [],
  "fatturato_min": null,
  "fatturato_max": null,
  "contributo_max": null,
  "percentuale_fondo_perduto": null,
  "spese_ammissibili": [],
  "link_fonte": ""
}}
"""

    try:

        response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2000,
    messages=[{"role": "user", "content": prompt}]
)

        content = response.content[0].text

        # pulizia JSON
        content = content.replace("```json", "")
        content = content.replace("```", "")
        content = content.strip()

        return json.loads(content)

    except json.JSONDecodeError:
        raise InvalidJSONResponse(
            "Claude non ha restituito JSON valido"
        )