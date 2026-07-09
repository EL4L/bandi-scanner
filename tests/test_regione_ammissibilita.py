from modules.matcher import check_ammissibilita

BANDO_LAZIO = {
    "bando": {
        "titolo": "Test Regione",
        "regioni_ammesse": ["Lazio"],
        "anzianita_impresa": {
            "mesi_minimi_dalla_costituzione": None,
            "mesi_massimi_dalla_costituzione": None,
        },
        "forme_giuridiche_ammesse": [],
        "spesa_minima_ammissibile": None,
        "dimensione_impresa": None,
        "fatturato_max": None,
        "numero_dipendenti_min": None,
        "numero_dipendenti_max": None,
        "note_esclusioni": None,
    }
}

BANDO_NAZIONALE = {
    "bando": {**BANDO_LAZIO["bando"], "regioni_ammesse": []}
}

BANDO_MULTI_REGIONE = {
    "bando": {**BANDO_LAZIO["bando"],
              "regioni_ammesse": ["Lazio", "Campania", "Puglia"]}
}

CLIENTE_LAZIO = {"ragione_sociale": "Test Lazio Srl", "regione": "Lazio"}
CLIENTE_LOMBARDIA = {"ragione_sociale": "Test Lombardia Srl", "regione": "Lombardia"}
CLIENTE_CAMPANIA = {"ragione_sociale": "Test Campania Srl", "regione": "Campania"}
CLIENTE_SENZA_REGIONE = {"ragione_sociale": "Test No Regione Srl"}


def test_cliente_regione_corretta_ammesso():
    result = check_ammissibilita(BANDO_LAZIO, CLIENTE_LAZIO)
    assert result["ammissibile"] is True

def test_cliente_regione_sbagliata_escluso():
    result = check_ammissibilita(BANDO_LAZIO, CLIENTE_LOMBARDIA)
    assert result["ammissibile"] is False
    assert any("Lombardia" in m for m in result["motivi_esclusione"])
    assert any("Lazio" in m for m in result["motivi_esclusione"])

def test_bando_nazionale_ammette_tutti():
    result = check_ammissibilita(BANDO_NAZIONALE, CLIENTE_LOMBARDIA)
    assert result["ammissibile"] is True

def test_cliente_in_multi_regione_ammesso():
    result = check_ammissibilita(BANDO_MULTI_REGIONE, CLIENTE_CAMPANIA)
    assert result["ammissibile"] is True

def test_cliente_fuori_multi_regione_escluso():
    result = check_ammissibilita(BANDO_MULTI_REGIONE, CLIENTE_LOMBARDIA)
    assert result["ammissibile"] is False

def test_cliente_senza_regione_non_esclude():
    result = check_ammissibilita(BANDO_LAZIO, CLIENTE_SENZA_REGIONE)
    assert result["ammissibile"] is True
    assert any("non verificabile" in c for c in result["criteri_verificati"])

def test_case_insensitive():
    cliente = {"ragione_sociale": "Test", "regione": "lazio"}
    result = check_ammissibilita(BANDO_LAZIO, cliente)
    assert result["ammissibile"] is True
