from pathlib import Path

from modules.evidence import (
    economic_detail_warnings,
    reconcile_economic_details,
    entity_source_warnings,
    reconcile_entity_source,
    reconcile_explicit_ateco_exclusions,
)


def test_recupera_abbuono_e_cumulabilita_espliciti():
    data = normalize_response({"bando": {
        "agevolazioni": [{
            "tipo": "finanziamento_agevolato",
            "abbuono_rate": None,
            "fonti": [],
        }],
        "cumulabilita": None,
    }})
    raw_text = (
        "--- PAGINA 7 ---\nAl finanziamento è abbinato un Abbuono delle ultime 12 rate mensili. "
        "--- PAGINA 34 ---\nNon aver beneficiato di altri sostegni pubblici sul medesimo investimento, "
        "salvo che siano rispettati i limiti di cumulo applicabili."
    )
    notices = reconcile_economic_details(data, raw_text)
    bando = data["bando"]
    assert bando["agevolazioni"][0]["abbuono_rate"] == 12
    assert "limiti di cumulo" in bando["cumulabilita"]
    assert economic_detail_warnings(data, raw_text) == []
    assert len(notices) == 2


def test_ricostruisce_dettagli_finanziamento_omessi_dal_modello():
    data = normalize_response({"bando": {
        "tipo_agevolazione": ["finanziamento_agevolato"],
        "agevolazioni": [],
    }})
    raw_text = (
        "--- PAGINA 6 ---\n"
        "importo minimo: 5.000,00 euro; "
        "importo massimo: 25.000,00 euro; "
        "periodo di rimborso del prestito: 72 mesi; "
        "preammortamento: 12 (sempre previsto); "
        "tasso di interesse: zero."
    )

    notices = reconcile_economic_details(data, raw_text)

    assert len(data["bando"]["agevolazioni"]) == 1
    financing = data["bando"]["agevolazioni"][0]
    assert financing["tipo"] == "finanziamento_agevolato"
    assert financing["importo_min"] == 5000
    assert financing["importo_max"] == 25000
    assert financing["durata_mesi"] == 72
    assert financing["preammortamento_mesi"] == 12
    assert financing["tasso_interesse_percentuale"] == 0
    assert financing["rimborso_richiesto"] is True
    assert {source["pagina"] for source in financing["fonti"]} == {6}
    assert any("ricostruita" in notice for notice in notices)


def test_corregge_durate_ai_convertite_male_usando_le_unita_del_testo():
    data = normalize_response({"bando": {
        "tipo_agevolazione": ["finanziamento_agevolato"],
        "agevolazioni": [{
            "tipo": "finanziamento_agevolato",
            "durata_mesi": 32,
            "preammortamento_mesi": 4,
            "fonti": [],
        }],
    }})
    raw_text = (
        "--- PAGINA 5 ---\n"
        "Il finanziamento avra una durata di ammortamento fino a 16 semestri "
        "comprensivi di un eventuale periodo di pre-ammortamento pari a 2 semestri."
    )

    notices = reconcile_economic_details(data, raw_text)

    financing = data["bando"]["agevolazioni"][0]
    assert financing["durata_mesi"] == 96
    assert financing["preammortamento_mesi"] == 12
    assert {source["pagina"] for source in financing["fonti"]} == {5}
    assert any("Durata corretto da 32 a 96 mesi" in notice for notice in notices)
    assert any("Preammortamento corretto da 4 a 12 mesi" in notice for notice in notices)


def test_normalizza_anni_e_trimestri_in_formulazioni_finanziarie():
    data = normalize_response({"bando": {
        "tipo_agevolazione": ["finanziamento_agevolato"],
        "agevolazioni": [{"tipo": "finanziamento_agevolato", "fonti": []}],
    }})
    raw_text = (
        "Il prestito ha una durata di 3 anni. "
        "Preammortamento: 2 trimestri."
    )

    reconcile_economic_details(data, raw_text)

    financing = data["bando"]["agevolazioni"][0]
    assert financing["durata_mesi"] == 36
    assert financing["preammortamento_mesi"] == 6


def test_non_confonde_una_scadenza_rata_con_i_mesi_di_preammortamento():
    data = normalize_response({"bando": {
        "tipo_agevolazione": ["finanziamento_agevolato"],
        "agevolazioni": [{"tipo": "finanziamento_agevolato", "fonti": []}],
    }})

    reconcile_economic_details(
        data,
        "La rata di preammortamento scade il 30/06 di ogni anno.",
    )

    assert data["bando"]["agevolazioni"][0]["preammortamento_mesi"] is None


def test_segnala_abbuono_citato_senza_strumento_finanziario():
    data = normalize_response({"bando": {"agevolazioni": [], "cumulabilita": None}})
    warnings = economic_detail_warnings(
        data,
        "È previsto un Abbuono delle ultime 6 rate mensili.",
    )
    assert any("abbuono" in warning for warning in warnings)
from modules.extractor import extract_text_from_pdf
from modules.schema import normalize_response


PDF_DIR = Path(__file__).resolve().parents[1] / "data" / "test_pdfs"


def test_recupera_sezioni_ateco_solo_se_esplicite_in_contesto_esclusione():
    raw_text = (
        "--- PAGINA 3 ---\n"
        "Sono escluse le attività finanziarie e assicurative (Sez. K ATECO) "
        "e le attività immobiliari (Sezione L ATECO)."
    )
    data = {"bando": {
        "ateco_aperto_a_tutti": True,
        "note_esclusioni": {
            "lista_testuale": "Settori esclusi",
            "sezioni_ateco_escluse": [],
            "attivita_vietate": [],
        },
        "fonti": [],
    }}
    warnings = reconcile_explicit_ateco_exclusions(data, raw_text)
    bando = data["bando"]
    assert bando["note_esclusioni"]["sezioni_ateco_escluse"] == ["Sez. K", "Sez. L"]
    assert bando["ateco_aperto_a_tutti"] is False
    assert {source["pagina"] for source in bando["fonti"]} == {3}
    assert any("recuperate" in warning for warning in warnings)


def test_non_inferisce_lettere_ateco_dai_nomi_delle_attivita():
    raw_text = (
        "--- PAGINA 8 ---\n"
        "Sono escluse le attività finanziarie e le attività di sviluppo immobiliare."
    )
    data = {"bando": {
        "note_esclusioni": {
            "lista_testuale": "Escluse attività finanziarie e immobiliari",
            "sezioni_ateco_escluse": ["Sez. K", "Sez. L"],
            "attivita_vietate": ["attività finanziarie", "sviluppo immobiliare"],
        },
        "fonti": [],
    }}
    warnings = reconcile_explicit_ateco_exclusions(data, raw_text)
    notes = data["bando"]["note_esclusioni"]
    assert notes["sezioni_ateco_escluse"] == []
    assert notes["attivita_vietate"] == ["attività finanziarie", "sviluppo immobiliare"]
    assert any("rimosse" in warning for warning in warnings)


def test_fonte_ente_deve_supportare_il_valore_estratto():
    data = {"bando": {
        "ente": "Regione Lazio",
        "fonti": [{
            "campo": "ente",
            "pagina": 4,
            "testo": "La gestione è affidata a Banca Nazionale del Lavoro S.p.A.",
        }],
    }}
    warnings = entity_source_warnings(data)
    assert len(warnings) == 1
    assert "non supporta" in warnings[0]


def test_fonte_ente_accetta_denominazione_testualmente_coerente():
    data = {"bando": {
        "ente": "Regione Lazio",
        "fonti": [{
            "campo": "ente",
            "pagina": 1,
            "testo": "Programma Regionale FESR Lazio 2021-2027",
        }],
    }}
    assert entity_source_warnings(data) == []


def test_ripara_fonte_ente_solo_con_contesto_istituzionale_forte():
    raw_text = (
        "--- PAGINA 1 ---\n"
        "AVVISO DEL PROGRAMMA REGIONALE FESR LAZIO 2021-2027. "
        "BOLLETTINO UFFICIALE DELLA REGIONE LAZIO."
    )
    data = {"bando": {
        "ente": "Regione Lazio",
        "fonti": [{"campo": "ente", "pagina": 4, "testo": "Gestore: BNL S.p.A."}],
    }}
    messages = reconcile_entity_source(data, raw_text)
    assert any("sostituita" in message for message in messages)
    assert entity_source_warnings(data) == []
    assert data["bando"]["fonti"][0]["pagina"] == 1


def test_non_ripara_ente_da_semplice_riferimento_geografico():
    raw_text = "--- PAGINA 2 ---\nSono ammesse imprese con sede nella Regione Lazio."
    data = {"bando": {
        "ente": "Regione Lazio",
        "fonti": [{"campo": "ente", "pagina": 4, "testo": "Gestore: BNL S.p.A."}],
    }}
    assert reconcile_entity_source(data, raw_text) == []
    assert entity_source_warnings(data)


def test_complesso_non_contiene_sezioni_ateco_esplicite():
    raw_text = extract_text_from_pdf(str(PDF_DIR / "Complesso.pdf"))
    data = {"bando": {
        "note_esclusioni": {
            "lista_testuale": "Escluse attività finanziarie e sviluppo immobiliare",
            "sezioni_ateco_escluse": ["Sez. K", "Sez. L"],
            "attivita_vietate": ["attività finanziarie", "sviluppo immobiliare"],
        },
        "fonti": [],
    }}
    reconcile_explicit_ateco_exclusions(data, raw_text)
    assert data["bando"]["note_esclusioni"]["sezioni_ateco_escluse"] == []


def test_complesso_permette_fonte_contestuale_per_regione_lazio():
    raw_text = extract_text_from_pdf(str(PDF_DIR / "Complesso.pdf"))
    data = {"bando": {
        "ente": "Regione Lazio",
        "fonti": [{
            "campo": "ente",
            "pagina": 4,
            "testo": "La gestione è affidata a Banca Nazionale del Lavoro",
        }],
    }}
    reconcile_entity_source(data, raw_text)
    assert entity_source_warnings(data) == []
