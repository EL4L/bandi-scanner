"""Test unitari per modules/date_infer.py.
Tutte le funzioni sono pure (regex + logica di scoring) — nessun mock necessario.
"""
import pytest
from datetime import date
from modules.date_infer import (
    infer_data_scadenza_from_text,
    _parse_dmy,
    _find_dates_with_positions,
    _sembra_sportello_continuo,
)


# ---------------------------------------------------------------------------
# _parse_dmy
# ---------------------------------------------------------------------------

def test_parse_dmy_data_valida():
    d = _parse_dmy("31", "12", "2099")
    assert d == date(2099, 12, 31)


def test_parse_dmy_data_mese_invalido_ritorna_none():
    assert _parse_dmy("01", "13", "2099") is None


def test_parse_dmy_giorno_zero_ritorna_none():
    assert _parse_dmy("0", "1", "2099") is None


def test_parse_dmy_data_con_zero_padding():
    d = _parse_dmy("01", "01", "2099")
    assert d == date(2099, 1, 1)


# ---------------------------------------------------------------------------
# _find_dates_with_positions
# ---------------------------------------------------------------------------

def test_find_dates_formato_slash():
    dates = _find_dates_with_positions("Scade il 31/12/2099.")
    assert any(d == date(2099, 12, 31) for _, d in dates)


def test_find_dates_formato_dots():
    dates = _find_dates_with_positions("Termine 31.12.2099")
    assert any(d == date(2099, 12, 31) for _, d in dates)


def test_find_dates_formato_iso():
    dates = _find_dates_with_positions("Data: 2099-12-31")
    assert any(d == date(2099, 12, 31) for _, d in dates)


def test_find_dates_testo_senza_date_lista_vuota():
    assert _find_dates_with_positions("Nessuna data qui.") == []


def test_find_dates_data_mese_invalido_ignorata():
    dates = _find_dates_with_positions("La data 01.13.2099 non esiste.")
    assert not any(d.month == 13 for _, d in dates)


def test_find_dates_restituisce_posizione_corretta():
    text = "Il termine è 2099-06-15."
    dates = _find_dates_with_positions(text)
    assert len(dates) >= 1
    pos, d = dates[0]
    assert d == date(2099, 6, 15)
    assert pos == text.index("2099")


# ---------------------------------------------------------------------------
# infer_data_scadenza_from_text — guard clause
# ---------------------------------------------------------------------------

def test_infer_testo_vuoto_ritorna_none():
    assert infer_data_scadenza_from_text("") is None


def test_infer_testo_none_ritorna_none():
    assert infer_data_scadenza_from_text(None) is None


def test_infer_testo_solo_spazi_ritorna_none():
    assert infer_data_scadenza_from_text("   ") is None


def test_infer_testo_senza_date_ritorna_none():
    assert infer_data_scadenza_from_text("Testo generico senza alcuna data.") is None


# ---------------------------------------------------------------------------
# infer_data_scadenza_from_text — scoring con keyword
# ---------------------------------------------------------------------------

def test_infer_trova_data_dmy_vicino_scadenza():
    text = "La scadenza per la presentazione è il 31/12/2099."
    assert infer_data_scadenza_from_text(text) == "2099-12-31"


def test_infer_trova_data_iso_vicino_keyword():
    text = "Data scadenza: 2099-12-31"
    assert infer_data_scadenza_from_text(text) == "2099-12-31"


def test_infer_keyword_alta_priorita_vince():
    """'scadenza presentazione' (peso 10) batte 'entro il' (peso 5)."""
    text = (
        "Entro il 01/06/2099 si raccolgono le adesioni. "
        "La scadenza presentazione è fissata al 31/12/2099."
    )
    assert infer_data_scadenza_from_text(text) == "2099-12-31"


def test_infer_keyword_entro_il():
    text = "Le domande vanno presentate entro il 31/12/2099."
    assert infer_data_scadenza_from_text(text) == "2099-12-31"


def test_infer_keyword_fino_al():
    text = "Le domande sono ammesse fino al 31/12/2099."
    assert infer_data_scadenza_from_text(text) == "2099-12-31"


def test_infer_keyword_data_limite():
    text = "Data limite per la consegna: 31.12.2099"
    assert infer_data_scadenza_from_text(text) == "2099-12-31"


# ---------------------------------------------------------------------------
# infer_data_scadenza_from_text — nessun fallback su date future senza keyword
# ---------------------------------------------------------------------------

def test_infer_senza_keyword_non_inventa_data():
    """Senza keyword di scadenza vicine, non deve restituire alcuna data anche se futura."""
    text = "Il documento è stato redatto il 01/01/2020. Valido sino al 31/12/2099."
    result = infer_data_scadenza_from_text(text)
    assert result is None


def test_infer_solo_date_passate_ritorna_none():
    """Con solo date passate e nessuna keyword: nessuna data futura → None."""
    text = "Documento del 01/01/2020 e del 15/03/2021."
    assert infer_data_scadenza_from_text(text) is None


def test_infer_due_date_future_senza_keyword_ritorna_none():
    """Tra due date future senza keyword, non sceglie più la più lontana: restituisce None."""
    text = "Prima finestra: 01/06/2099. Termine ultimo: 31/12/2099."
    assert infer_data_scadenza_from_text(text) is None


# ---------------------------------------------------------------------------
# _sembra_sportello_continuo
# ---------------------------------------------------------------------------

class TestSportelloContinuo:
    def test_sportello_continuo(self):
        assert _sembra_sportello_continuo("misura a sportello continuo") is True

    def test_esaurimento_fondi(self):
        assert _sembra_sportello_continuo("fino ad esaurimento fondi disponibili") is True

    def test_testo_normale(self):
        assert _sembra_sportello_continuo("scadenza domande entro il 30 giugno") is False


# ---------------------------------------------------------------------------
# Date in lettere
# ---------------------------------------------------------------------------

class TestDateInLettere:
    def test_data_mese_letterale(self):
        testo = "Le domande devono essere presentate entro il 31 dicembre 2026"
        result = infer_data_scadenza_from_text(testo)
        assert result == "2026-12-31"

    def test_data_mese_letterale_minuscolo(self):
        testo = "scadenza presentazione: 15 marzo 2027"
        result = infer_data_scadenza_from_text(testo)
        assert result == "2027-03-15"

    def test_data_mese_letterale_maiuscolo(self):
        testo = "termine per la presentazione entro il 28 Febbraio 2027"
        result = infer_data_scadenza_from_text(testo)
        assert result == "2027-02-28"


# ---------------------------------------------------------------------------
# Fallback rimosso + guardia sportello continuo (integrazione)
# ---------------------------------------------------------------------------

class TestFallbackRimosso:
    def test_no_fallback_su_data_lontana(self):
        """Senza alcun match di keyword vicino a nessuna data, non deve
        restituire la data più lontana nel testo (nessun fallback cieco)."""
        testo = (
            "Il progetto viene realizzato in due fasi. Prima fase: 31 dicembre 2028. "
            "Seconda fase: 30 giugno 2029."
        )
        result = infer_data_scadenza_from_text(testo)
        assert result is None

    def test_sportello_continuo_restituisce_none(self):
        testo = (
            "La misura è a sportello continuo fino ad esaurimento delle risorse. "
            "Data di riferimento: 01/01/2025."
        )
        result = infer_data_scadenza_from_text(testo)
        assert result is None


class TestKeywordVicine:
    def test_keyword_scadenza_con_data_numerica(self):
        testo = "scadenza presentazione domande: 30/06/2027"
        result = infer_data_scadenza_from_text(testo)
        assert result == "2027-06-30"

    def test_entro_il_con_data_letterale(self):
        testo = "Le domande vanno inviate entro il 15 ottobre 2026"
        result = infer_data_scadenza_from_text(testo)
        assert result == "2026-10-15"
