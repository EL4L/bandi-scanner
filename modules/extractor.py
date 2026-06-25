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
from modules.schema import BANDO_SCHEMA, MIN_TEXT_CHARS, normalize_response

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts" / "system_extraction.md"
# Usiamo il modello DeepSeek reale, senza ":free"
LLM_MODEL = "deepseek/deepseek-v4-flash"
RETRY_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 300
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
    """Estrae testo grezzo da tutte le pagine del PDF."""
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF non trovato: {pdf_path}")

    doc = fitz.open(pdf_path)
    try:
        parts: list[str] = []
        for page in doc:
            parts.append(page.get_text())
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
def _call_llm_api(prompt: str) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    if not response.choices:
        raise InvalidJSONResponse("Risposta API vuota")
    return response.choices[0].message.content


def extract_bando_data(raw_text: str) -> dict:
    """Carica il prompt, chiama DeepSeek e restituisce il bando normalizzato."""
    prompt = _load_system_prompt(raw_text)

    try:
        content = _call_llm_api(prompt)
    except (APIConnectionError, APITimeoutError, RateLimitError, APIStatusError) as exc:
        if not _is_retryable_api_error(exc):
            log_error(f"Errore API non recuperabile: {exc}")
            raise
        msg = f"API OpenRouter non disponibile dopo {RETRY_ATTEMPTS} tentativi: {exc}"
        log_error(msg)
        log_incident(
            description="API OpenRouter non risponde",
            impact="Estrazione bando fallita",
            cause=str(exc),
            fix=f"Retry automatico ({RETRY_ATTEMPTS}x)",
        )
        raise
    except MissingAPIKeyError:
        raise
    except Exception as exc:
        msg = f"Errore imprevisto chiamata LLM: {exc}"
        log_error(msg)
        raise

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