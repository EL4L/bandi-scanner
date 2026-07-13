"""Riconciliazione deterministica tra JSON estratto e testo sorgente."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from modules.schema import normalize_duration_months


_PAGE_MARKER_RE = re.compile(r"---\s*PAGINA\s+(\d+)\s*---", re.IGNORECASE)
_ATECO_SECTION_RE = re.compile(
    r"\b(?:sez(?:ione)?\.?\s*(?:ateco\s*)?|sezione\s+ateco\s+)([A-U])\b",
    re.IGNORECASE,
)
_EXCLUSION_RE = re.compile(
    r"esclus|non\s+ammiss|vietat|non\s+possono|non\s+pu[oò]",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_ENTITY_STOPWORDS = {
    "spa", "srl", "societa", "ente", "del", "della", "delle", "degli",
    "dei", "di", "e", "per", "il", "la", "le", "lo", "un", "una",
}
_ENTITY_CONTEXT_RE = re.compile(
    r"bollettino\s+ufficiale|programma\s+region|autorit[aà]|amministrazione|"
    r"promoss|adottat|approvat|finanziat|ente\s+(?:promotore|concedente)",
    re.IGNORECASE,
)
_ENTITY_NEGATIVE_CONTEXT_RE = re.compile(
    r"gestore|gestione\s+(?:è\s+)?affidata|responsabile\s+del\s+procedimento|"
    r"trattamento\s+dei\s+dati",
    re.IGNORECASE,
)
_ABBUONO_RE = re.compile(
    r"abbuon\w*\s+(?:delle\s+)?ultime\s+(\d{1,3})\s+rate",
    re.IGNORECASE,
)
_CUMULABILITA_RE = re.compile(
    r"(?:non\s+aver\s+beneficiato\s+di\s+altri\s+sostegni\s+pubblici[^.]{0,500}"
    r"|[^.]{0,220}(?:limiti?\s+di\s+cumulo|non\s+cumulabil|non\s+[èe]\s+compatibil)"
    r"[^.]{0,320})\.",
    re.IGNORECASE,
)
_ITALIAN_NUMBER = r"(\d+(?:\.\d{3})*(?:,\d+)?)"
_FINANCING_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "importo_min": re.compile(
        rf"\bimporto\s+minimo\s*:?\s*(?:€\s*)?{_ITALIAN_NUMBER}\s*(?:euro|€)?",
        re.IGNORECASE,
    ),
    "importo_max": re.compile(
        rf"\bimporto\s+massimo\s*:?\s*(?:€\s*)?{_ITALIAN_NUMBER}\s*(?:euro|€)?",
        re.IGNORECASE,
    ),
}
_FINANCING_RATE_RE = re.compile(
    rf"\btasso\s+di\s+interesse\s*:?\s*(zero|{_ITALIAN_NUMBER}\s*%)",
    re.IGNORECASE,
)
_TEMPORAL_AMOUNT = r"(?P<amount>\d+(?:[.,]\d+)?)"
_TEMPORAL_UNIT = r"(?P<unit>mesi?|trimestr[ei]|semestr[ei]|ann[oi])"
_FINANCING_DURATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"\b(?:finanziamento|prestito|mutuo)\b[^.;\n]{{0,120}}?"
        rf"\bdurata(?:\s+di\s+ammortamento)?\b[^\d.;\n]{{0,40}}?"
        rf"{_TEMPORAL_AMOUNT}\s*{_TEMPORAL_UNIT}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bperiodo\s+di\s+(?:rimborso|ammortamento)"
        rf"(?:\s+del\s+(?:prestito|finanziamento|mutuo))?\b"
        rf"[^\d.;\n]{{0,40}}?{_TEMPORAL_AMOUNT}\s*{_TEMPORAL_UNIT}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bdurata\s*:\s*{_TEMPORAL_AMOUNT}\s*{_TEMPORAL_UNIT}\b",
        re.IGNORECASE,
    ),
)
_PREAMMORTAMENTO_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"\bpre[\s\-\u2010\u2011\u2012\u2013\u2014]?ammortamento\b"
        rf"[^\d.;\n]{{0,40}}?{_TEMPORAL_AMOUNT}\s*{_TEMPORAL_UNIT}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bpre[\s\-\u2010\u2011\u2012\u2013\u2014]?ammortamento\s*:\s*"
        rf"{_TEMPORAL_AMOUNT}(?!\s*[/\\-]\s*\d)",
        re.IGNORECASE,
    ),
)


def _empty_exclusions() -> dict[str, object]:
    return {
        "lista_testuale": None,
        "sezioni_ateco_escluse": [],
        "attivita_vietate": [],
        "soggetti_esclusi": [],
        "spese_non_ammissibili": [],
        "altre_esclusioni": [],
    }


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _page_at(raw_text: str, position: int) -> int | None:
    page: int | None = None
    for match in _PAGE_MARKER_RE.finditer(raw_text, 0, position + 1):
        page = int(match.group(1))
    return page


def _snippet(raw_text: str, start: int, end: int, radius: int = 220) -> str:
    return _compact(raw_text[max(0, start - radius):min(len(raw_text), end + radius)])


def _parse_italian_number(value: str) -> float | int:
    number = float(value.replace(".", "").replace(",", "."))
    return int(number) if number.is_integer() else number


def _first_match(
    patterns: tuple[re.Pattern[str], ...], raw_text: str
) -> re.Match[str] | None:
    matches = [match for pattern in patterns if (match := pattern.search(raw_text))]
    return min(matches, key=lambda match: match.start()) if matches else None


def _months_from_match(match: re.Match[str]) -> float | int | None:
    unit = match.groupdict().get("unit")
    value = f"{match.group('amount')} {unit}" if unit else match.group("amount")
    return normalize_duration_months(value)


def _append_financing_source(
    financing: dict[str, Any], field: str, raw_text: str, match: re.Match[str]
) -> None:
    sources = financing.get("fonti")
    sources = list(sources) if isinstance(sources, list) else []
    source = {
        "campo": f"agevolazioni[].{field}",
        "pagina": _page_at(raw_text, match.start()),
        "testo": _snippet(raw_text, match.start(), match.end(), radius=80),
        "certezza": "alta",
    }
    signature = (source["campo"], source["pagina"], source["testo"])
    existing = {
        (item.get("campo"), item.get("pagina"), item.get("testo"))
        for item in sources if isinstance(item, dict)
    }
    if signature not in existing:
        sources.append(source)
    financing["fonti"] = sources


def _empty_financing() -> dict[str, Any]:
    return {
        "tipo": "finanziamento_agevolato",
        "importo_min": None,
        "importo_max": None,
        "percentuale": None,
        "percentuali_per_dimensione": {
            "micro": None, "piccola": None, "media": None, "default": None,
        },
        "tasso_interesse_percentuale": None,
        "tasso_descrizione": None,
        "durata_mesi": None,
        "preammortamento_mesi": None,
        "rimborso_richiesto": True,
        "abbuono_rate": None,
        "descrizione": None,
        "condizioni": [],
        "fonti": [],
    }


def _explicit_excluded_sections(raw_text: str) -> dict[str, dict[str, Any]]:
    """Trova sezioni ATECO esplicite inserite in un contesto di esclusione."""
    found: dict[str, dict[str, Any]] = {}
    for match in _ATECO_SECTION_RE.finditer(raw_text):
        context = raw_text[max(0, match.start() - 800):min(len(raw_text), match.end() + 800)]
        if not _EXCLUSION_RE.search(context):
            continue
        letter = match.group(1).upper()
        found.setdefault(letter, {
            "campo": "note_esclusioni.sezioni_ateco_escluse",
            "pagina": _page_at(raw_text, match.start()),
            "testo": _snippet(raw_text, match.start(), match.end()),
            "certezza": "alta",
        })
    return found


def _section_letter(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    match = re.search(r"\b([A-U])\b", value.upper())
    return match.group(1) if match else None


def reconcile_explicit_ateco_exclusions(data: dict[str, Any], raw_text: str) -> list[str]:
    """Aggiunge solo sezioni esplicite e rimuove lettere inferite dal settore."""
    bando = data.get("bando") if isinstance(data, dict) else None
    if not isinstance(bando, dict) or not raw_text:
        return []

    explicit_anywhere = {
        match.group(1).upper() for match in _ATECO_SECTION_RE.finditer(raw_text)
    }
    explicit_excluded = _explicit_excluded_sections(raw_text)
    notes = bando.get("note_esclusioni")
    if isinstance(notes, str):
        converted = _empty_exclusions()
        converted["lista_testuale"] = notes
        notes = converted
    elif not isinstance(notes, dict):
        notes = _empty_exclusions()
    else:
        notes = dict(notes)
        for key, default in _empty_exclusions().items():
            notes.setdefault(key, default)

    raw_sections = notes.get("sezioni_ateco_escluse")
    raw_sections = raw_sections if isinstance(raw_sections, list) else []
    kept: list[str] = []
    removed: list[str] = []
    kept_letters: set[str] = set()
    for item in raw_sections:
        letter = _section_letter(item)
        if letter is None:
            continue
        if letter not in explicit_anywhere:
            removed.append(str(item))
            continue
        if letter not in kept_letters:
            kept_letters.add(letter)
            kept.append(f"Sez. {letter}")

    added: list[str] = []
    for letter in explicit_excluded:
        if letter not in kept_letters:
            kept_letters.add(letter)
            kept.append(f"Sez. {letter}")
            added.append(letter)

    notes["sezioni_ateco_escluse"] = kept
    bando["note_esclusioni"] = notes
    if kept:
        bando["ateco_aperto_a_tutti"] = False

    sources = bando.get("fonti")
    sources = list(sources) if isinstance(sources, list) else []
    existing_source_letters = {
        _section_letter(source.get("testo"))
        for source in sources
        if isinstance(source, dict)
        and source.get("campo") == "note_esclusioni.sezioni_ateco_escluse"
    }
    for letter, source in explicit_excluded.items():
        if letter not in existing_source_letters:
            sources.append(source)
    bando["fonti"] = sources

    warnings: list[str] = []
    if removed:
        warnings.append(
            "Coerenza ATECO: rimosse sezioni non citate esplicitamente nel testo: "
            + ", ".join(removed)
        )
    if added:
        warnings.append(
            "Coerenza ATECO: recuperate dal testo sezioni escluse esplicite: "
            + ", ".join(f"Sez. {letter}" for letter in added)
        )
    return warnings


def reconcile_economic_details(data: dict[str, Any], raw_text: str) -> list[str]:
    """Recupera dettagli economici espliciti che il modello può omettere.

    Interviene soltanto su formulazioni inequivocabili e conserva una fonte
    testuale; non deduce importi o condizioni implicite.
    """
    bando = data.get("bando") if isinstance(data, dict) else None
    if not isinstance(bando, dict) or not raw_text:
        return []

    notices: list[str] = []
    agevolazioni = bando.get("agevolazioni")
    agevolazioni = agevolazioni if isinstance(agevolazioni, list) else []
    financing = next(
        (
            item for item in agevolazioni
            if isinstance(item, dict) and item.get("tipo") == "finanziamento_agevolato"
        ),
        None,
    )
    legacy_types = bando.get("tipo_agevolazione")
    if financing is None and isinstance(legacy_types, list) and "finanziamento_agevolato" in legacy_types:
        financing = _empty_financing()
        agevolazioni.append(financing)
        bando["agevolazioni"] = agevolazioni
        notices.append("Struttura del finanziamento ricostruita dal tipo di agevolazione")

    if isinstance(financing, dict):
        financing["rimborso_richiesto"] = True
        for field, pattern in _FINANCING_FIELD_PATTERNS.items():
            match = pattern.search(raw_text)
            if match and financing.get(field) is None:
                financing[field] = _parse_italian_number(match.group(1))
                sources = financing.get("fonti")
                sources = list(sources) if isinstance(sources, list) else []
                sources.append({
                    "campo": f"agevolazioni[].{field}",
                    "pagina": _page_at(raw_text, match.start()),
                    "testo": _snippet(raw_text, match.start(), match.end(), radius=80),
                    "certezza": "alta",
                })
                financing["fonti"] = sources

        temporal_matches = {
            "durata_mesi": _first_match(_FINANCING_DURATION_PATTERNS, raw_text),
            "preammortamento_mesi": _first_match(_PREAMMORTAMENTO_PATTERNS, raw_text),
        }
        for field, match in temporal_matches.items():
            if match is None:
                continue
            months = _months_from_match(match)
            if months is None:
                continue
            previous = financing.get(field)
            if previous != months:
                financing[field] = months
                label = "Durata" if field == "durata_mesi" else "Preammortamento"
                if previous is None:
                    notices.append(f"{label} recuperato dal testo: {months} mesi")
                else:
                    notices.append(
                        f"{label} corretto da {previous} a {months} mesi "
                        f"({match.group('amount')} {match.groupdict().get('unit') or 'mesi'})"
                    )
            _append_financing_source(financing, field, raw_text, match)

        rate_match = _FINANCING_RATE_RE.search(raw_text)
        if rate_match and financing.get("tasso_interesse_percentuale") is None:
            raw_rate = rate_match.group(1)
            financing["tasso_interesse_percentuale"] = (
                0 if raw_rate.casefold() == "zero"
                else _parse_italian_number(raw_rate.replace("%", "").strip())
            )

    abbuono_match = _ABBUONO_RE.search(raw_text)
    if abbuono_match:
        rate = int(abbuono_match.group(1))
        if isinstance(financing, dict) and financing.get("abbuono_rate") is None:
            financing["abbuono_rate"] = rate
            sources = financing.get("fonti")
            sources = list(sources) if isinstance(sources, list) else []
            sources.append({
                "campo": "agevolazioni[].abbuono_rate",
                "pagina": _page_at(raw_text, abbuono_match.start()),
                "testo": _snippet(raw_text, abbuono_match.start(), abbuono_match.end(), radius=100),
                "certezza": "alta",
            })
            financing["fonti"] = sources
            notices.append(f"Abbuono di {rate} rate recuperato dal testo")

    current_cumulabilita = bando.get("cumulabilita")
    current_text = current_cumulabilita if isinstance(current_cumulabilita, str) else ""
    cumulo_match = _CUMULABILITA_RE.search(_compact(raw_text))
    should_replace_cumulabilita = not current_text.strip() or (
        "de minimis" in current_text.casefold()
        and "medesimo investimento" not in current_text.casefold()
        and cumulo_match is not None
        and "medesimo investimento" in cumulo_match.group(0).casefold()
    )
    if should_replace_cumulabilita and cumulo_match:
            clause = _compact(cumulo_match.group(0))
            bando["cumulabilita"] = clause
            sources = bando.get("fonti")
            sources = list(sources) if isinstance(sources, list) else []
            original_match = re.search(
                r"\b(?:cumulo|cumulabil\w*|medesimo\s+investimento)\b",
                raw_text,
                re.IGNORECASE,
            )
            position = original_match.start() if original_match else 0
            sources.append({
                "campo": "cumulabilita",
                "pagina": _page_at(raw_text, position),
                "testo": clause,
                "certezza": "alta",
            })
            bando["fonti"] = sources
            notices.append("Cumulabilità recuperata dal testo")
    return notices


def economic_detail_warnings(data: dict[str, Any], raw_text: str) -> list[str]:
    """Segnala dettagli espliciti rimasti assenti dopo la riconciliazione."""
    bando = data.get("bando") if isinstance(data, dict) else None
    if not isinstance(bando, dict) or not raw_text:
        return []
    warnings: list[str] = []
    agevolazioni = bando.get("agevolazioni")
    has_abbuono = any(
        isinstance(item, dict) and item.get("abbuono_rate") is not None
        for item in agevolazioni
    ) if isinstance(agevolazioni, list) else False
    if _ABBUONO_RE.search(raw_text) and not has_abbuono:
        warnings.append("Completezza economica: il testo cita un abbuono ma il campo è vuoto")
    if re.search(r"\bcumul\w*\b", raw_text, re.IGNORECASE) and not bando.get("cumulabilita"):
        warnings.append("Completezza economica: il testo cita il cumulo ma il campo è vuoto")
    return warnings


def _normalize_tokens(value: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", value.lower())
    ascii_value = "".join(char for char in folded if not unicodedata.combining(char))
    return {
        token[:6] for token in _TOKEN_RE.findall(ascii_value)
        if len(token) >= 3 and token not in _ENTITY_STOPWORDS
    }


def entity_source_warnings(data: dict[str, Any]) -> list[str]:
    """Segnala fonti che non supportano testualmente il valore di `ente`."""
    bando = data.get("bando") if isinstance(data, dict) else None
    if not isinstance(bando, dict):
        return []
    entity = bando.get("ente")
    if not isinstance(entity, str) or not entity.strip():
        return []
    sources = bando.get("fonti")
    entity_sources = [
        source for source in sources if isinstance(source, dict) and source.get("campo") == "ente"
    ] if isinstance(sources, list) else []
    if not entity_sources:
        return ["Coerenza fonti: manca una fonte testuale per il campo ente"]
    expected = _normalize_tokens(entity)
    for source in entity_sources:
        quote = source.get("testo")
        if isinstance(quote, str) and expected and expected <= _normalize_tokens(quote):
            return []
    return [
        "Coerenza fonti: la fonte associata a ente non supporta il valore estratto "
        f"“{entity}”"
    ]


def _page_segments(raw_text: str) -> list[tuple[int | None, str]]:
    markers = list(_PAGE_MARKER_RE.finditer(raw_text))
    if not markers:
        return [(None, raw_text)]
    result: list[tuple[int | None, str]] = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(raw_text)
        result.append((int(marker.group(1)), raw_text[marker.end():end]))
    return result


def _entity_source_candidate(entity: str, raw_text: str) -> dict[str, Any] | None:
    expected = _normalize_tokens(entity)
    if not expected:
        return None
    candidates: list[tuple[int, int | None, str]] = []
    meaningful_words = [
        word for word in re.findall(r"[A-Za-zÀ-ÿ0-9]+", entity)
        if len(word) >= 3 and word.lower() not in _ENTITY_STOPWORDS
    ]
    anchor = meaningful_words[-1] if meaningful_words else entity
    for page, page_text in _page_segments(raw_text):
        compact_page = _compact(page_text)
        if not compact_page or not expected <= _normalize_tokens(compact_page):
            continue
        anchor_match = re.search(re.escape(anchor), compact_page, re.IGNORECASE)
        center = anchor_match.start() if anchor_match else 0
        snippet = compact_page[max(0, center - 320):min(len(compact_page), center + 520)]
        if not _ENTITY_CONTEXT_RE.search(snippet):
            continue
        score = 10
        if re.search(re.escape(entity), snippet, re.IGNORECASE):
            score += 5
        score += len(_ENTITY_CONTEXT_RE.findall(snippet)) * 2
        if _ENTITY_NEGATIVE_CONTEXT_RE.search(snippet):
            score -= 8
        if page == 1:
            score += 2
        candidates.append((score, page, snippet))
    if not candidates:
        return None
    _, page, snippet = max(candidates, key=lambda item: item[0])
    return {
        "campo": "ente",
        "pagina": page,
        "testo": snippet,
        "certezza": "media",
    }


def reconcile_entity_source(data: dict[str, Any], raw_text: str) -> list[str]:
    """Sostituisce una fonte ente incoerente solo con evidenza contestuale forte."""
    bando = data.get("bando") if isinstance(data, dict) else None
    if not isinstance(bando, dict) or not raw_text:
        return []
    if not entity_source_warnings(data):
        return []
    entity = bando.get("ente")
    if not isinstance(entity, str) or not entity.strip():
        return []
    candidate = _entity_source_candidate(entity, raw_text)
    if candidate is None:
        return []
    sources = bando.get("fonti")
    sources = list(sources) if isinstance(sources, list) else []
    sources = [
        source for source in sources
        if not (isinstance(source, dict) and source.get("campo") == "ente")
    ]
    sources.append(candidate)
    bando["fonti"] = sources
    return [
        "Fonte ente: citazione incoerente sostituita con evidenza contestuale "
        f"a pagina {candidate['pagina']}"
    ]
