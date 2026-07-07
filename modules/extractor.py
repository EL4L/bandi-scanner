"""Estrazione testo PDF e dati bando via API OpenRouter (DeepSeek)."""

from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path
import fitz
from openai import (
    OpenAI,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    RateLimitError,
)
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_fixed

from modules.log_utils import log_error, log_incident
from modules.schema import BANDO_SCHEMA, MAX_TEXT_CHARS, MIN_TEXT_CHARS, normalize_response

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts" / "system_extraction.md"
# Usiamo il modello DeepSeek reale, senza ":free"
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek/deepseek-v4-flash")
# ATTENZIONE — TODO: verificare su openrouter.ai/models il nome ESATTO dello slug
# per Claude Haiku 4.5 prima di affidarsi a questo fallback in produzione. Gli ID
# OpenRouter richiedono sempre il prefisso vendor (es. "anthropic/..."); un ID senza
# prefisso (come in una versione precedente di questa costante) causa 404 silenziosi
# su ogni tentativo di fallback (vedi audit D-2 / error_log.txt storico).
LLM_FALLBACK_MODEL = os.environ.get("LLM_FALLBACK_MODEL", "anthropic/claude-haiku-4.5")
RETRY_ATTEMPTS = 3
RETRY_WAIT_SECONDS = int(os.environ.get("LLM_RETRY_WAIT_SECONDS", "60"))
# Limite pagine per evitare PDF abnormi/malformati che saturano CPU/RAM in parsing
MAX_PDF_PAGES = int(os.environ.get("MAX_PDF_PAGES", "300"))
_JSON_BLOCK_RE = re.compile(r'\{[\s\S]*\}')


def _is_retryable_api_error(exc: BaseException) -> bool:
    if isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError)):
        return True
    if isinstance(exc, APIStatusError):
        code = getattr(exc, "status_code", 0)
        return code >= 500 or code == 529
    return False


class EmptyPDFException(Exception):
    """PDF senza testo sufficiente o illeggibile."""


class PDFInvalidoException(Exception):
    """PDF non apribile, corrotto o malformato (fallito il parsing PyMuPDF)."""


class PDFTroppoGrandeException(Exception):
    """PDF con un numero di pagine oltre il limite consentito."""


class InvalidJSONResponse(Exception):
    """Risposta LLM non parsabile come JSON."""


class MissingAPIKeyError(Exception):
    """Variabile OPENROUTER_API_KEY assente."""


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise MissingAPIKeyError(
            "OPENROUTER_API_KEY non configurata. Inserisci la chiave nel file .env."
        )
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


def _load_system_prompt(raw_text: str) -> str:
    if not PROMPT_PATH.is_file():
        raise FileNotFoundError(f"Prompt non trovato: {PROMPT_PATH}")
    template = PROMPT_PATH.read_text(encoding="utf-8")
    if "{raw_text}" not in template:
        return f"{template.strip()}\n\nTesto del bando:\n{raw_text}"
    return template.replace("{raw_text}", raw_text)


def _tronca_testo(raw_text: str) -> str:
    """Limita il testo del bando a MAX_TEXT_CHARS prima di costruire il prompt.

    Senza questo limite un PDF molto lungo viene inviato per intero al LLM:
    costo per token non limitato e rischio di superare la finestra di
    contesto del modello (vedi audit D-1).
    """
    if len(raw_text) <= MAX_TEXT_CHARS:
        return raw_text
    log_error(f"Testo bando troncato da {len(raw_text)} a {MAX_TEXT_CHARS} caratteri prima della chiamata API")
    return raw_text[:MAX_TEXT_CHARS]


def _clean_json_response(content: str) -> str:
    """Rimuove blocchi Markdown e testo prose attorno al JSON."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines)
    content = content.strip()
    # Se c'è del testo prima del JSON (es. "Ecco il risultato: {...}"), estrai solo il blocco
    if not content.startswith("{"):
        match = _JSON_BLOCK_RE.search(content)
        if match:
            content = match.group(0)
    return content.strip()


def calcola_urgenza(data_scadenza: str | None) -> str | None:
    """Calcola l'urgenza del bando dalla data di scadenza.

    Restituisce "alta" (<30gg), "media" (<90gg), "bassa" (>=90gg),
    "scaduto" (data passata), None se data_scadenza è assente o non parsabile.
    """
    if not data_scadenza or not isinstance(data_scadenza, str):
        return None
    try:
        scadenza = date.fromisoformat(data_scadenza.strip())
    except ValueError:
        return None
    giorni = (scadenza - date.today()).days
    if giorni < 0:
        return "scaduto"
    if giorni < 30:
        return "alta"
    if giorni < 90:
        return "media"
    return "bassa"


def calcola_null_percentage(bando_dict: dict) -> float:
    """Percentuale di campi null/vuoti rispetto allo schema bando."""
    if not isinstance(bando_dict, dict):
        return 100.0
    total = len(BANDO_SCHEMA)
    if total == 0:
        return 0.0
    vuoti = 0
    for key in BANDO_SCHEMA:
        val = bando_dict.get(key)
        if val is None:
            vuoti += 1
        elif isinstance(val, str) and not val.strip():
            vuoti += 1
        elif isinstance(val, list) and not val:
            vuoti += 1
    return (vuoti / total) * 100.0


def extract_text_from_pdf(pdf_path: str) -> str:
    """Estrae testo grezzo da tutte le pagine del PDF.

    Valida che il file sia un PDF apribile e non ecceda il limite di pagine
    prima di leggerne il contenuto, per non esporre il parser a file
    corrotti o abnormemente grandi (vedi audit D-4).
    """
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF non trovato: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise PDFInvalidoException(f"PDF non apribile o corrotto: {exc}") from exc

    try:
        if doc.page_count > MAX_PDF_PAGES:
            raise PDFTroppoGrandeException(
                f"PDF con {doc.page_count} pagine, limite massimo {MAX_PDF_PAGES}."
            )
        try:
            parts: list[str] = [page.get_text() for page in doc]
        except Exception as exc:
            raise PDFInvalidoException(f"Errore durante la lettura del PDF: {exc}") from exc
        text = "\n".join(parts)
    finally:
        doc.close()

    stripped = text.strip()
    if len(stripped) < MIN_TEXT_CHARS:
        raise EmptyPDFException(
            f"PDF vuoto o non leggibile (estratto {len(stripped)} caratteri)."
        )
    return text


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_fixed(RETRY_WAIT_SECONDS),
    retry=retry_if_exception(_is_retryable_api_error),
    reraise=True,
)
def _call_llm_api(prompt: str, model: str = LLM_MODEL) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    if not response.choices:
        raise InvalidJSONResponse("Risposta API vuota")
    return response.choices[0].message.content


def extract_bando_data(raw_text: str) -> dict:
    """Carica il prompt, chiama DeepSeek e restituisce il bando normalizzato."""
    raw_text = _tronca_testo(raw_text)
    prompt = _load_system_prompt(raw_text)

    try:
        content = _call_llm_api(prompt, model=LLM_MODEL)
    except MissingAPIKeyError:
        raise
    except Exception as primary_exc:
        log_error(f"Modello primario ({LLM_MODEL}) fallito: {primary_exc}. Tentativo con fallback {LLM_FALLBACK_MODEL}.")
        try:
            content = _call_llm_api(prompt, model=LLM_FALLBACK_MODEL)
        except Exception as fallback_exc:
            msg = f"Anche il modello fallback ({LLM_FALLBACK_MODEL}) ha fallito: {fallback_exc}"
            log_error(msg)
            log_incident(
                description="Entrambi i modelli LLM non disponibili",
                impact="Estrazione bando fallita",
                cause=str(fallback_exc),
                fix=f"Verificare stato OpenRouter e variabili LLM_MODEL / LLM_FALLBACK_MODEL",
            )
            raise primary_exc from fallback_exc

    cleaned = _clean_json_response(content)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        log_error(f"JSON non valido da LLM: {exc}")
        raise InvalidJSONResponse("L'LLM non ha restituito JSON valido") from exc

    if not isinstance(data, dict):
        raise InvalidJSONResponse("La risposta JSON non è un oggetto")

    result = normalize_response(data)

    bando = result.get("bando", {})
    if isinstance(bando, dict):
        bando["urgenza"] = calcola_urgenza(bando.get("data_scadenza"))
        null_pct = calcola_null_percentage(bando)
        if null_pct > 50.0:
            result["warning"] = "Da revisionare manualmente - troppi campi mancanti"

    return result