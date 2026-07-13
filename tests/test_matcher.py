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


def test_genera_scheda_mostra_solo_origine_verificata_dalla_pipeline():
    legacy = {"bando": {
        "titolo": "Bando Test",
        "link_fonte_ufficiale": "https://example.org/home-generica",
    }}
    assert "home-generica" not in genera_scheda(legacy)

    da_url = {"bando": {
        "titolo": "Bando Test",
        "url_documento_origine": "https://example.org/bando.pdf",
    }}
    result = genera_scheda(da_url)
    assert "## Documento di origine" in result
    assert "https://example.org/bando.pdf" in result


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
    assert "Escluse le imprese agricole" not in result
    assert "Sez. A – Agricoltura, silvicoltura e pesca" in result
    assert "Sez. K – Attività finanziarie e assicurative" in result
    assert "### Attività vietate\n\n- Gioco d'azzardo" in result


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
    assert "**Presentazione:** Click day" in result


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
    assert "Cumulabilità:** Non cumulabile sul medesimo investimento" in result


def test_genera_scheda_agevolazione_finanziamento_non_mostra_fonti_interne():
    bando = {"bando": {
        "titolo": "Nuovo Fondo Futuro",
        "agevolazioni": [{
            "tipo": "finanziamento_agevolato",
            "importo_min": 5000,
            "importo_max": 25000,
            "tasso_interesse_percentuale": 0,
            "durata_mesi": 72,
            "rimborso_richiesto": True,
            "fonti": [{"pagina": 6, "testo": "importo massimo: 25.000 euro"}],
        }],
    }}
    result = genera_scheda(bando)
    assert "**Finanziamento agevolato**" in result
    assert "Importo massimo del finanziamento: € 25.000" in result
    assert "Durata: 72 mesi" in result
    assert "Rimborso richiesto: sì" in result
    assert "Fonte:" not in result
    assert "pag. 6" not in result


def test_genera_scheda_mostra_descrizione_sezioni_e_settori_esclusi():
    bando = {"bando": {
        "titolo": "Bando Test",
        "note_esclusioni": {
            "lista_testuale": None,
            "sezioni_ateco_escluse": ["K"],
            "attivita_vietate": ["attività immobiliari", "gioco d'azzardo"],
        },
    }}
    result = genera_scheda(bando)
    assert "Sez. K – Attività finanziarie e assicurative" in result
    assert "### Settori esclusi\n\n- Attività immobiliari" in result
    assert "### Attività vietate\n\n- Gioco d'azzardo" in result


def test_genera_scheda_riassume_settori_senza_inventare_lettere_ateco():
    bando = {"bando": {
        "titolo": "Bando Test",
        "note_esclusioni": {
            "lista_testuale": None,
            "sezioni_ateco_escluse": [],
            "attivita_vietate": ["attività finanziarie", "attività di sviluppo immobiliare"],
        },
    }}
    result = genera_scheda(bando)
    assert "### Settori esclusi\n\n- Attività finanziarie\n- Attività immobiliari" in result
    assert "Sez. K" not in result
    assert "Sez. L" not in result


def test_genera_scheda_sintetizza_condizioni_verbose_nelle_esclusioni_di_settore():
    bando = {"bando": {
        "titolo": "Bando Test",
        "note_esclusioni": {
            "lista_testuale": None,
            "sezioni_ateco_escluse": [],
            "attivita_vietate": [
                "attività finanziarie quali acquisto o negoziazione di strumenti finanziari",
                "sviluppo immobiliare con unico scopo di rinnovo, rilocazione o rivendita",
            ],
        },
    }}
    result = genera_scheda(bando)
    assert "Attività finanziarie" in result
    assert "acquisto o negoziazione di strumenti finanziari" not in result
    assert "Attività immobiliari" in result
    assert "Sviluppo immobiliare speculativo" in result
    assert "unico scopo di rinnovo" not in result


def test_genera_scheda_sintetizza_spese_ammissibili_in_categorie_atomiche():
    bando = {"bando": {
        "titolo": "Bando Test",
        "spese_ammissibili": [
            "Acquisto di arredi, impianti, macchinari e attrezzature",
            "Acquisto di mezzi targati solo se beni strumentali",
            "Acquisto di software",
            "Acquisto brevetti, realizzazione sistema di qualità, certificazione e realizzazione sito web",
            "Opere per adeguamento funzionale e ristrutturazione della sede operativa",
            "IVA e imposta di bollo",
            "Servizi di accompagnamento alla realizzazione",
        ],
    }}
    result = genera_scheda(bando)
    for label in (
        "Arredi", "Impianti", "Macchinari", "Attrezzature", "Mezzi targati",
        "Software", "Brevetti", "Certificazioni di qualità", "Realizzazione sito web",
        "Adeguamento funzionale sede operativa", "Ristrutturazione sede operativa",
        "IVA", "Imposta di bollo", "Servizi di accompagnamento alla realizzazione",
    ):
        assert f"- {label}" in result
    assert "Acquisto di arredi, impianti" not in result


def test_genera_scheda_sintetizza_attivita_vietate_in_categorie():
    bando = {"bando": {
        "titolo": "Bando Test",
        "note_esclusioni": {
            "lista_testuale": None,
            "sezioni_ateco_escluse": [],
            "attivita_vietate": [
                "attività finanziarie",
                "attività immobiliari",
                "produzione e commercio di tabacco, salvo i bar tabacchi",
                "case da gioco e gioco d'azzardo su Internet",
                "pornografia e commercio sessuale e relative infrastrutture",
                "produzione e commercio di armi e munizioni",
                "energia nucleare",
                "produzione primaria di prodotti agricoli, pesca e acquacoltura",
                "sviluppo immobiliare con unico scopo di rinnovo o rivendita",
            ],
        },
    }}
    result = genera_scheda(bando)
    assert "### Settori esclusi\n\n- Attività finanziarie\n- Attività immobiliari" in result
    for label in (
        "Tabacco (salvo bar tabacchi)", "Gioco d'azzardo",
        "Pornografia e commercio sessuale", "Armi e munizioni", "Energia nucleare",
        "Pesca e acquacoltura", "Attività agricole primarie",
        "Sviluppo immobiliare speculativo",
    ):
        assert f"- {label}" in result
    assert "relative infrastrutture" not in result


def test_genera_scheda_esclusioni_in_blocchi_schematici_senza_paragrafo_duplicato():
    bando = {"bando": {
        "titolo": "Bando Test",
        "note_esclusioni": {
            "lista_testuale": "Lungo riepilogo duplicato delle esclusioni",
            "sezioni_ateco_escluse": [],
            "attivita_vietate": ["tabacco"],
            "soggetti_esclusi": ["imprese in liquidazione"],
            "spese_non_ammissibili": ["beni usati"],
            "altre_esclusioni": ["progetti già conclusi"],
        },
    }}
    result = genera_scheda(bando)
    assert "Lungo riepilogo duplicato" not in result
    assert "### Attività vietate\n\n- Tabacco" in result
    assert "### Soggetti esclusi\n\n- imprese in liquidazione" in result
    assert "### Spese non ammissibili\n\n- beni usati" in result
    assert "### Altre esclusioni\n\n- progetti già conclusi" in result


def test_genera_scheda_mostra_tutte_le_spese_e_le_esclusioni_deduplicate():
    bando = {"bando": {
        "titolo": "Bando sintetico",
        "spese_ammissibili": [f"Categoria di spesa {index}" for index in range(10)],
        "note_esclusioni": {
            "lista_testuale": None,
            "sezioni_ateco_escluse": [],
            "attivita_vietate": [],
            "soggetti_esclusi": [f"Condizione soggettiva {index}" for index in range(9)],
            "spese_non_ammissibili": [],
            "altre_esclusioni": [],
        },
    }}
    result = genera_scheda(bando)
    assert "Categoria di spesa 9" in result
    assert "Condizione soggettiva 8" in result
    assert "ulteriori voci" not in result


def test_genera_scheda_compatta_forme_giuridiche_equivalenti():
    bando = {"bando": {
        "titolo": "Bando sintetico",
        "forme_giuridiche_ammesse": [
            "Liberi Professionisti", "Libero professionista",
            "Ditte individuali", "Ditta individuale",
            "Società a responsabilità limitata (S.r.l)",
            "Società a responsabilità limitata",
            "Società a responsabilità limitata semplificata (S.r.l.s.)",
        ],
    }}
    result = genera_scheda(bando)
    assert (
        "**Forme giuridiche:** Liberi professionisti, Ditte individuali, S.r.l., S.r.l.s."
        in result
    )


def test_genera_scheda_se_ha_spese_non_ripete_attivita_ammesse():
    bando = {"bando": {
        "titolo": "Bando sintetico",
        "attivita_ammesse": ["Acquisto macchinari", "Digitalizzazione"],
        "spese_ammissibili": ["Macchinari", "Software"],
    }}
    result = genera_scheda(bando)
    assert "## Spese ammissibili" in result
    assert "### Interventi ammessi" not in result
    assert "Digitalizzazione" not in result


def test_genera_scheda_distingue_promotore_e_gestore():
    bando = {"bando": {
        "titolo": "Bando Test",
        "ente": "Regione Lazio",
        "enti_coinvolti": [
            {"nome": "Banca Nazionale del Lavoro", "ruolo": "gestore"},
            {"nome": "Mediocredito Centrale", "ruolo": "gestore"},
        ],
    }}
    result = genera_scheda(bando)
    assert "**Ente promotore:** Regione Lazio" in result
    assert "**Gestore:** Banca Nazionale del Lavoro" in result
    assert "**Gestore:** Mediocredito Centrale" in result


def test_genera_scheda_cumulabilita_assente_non_mostrata():
    bando = {"bando": {"titolo": "Bando Test", "cumulabilita": None}}
    result = genera_scheda(bando)
    assert "Cumulabilità" not in result
