"""Validazione formato e logica del JSON bando (chiave radice 'bando')."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from modules.date_infer import _sembra_sportello_continuo, infer_data_scadenza_from_text
from modules.evidence import (
    economic_detail_warnings,
    entity_source_warnings,
    reconcile_economic_details,
    reconcile_entity_source,
    reconcile_explicit_ateco_exclusions,
)
from modules.schema import (
    BANDO_SCHEMA,
    DATE_FIELDS,
    DIMENSIONE_IMPRESA_KEYS,
    LIST_STRING_FIELDS,
    RUOLO_ENTE_VALUES,
    TIPO_AGEVOLAZIONE_VALUES,
    normalize_response,
)

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MANUAL_REVIEW_THRESHOLD = 50.0


def _get_bando(data: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    bando = data.get("bando")
    if isinstance(bando, dict):
        return bando
    return None


def _raw_agevolazioni_warnings(data: dict[str, Any]) -> list[str]:
    """Rileva conflitti prima che la normalizzazione li corregga."""
    bando = _get_bando(data)
    if not isinstance(bando, dict):
        return []
    agevolazioni = bando.get("agevolazioni")
    if not isinstance(agevolazioni, list) or not agevolazioni:
        return []
    structured_types = {
        item.get("tipo") for item in agevolazioni
        if isinstance(item, dict) and item.get("tipo") in TIPO_AGEVOLAZIONE_VALUES
    }
    legacy_types = set(bando.get("tipo_agevolazione") or [])
    warnings: list[str] = []
    if structured_types and structured_types != legacy_types:
        warnings.append(
            "Coerenza agevolazioni: tipo_agevolazione è stato riallineato "
            "automaticamente ad agevolazioni[].tipo"
        )
    non_rimborsabili = {"fondo_perduto", "voucher", "credito_imposta"}
    if structured_types and not (structured_types & non_rimborsabili):
        if bando.get("contributo_max") is not None:
            warnings.append(
                "Coerenza agevolazioni: contributo_max conteneva il massimale "
                "del prestito ed è stato azzerato automaticamente"
            )
    return warnings


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    if isinstance(value, dict):
        if len(value) == 0:
            return True
        if set(value.keys()) >= set(DIMENSIONE_IMPRESA_KEYS):
            return not any(value.get(k) for k in DIMENSIONE_IMPRESA_KEYS)
        # dict generico (es. anzianita_impresa, note_esclusioni): vuoto se
        # tutti i suoi valori sono a loro volta vuoti (ricorsivo).
        return all(_is_empty(v) for v in value.values())
    return False


def _type_ok(value: Any, expected: type | tuple[type, ...]) -> bool:
    return isinstance(value, expected)


def _parse_date(raw: str) -> datetime | None:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def _normalize_date_field(value: Any) -> Any:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str):
        return value
    parsed = _parse_date(value)
    if parsed is not None:
        return parsed.strftime("%Y-%m-%d")
    return value


def normalize_bando_dates(bando: dict[str, Any]) -> dict[str, Any]:
    result = dict(bando)
    for field in DATE_FIELDS:
        if field in result:
            result[field] = _normalize_date_field(result.get(field))
    return result


def validate_structure(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["La risposta deve essere un oggetto JSON"]
    if "bando" not in data:
        errors.append("Chiave radice 'bando' mancante")
    elif not isinstance(data["bando"], dict):
        errors.append("'bando' deve essere un oggetto")
    return errors


def validate_format_fields(bando: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(bando, dict):
        return ["'bando' deve essere un oggetto"]

    for key, expected_type in BANDO_SCHEMA.items():
        if key not in bando:
            errors.append(f"Chiave schema mancante in bando: {key}")
            continue
        value = bando[key]
        if not _type_ok(value, expected_type):
            errors.append(
                f"Tipo non valido per 'bando.{key}': atteso {expected_type}, "
                f"ricevuto {type(value).__name__}"
            )

    dim = bando.get("dimensione_impresa")
    if isinstance(dim, dict):
        for k in DIMENSIONE_IMPRESA_KEYS:
            if k not in dim:
                errors.append(f"bando.dimensione_impresa.{k} mancante")
            elif not isinstance(dim[k], bool):
                errors.append(f"bando.dimensione_impresa.{k} deve essere booleano")

    for field in DATE_FIELDS:
        raw = bando.get(field)
        if raw is not None and isinstance(raw, str) and raw.strip():
            if not ISO_DATE_RE.match(raw.strip()):
                errors.append(
                    f"bando.{field} deve essere YYYY-MM-DD o null"
                )

    for list_key in LIST_STRING_FIELDS:
        items = bando.get(list_key)
        if isinstance(items, list):
            for i, item in enumerate(items):
                if not isinstance(item, str):
                    errors.append(f"bando.{list_key}[{i}] deve essere una stringa")

    if bando.get("ateco_aperto_a_tutti") is True:
        codici = bando.get("codici_ateco_ammessi")
        if isinstance(codici, list) and len(codici) > 0:
            errors.append(
                "Se ateco_aperto_a_tutti è true, codici_ateco_ammessi deve essere []"
            )

    agevolazioni = bando.get("agevolazioni")
    if isinstance(agevolazioni, list):
        for index, agevolazione in enumerate(agevolazioni):
            prefix = f"bando.agevolazioni[{index}]"
            if not isinstance(agevolazione, dict):
                errors.append(f"{prefix} deve essere un oggetto")
                continue
            if agevolazione.get("tipo") not in TIPO_AGEVOLAZIONE_VALUES:
                errors.append(f"{prefix}.tipo non valido")
            for field in (
                "importo_min", "importo_max", "percentuale",
                "tasso_interesse_percentuale", "durata_mesi",
                "preammortamento_mesi", "abbuono_rate",
            ):
                value = agevolazione.get(field)
                if value is not None and not isinstance(value, (int, float)):
                    errors.append(f"{prefix}.{field} deve essere numerico o null")
                elif isinstance(value, (int, float)) and value < 0:
                    errors.append(f"{prefix}.{field} non può essere negativo")
            percentage = agevolazione.get("percentuale")
            if isinstance(percentage, (int, float)) and percentage > 100:
                errors.append(f"{prefix}.percentuale non può superare 100")
            repayment = agevolazione.get("rimborso_richiesto")
            if repayment is not None and not isinstance(repayment, bool):
                errors.append(f"{prefix}.rimborso_richiesto deve essere booleano o null")

    fonti = bando.get("fonti")
    if isinstance(fonti, list):
        for index, fonte in enumerate(fonti):
            prefix = f"bando.fonti[{index}]"
            if not isinstance(fonte, dict):
                errors.append(f"{prefix} deve essere un oggetto")
                continue
            pagina = fonte.get("pagina")
            if pagina is not None and (not isinstance(pagina, int) or pagina < 1):
                errors.append(f"{prefix}.pagina deve essere un intero positivo o null")

    entities = bando.get("enti_coinvolti")
    if isinstance(entities, list):
        for index, entity in enumerate(entities):
            prefix = f"bando.enti_coinvolti[{index}]"
            if not isinstance(entity, dict):
                errors.append(f"{prefix} deve essere un oggetto")
                continue
            if not isinstance(entity.get("nome"), str) or not entity["nome"].strip():
                errors.append(f"{prefix}.nome deve essere una stringa non vuota")
            role = entity.get("ruolo")
            if role is not None and role not in RUOLO_ENTE_VALUES:
                errors.append(f"{prefix}.ruolo non valido")

    return errors


def validate_logical_fields(bando: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    raw = bando.get("data_scadenza")
    if isinstance(raw, str) and ISO_DATE_RE.match(raw.strip()):
        parsed = _parse_date(raw)
        if parsed is None:
            errors.append("bando.data_scadenza non è una data valida")
        elif parsed.date() <= date.today():
            warnings.append("data_scadenza nel passato — verificare se il bando è ancora attivo")

    agevolazioni = bando.get("agevolazioni")
    agevolazioni = agevolazioni if isinstance(agevolazioni, list) else []
    tipi_strutturati = {
        item.get("tipo") for item in agevolazioni
        if isinstance(item, dict) and item.get("tipo") in TIPO_AGEVOLAZIONE_VALUES
    }
    tipi_legacy = set(bando.get("tipo_agevolazione") or [])
    if tipi_strutturati and tipi_legacy != tipi_strutturati:
        warnings.append(
            "Coerenza agevolazioni: tipo_agevolazione non coincide con agevolazioni[].tipo"
        )

    solo_finanziamento = bool(tipi_strutturati or tipi_legacy) and not (
        {"fondo_perduto", "voucher", "credito_imposta"} & (tipi_strutturati or tipi_legacy)
    )
    if solo_finanziamento and bando.get("contributo_max") is not None:
        warnings.append(
            "Coerenza agevolazioni: contributo_max è valorizzato per uno strumento "
            "solo rimborsabile; verificare che non sia il massimale del prestito"
        )

    for index, item in enumerate(agevolazioni):
        if not isinstance(item, dict):
            continue
        tipo = item.get("tipo")
        if tipo == "finanziamento_agevolato" and item.get("rimborso_richiesto") is False:
            warnings.append(
                f"Coerenza agevolazioni: agevolazioni[{index}] è un finanziamento "
                "ma rimborso_richiesto è false"
            )
        if tipo == "fondo_perduto":
            percentages = item.get("percentuali_per_dimensione")
            has_percentage = item.get("percentuale") is not None or (
                isinstance(percentages, dict) and any(v is not None for v in percentages.values())
            )
            if item.get("importo_max") is None and not has_percentage:
                warnings.append(
                    f"Coerenza agevolazioni: agevolazioni[{index}] è a fondo perduto "
                    "ma non contiene né importo massimo né percentuale"
                )

    coverage = bando.get("copertura_estrazione")
    if isinstance(coverage, dict) and coverage.get("completa") is False:
        warnings.append("Copertura estrazione incompleta — revisione manuale obbligatoria")
    return errors, warnings


def calculate_null_percentage(bando: dict[str, Any]) -> float:
    if not isinstance(bando, dict) or not bando:
        return 100.0
    # I nuovi campi strutturati sono additivi e i metadati non rappresentano
    # informazioni mancanti del bando. Escluderli mantiene confrontabile la
    # percentuale con le estrazioni legacy già salvate.
    completeness_fields = tuple(
        key for key in BANDO_SCHEMA
        if key not in {
            "agevolazioni", "fonti", "enti_coinvolti", "copertura_estrazione",
            "url_documento_origine",
        }
    )
    total = len(completeness_fields)
    empty = sum(1 for key in completeness_fields if _is_empty(bando.get(key)))
    return (empty / total) * 100.0


def critical_gaps(bando: dict[str, Any], raw_text: str | None = None) -> list[str]:
    """Campi critici mancanti: titolo, scadenza (salvo sportello continuo),
    contributo/percentuale, ATECO. La soglia sulla % globale sottostima i
    bandi con pochi campi minori valorizzati ma i dati chiave assenti — questi
    quattro gruppi vengono quindi controllati esplicitamente, indipendentemente
    dalla percentuale complessiva di null.
    """
    if not isinstance(bando, dict):
        return ["titolo", "data_scadenza", "contributo_max/percentuale_fondo_perduto",
                "codici_ateco_ammessi/ateco_aperto_a_tutti/attivita_ammesse"]

    gaps: list[str] = []

    if _is_empty(bando.get("titolo")):
        gaps.append("titolo")

    if _is_empty(bando.get("data_scadenza")):
        sportello = bool(raw_text) and _sembra_sportello_continuo(raw_text)
        if not sportello:
            gaps.append("data_scadenza")

    economic_info = (
        not _is_empty(bando.get("contributo_max"))
        or not _is_empty(bando.get("percentuale_fondo_perduto"))
        or not _is_empty(bando.get("agevolazioni"))
        or not _is_empty(bando.get("tipo_agevolazione"))
    )
    if not economic_info:
        gaps.append("contributo_max/percentuale_fondo_perduto")

    ateco_presente = (
        not _is_empty(bando.get("codici_ateco_ammessi"))
        or bando.get("ateco_aperto_a_tutti") is True
        or not _is_empty(bando.get("attivita_ammesse"))
    )
    if not ateco_presente:
        gaps.append("codici_ateco_ammessi/ateco_aperto_a_tutti/attivita_ammesse")

    return gaps


def should_review_manually(bando: dict[str, Any], raw_text: str | None = None) -> bool:
    if critical_gaps(bando, raw_text):
        return True
    return calculate_null_percentage(bando) > MANUAL_REVIEW_THRESHOLD


def validate_bando(
    data: dict[str, Any],
    raw_text: str | None = None,
) -> dict[str, Any]:
    """
    Valida {"bando": {...}}.
    Ritorna: data, errors, warnings, null_percentage, needs_manual_review.
    """
    raw_input = data if isinstance(data, dict) else {}
    raw_bando = _get_bando(raw_input)
    raw_warnings = _raw_agevolazioni_warnings(raw_input)
    wrapped = normalize_response(data if isinstance(data, dict) else {})
    errors = validate_structure(wrapped)
    warnings: list[str] = list(raw_warnings)

    bando = wrapped.get("bando")
    if not isinstance(bando, dict):
        return {
            "data": wrapped,
            "errors": errors,
            "warnings": warnings,
            "null_percentage": 100.0,
            "needs_manual_review": True,
            "critical_gaps": [
                "titolo",
                "data_scadenza",
                "contributo_max/percentuale_fondo_perduto",
                "codici_ateco_ammessi/ateco_aperto_a_tutti/attivita_ammesse",
            ],
        }

    bando = normalize_bando_dates(bando)

    if raw_text and _is_empty(bando.get("data_scadenza")):
        inferred = infer_data_scadenza_from_text(raw_text)
        if inferred:
            bando["data_scadenza"] = inferred
            warnings.append(
                "bando.data_scadenza ricavata dal testo PDF (il modello non l'aveva compilata)"
            )

    wrapped["bando"] = bando
    if raw_text:
        warnings.extend(reconcile_explicit_ateco_exclusions(wrapped, raw_text))
        warnings.extend(reconcile_entity_source(wrapped, raw_text))
        reconcile_economic_details(wrapped, raw_text)
        warnings.extend(economic_detail_warnings(wrapped, raw_text))
    if isinstance(raw_bando, dict) and "fonti" in raw_bando:
        warnings.extend(entity_source_warnings(wrapped))
    errors.extend(validate_format_fields(bando))
    logical_errors, logical_warnings = validate_logical_fields(bando)
    errors.extend(logical_errors)
    warnings.extend(logical_warnings)

    null_pct = calculate_null_percentage(bando)
    gaps = critical_gaps(bando, raw_text)
    coherence_warnings = [
        warning for warning in warnings
        if warning.startswith("Coerenza agevolazioni")
        or warning.startswith("Coerenza fonti")
        or warning.startswith("Coerenza ATECO")
        or warning.startswith("Copertura estrazione incompleta")
        or warning.startswith("Completezza economica")
    ]
    needs_review = should_review_manually(bando, raw_text) or bool(coherence_warnings)
    if needs_review:
        if gaps:
            warnings.append(
                "Da revisionare manualmente — campi critici mancanti: " + ", ".join(gaps)
            )
        if null_pct > MANUAL_REVIEW_THRESHOLD:
            warnings.append(
                "RF-007: Da revisionare manualmente — più del 50% dei campi è nullo "
                f"({null_pct:.0f}%)"
            )
        if coherence_warnings and not gaps and null_pct <= MANUAL_REVIEW_THRESHOLD:
            warnings.append(
                "Da revisionare manualmente — verificare le avvertenze di coerenza"
            )

    return {
        "data": wrapped,
        "errors": errors,
        "warnings": warnings,
        "null_percentage": null_pct,
        "needs_manual_review": needs_review,
        "critical_gaps": gaps,
    }


def fields_status(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Campi valorizzati vs null (per PROMPT_LOG), prefisso bando."""
    bando = _get_bando(data) or {}
    ok_fields: list[str] = []
    null_fields: list[str] = []
    for key in BANDO_SCHEMA:
        label = f"bando.{key}"
        if _is_empty(bando.get(key)):
            null_fields.append(label)
        else:
            ok_fields.append(label)
    return ok_fields, null_fields
