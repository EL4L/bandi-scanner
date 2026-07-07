"""Test di integrazione degli endpoint FastAPI via TestClient.
Usa le fixture client e mock_db da conftest.py.
"""
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
