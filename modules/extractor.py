"""Estrazione testo PDF e dati bando via API OpenRouter."""

import os
import json
import fitz  # PyMuPDF
from openai import OpenAI
from dotenv import load_dotenv
from modules.log_utils import log_error
from modules.schema import MAX_TEXT_CHARS, MIN_TEXT_CHARS, normalize_response

load_dotenv()

# --- Eccezioni necessarie per lo script di test ---
class EmptyPDFException(Exception): pass
class InvalidJSONResponse(Exception): pass
class MissingAPIKeyError(Exception): pass

def extract_text_from_pdf(pdf_path: str) -> str:
    """Estrae testo da PDF, gestendo eventuali errori."""
    doc = fitz.open(pdf_path)
    text = "\n".join([page.get_text() for page in doc])
    doc.close()
    if len(text.strip()) < MIN_TEXT_CHARS:
        raise EmptyPDFException("PDF vuoto o illeggibile")
    return text

def _truncate_text(raw_text: str) -> str:
    """Tronca il testo se troppo lungo."""
    if len(raw_text) <= MAX_TEXT_CHARS:
        return raw_text
    return raw_text[:MAX_TEXT_CHARS]

def extract_bando_data(raw_text: str) -> dict:
    """Chiama OpenRouter con i modelli gratuiti."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise MissingAPIKeyError("OPENROUTER_API_KEY non trovata nel .env")

    # Tronca il testo prima di inviarlo
    text = _truncate_text(raw_text)

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    
    # Scelta modello (DeepSeek per bandi lunghi)
    model = "deepseek/deepseek-v4-flash:free" if len(text) > 100000 else "minimax/minimax-m2.5:free"

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": f"Estrai dati JSON dal seguente bando:\n\n{text}"}]
        )
        content = response.choices[0].message.content
        cleaned = content.replace("```json", "").replace("```", "").strip()
        
        # Estrazione sicura del blocco JSON
        start = cleaned.find('{')
        end = cleaned.rfind('}') + 1
        data = json.loads(cleaned[start:end])
        
        return normalize_response(data)
    except Exception as e:
        log_error(f"Errore API: {e}")
        raise InvalidJSONResponse("Risposta non valida dall'AI")