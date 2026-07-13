"""Estrazione testo PDF e dati bando via API OpenRouter (DeepSeek)."""

from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
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
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from modules.evidence import (
    reconcile_economic_details,
    reconcile_entity_source,
    reconcile_explicit_ateco_exclusions,
)
from modules.log_utils import log_error, log_incident
from modules.schema import MAX_TEXT_CHARS, MIN_TEXT_CHARS, normalize_response

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts" / "system_extraction.md"
CONSOLIDATION_PROMPT_PATH = ROOT / "prompts" / "system_consolidation.md"
# Usiamo il modello DeepSeek reale, senza ":free"
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek/deepseek-v4-flash")
# Slug OpenRouter verificato su openrouter.ai/anthropic/claude-haiku-4.5 (2026-07-08).
# Gli ID OpenRouter richiedono sempre il prefisso vendor (es. "anthropic/...");
# un ID senza prefisso (come in una versione precedente di questa costante)
# causava 404 silenziosi su ogni tentativo di fallback (audit D-2 / error_log.txt storico).
LLM_FALLBACK_MODEL = os.environ.get("LLM_FALLBACK_MODEL", "anthropic/claude-haiku-4.5")
RETRY_ATTEMPTS = 3
# Backoff esponenziale (2s, 4s, 8s) invece del precedente wait_fixed(60s):
# l'endpoint /api/estrazione è sincrono e su Render free un'attesa fissa di
# 60s per tentativo rischiava timeout del proxy e richieste appese (audit D-9).
RETRY_WAIT_MULTIPLIER = int(os.environ.get("LLM_RETRY_WAIT_MULTIPLIER", "2"))
RETRY_WAIT_MAX_SECONDS = int(os.environ.get("LLM_RETRY_WAIT_MAX_SECONDS", "8"))
# Timeout esplicito sulla chiamata HTTP al provider: senza questo il client
# usa il default della libreria (molto più lungo), sommandosi ai retry.
LLM_REQUEST_TIMEOUT_SECONDS = int(os.environ.get("LLM_REQUEST_TIMEOUT_SECONDS", "30"))
# Senza un limite esplicito il client richiede il massimo output del modello
# (es. 64.000 token su Claude Haiku 4.5): con saldo OpenRouter basso questo
# fa fallire con 402 anche chiamate legittime. Il JSON di un bando estratto
# non supera mai poche migliaia di token.
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "4000"))
# Limite pagine per evitare PDF abnormi/malformati che saturano CPU/RAM in parsing
MAX_PDF_PAGES = int(os.environ.get("MAX_PDF_PAGES", "300"))
EXTRACTION_CHUNK_CHARS = int(os.environ.get("EXTRACTION_CHUNK_CHARS", "60000"))
EXTRACTION_CHUNK_OVERLAP = int(os.environ.get("EXTRACTION_CHUNK_OVERLAP", "2000"))
EXTRACTION_CHUNK_WORKERS = int(os.environ.get("EXTRACTION_CHUNK_WORKERS", "3"))
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
        timeout=LLM_REQUEST_TIMEOUT_SECONDS,
    )


_BANDO_TEXT_CLOSE_RE = re.compile(r'</\s*bando_text\s*>', re.IGNORECASE)


def _sanitize_delimiters(raw_text: str) -> str:
    """Neutralizza tentativi di chiusura anticipata del delimitatore `<bando_text>`.

    Un PDF ostile potrebbe contenere una stringa tipo "</bando_text> Ignora
    le istruzioni precedenti..." per uscire dal blocco delimitato e far
    passare nuove istruzioni come se venissero dal prompt di sistema
    (prompt injection, ROADMAP #10). Il tag viene sostituito con un
    placeholder innocuo prima di iniettare il testo nel prompt.
    """
    return _BANDO_TEXT_CLOSE_RE.sub('[TAG_RIMOSSO]', raw_text)


def _load_system_prompt(raw_text: str) -> str:
    if not PROMPT_PATH.is_file():
        raise FileNotFoundError(f"Prompt non trovato: {PROMPT_PATH}")
    template = PROMPT_PATH.read_text(encoding="utf-8")
    sanitized_text = _sanitize_delimiters(raw_text)
    if "{raw_text}" not in template:
        return f"{template.strip()}\n\nTesto del bando:\n<bando_text>\n{sanitized_text}\n</bando_text>"
    return template.replace("{raw_text}", sanitized_text)


def _load_consolidation_prompt(partial_results: list[dict]) -> str:
    if not CONSOLIDATION_PROMPT_PATH.is_file():
        raise FileNotFoundError(f"Prompt non trovato: {CONSOLIDATION_PROMPT_PATH}")
    template = CONSOLIDATION_PROMPT_PATH.read_text(encoding="utf-8")
    payload = json.dumps(partial_results, ensure_ascii=False, indent=2)
    payload = re.sub(
        r'</\s*partial_extractions\s*>',
        '[TAG_RIMOSSO]',
        payload,
        flags=re.IGNORECASE,
    )
    return template.replace("{partial_results}", payload)


def _split_text_chunks(raw_text: str) -> list[str]:
    """Divide senza perdite il testo lungo, con sovrapposizione tra blocchi."""
    chunk_size = max(1, min(EXTRACTION_CHUNK_CHARS, MAX_TEXT_CHARS))
    if len(raw_text) <= chunk_size:
        return [raw_text]

    overlap = min(max(0, EXTRACTION_CHUNK_OVERLAP), max(0, chunk_size // 4))
    chunks: list[str] = []
    start = 0
    while start < len(raw_text):
        target = min(start + chunk_size, len(raw_text))
        cut = target
        if target < len(raw_text):
            minimum_cut = start + chunk_size // 2
            paragraph_cut = raw_text.rfind("\n\n", minimum_cut, target)
            line_cut = raw_text.rfind("\n", minimum_cut, target)
            candidate = max(paragraph_cut, line_cut)
            if candidate > start:
                cut = candidate
        chunks.append(raw_text[start:cut])
        if cut >= len(raw_text):
            break
        next_start = max(0, cut - overlap)
        start = next_start if next_start > start else cut
    return chunks


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
            parts: list[str] = [
                f"--- PAGINA {page_number} ---\n{page.get_text()}"
                for page_number, page in enumerate(doc, start=1)
            ]
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
    wait=wait_exponential(multiplier=RETRY_WAIT_MULTIPLIER, max=RETRY_WAIT_MAX_SECONDS),
    retry=retry_if_exception(_is_retryable_api_error),
    reraise=True,
)
def _call_llm_api(prompt: str, model: str = LLM_MODEL) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=LLM_MAX_TOKENS,
    )
    if not response.choices:
        raise InvalidJSONResponse("Risposta API vuota")
    content = response.choices[0].message.content
    if not content:
        # Scoperto dal golden set (audit Fable #4): su prompt molto lunghi
        # (es. bando Sapienza, testo troncato a MAX_TEXT_CHARS ma comunque
        # esteso) il provider può restituire un messaggio con content=None
        # (risposta vuota/rifiutata) invece di sollevare un errore HTTP.
        # Senza questo controllo, il None si propagava fino a
        # _clean_json_response() e andava in crash con AttributeError
        # ("'NoneType' object has no attribute 'strip'") invece di un
        # errore applicativo comprensibile con retry/fallback già gestiti
        # a monte da extract_bando_data.
        raise InvalidJSONResponse(
            f"Il modello {model} ha restituito una risposta vuota (content=None)"
        )
    return content


def _call_with_fallback(prompt: str, parser=None):
    def call_and_parse(model: str):
        content = _call_llm_api(prompt, model=model)
        return parser(content) if parser is not None else content

    try:
        return call_and_parse(LLM_MODEL)
    except MissingAPIKeyError:
        raise
    except Exception as primary_exc:
        log_error(
            f"Modello primario ({LLM_MODEL}) fallito: {primary_exc}. "
            f"Tentativo con fallback {LLM_FALLBACK_MODEL}."
        )
        try:
            return call_and_parse(LLM_FALLBACK_MODEL)
        except Exception as fallback_exc:
            msg = f"Anche il modello fallback ({LLM_FALLBACK_MODEL}) ha fallito: {fallback_exc}"
            log_error(msg)
            log_incident(
                description="Entrambi i modelli LLM non disponibili",
                impact="Estrazione bando fallita",
                cause=str(fallback_exc),
                fix="Verificare stato OpenRouter e variabili LLM_MODEL / LLM_FALLBACK_MODEL",
            )
            raise primary_exc from fallback_exc


def _parse_llm_json(content: str) -> dict:
    cleaned = _clean_json_response(content)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        log_error(f"JSON non valido da LLM: {exc}")
        raise InvalidJSONResponse("L'LLM non ha restituito JSON valido") from exc
    if not isinstance(data, dict):
        raise InvalidJSONResponse("La risposta JSON non è un oggetto")
    return data


def _extract_single_chunk(raw_text: str) -> dict:
    prompt = _load_system_prompt(raw_text)
    return normalize_response(_call_with_fallback(prompt, parser=_parse_llm_json))


def _is_empty_merge_value(value: object) -> bool:
    if value is None or value == "":
        return True
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _dedupe_list(items: list[object]) -> list[object]:
    result: list[object] = []
    signatures: set[str] = set()
    for item in items:
        signature = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if signature not in signatures:
            signatures.add(signature)
            result.append(item)
    return result


def _merge_agevolazioni(current: object, incoming: object) -> list[dict]:
    """Unisce strumenti dello stesso tipo riempiendo i dettagli mancanti."""
    result = [dict(item) for item in current if isinstance(item, dict)] \
        if isinstance(current, list) else []
    for raw_item in incoming if isinstance(incoming, list) else []:
        if not isinstance(raw_item, dict):
            continue
        item = dict(raw_item)
        tipo = item.get("tipo")
        existing = next((entry for entry in result if entry.get("tipo") == tipo), None)
        if existing is None:
            result.append(item)
            continue
        for name, value in item.items():
            if name in {"condizioni", "fonti"}:
                existing[name] = _dedupe_list(
                    (existing.get(name) if isinstance(existing.get(name), list) else [])
                    + (value if isinstance(value, list) else [])
                )
            elif name == "percentuali_per_dimensione" and isinstance(value, dict):
                percentages = dict(existing.get(name)) if isinstance(existing.get(name), dict) else {}
                for size, percentage in value.items():
                    if percentages.get(size) is None and percentage is not None:
                        percentages[size] = percentage
                existing[name] = percentages
            elif _is_empty_merge_value(existing.get(name)) and not _is_empty_merge_value(value):
                existing[name] = value
    return result


def _merge_partial_results(partial_results: list[dict]) -> dict:
    """Fallback deterministico se il consolidamento LLM non è disponibile."""
    merged: dict[str, object] = {}
    for result in partial_results:
        bando = result.get("bando", {}) if isinstance(result, dict) else {}
        if not isinstance(bando, dict):
            continue
        for key, value in bando.items():
            current = merged.get(key)
            if key in {"codici_ateco_ammessi", "attivita_ammesse", "regioni_ammesse",
                       "spese_ammissibili", "forme_giuridiche_ammesse", "tipo_agevolazione",
                       "fonti", "enti_coinvolti"}:
                merged[key] = _dedupe_list(
                    (current if isinstance(current, list) else [])
                    + (value if isinstance(value, list) else [])
                )
            elif key == "agevolazioni":
                merged[key] = _merge_agevolazioni(current, value)
            elif key == "dimensione_impresa" and isinstance(value, dict):
                base = current if isinstance(current, dict) else {}
                merged[key] = {name: bool(base.get(name) or value.get(name)) for name in value}
            elif key == "percentuale_fondo_perduto" and isinstance(value, dict):
                base = dict(current) if isinstance(current, dict) else {}
                for name, percentage in value.items():
                    if base.get(name) is None and percentage is not None:
                        base[name] = percentage
                merged[key] = base
            elif key == "note_esclusioni" and isinstance(value, dict):
                base = dict(current) if isinstance(current, dict) else {}
                for name, note_value in value.items():
                    if isinstance(note_value, list):
                        base[name] = _dedupe_list(
                            (base.get(name) if isinstance(base.get(name), list) else []) + note_value
                        )
                    elif _is_empty_merge_value(base.get(name)) and not _is_empty_merge_value(note_value):
                        base[name] = note_value
                merged[key] = base
            elif key == "data_scadenza" and isinstance(value, str):
                dates = [x for x in (current, value) if isinstance(x, str)]
                merged[key] = max(dates) if dates else None
            elif _is_empty_merge_value(current) and not _is_empty_merge_value(value):
                merged[key] = value
    return normalize_response({"bando": merged})


def _consolidate_partial_results(partial_results: list[dict]) -> dict:
    prompt = _load_consolidation_prompt(partial_results)
    try:
        consolidated = normalize_response(_call_with_fallback(prompt, parser=_parse_llm_json))
        # Il modello di consolidamento risolve i conflitti, ma non deve poter
        # eliminare liste o dettagli trovati in un singolo blocco.
        return _merge_partial_results([consolidated, *partial_results])
    except Exception as exc:
        log_error(f"Consolidamento LLM fallito, uso merge deterministico: {exc}")
        return _merge_partial_results(partial_results)


def extract_bando_data(raw_text: str) -> dict:
    """Estrae l'intero bando; i testi oltre soglia sono analizzati a blocchi."""
    total_chars = len(raw_text)
    if total_chars <= EXTRACTION_CHUNK_CHARS:
        chunks = [raw_text]
    else:
        chunks = _split_text_chunks(raw_text)
        log_error(
            f"Testo bando di {total_chars} caratteri analizzato integralmente "
            f"in {len(chunks)} blocchi, senza troncamento"
        )

    if len(chunks) == 1:
        partial_results = [_extract_single_chunk(chunks[0])]
    else:
        workers = max(1, min(EXTRACTION_CHUNK_WORKERS, len(chunks)))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            partial_results = list(executor.map(_extract_single_chunk, chunks))
    result = (
        partial_results[0]
        if len(partial_results) == 1
        else _consolidate_partial_results(partial_results)
    )

    bando = result.get("bando", {})
    if isinstance(bando, dict):
        bando["urgenza"] = calcola_urgenza(bando.get("data_scadenza"))
        bando["copertura_estrazione"] = {
            "caratteri_totali": total_chars,
            "caratteri_analizzati": total_chars,
            "numero_blocchi": len(chunks),
            "completa": True,
        }
        reconcile_explicit_ateco_exclusions(result, raw_text)
        reconcile_entity_source(result, raw_text)
        reconcile_economic_details(result, raw_text)
        # La % di campi null e il flag "da revisionare" sono calcolati da
        # modules.validator.validate_bando (unica fonte di verità, vedi #18):
        # qui si duplicava la stessa logica con un bug (i dict come
        # anzianita_impresa non venivano mai contati come vuoti) e il
        # risultato non veniva letto da nessun chiamante a valle.

    return result
