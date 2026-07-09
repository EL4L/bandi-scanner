from modules.matcher import valida_coerenza_dimensione

VALID_CLIENTE = {
    "ragione_sociale": "Test Srl",
    "p_iva": "12345678901",
    "codice_ateco": "62.01",
    "regione": "Lombardia",
    "fatturato": 100000,
    "dimensione_impresa": "piccola",
    "descrizione_attivita": "sviluppo software",
}


def test_micro_coerente():
    assert valida_coerenza_dimensione("micro", 1_000_000, 5) == []


def test_micro_troppi_dipendenti_errore():
    errori = valida_coerenza_dimensione("micro", 1_000_000, 20)
    assert any("non può avere più di" in e for e in errori)


def test_micro_fatturato_eccessivo_errore():
    errori = valida_coerenza_dimensione("micro", 5_000_000, 5)
    assert any("fatturato superiore" in e for e in errori)


def test_grande_con_250_dipendenti_ok():
    assert valida_coerenza_dimensione("grande", 100_000_000, 250) == []


def test_grande_con_249_dipendenti_errore():
    errori = valida_coerenza_dimensione("grande", 100_000_000, 249)
    assert any("almeno" in e for e in errori)


def test_grande_senza_dipendenti_non_blocca():
    assert valida_coerenza_dimensione("grande", 100_000_000, None) == []


def test_dimensione_sconosciuta_non_blocca():
    assert valida_coerenza_dimensione("altro", 1_000_000, 5) == []


def test_dati_assenti_non_bloccano():
    assert valida_coerenza_dimensione("micro", None, None) == []


# ---------------------------------------------------------------------------
# Integrazione server-side — POST /api/clienti (main.py _validate_cliente_form)
# ---------------------------------------------------------------------------

def test_post_cliente_dimensione_incoerente_dipendenti(client):
    payload = {**VALID_CLIENTE, "dimensione_impresa": "micro", "numero_dipendenti": 50}
    response = client.post("/api/clienti", json=payload)
    assert response.status_code == 400
    assert any("non può avere più di" in e for e in response.json()["errors"])


def test_post_cliente_dimensione_incoerente_fatturato(client):
    payload = {**VALID_CLIENTE, "dimensione_impresa": "micro", "fatturato": 5_000_000}
    response = client.post("/api/clienti", json=payload)
    assert response.status_code == 400
    assert any("fatturato superiore" in e for e in response.json()["errors"])


def test_post_cliente_dimensione_coerente_ok(client, mock_db):
    mock_db.execute.return_value.fetchone.return_value = {"id": 99}
    payload = {**VALID_CLIENTE, "dimensione_impresa": "piccola", "numero_dipendenti": 20, "fatturato": 3_000_000}
    response = client.post("/api/clienti", json=payload)
    assert response.status_code == 201
