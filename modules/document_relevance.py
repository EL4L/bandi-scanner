"""Classificazione prudente dei documenti estranei al matching aziendale."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


NON_COMPATIBLE_DOCUMENT_TYPE = "concorso_o_selezione_personale"


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents).strip().lower()


def _bando_data(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    inner = payload.get("bando")
    return inner if isinstance(inner, dict) else payload


def classify_non_compatible_document(
    payload: dict[str, Any] | None = None,
    raw_text: str | None = None,
) -> dict[str, str] | None:
    """Riconosce concorsi e selezioni per l'assunzione di personale.

    Il controllo privilegia il titolo estratto. Sul testo grezzo analizza solo
    l'intestazione iniziale, così una misura per imprese che cita più avanti
    l'assunzione di dipendenti non viene esclusa per errore.
    """
    bando = _bando_data(payload)
    title = _normalize_text(bando.get("titolo"))
    header = _normalize_text((raw_text or "")[:3000])

    direct_title_patterns = (
        r"\bconcorso pubblico\b",
        r"\bconcorso per (?:titoli|esami|titoli ed esami)\b",
        r"\bbando di concorso\b",
    )
    if any(re.search(pattern, title) for pattern in direct_title_patterns):
        return {
            "tipo": NON_COMPATIBLE_DOCUMENT_TYPE,
            "motivo": "Il documento è un concorso pubblico per il reclutamento di personale.",
        }

    personnel_terms = r"(?:assunzion\w*|reclutament\w*|personale|posti? di lavoro)"
    public_selection_terms = r"(?:selezione pubblica|procedura selettiva)"
    personnel_ranking_terms = r"(?:concorso|idone[io]|vincitor\w*|selezione (?:di |del )?personale)"
    is_public_selection = (
        title
        and re.search(public_selection_terms, title)
        and re.search(personnel_terms, title)
    )
    is_personnel_ranking = (
        title
        and re.search(r"\bgraduatoria\b", title)
        and re.search(personnel_ranking_terms, title)
    )
    if is_public_selection or is_personnel_ranking:
        return {
            "tipo": NON_COMPATIBLE_DOCUMENT_TYPE,
            "motivo": "Il documento riguarda una selezione o graduatoria per personale.",
        }

    # Fallback sull'intestazione: richiede sempre un segnale concorsuale forte
    # insieme a un riferimento esplicito al reclutamento.
    header_is_public_competition = (
        re.search(r"\bconcorso pubblico\b", header)
        and re.search(personnel_terms, header)
    )
    header_is_public_selection = (
        re.search(public_selection_terms, header)
        and re.search(r"(?:assunzion\w*|reclutament\w*)", header)
    )
    header_is_personnel_ranking = (
        re.search(r"\bgraduatoria\b", header)
        and re.search(personnel_ranking_terms, header)
    )
    if header and (
        header_is_public_competition
        or header_is_public_selection
        or header_is_personnel_ranking
    ):
        return {
            "tipo": NON_COMPATIBLE_DOCUMENT_TYPE,
            "motivo": "Il documento riguarda un concorso o una selezione di personale.",
        }

    return None
