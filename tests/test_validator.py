"""Test unitari per modules/validator.py.
Nessun mock DB — tutte le funzioni sono pure.
"""
import pytest
from modules.validator import (
    validate_structure,
    validate_format_fields,
    validate_logical_fields,
    calculate_null_percentage,
    validate_bando,
)


# ---------------------------------------------------------------------------
# validate_structure
# ---------------------------------------------------------------------------

def test_validate_structure_chiave_bando_mancante():
    errors = validate_structure({})
    assert any("bando" in e.lower() for e in errors)


def test_validate_structure_bando_non_dict():
    errors = validate_structure({"bando": "non un dizionario"})
    assert any("oggetto" in e for e in errors)


def test_validate_structure_ok():
    assert validate_structure({"bando": {}}) == []


# ---------------------------------------------------------------------------
# validate_format_fields
# ---------------------------------------------------------------------------

def test_validate_format_tipo_errato_titolo(bando_minimo):
    """titolo deve essere str|None — passare int genera errore di tipo."""
    bando = bando_minimo(titolo=123)
    errors = validate_format_fields(bando)
    assert any("titolo" in e for e in errors)


def test_validate_format_ateco_aperto_con_codici(bando_minimo):
    """Combinazione inconsistente: ateco_aperto_a_tutti=True + codici non vuoti."""
    bando = bando_minimo(ateco_aperto_a_tutti=True, codici_ateco_ammessi=["62.01"])
    errors = validate_format_fields(bando)
    assert len(errors) > 0


def test_validate_format_data_non_iso(bando_minimo):
    """Chiamata diretta (senza normalize_bando_dates) per testare il controllo formato ISO."""
    bando = bando_minimo(data_scadenza="31/12/2099")
    errors = validate_format_fields(bando)
    assert any("data_scadenza" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_logical_fields
# ---------------------------------------------------------------------------

def test_validate_logical_data_passata(bando_minimo):
    bando = bando_minimo(data_scadenza="2020-01-01")
    errors = validate_logical_fields(bando)
    assert len(errors) > 0


def test_validate_logical_data_futura(bando_minimo):
    bando = bando_minimo(data_scadenza="2099-12-31")
    assert validate_logical_fields(bando) == []


# ---------------------------------------------------------------------------
# calculate_null_percentage
# ---------------------------------------------------------------------------

def test_calculate_null_percentage_tutto_null(bando_minimo):
    """Bando con tutti i campi a null/vuoto → percentuale alta (>80%).
    Due campi non sono mai "vuoti" per definizione: ateco_aperto_a_tutti=False
    e anzianita_impresa (dict non vuoto con 2 chiavi).
    """
    bando = bando_minimo()
    pct = calculate_null_percentage(bando)
    assert pct > 80.0


def test_calculate_null_percentage_parziale(bando_minimo):
    bando = bando_minimo(
        titolo="Test",
        ente="Ente",
        data_scadenza="2099-12-31",
        contributo_max=50_000.0,
        codici_ateco_ammessi=["62.01"],
    )
    pct = calculate_null_percentage(bando)
    assert 0.0 < pct < 100.0


# ---------------------------------------------------------------------------
# validate_bando
# ---------------------------------------------------------------------------

def test_validate_bando_ritorna_keys_attese(bando_minimo):
    data = {"bando": bando_minimo(data_scadenza="2099-12-31")}
    result = validate_bando(data)
    assert "data" in result
    assert "errors" in result
    assert "warnings" in result
    assert "null_percentage" in result
    assert "needs_manual_review" in result


def test_validate_bando_needs_manual_review_true(bando_minimo):
    """Bando con quasi tutti i campi vuoti → needs_manual_review=True."""
    data = {"bando": bando_minimo()}
    result = validate_bando(data)
    assert result["needs_manual_review"] is True
