"""Test unitari per le funzioni pure di modules/matcher.py.
Nessun mock DB necessario — tutte le funzioni testate sono pure.
"""
import pytest
from modules.matcher import (
    _score_regione,
    _score_ateco,
    _score_dimensione,
    _score_fatturato,
    calculate_score,
    bando_has_constraints,
    bando_ambiguo,
    get_score_breakdown,
    settore_da_verificare,
    genera_scheda,
    WEIGHT_REGIONE,
    WEIGHT_ATECO,
    WEIGHT_DIMENSIONE,
    WEIGHT_FATTURATO,
)


# ---------------------------------------------------------------------------
# Score Regione
# ---------------------------------------------------------------------------

def test_score_regione_nessun_vincolo():
    assert _score_regione({"regioni_ammesse": []}, {"regione": "Lombardia"}) == WEIGHT_REGIONE


def test_score_regione_tutta_italia():
    assert _score_regione({"regioni_ammesse": ["Tutta Italia"]}, {"regione": "Sicilia"}) == WEIGHT_REGIONE


def test_score_regione_match_diretto():
    assert _score_regione({"regioni_ammesse": ["Lombardia"]}, {"regione": "Lombardia"}) == WEIGHT_REGIONE


def test_score_regione_no_match():
    assert _score_regione({"regioni_ammesse": ["Lombardia"]}, {"regione": "Sicilia"}) == 0


def test_score_regione_cliente_senza_regione():
    assert _score_regione({"regioni_ammesse": ["Lombardia"]}, {}) == 0


# ---------------------------------------------------------------------------
# Score ATECO
# ---------------------------------------------------------------------------

def test_score_ateco_aperto_a_tutti():
    bando = {"ateco_aperto_a_tutti": True, "codici_ateco_ammessi": [], "attivita_ammesse": []}
    assert _score_ateco(bando, {"codice_ateco": "99.99"}) == WEIGHT_ATECO


def test_score_ateco_match_esatto():
    bando = {"ateco_aperto_a_tutti": False, "codici_ateco_ammessi": ["62.01"], "attivita_ammesse": []}
    assert _score_ateco(bando, {"codice_ateco": "62.01"}) == WEIGHT_ATECO


def test_score_ateco_match_prefisso_due_cifre():
    """Prefisso ATECO identico ("62") ma codice diverso → punteggio parziale."""
    bando = {"ateco_aperto_a_tutti": False, "codici_ateco_ammessi": ["62.01"], "attivita_ammesse": []}
    assert _score_ateco(bando, {"codice_ateco": "62.02"}) == WEIGHT_ATECO // 2


def test_score_ateco_no_match():
    bando = {"ateco_aperto_a_tutti": False, "codici_ateco_ammessi": ["62.01"], "attivita_ammesse": []}
    assert _score_ateco(bando, {"codice_ateco": "47.11"}) == 0


def test_score_ateco_ambiguo_nessun_dato():
    """PDF ambiguo senza dati ATECO estratti → punteggio parziale (non penalizzato)."""
    bando = {"ateco_aperto_a_tutti": False, "codici_ateco_ammessi": [], "attivita_ammesse": []}
    assert _score_ateco(bando, {"codice_ateco": "62.01"}) == WEIGHT_ATECO // 2


# ---------------------------------------------------------------------------
# Score Dimensione
# ---------------------------------------------------------------------------

def test_score_dimensione_nessun_vincolo():
    assert _score_dimensione({}, {"dimensione_impresa": "piccola"}) == WEIGHT_DIMENSIONE


def test_score_dimensione_match():
    assert _score_dimensione({"dimensione": "piccola"}, {"dimensione_impresa": "piccola"}) == WEIGHT_DIMENSIONE


def test_score_dimensione_no_match():
    assert _score_dimensione({"dimensione": "grande"}, {"dimensione_impresa": "micro"}) == 0


# ---------------------------------------------------------------------------
# Score Fatturato
# ---------------------------------------------------------------------------

def test_score_fatturato_nessun_vincolo():
    assert _score_fatturato({"fatturato_max": None}, {"fatturato": 9_999_999}) == WEIGHT_FATTURATO


def test_score_fatturato_entro_limite():
    assert _score_fatturato({"fatturato_max": 100_000}, {"fatturato": 50_000}) == WEIGHT_FATTURATO


def test_score_fatturato_oltre_limite():
    assert _score_fatturato({"fatturato_max": 100_000}, {"fatturato": 200_000}) == 0


# ---------------------------------------------------------------------------
# calculate_score e bando_has_constraints
# ---------------------------------------------------------------------------

def test_calculate_score_bando_senza_vincoli_non_forza_piu_zero():
    """ROADMAP #13: un bando senza alcun dato di vincolo estratto non è più
    forzato a score 0 (che comunicava "incompatibile" invece di "dati
    insufficienti"). Lo score riflette i punteggi di default dei singoli
    criteri; l'ambiguità è segnalata separatamente da bando_ambiguo()/
    get_score_breakdown()["status"]."""
    bando = {"bando": {"titolo": "Avviso generico"}}
    cliente = {
        "codice_ateco": "62.01",
        "regione": "Lombardia",
        "dimensione_impresa": "piccola",
        "fatturato": 50_000,
    }
    assert calculate_score(bando, cliente) > 0
    assert bando_ambiguo(bando) is True


def test_get_score_breakdown_status_da_verificare_per_bando_ambiguo():
    bando = {"bando": {"titolo": "Avviso generico"}}
    cliente = {"codice_ateco": "62.01", "regione": "Lombardia"}
    bd = get_score_breakdown(bando, cliente)
    assert bd["status"] == "da_verificare"


def test_get_score_breakdown_status_ok_per_bando_con_vincoli():
    bando = {"bando": {"titolo": "Bando Lombardia", "regioni_ammesse": ["Lombardia"]}}
    cliente = {"codice_ateco": "62.01", "regione": "Lombardia"}
    bd = get_score_breakdown(bando, cliente)
    assert bd["status"] == "ok"


def test_bando_has_constraints_riconosce_attivita_ammesse_testuali():
    """ROADMAP #13: un bando con sole attivita_ammesse testuali (nessun codice
    ATECO, nessuna dichiarazione aperto_a_tutti) ha comunque un vincolo
    settoriale reale e non deve essere trattato come ambiguo."""
    bando = {"bando": {"attivita_ammesse": ["Digitalizzazione processi"]}}
    assert bando_has_constraints(bando) is True
    assert bando_ambiguo(bando) is False


def test_calculate_score_bando_con_vincoli(bando_con_ateco, cliente_matching):
    score = calculate_score(bando_con_ateco, cliente_matching)
    assert score > 0


def test_bando_has_constraints_true_per_codici_ateco():
    bando = {"bando": {"codici_ateco_ammessi": ["62.01"], "ateco_aperto_a_tutti": False}}
    assert bando_has_constraints(bando) is True


def test_bando_has_constraints_false_per_bando_aperto():
    """ateco_aperto_a_tutti=True senza altri vincoli → nessun constraint di matching."""
    bando = {"bando": {"ateco_aperto_a_tutti": True}}
    assert bando_has_constraints(bando) is False


def test_bando_has_constraints_false_tutta_italia():
    bando = {"bando": {"regioni_ammesse": ["Tutta Italia"], "ateco_aperto_a_tutti": False}}
    assert bando_has_constraints(bando) is False


# ---------------------------------------------------------------------------
# genera_scheda
# ---------------------------------------------------------------------------

def test_genera_scheda_bando_vuoto():
    result = genera_scheda({})
    assert result.startswith("*") or "non disponibile" in result.lower()


def test_genera_scheda_contiene_titolo():
    bando = {"bando": {"titolo": "Bando Test Univoco"}}
    assert "Bando Test Univoco" in genera_scheda(bando)


def test_genera_scheda_contiene_ente():
    bando = {"bando": {"ente": "Ministero Test"}}
    assert "Ministero Test" in genera_scheda(bando)


def test_genera_scheda_contiene_disclaimer():
    bando = {"bando": {"titolo": "Bando Test"}}
    result = genera_scheda(bando)
    assert "estratti automaticamente tramite AI" in result
    assert "fonte ufficiale" in result.lower()


def test_genera_scheda_note_esclusioni_dict():
    bando = {"bando": {
        "titolo": "Bando Test",
        "note_esclusioni": {
            "lista_testuale": "Escluse le imprese agricole",
            "sezioni_ateco_escluse": ["A", "K"],
            "attivita_vietate": ["Gioco d'azzardo"],
        },
    }}
    result = genera_scheda(bando)
    assert "## Esclusioni" in result
    assert "Escluse le imprese agricole" in result
    assert "Sezioni ATECO escluse:** A, K" in result
    assert "Attività vietate:** Gioco d'azzardo" in result


def test_genera_scheda_note_esclusioni_stringa():
    bando = {"bando": {"titolo": "Bando Test", "note_esclusioni": "Escluse le start-up"}}
    result = genera_scheda(bando)
    assert "## Esclusioni" in result
    assert "Escluse le start-up" in result


def test_genera_scheda_scadenza_futura_mostra_giorni():
    from datetime import date, timedelta
    data_futura = (date.today() + timedelta(days=10)).isoformat()
    bando = {"bando": {"titolo": "Bando Test", "data_scadenza": data_futura}}
    result = genera_scheda(bando)
    assert "giorni" in result
    assert "urgenza alta" in result


def test_genera_scheda_scadenza_passata_mostra_scaduto():
    from datetime import date, timedelta
    data_passata = (date.today() - timedelta(days=5)).isoformat()
    bando = {"bando": {"titolo": "Bando Test", "data_scadenza": data_passata}}
    result = genera_scheda(bando)
    assert "SCADUTO" in result


# ---------------------------------------------------------------------------
# settore_da_verificare
# ---------------------------------------------------------------------------

def test_settore_da_verificare_bando_con_codici_ateco():
    """Bando con codici_ateco_ammessi → settore non è solo attivita_ammesse → False."""
    bando = {
        "bando": {
            "codici_ateco_ammessi": ["62.01"],
            "ateco_aperto_a_tutti": False,
            "attivita_ammesse": [],
        }
    }
    cliente = {"codice_ateco": "62.01", "descrizione_attivita": "software"}
    assert settore_da_verificare(bando, cliente) is False


def test_settore_da_verificare_cliente_senza_descrizione():
    """Bando con solo attivita_ammesse + cliente senza descrizione_attivita → da verificare."""
    bando = {
        "bando": {
            "codici_ateco_ammessi": [],
            "ateco_aperto_a_tutti": False,
            "attivita_ammesse": ["consulenza software"],
        }
    }
    cliente = {"codice_ateco": "62.01", "descrizione_attivita": ""}
    assert settore_da_verificare(bando, cliente) is True


# ---------------------------------------------------------------------------
# #17 — nuovi campi in scheda: percentuale per fascia, modalità, tipo
# agevolazione, cumulabilità
# ---------------------------------------------------------------------------

def test_genera_scheda_percentuale_per_fascia():
    bando = {"bando": {
        "titolo": "Bando Test",
        "percentuale_fondo_perduto": {"micro": 60, "piccola": 50, "media": 40, "default": None},
    }}
    result = genera_scheda(bando)
    assert "Fondo perduto per fascia" in result
    assert "Micro 60%" in result
    assert "Piccola 50%" in result
    assert "Media 40%" in result


def test_genera_scheda_percentuale_default_singola():
    bando = {"bando": {
        "titolo": "Bando Test",
        "percentuale_fondo_perduto": {"micro": None, "piccola": None, "media": None, "default": 50},
    }}
    result = genera_scheda(bando)
    assert "**Fondo perduto:** 50%" in result
    assert "per fascia" not in result


def test_genera_scheda_percentuale_formato_legacy_numero():
    """Bando salvato prima di #17 (percentuale_fondo_perduto come numero
    semplice, non ancora passato da normalize_response): genera_scheda deve
    comunque renderizzarlo correttamente, non andare in errore."""
    bando = {"bando": {"titolo": "Bando Test", "percentuale_fondo_perduto": 35}}
    result = genera_scheda(bando)
    assert "**Fondo perduto:** 35%" in result


def test_genera_scheda_percentuale_assente_non_mostra_sezione_vuota():
    bando = {"bando": {"titolo": "Bando Test", "contributo_max": None, "percentuale_fondo_perduto": None}}
    result = genera_scheda(bando)
    assert "Contributi" not in result


def test_genera_scheda_modalita_presentazione():
    bando = {"bando": {"titolo": "Bando Test", "modalita_presentazione": "click_day"}}
    result = genera_scheda(bando)
    assert "Modalità di presentazione:** Click day" in result


def test_genera_scheda_modalita_presentazione_none_non_mostrata():
    bando = {"bando": {"titolo": "Bando Test", "modalita_presentazione": None}}
    result = genera_scheda(bando)
    assert "Modalità di presentazione" not in result


def test_genera_scheda_tipo_agevolazione():
    bando = {"bando": {
        "titolo": "Bando Test",
        "tipo_agevolazione": ["fondo_perduto", "finanziamento_agevolato"],
    }}
    result = genera_scheda(bando)
    assert "Tipo di agevolazione:** Fondo perduto, Finanziamento agevolato" in result


def test_genera_scheda_cumulabilita_tra_virgolette():
    bando = {"bando": {
        "titolo": "Bando Test",
        "cumulabilita": "Non cumulabile con altre misure a valere sullo stesso investimento",
    }}
    result = genera_scheda(bando)
    assert "Cumulabilità:** “Non cumulabile con altre misure a valere sullo stesso investimento”" in result


def test_genera_scheda_cumulabilita_assente_non_mostrata():
    bando = {"bando": {"titolo": "Bando Test", "cumulabilita": None}}
    result = genera_scheda(bando)
    assert "Cumulabilità" not in result
