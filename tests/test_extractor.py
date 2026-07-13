"""Test unitari per modules/extractor.py — nessuna chiamata API reale.

Copre le correzioni dell'audit del 2026-07-07:
- D-1: il testo del bando viene troncato a MAX_TEXT_CHARS prima della chiamata LLM
- D-2: il modello di fallback ha un ID OpenRouter valido (con prefisso vendor),
  verificato anche con una chiamata reale il 2026-07-08 (402 credito insufficiente,
  non 404 slug inesistente), e la chiamata imposta un max_tokens esplicito per
  evitare che il default (max output del modello) causi 402 anche a saldo normale
"""
from unittest.mock import MagicMock, patch

import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

from modules.extractor import (
    EmptyPDFException,
    InvalidJSONResponse,
    LLM_FALLBACK_MODEL,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    PDFInvalidoException,
    PDFTroppoGrandeException,
    _call_llm_api,
    _clean_json_response,
    _is_retryable_api_error,
    _merge_partial_results,
    _split_text_chunks,
    _tronca_testo,
    extract_bando_data,
    extract_text_from_pdf,
)
from modules.schema import MAX_TEXT_CHARS, normalize_response


# ---------------------------------------------------------------------------
# D-1: limite testo (250.000 caratteri)
# ---------------------------------------------------------------------------

def test_limite_testo_impostato_a_250000_caratteri():
    assert MAX_TEXT_CHARS == 250_000


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


def test_call_llm_api_content_none_solleva_errore_pulito():
    """Scoperto dal golden set (audit Fable #4, run reale su bando_a_cascata
    Sapienza): su prompt molto lunghi il provider può restituire un messaggio
    con content=None (risposta vuota/rifiutata) invece di un errore HTTP.
    Prima del fix questo si propagava fino a _clean_json_response() e
    andava in crash con AttributeError ("'NoneType' object has no attribute
    'strip'"), bypassando anche il fallback al modello di riserva in
    extract_bando_data (perché _clean_json_response viene chiamato FUORI
    dal blocco try/except che gestisce il fallback)."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=None))]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("modules.extractor._get_client", return_value=mock_client):
        with pytest.raises(InvalidJSONResponse):
            _call_llm_api("prompt di test")


def test_extract_bando_data_content_none_attiva_il_fallback():
    """Stesso caso del test sopra, ma verificato end-to-end su
    extract_bando_data: un content=None dal modello primario (che ora
    _call_llm_api trasforma in InvalidJSONResponse) deve attivare il
    fallback esattamente come un qualunque altro errore, non bypassarlo."""
    payload_ok = '{"bando": {"titolo": "Da fallback", "ateco_aperto_a_tutti": true}}'

    def side_effect(prompt, model=LLM_MODEL):
        if model == LLM_MODEL:
            raise InvalidJSONResponse("content=None dal modello primario")
        return payload_ok

    with patch("modules.extractor._call_llm_api", side_effect=side_effect) as mock_call:
        result = extract_bando_data("testo del bando")
    assert result["bando"]["titolo"] == "Da fallback"
    assert mock_call.call_count == 2


# ---------------------------------------------------------------------------
# _clean_json_response
# ---------------------------------------------------------------------------

def test_clean_json_response_json_puro():
    assert _clean_json_response('{"a": 1}') == '{"a": 1}'


def test_clean_json_response_fence_markdown():
    content = '```json\n{"a": 1}\n```'
    assert _clean_json_response(content) == '{"a": 1}'


def test_clean_json_response_prosa_prima_del_json():
    content = 'Ecco il risultato:\n{"a": 1}'
    assert _clean_json_response(content) == '{"a": 1}'


# ---------------------------------------------------------------------------
# _is_retryable_api_error
# ---------------------------------------------------------------------------

def _api_status_error(status_code: int) -> APIStatusError:
    import httpx

    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(status_code=status_code, request=request)
    return APIStatusError("errore", response=response, body=None)


def test_is_retryable_connection_error():
    assert _is_retryable_api_error(APIConnectionError(request=MagicMock())) is True


def test_is_retryable_timeout_error():
    assert _is_retryable_api_error(APITimeoutError(request=MagicMock())) is True


def test_is_retryable_rate_limit_error():
    error_429 = _api_status_error(429)
    assert _is_retryable_api_error(RateLimitError("limite", response=error_429.response, body=None)) is True


def test_status_429_non_gestito_come_5xx():
    """Un 429 grezzo (non incapsulato in RateLimitError) non deve rientrare nel
    ramo APIStatusError >=500: la libreria openai lo alza già come RateLimitError."""
    assert _is_retryable_api_error(_api_status_error(429)) is False


def test_is_retryable_5xx_status():
    assert _is_retryable_api_error(_api_status_error(500)) is True
    assert _is_retryable_api_error(_api_status_error(529)) is True


def test_non_retryable_4xx_status():
    assert _is_retryable_api_error(_api_status_error(400)) is False
    assert _is_retryable_api_error(_api_status_error(404)) is False


# ---------------------------------------------------------------------------
# extract_text_from_pdf
# ---------------------------------------------------------------------------

def test_extract_text_from_pdf_file_non_trovato():
    with pytest.raises(FileNotFoundError):
        extract_text_from_pdf("non/esiste.pdf")


def test_extract_text_from_pdf_corrotto(tmp_path):
    finto = tmp_path / "corrotto.pdf"
    finto.write_bytes(b"%PDF-1.4\ncontenuto non valido" * 5)
    with pytest.raises(PDFInvalidoException):
        extract_text_from_pdf(str(finto))


def test_extract_text_from_pdf_vuoto(tmp_path):
    import fitz

    path = tmp_path / "vuoto.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()
    with pytest.raises(EmptyPDFException):
        extract_text_from_pdf(str(path))


def test_extract_text_from_pdf_estrae_testo(tmp_path):
    import fitz

    path = tmp_path / "valido.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Testo di prova " * 20)
    doc.save(str(path))
    doc.close()
    testo = extract_text_from_pdf(str(path))
    assert "Testo di prova" in testo
    assert "--- PAGINA 1 ---" in testo


def test_extract_text_from_pdf_troppe_pagine(tmp_path):
    import fitz
    from modules import extractor

    path = tmp_path / "multi.pdf"
    doc = fitz.open()
    for _ in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), "Testo di prova " * 20)
    doc.save(str(path))
    doc.close()

    with patch.object(extractor, "MAX_PDF_PAGES", 1):
        with pytest.raises(PDFTroppoGrandeException):
            extract_text_from_pdf(str(path))


# ---------------------------------------------------------------------------
# extract_bando_data — catena primario/fallback e JSON invalido
# ---------------------------------------------------------------------------

def test_extract_bando_data_successo_modello_primario():
    payload = '{"bando": {"titolo": "Test", "ateco_aperto_a_tutti": true}}'
    with patch("modules.extractor._call_llm_api", return_value=payload) as mock_call:
        result = extract_bando_data("testo del bando")
    assert result["bando"]["titolo"] == "Test"
    mock_call.assert_called_once()


def test_extract_bando_data_fallback_su_errore_primario():
    payload = '{"bando": {"titolo": "Da fallback", "ateco_aperto_a_tutti": true}}'

    def side_effect(prompt, model=LLM_MODEL):
        if model == LLM_MODEL:
            raise RuntimeError("primario giu")
        return payload

    with patch("modules.extractor._call_llm_api", side_effect=side_effect) as mock_call:
        result = extract_bando_data("testo del bando")
    assert result["bando"]["titolo"] == "Da fallback"
    assert mock_call.call_count == 2
    assert mock_call.call_args_list[1].kwargs.get("model") == LLM_FALLBACK_MODEL


def test_extract_bando_data_entrambi_i_modelli_falliscono():
    with patch("modules.extractor._call_llm_api", side_effect=RuntimeError("giu")):
        with pytest.raises(RuntimeError):
            extract_bando_data("testo del bando")


def test_extract_bando_data_json_non_valido():
    with patch("modules.extractor._call_llm_api", return_value="questo non e' json"):
        with pytest.raises(InvalidJSONResponse):
            extract_bando_data("testo del bando")


def test_extract_bando_data_json_primario_non_valido_attiva_fallback():
    payload_ok = '{"bando": {"titolo": "JSON valido dal fallback"}}'

    def side_effect(prompt, model=LLM_MODEL):
        if model == LLM_MODEL:
            return '{"bando": {"titolo": "JSON troncato",}'
        return payload_ok

    with patch("modules.extractor._call_llm_api", side_effect=side_effect) as mock_call:
        result = extract_bando_data("testo del bando")
    assert result["bando"]["titolo"] == "JSON valido dal fallback"
    assert mock_call.call_count == 2
    assert mock_call.call_args_list[1].kwargs["model"] == LLM_FALLBACK_MODEL


# ---------------------------------------------------------------------------
# Documenti lunghi: chunking e consolidamento senza perdita
# ---------------------------------------------------------------------------

def test_split_text_chunks_copre_tutto_il_testo_senza_troncamento():
    from modules import extractor

    tokens = [f"RIGA-{index:04d}" for index in range(120)]
    testo = "\n".join(tokens)
    with patch.object(extractor, "MAX_TEXT_CHARS", 250):
        with patch.object(extractor, "EXTRACTION_CHUNK_CHARS", 180):
            with patch.object(extractor, "EXTRACTION_CHUNK_OVERLAP", 20):
                chunks = _split_text_chunks(testo)
    assert len(chunks) > 1
    assert all(len(chunk) <= 180 for chunk in chunks)
    assert all(any(token in chunk for chunk in chunks) for token in tokens)
    assert chunks[0].startswith(tokens[0])
    assert chunks[-1].endswith(tokens[-1])


def test_extract_bando_data_lungo_usa_blocchi_e_registra_copertura_completa():
    from modules import extractor

    testo = "\n".join(f"RIGA-{index:04d}" for index in range(80))
    partial = normalize_response({"bando": {"titolo": "Parziale"}})
    consolidated = normalize_response({"bando": {"titolo": "Consolidato"}})
    with patch.object(extractor, "MAX_TEXT_CHARS", 200):
        with patch.object(extractor, "EXTRACTION_CHUNK_CHARS", 150):
            with patch.object(extractor, "EXTRACTION_CHUNK_OVERLAP", 15):
                with patch("modules.extractor._extract_single_chunk", return_value=partial) as extract_mock:
                    with patch("modules.extractor._consolidate_partial_results", return_value=consolidated):
                        result = extract_bando_data(testo)
    assert extract_mock.call_count > 1
    coverage = result["bando"]["copertura_estrazione"]
    assert coverage == {
        "caratteri_totali": len(testo),
        "caratteri_analizzati": len(testo),
        "numero_blocchi": extract_mock.call_count,
        "completa": True,
    }


def test_chunking_scattata_prima_del_limite_documento_250mila():
    from modules import extractor

    testo = "X" * 500
    partial = normalize_response({"bando": {"titolo": "Parziale"}})
    consolidated = normalize_response({"bando": {"titolo": "Consolidato"}})
    with patch.object(extractor, "MAX_TEXT_CHARS", 250_000), \
         patch.object(extractor, "EXTRACTION_CHUNK_CHARS", 180), \
         patch.object(extractor, "EXTRACTION_CHUNK_OVERLAP", 10), \
         patch("modules.extractor._extract_single_chunk", return_value=partial) as extract_mock, \
         patch("modules.extractor._consolidate_partial_results", return_value=consolidated):
        result = extract_bando_data(testo)
    assert extract_mock.call_count > 1
    assert result["bando"]["copertura_estrazione"]["caratteri_analizzati"] == 500


def test_merge_deterministico_unisce_agevolazioni_ed_esclusioni():
    first = normalize_response({"bando": {
        "titolo": "Bando Test",
        "agevolazioni": [{"tipo": "finanziamento_agevolato", "importo_max": 25000}],
        "note_esclusioni": {"sezioni_ateco_escluse": ["K"]},
    }})
    second = normalize_response({"bando": {
        "agevolazioni": [{"tipo": "fondo_perduto", "importo_max": 10000}],
        "note_esclusioni": {"sezioni_ateco_escluse": ["L"]},
    }})
    merged = _merge_partial_results([first, second])["bando"]
    assert {item["tipo"] for item in merged["agevolazioni"]} == {
        "finanziamento_agevolato", "fondo_perduto",
    }
    assert merged["note_esclusioni"]["sezioni_ateco_escluse"] == ["K", "L"]


def test_merge_deterministico_completa_lo_stesso_finanziamento_senza_duplicarlo():
    first = normalize_response({"bando": {"agevolazioni": [{
        "tipo": "finanziamento_agevolato", "importo_max": 25000,
    }]}})
    second = normalize_response({"bando": {"agevolazioni": [{
        "tipo": "finanziamento_agevolato", "abbuono_rate": 12,
        "condizioni": ["assenza di garanzie"],
    }]}})
    agevolazioni = _merge_partial_results([first, second])["bando"]["agevolazioni"]
    assert len(agevolazioni) == 1
    assert agevolazioni[0]["importo_max"] == 25000
    assert agevolazioni[0]["abbuono_rate"] == 12
