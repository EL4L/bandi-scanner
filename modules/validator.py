"""Validazione formato e logica del JSON bando (chiave radice 'bando')."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from modules.date_infer import infer_data_scadenza_from_text
from modules.schema import (
    BANDO_SCHEMA,
    DATE_FIELDS,
    DIMENSIONE_IMPRESA_KEYS,
    LIST_STRING_FIELDS,
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


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    if isinstance(value, dict):
        if set(value.keys()) >= set(DIMENSIONE_IMPRESA_KEYS):
            return not any(value.get(k) for k in DIMENSIONE_IMPRESA_KEYS)
        return len(value) == 0
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

    return errors


def validate_logical_fields(bando: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    raw = bando.get("data_scadenza")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return errors
    if not isinstance(raw, str) or not ISO_DATE_RE.match(raw.strip()):
        return errors
    parsed = _parse_date(raw)
    if parsed is None:
        errors.append("bando.data_scadenza non è una data valida")
        return errors
    if parsed.date() <= date.today():
        errors.append("bando.data_scadenza deve essere successiva alla data odierna")
    return errors


def calculate_null_percentage(bando: dict[str, Any]) -> float:
    if not isinstance(bando, dict) or not bando:
        return 100.0
    total = len(BANDO_SCHEMA)
    empty = sum(1 for key in BANDO_SCHEMA if _is_empty(bando.get(key)))
    return (empty / total) * 100.0


def should_review_manually(bando: dict[str, Any]) -> bool:
    return calculate_null_percentage(bando) > MANUAL_REVIEW_THRESHOLD


def validate_bando(
    data: dict[str, Any],
    raw_text: str | None = None,
) -> dict[str, Any]:
    """
    Valida {"bando": {...}}.
    Ritorna: data, errors, warnings, null_percentage, needs_manual_review.
    """
    wrapped = normalize_response(data if isinstance(data, dict) else {})
    errors = validate_structure(wrapped)
    warnings: list[str] = []

    bando = wrapped.get("bando")
    if not isinstance(bando, dict):
        return {
            "data": wrapped,
            "errors": errors,
            "warnings": warnings,
            "null_percentage": 100.0,
            "needs_manual_review": True,
        }

    bando = normalize_bando_dates(bando)

    if raw_text and _is_empty(bando.get("data_scadenza")):
        inferred = infer_data_scadenza_from_text(raw_text)
        if inferred:
            bando["data_scadenza"] = inferred
            warnings.append(
                "bando.data_scadenza ricavata dal testo PDF (Claude non l'aveva compilata)"
            )

    wrapped["bando"] = bando
    errors.extend(validate_format_fields(bando))
    errors.extend(validate_logical_fields(bando))

    null_pct = calculate_null_percentage(bando)
    needs_review = should_review_manually(bando)
    if needs_review:
        warnings.append("Da revisionare manualmente")

    return {
        "data": wrapped,
        "errors": errors,
        "warnings": warnings,
        "null_percentage": null_pct,
        "needs_manual_review": needs_review,
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
