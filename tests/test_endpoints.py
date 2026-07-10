"""Test di integrazione degli endpoint FastAPI via TestClient.
Usa le fixture client e mock_db da conftest.py.
"""
from collections import defaultdict, deque
from unittest.mock import patch

import pytest


VALID_CLIENTE = {
    "ragione_sociale": "Test Srl",
    "p_iva": "12345678901",
    "codice_ateco": "62.01",
    "regione": "Lombardia",
    "fatturato": 100000,
    "dimensione_impresa": "piccola",
    "descrizione_attivita": "sviluppo software",
}


# ---------------------------------------------------------------------------
# GET /api/clienti
# ---------------------------------------------------------------------------

def test_get_clienti_200_struttura(client):
    response = client.get("/api/clienti")
    assert response.status_code == 200
    data = response.json()
    assert "clienti" in data
    assert "regioni" in data
    assert "dimensioni" in data


def test_get_clienti_lista_vuota(client):
    response = client.get("/api/clienti")
    assert response.status_code == 200
    assert response.json()["clienti"] == []


# ---------------------------------------------------------------------------
# POST /api/clienti — validazione
# ---------------------------------------------------------------------------

def test_post_cliente_p_iva_non_valida(client):
    payload = {**VALID_CLIENTE, "p_iva": "123"}
    response = client.post("/api/clienti", json=payload)
    assert response.status_code == 400
    assert "errors" in response.json()


def test_post_cliente_ragione_sociale_vuota(client):
    payload = {**VALID_CLIENTE, "ragione_sociale": ""}
    response = client.post("/api/clienti", json=payload)
    assert response.status_code == 400
    assert "errors" in response.json()


def test_post_cliente_codice_ateco_non_valido(client):
    payload = {**VALID_CLIENTE, "codice_ateco": "AAAA"}
    response = client.post("/api/clienti", json=payload)
    assert response.status_code == 400
    assert "errors" in response.json()


# ---------------------------------------------------------------------------
# POST /api/clienti — successo
# ---------------------------------------------------------------------------

def test_post_cliente_ok(client, mock_db):
    mock_db.execute.return_value.fetchone.return_value = {"id": 99}
    response = client.post("/api/clienti", json=VALID_CLIENTE)
    assert response.status_code == 201
    assert response.json()["id"] == 99


# ---------------------------------------------------------------------------
# PUT /api/clienti/{id}
# ---------------------------------------------------------------------------

def test_put_cliente_ok(client, mock_db):
    response = client.put("/api/clienti/1", json=VALID_CLIENTE)
    assert response.status_code == 200
    assert response.json()["id"] == 1


# ---------------------------------------------------------------------------
# DELETE /api/clienti/{id}
# ---------------------------------------------------------------------------

def test_delete_cliente_ok(client):
    response = client.delete("/api/clienti/1")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# GET /api/bandi
# ---------------------------------------------------------------------------

def test_get_bandi_200(client):
    response = client.get("/api/bandi")
    assert response.status_code == 200
    assert "bandi" in response.json()


# ---------------------------------------------------------------------------
# GET /api/clienti/{id}/bandi
# ---------------------------------------------------------------------------

def test_get_cliente_bandi_include_ammissibilita_e_fonte_url(client, mock_db, cliente_matching):
    import json as jsonlib

    bando_payload = {
        "bando": {
            "titolo": "Bando Grandi Imprese",
            "ente": "MIMIT",
            "dimensione_impresa": {"micro": False, "piccola": False, "media": False, "grande": True},
            "link_fonte_ufficiale": "https://www.mimit.gov.it/bando",
        }
    }
    row = {
        "score": 80,
        "bando_id": 1,
        "titolo": "Bando Grandi Imprese",
        "ente": "MIMIT",
        "data_scadenza": None,
        "json_completo": jsonlib.dumps(bando_payload),
    }
    mock_db.execute.return_value.fetchall.return_value = [row]

    with patch("main.get_cliente", return_value=cliente_matching):
        response = client.get(f"/api/clienti/{cliente_matching['id']}/bandi")

    assert response.status_code == 200
    data = response.json()
    assert len(data["bandi"]) == 1
    entry = data["bandi"][0]
    assert "ammissibilita" in entry
    assert entry["ammissibilita"]["ammissibile"] is False
    assert entry["fonte_url"] == "https://www.mimit.gov.it/bando"


# ---------------------------------------------------------------------------
# GET /api/dashboard
# ---------------------------------------------------------------------------

def test_get_dashboard_200(client, mock_db):
    # count_bandi usa fetchone() per "SELECT COUNT(*) AS n"
    mock_db.execute.return_value.fetchone.return_value = {"n": 0}
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "n_bandi" in data
    assert "cards" in data


# ---------------------------------------------------------------------------
# POST /api/bandi/recalc
# ---------------------------------------------------------------------------

def test_post_recalc_ok(client):
    response = client.post("/api/bandi/recalc")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /api/bandi/deduplica
# ---------------------------------------------------------------------------

def test_post_deduplica_ok(client):
    response = client.post("/api/bandi/deduplica", json={"strict": True})
    assert response.status_code == 200
    data = response.json()
    assert "eliminati" in data
    assert data["status"] == "ok"


def test_post_deduplica_errore_non_espone_dettaglio(client):
    """D-6: un'eccezione interna non deve mai raggiungere il client come testo grezzo."""
    with patch("main.deduplica_bandi", side_effect=RuntimeError("dettaglio interno sensibile")):
        response = client.post("/api/bandi/deduplica", json={"strict": True})
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "dettaglio interno sensibile" not in detail


# ---------------------------------------------------------------------------
# POST /api/estrazione — validazione upload (D-4) e sanificazione errori (D-6)
# ---------------------------------------------------------------------------

def test_post_estrazione_rifiuta_file_senza_intestazione_pdf(client):
    """D-4: il controllo dei magic bytes rifiuta un file che non è un vero PDF,
    anche se estensione e content-type dichiarano application/pdf."""
    response = client.post(
        "/api/estrazione",
        files={"file": ("finto.pdf", b"questo non e un pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert "errors" in response.json()


def test_post_estrazione_rifiuta_file_troppo_grande(client):
    contenuto = b"%PDF-1.4\n" + b"0" * (10_000_001 - 9)
    response = client.post(
        "/api/estrazione",
        files={"file": ("grande.pdf", contenuto, "application/pdf")},
    )
    assert response.status_code == 400
    assert "errors" in response.json()


def test_post_estrazione_pdf_corrotto_messaggio_pulito(client):
    """D-4/D-6: un PDF con intestazione valida ma corrotto viene rifiutato con
    un messaggio pulito in italiano, senza dettagli tecnici del parser PyMuPDF."""
    corrotto = b"%PDF-1.4\n" + b"contenuto non valido" * 5
    response = client.post(
        "/api/estrazione",
        files={"file": ("corrotto.pdf", corrotto, "application/pdf")},
    )
    assert response.status_code == 400
    errors = response.json()["errors"]
    assert any("corrotto" in e.lower() or "leggibile" in e.lower() for e in errors)
    # Nessun dettaglio tecnico (traceback, percorso file, nome eccezione Python) esposto
    testo_completo = " ".join(errors)
    assert "Traceback" not in testo_completo
    assert "Exception" not in testo_completo


# ---------------------------------------------------------------------------
# Autenticazione API key statica (D-3) — TestClient SENZA header di default,
# a differenza della fixture `client` che lo invia sempre.
# ---------------------------------------------------------------------------

def _client_senza_header(mock_db, api_key="test-api-key"):
    import main
    from fastapi.testclient import TestClient

    ctx = patch("main.ensure_database")
    ctx.start()
    key_ctx = patch.object(main, "APP_API_KEY", api_key)
    key_ctx.start()
    return TestClient(main.app), (ctx, key_ctx)


def test_get_dashboard_senza_api_key_e_401(mock_db):
    tc, ctxs = _client_senza_header(mock_db)
    try:
        response = tc.get("/api/dashboard")
        assert response.status_code == 401
    finally:
        for c in ctxs:
            c.stop()


def test_get_dashboard_con_api_key_sbagliata_e_401(mock_db):
    tc, ctxs = _client_senza_header(mock_db)
    try:
        response = tc.get("/api/dashboard", headers={"X-API-Key": "chiave-sbagliata"})
        assert response.status_code == 401
    finally:
        for c in ctxs:
            c.stop()


def test_get_dashboard_con_api_key_corretta_su_query_string(mock_db):
    """Necessario per i link <a href download> che il browser naviga senza header custom."""
    tc, ctxs = _client_senza_header(mock_db)
    try:
        response = tc.get("/api/dashboard?api_key=test-api-key")
        assert response.status_code == 200
    finally:
        for c in ctxs:
            c.stop()


def test_get_health_resta_pubblico_senza_api_key(mock_db):
    tc, ctxs = _client_senza_header(mock_db)
    try:
        response = tc.get("/api/health")
        assert response.status_code == 200
    finally:
        for c in ctxs:
            c.stop()


def test_delete_cliente_senza_api_key_e_401(mock_db):
    """Le rotte mutanti sono protette quanto quelle di lettura."""
    tc, ctxs = _client_senza_header(mock_db)
    try:
        response = tc.delete("/api/clienti/1")
        assert response.status_code == 401
    finally:
        for c in ctxs:
            c.stop()


def test_post_estrazione_senza_apikey_configurata_ritorna_500(mock_db):
    """Se APP_API_KEY non è configurata sul server, l'endpoint fallisce in modo
    esplicito (fail-closed) invece di lasciar passare tutti."""
    tc, ctxs = _client_senza_header(mock_db, api_key="")
    try:
        response = tc.get("/api/dashboard", headers={"X-API-Key": "qualsiasi"})
        assert response.status_code == 500
    finally:
        for c in ctxs:
            c.stop()


# ---------------------------------------------------------------------------
# Rate limit /api/estrazione (D-3)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# POST /api/estrazione — rami di successo/estrazione (J-1), con extract_text_from_pdf
# ed extract_bando_data mockati: nessuna chiamata reale a PyMuPDF/OpenRouter.
# ---------------------------------------------------------------------------

VALID_PDF_BYTES = b"%PDF-1.4\n" + b"contenuto finto" * 5

BANDO_ESTRATTO = {
    "bando": {
        "titolo": "Bando Test",
        "ente": "Regione Test",
        "data_pubblicazione": None,
        "data_scadenza": "2026-12-31",
        "codici_ateco_ammessi": [],
        "attivita_ammesse": [],
        "ateco_aperto_a_tutti": True,
        "regioni_ammesse": [],
        "dimensione_impresa": {"micro": True, "piccola": True, "media": True, "grande": True},
        "fatturato_max": None,
        "contributo_max": 50000.0,
        "percentuale_fondo_perduto": None,
        "spese_ammissibili": [],
        "link_fonte_ufficiale": None,
        "note_esclusioni": None,
        "spesa_minima_ammissibile": None,
        "anzianita_impresa": {"mesi_minimi_dalla_costituzione": None, "mesi_massimi_dalla_costituzione": None},
        "forme_giuridiche_ammesse": [],
        "urgenza": "bassa",
    }
}


def test_post_estrazione_pdf_vuoto(client):
    """extract_text_from_pdf solleva EmptyPDFException -> risposta con empty_pdf=True."""
    from modules.extractor import EmptyPDFException

    with patch("main.extract_text_from_pdf", side_effect=EmptyPDFException("vuoto")):
        response = client.post(
            "/api/estrazione",
            files={"file": ("vuoto.pdf", VALID_PDF_BYTES, "application/pdf")},
        )
    assert response.status_code == 200
    assert response.json()["empty_pdf"] is True


def test_post_estrazione_successo(client, mock_db):
    """Flusso completo: estrazione ok, nessun duplicato, salvataggio riuscito."""
    with patch("main.extract_text_from_pdf", return_value="testo del bando " * 10), \
         patch("main.extract_bando_data", return_value=BANDO_ESTRATTO), \
         patch("main.find_duplicate_bando", return_value=None), \
         patch("main.save_bando_from_json", return_value=123), \
         patch("main.run_matching_for_bando"):
        response = client.post(
            "/api/estrazione",
            files={"file": ("bando.pdf", VALID_PDF_BYTES, "application/pdf")},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["bando_id"] == 123
    assert "scheda" in data
    assert data["errors"] == []


def test_post_estrazione_duplicato(client, mock_db):
    with patch("main.extract_text_from_pdf", return_value="testo del bando " * 10), \
         patch("main.extract_bando_data", return_value=BANDO_ESTRATTO), \
         patch("main.find_duplicate_bando", return_value=42):
        response = client.post(
            "/api/estrazione",
            files={"file": ("bando.pdf", VALID_PDF_BYTES, "application/pdf")},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "duplicato"
    assert data["bando_id"] == 42


def test_post_estrazione_json_invalido_dal_llm(client):
    """extract_bando_data solleva InvalidJSONResponse -> extraction_error sanificato, no stacktrace."""
    from modules.extractor import InvalidJSONResponse

    with patch("main.extract_text_from_pdf", return_value="testo del bando " * 10), \
         patch("main.extract_bando_data", side_effect=InvalidJSONResponse("non e' JSON")):
        response = client.post(
            "/api/estrazione",
            files={"file": ("bando.pdf", VALID_PDF_BYTES, "application/pdf")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "extraction_error" in data
    assert "non e' JSON" not in data["extraction_error"]


def test_post_estrazione_errore_salvataggio(client, mock_db):
    """save_bando_from_json fallisce -> save_error sanificato, non extraction_error."""
    with patch("main.extract_text_from_pdf", return_value="testo del bando " * 10), \
         patch("main.extract_bando_data", return_value=BANDO_ESTRATTO), \
         patch("main.find_duplicate_bando", return_value=None), \
         patch("main.save_bando_from_json", side_effect=RuntimeError("dettaglio interno db")):
        response = client.post(
            "/api/estrazione",
            files={"file": ("bando.pdf", VALID_PDF_BYTES, "application/pdf")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "save_error" in data
    assert "dettaglio interno db" not in data["save_error"]


def test_estrazione_rate_limit_oltre_soglia_ritorna_429(client):
    import main

    with patch.object(main, "ESTRAZIONE_RATE_LIMIT_MAX", 2), \
         patch.object(main, "_rate_limit_hits", defaultdict(deque)):
        file_non_pdf = {"file": ("finto.pdf", b"non un pdf", "application/pdf")}
        r1 = client.post("/api/estrazione", files=file_non_pdf)
        r2 = client.post("/api/estrazione", files=file_non_pdf)
        r3 = client.post("/api/estrazione", files=file_non_pdf)
        assert r1.status_code == 400  # rifiutato per magic bytes, ma conta ai fini del rate limit
        assert r2.status_code == 400
        assert r3.status_code == 429


def test_post_estrazione_url_rifiuta_url_non_valido(client):
    from modules.url_extractor import InvalidUrlException

    with patch("main.fetch_url_safely", side_effect=InvalidUrlException("Sono supportati solo link https://.")):
        response = client.post("/api/estrazione-url", json={"url": "http://esempio.it/bando"})
    assert response.status_code == 400
    assert "https" in response.json()["errors"][0]


def test_post_estrazione_url_errore_di_rete(client):
    import requests

    with patch("main.fetch_url_safely", side_effect=requests.ConnectionError("timeout")):
        response = client.post("/api/estrazione-url", json={"url": "https://esempio.it/bando"})
    assert response.status_code == 400
    assert "scaricare" in response.json()["errors"][0]


def test_post_estrazione_url_pagina_html_vuota(client):
    html = b"<html><body><p>pagina troppo corta</p></body></html>"
    with patch("main.fetch_url_safely", return_value=(html, "text/html", "utf-8", "https://esempio.it/bando")), \
         patch("main.extract_text_from_html", return_value=""):
        response = client.post("/api/estrazione-url", json={"url": "https://esempio.it/bando"})
    assert response.status_code == 200
    assert response.json()["empty_pdf"] is True


def test_post_estrazione_url_successo_html(client, mock_db):
    html = b"<html><body><article>contenuto bando</article></body></html>"
    with patch("main.fetch_url_safely", return_value=(html, "text/html", "utf-8", "https://esempio.it/bando")), \
         patch("main.extract_text_from_html", return_value="testo del bando " * 10), \
         patch("main.extract_bando_data", return_value=BANDO_ESTRATTO), \
         patch("main.find_duplicate_bando", return_value=None), \
         patch("main.save_bando_from_json", return_value=321), \
         patch("main.run_matching_for_bando"):
        response = client.post("/api/estrazione-url", json={"url": "https://esempio.it/bando"})
    assert response.status_code == 200
    data = response.json()
    assert data["bando_id"] == 321
    assert data["filename"] == "esempio.it"
    assert "scheda" in data


def test_post_estrazione_url_successo_pdf_diretto(client, mock_db):
    """L'URL punta direttamente a un PDF (Content-Type application/pdf):
    deve passare per extract_text_from_pdf, non extract_text_from_html."""
    with patch("main.fetch_url_safely", return_value=(VALID_PDF_BYTES, "application/pdf", None, "https://esempio.it/bando.pdf")), \
         patch("main.extract_text_from_pdf", return_value="testo del bando " * 10), \
         patch("main.extract_text_from_html") as mock_html, \
         patch("main.extract_bando_data", return_value=BANDO_ESTRATTO), \
         patch("main.find_duplicate_bando", return_value=None), \
         patch("main.save_bando_from_json", return_value=99), \
         patch("main.run_matching_for_bando"):
        response = client.post("/api/estrazione-url", json={"url": "https://esempio.it/bando.pdf"})
    assert response.status_code == 200
    data = response.json()
    assert data["bando_id"] == 99
    mock_html.assert_not_called()


def test_post_estrazione_url_duplicato(client, mock_db):
    html = b"<html><body><article>contenuto bando</article></body></html>"
    with patch("main.fetch_url_safely", return_value=(html, "text/html", "utf-8", "https://esempio.it/bando")), \
         patch("main.extract_text_from_html", return_value="testo del bando " * 10), \
         patch("main.extract_bando_data", return_value=BANDO_ESTRATTO), \
         patch("main.find_duplicate_bando", return_value=42):
        response = client.post("/api/estrazione-url", json={"url": "https://esempio.it/bando"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "duplicato"
    assert data["bando_id"] == 42
