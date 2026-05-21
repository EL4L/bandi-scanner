"""Estrazione testo PDF e dati bando via API Anthropic."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
import fitz
from anthropic import (
    Anthropic,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    RateLimitError,
)
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_fixed

from modules.log_utils import log_error, log_incident
from modules.schema import MAX_TEXT_CHARS, MIN_TEXT_CHARS, normalize_response

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts" / "system_extraction.md"
CLAUDE_MODEL = "claude-sonnet-4-6"
RETRY_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 300


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
    """Risposta Claude non parsabile come JSON."""


class MissingAPIKeyError(Exception):
    """Variabile ANTHROPIC_API_KEY assente."""


def _get_client() -> Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise MissingAPIKeyError(
            "ANTHROPIC_API_KEY non configurata. Copia .env.example in .env e inserisci la chiave."
        )
    return Anthropic(api_key=api_key)


def _load_system_prompt(raw_text: str) -> str:
    if not PROMPT_PATH.is_file():
        raise FileNotFoundError(f"Prompt non trovato: {PROMPT_PATH}")
    template = PROMPT_PATH.read_text(encoding="utf-8")
    if "{raw_text}" not in template:
        return f"{template.strip()}\n\nTesto del bando:\n{raw_text}"
    return template.replace("{raw_text}", raw_text)


def _clean_json_response(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    return content.strip()


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
            f"PDF vuoto o non leggibile (estratto {len(stripped)} caratteri, "
            f"soglia minima {MIN_TEXT_CHARS})"
        )
    return text


def _truncate_text(raw_text: str) -> str:
    if len(raw_text) <= MAX_TEXT_CHARS:
        return raw_text
    log_error(
        f"Testo bando troncato da {len(raw_text)} a {MAX_TEXT_CHARS} caratteri prima della chiamata API"
    )
    return raw_text[:MAX_TEXT_CHARS]


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_fixed(RETRY_WAIT_SECONDS),
    retry=retry_if_exception(_is_retryable_api_error),
    reraise=True,
)
def _call_claude_api(prompt: str) -> str:
    client = _get_client()
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    if not response.content:
        raise InvalidJSONResponse("Risposta API vuota")
    return response.content[0].text


def extract_bando_data(raw_text: str) -> dict:
    """Carica il prompt, chiama Claude e restituisce {"bando": {...}}."""
    text = _truncate_text(raw_text)
    prompt = _load_system_prompt(text)

    try:
        content = _call_claude_api(prompt)
    except (APIConnectionError, APITimeoutError, RateLimitError, APIStatusError) as exc:
        if not _is_retryable_api_error(exc):
            log_error(f"Errore API non recuperabile: {exc}")
            raise
        msg = f"API Anthropic non disponibile dopo {RETRY_ATTEMPTS} tentativi: {exc}"
        log_error(msg)
        log_incident(
            description="API Anthropic non risponde",
            impact="Estrazione bando fallita",
            cause=str(exc),
            fix=f"Retry automatico ({RETRY_ATTEMPTS}x, attesa {RETRY_WAIT_SECONDS}s)",
        )
        raise
    except MissingAPIKeyError:
        raise
    except Exception as exc:
        msg = f"Errore imprevisto chiamata Claude: {exc}"
        log_error(msg)
        raise

    cleaned = _clean_json_response(content)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        log_error(f"JSON non valido da Claude: {exc}")
        raise InvalidJSONResponse(
            "Claude non ha restituito JSON valido"
        ) from exc

    if not isinstance(data, dict):
        raise InvalidJSONResponse("La risposta JSON non è un oggetto")

    return normalize_response(data)
