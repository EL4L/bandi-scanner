from modules.matcher import check_ammissibilita

BANDO_MAX_50 = {
    "bando": {
        "titolo": "Test dipendenti",
        "numero_dipendenti_min": None,
        "numero_dipendenti_max": 50,
        "anzianita_impresa": {
            "mesi_minimi_dalla_costituzione": None,
            "mesi_massimi_dalla_costituzione": None,
        },
        "forme_giuridiche_ammesse": [],
        "spesa_minima_ammissibile": None,
        "dimensione_impresa": None,
        "fatturato_max": None,
        "note_esclusioni": None,
    }
}

BANDO_MIN_5 = {
    "bando": {**BANDO_MAX_50["bando"],
              "numero_dipendenti_min": 5,
              "numero_dipendenti_max": None}
}

def test_dipendenti_sotto_massimo_ammesso():
    cliente = {"numero_dipendenti": 30}
    result = check_ammissibilita(BANDO_MAX_50, cliente)
    assert result["ammissibile"] is True

def test_dipendenti_sopra_massimo_escluso():
    cliente = {"numero_dipendenti": 100}
    result = check_ammissibilita(BANDO_MAX_50, cliente)
    assert result["ammissibile"] is False
    assert any("troppo alto" in m for m in result["motivi_esclusione"])

def test_dipendenti_sotto_minimo_escluso():
    cliente = {"numero_dipendenti": 2}
    result = check_ammissibilita(BANDO_MIN_5, cliente)
    assert result["ammissibile"] is False
    assert any("insufficiente" in m for m in result["motivi_esclusione"])

def test_dipendenti_sopra_minimo_ammesso():
    cliente = {"numero_dipendenti": 10}
    result = check_ammissibilita(BANDO_MIN_5, cliente)
    assert result["ammissibile"] is True

def test_dipendenti_assenti_non_esclude():
    cliente = {"numero_dipendenti": None}
    result = check_ammissibilita(BANDO_MAX_50, cliente)
    assert result["ammissibile"] is True
    assert any("non verificabile" in c for c in result["criteri_verificati"])

def test_bando_senza_vincolo_dipendenti():
    bando = {"bando": {**BANDO_MAX_50["bando"],
                       "numero_dipendenti_max": None}}
    cliente = {"numero_dipendenti": 999}
    result = check_ammissibilita(bando, cliente)
    assert result["ammissibile"] is True
