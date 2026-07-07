"""Test di integrazione degli endpoint FastAPI via TestClient.
Usa le fixture client e mock_db da conftest.py.
"""
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
