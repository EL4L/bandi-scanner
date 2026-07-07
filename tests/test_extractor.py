"""Test unitari per modules/extractor.py — nessuna chiamata API reale.

Copre le correzioni dell'audit del 2026-07-07:
- D-1: il testo del bando viene troncato a MAX_TEXT_CHARS prima della chiamata LLM
- D-2: il modello di fallback ha un ID OpenRouter valido (con prefisso vendor),
  verificato anche con una chiamata reale il 2026-07-08 (402 credito insufficiente,
  non 404 slug inesistente), e la chiamata imposta un max_tokens esplicito per
  evitare che il default (max output del modello) causi 402 anche a saldo normale
"""
from unittest.mock import MagicMock, patch

from modules.extractor import LLM_FALLBACK_MODEL, LLM_MAX_TOKENS, _call_llm_api, _tronca_testo
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


# ---------------------------------------------------------------------------
# Limite max_tokens espliciti sulla chiamata LLM
# ---------------------------------------------------------------------------

def test_call_llm_api_imposta_max_tokens():
    """Senza max_tokens esplicito alcuni modelli richiedono il massimo output
    possibile, causando 402 (credito insufficiente) anche a saldo normale
    (riprodotto con una chiamata reale il 2026-07-08)."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="{}"))]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("modules.extractor._get_client", return_value=mock_client):
        _call_llm_api("prompt di test")

    _, kwargs = mock_client.chat.completions.create.call_args
    assert kwargs.get("max_tokens") == LLM_MAX_TOKENS
