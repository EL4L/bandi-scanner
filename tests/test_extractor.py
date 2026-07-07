"""Test unitari per modules/extractor.py — nessuna chiamata API reale.

Copre le due correzioni dell'audit del 2026-07-07:
- D-1: il testo del bando viene troncato a MAX_TEXT_CHARS prima della chiamata LLM
- D-2: il modello di fallback ha un ID OpenRouter valido (con prefisso vendor)
"""
from unittest.mock import patch

from modules.extractor import LLM_FALLBACK_MODEL, _tronca_testo
from modules.schema import MAX_TEXT_CHARS


# ---------------------------------------------------------------------------
# D-1: troncamento testo
# ---------------------------------------------------------------------------

def test_tronca_testo_sotto_soglia_non_modifica():
    testo = "x" * 100
    assert _tronca_testo(testo) == testo


def test_tronca_testo_esattamente_alla_soglia_non_modifica():
    testo = "x" * MAX_TEXT_CHARS
    assert _tronca_testo(testo) == testo


def test_tronca_testo_sopra_soglia_viene_tagliato():
    testo = "x" * (MAX_TEXT_CHARS + 50_000)
    risultato = _tronca_testo(testo)
    assert len(risultato) == MAX_TEXT_CHARS


def test_tronca_testo_logga_il_troncamento():
    testo = "x" * (MAX_TEXT_CHARS + 1)
    with patch("modules.extractor.log_error") as mock_log:
        _tronca_testo(testo)
        mock_log.assert_called_once()
        messaggio = mock_log.call_args[0][0]
        assert str(MAX_TEXT_CHARS) in messaggio
        assert str(len(testo)) in messaggio


# ---------------------------------------------------------------------------
# D-2: model id di fallback valido per OpenRouter
# ---------------------------------------------------------------------------

def test_fallback_model_ha_prefisso_vendor():
    """Un ID OpenRouter valido è sempre nella forma 'vendor/modello'.
    Un ID senza prefisso (bug storico) causava 404 silenziosi ad ogni fallback.
    """
    assert "/" in LLM_FALLBACK_MODEL
