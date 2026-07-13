from modules.matcher import calculate_score, check_ammissibilita

BANDO_PMI = {
    "bando": {
        "titolo": "Test Bando PMI",
        "dimensione_impresa": {
            "micro": True,
            "piccola": True,
            "media": False,
            "grande": False,
        },
        "fatturato_max": 5_000_000,
        "anzianita_impresa": {
            "mesi_minimi_dalla_costituzione": None,
            "mesi_massimi_dalla_costituzione": None,
        },
        "forme_giuridiche_ammesse": [],
        "spesa_minima_ammissibile": None,
    }
}

CLIENTE_MICRO = {
    "ragione_sociale": "Test Micro Srl",
    "dimensione_impresa": "micro",
    "fatturato": 500_000,
    "forma_giuridica": "srl",
    "mesi_dalla_costituzione": 36,
}

CLIENTE_GRANDE = {
    "ragione_sociale": "Test Grande Spa",
    "dimensione_impresa": "grande",
    "fatturato": 50_000_000,
    "forma_giuridica": "spa",
    "mesi_dalla_costituzione": 120,
}

CLIENTE_FATTURATO_ALTO = {
    "ragione_sociale": "Test Fatturato Alto Srl",
    "dimensione_impresa": "piccola",
    "fatturato": 10_000_000,
    "forma_giuridica": "srl",
    "mesi_dalla_costituzione": 36,
}


def test_cliente_ammesso():
    result = check_ammissibilita(BANDO_PMI, CLIENTE_MICRO)
    assert result["ammissibile"] is True
    assert not result["motivi_esclusione"]


def test_dimensione_grande_esclusa():
    result = check_ammissibilita(BANDO_PMI, CLIENTE_GRANDE)
    assert result["ammissibile"] is False
    assert any("grande" in m.lower() for m in result["motivi_esclusione"])


def test_fatturato_oltre_limite_escluso():
    result = check_ammissibilita(BANDO_PMI, CLIENTE_FATTURATO_ALTO)
    assert result["ammissibile"] is False
    assert any("fatturato" in m.lower() for m in result["motivi_esclusione"])


def test_spesa_minima_e_warning_non_esclusione():
    bando = {"bando": {**BANDO_PMI["bando"], "spesa_minima_ammissibile": 100_000}}
    cliente = {**CLIENTE_MICRO, "fatturato": 50_000}
    result = check_ammissibilita(bando, cliente)
    # Non deve escludere, solo avvisare
    assert result["ammissibile"] is True
    assert any("⚠️" in c for c in result["criteri_verificati"])


def test_dimensione_assente_nel_cliente_non_esclude():
    cliente_senza_dim = {k: v for k, v in CLIENTE_MICRO.items()
                         if k != "dimensione_impresa"}
    result = check_ammissibilita(BANDO_PMI, cliente_senza_dim)
    assert result["ammissibile"] is True
    assert any("non verificabile" in c for c in result["criteri_verificati"])


def test_bando_senza_vincoli_dimensione():
    bando = {
        "bando": {
            **BANDO_PMI["bando"],
            "dimensione_impresa": None,
            "fatturato_max": None,
        }
    }
    result = check_ammissibilita(bando, CLIENTE_GRANDE)
    assert result["ammissibile"] is True


def test_snc_corrisponde_a_societa_in_nome_collettivo():
    bando = {
        "bando": {
            **BANDO_PMI["bando"],
            "forme_giuridiche_ammesse": ["Società in nome collettivo"],
        }
    }
    cliente = {**CLIENTE_MICRO, "forma_giuridica": "snc"}
    result = check_ammissibilita(bando, cliente)
    assert result["ammissibile"] is True
    assert not result["motivi_esclusione"]


def test_sezione_ateco_esclusa_disammette():
    # Sezione K (attività finanziarie e assicurative) = divisioni 64-66
    bando = {
        "bando": {
            **BANDO_PMI["bando"],
            "note_esclusioni": {"sezioni_ateco_escluse": ["K"]},
        }
    }
    cliente = {**CLIENTE_MICRO, "codice_ateco": "64.19"}
    result = check_ammissibilita(bando, cliente)
    assert result["ammissibile"] is False
    assert any("escluso" in m.lower() for m in result["motivi_esclusione"])


def test_sezione_ateco_esclusa_con_testo_libero_e_score_zero():
    bando = {
        "bando": {
            **BANDO_PMI["bando"],
            "note_esclusioni": {"sezioni_ateco_escluse": ["Sezione K - Attività finanziarie e assicurative"]},
        }
    }
    cliente = {**CLIENTE_MICRO, "codice_ateco": "66.30"}
    result = check_ammissibilita(bando, cliente)
    assert result["ammissibile"] is False
    assert calculate_score(bando, cliente) < 100


def test_sezione_ateco_non_esclusa_non_disammette():
    bando = {
        "bando": {
            **BANDO_PMI["bando"],
            "note_esclusioni": {"sezioni_ateco_escluse": ["K"]},
        }
    }
    cliente = {**CLIENTE_MICRO, "codice_ateco": "62.01"}
    result = check_ammissibilita(bando, cliente)
    assert result["ammissibile"] is True
