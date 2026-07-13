"""Test unitari per modules/validator.py.
Nessun mock DB — tutte le funzioni sono pure.
"""
import pytest
from modules.validator import (
    validate_structure,
    validate_format_fields,
    validate_logical_fields,
    calculate_null_percentage,
    validate_bando,
    critical_gaps,
    should_review_manually,
    _is_empty,
)


# ---------------------------------------------------------------------------
# validate_structure
# ---------------------------------------------------------------------------

def test_validate_structure_chiave_bando_mancante():
    errors = validate_structure({})
    assert any("bando" in e.lower() for e in errors)


def test_validate_structure_bando_non_dict():
    errors = validate_structure({"bando": "non un dizionario"})
    assert any("oggetto" in e for e in errors)


def test_validate_structure_ok():
    assert validate_structure({"bando": {}}) == []


# ---------------------------------------------------------------------------
# validate_format_fields
# ---------------------------------------------------------------------------

def test_validate_format_tipo_errato_titolo(bando_minimo):
    """titolo deve essere str|None — passare int genera errore di tipo."""
    bando = bando_minimo(titolo=123)
    errors = validate_format_fields(bando)
    assert any("titolo" in e for e in errors)


def test_validate_format_ateco_aperto_con_codici(bando_minimo):
    """Combinazione inconsistente: ateco_aperto_a_tutti=True + codici non vuoti."""
    bando = bando_minimo(ateco_aperto_a_tutti=True, codici_ateco_ammessi=["62.01"])
    errors = validate_format_fields(bando)
    assert len(errors) > 0


def test_validate_format_data_non_iso(bando_minimo):
    """Chiamata diretta (senza normalize_bando_dates) per testare il controllo formato ISO."""
    bando = bando_minimo(data_scadenza="31/12/2099")
    errors = validate_format_fields(bando)
    assert any("data_scadenza" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_logical_fields
# ---------------------------------------------------------------------------

def test_validate_logical_data_passata(bando_minimo):
    """Una data_scadenza nel passato non è più un errore bloccante, ma un
    warning (verificare se il bando è ancora attivo)."""
    bando = bando_minimo(data_scadenza="2020-01-01")
    errors, warnings = validate_logical_fields(bando)
    assert errors == []
    assert len(warnings) > 0


def test_validate_logical_data_futura(bando_minimo):
    bando = bando_minimo(data_scadenza="2099-12-31")
    errors, warnings = validate_logical_fields(bando)
    assert errors == []
    assert warnings == []


# ---------------------------------------------------------------------------
# calculate_null_percentage
# ---------------------------------------------------------------------------

def test_calculate_null_percentage_tutto_null(bando_minimo):
    """Bando con tutti i campi a null/vuoto → percentuale altissima (100%).
    Un solo campo non è mai "vuoto" per definizione: ateco_aperto_a_tutti=False
    (è un booleano valido, non un dato mancante). anzianita_impresa, pur
    essendo un dict non vuoto con 2 chiavi, viene ora contato come vuoto
    perché entrambi i suoi valori sono null (fix _is_empty, #18).
    """
    bando = bando_minimo()
    pct = calculate_null_percentage(bando)
    assert pct > 90.0


def test_calculate_null_percentage_parziale(bando_minimo):
    bando = bando_minimo(
        titolo="Test",
        ente="Ente",
        data_scadenza="2099-12-31",
        contributo_max=50_000.0,
        codici_ateco_ammessi=["62.01"],
    )
    pct = calculate_null_percentage(bando)
    assert 0.0 < pct < 100.0


# ---------------------------------------------------------------------------
# validate_bando
# ---------------------------------------------------------------------------

def test_validate_bando_ritorna_keys_attese(bando_minimo):
    data = {"bando": bando_minimo(data_scadenza="2099-12-31")}
    result = validate_bando(data)
    assert "data" in result
    assert "errors" in result
    assert "warnings" in result
    assert "null_percentage" in result
    assert "needs_manual_review" in result


def test_validate_bando_needs_manual_review_true(bando_minimo):
    """Bando con quasi tutti i campi vuoti → needs_manual_review=True."""
    data = {"bando": bando_minimo()}
    result = validate_bando(data)
    assert result["needs_manual_review"] is True
    assert any(warning.startswith("RF-007:") for warning in result["warnings"])


# ---------------------------------------------------------------------------
# _is_empty — fix dict generici (#18)
# ---------------------------------------------------------------------------

def test_is_empty_dict_generico_valori_tutti_null():
    """Bug storico: un dict non vuoto (len > 0) con soli valori None passava
    come 'pieno'. anzianita_impresa con entrambi i campi a null deve essere
    considerato vuoto."""
    valore = {"mesi_minimi_dalla_costituzione": None, "mesi_massimi_dalla_costituzione": None}
    assert _is_empty(valore) is True


def test_is_empty_dict_generico_con_un_valore_presente():
    valore = {"mesi_minimi_dalla_costituzione": 12, "mesi_massimi_dalla_costituzione": None}
    assert _is_empty(valore) is False


def test_is_empty_dict_vuoto():
    assert _is_empty({}) is True


def test_is_empty_dimensione_impresa_tutti_false():
    """Caso già gestito prima del fix: non deve essere toccato dalla modifica."""
    valore = {"micro": False, "piccola": False, "media": False, "grande": False}
    assert _is_empty(valore) is True


def test_is_empty_dimensione_impresa_con_true():
    valore = {"micro": False, "piccola": True, "media": False, "grande": False}
    assert _is_empty(valore) is False


# ---------------------------------------------------------------------------
# critical_gaps / should_review_manually — soglia su campi critici (#18)
# ---------------------------------------------------------------------------

def test_critical_gaps_tutti_mancanti(bando_minimo):
    bando = bando_minimo()
    gaps = critical_gaps(bando)
    assert "titolo" in gaps
    assert "data_scadenza" in gaps
    assert "contributo_max/percentuale_fondo_perduto" in gaps
    assert "codici_ateco_ammessi/ateco_aperto_a_tutti/attivita_ammesse" in gaps


def test_critical_gaps_bando_completo_su_campi_critici(bando_minimo):
    bando = bando_minimo(
        titolo="Bando Digitalizzazione PMI",
        data_scadenza="2099-12-31",
        contributo_max=100_000.0,
        codici_ateco_ammessi=["62.01"],
    )
    assert critical_gaps(bando) == []


def test_critical_gaps_ateco_aperto_a_tutti_conta_come_presente(bando_minimo):
    """ateco_aperto_a_tutti=True è un dato esplicito, non un campo mancante."""
    bando = bando_minimo(
        titolo="Bando Digitalizzazione PMI",
        data_scadenza="2099-12-31",
        contributo_max=100_000.0,
        ateco_aperto_a_tutti=True,
    )
    assert "codici_ateco_ammessi/ateco_aperto_a_tutti/attivita_ammesse" not in critical_gaps(bando)


def test_critical_gaps_percentuale_sostituisce_contributo(bando_minimo):
    bando = bando_minimo(
        titolo="Bando Digitalizzazione PMI",
        data_scadenza="2099-12-31",
        percentuale_fondo_perduto=50.0,
        codici_ateco_ammessi=["62.01"],
    )
    assert "contributo_max/percentuale_fondo_perduto" not in critical_gaps(bando)


def test_critical_gaps_sportello_continuo_non_conta_scadenza_come_gap(bando_minimo):
    """Se il testo indica sportello continuo, data_scadenza=null è atteso e
    non deve generare un gap critico."""
    bando = bando_minimo(
        titolo="Nuova Sabatini",
        contributo_max=100_000.0,
        codici_ateco_ammessi=["62.01"],
    )
    raw_text = "Il presente bando opera a sportello continuo fino ad esaurimento fondi."
    assert "data_scadenza" not in critical_gaps(bando, raw_text)


def test_should_review_manually_pochi_campi_minori_mancanti_non_serve_revisione(bando_minimo):
    """Bando con tutti i campi critici presenti e la maggior parte dei campi
    minori valorizzati: non deve finire in revisione (né per campi critici
    né per soglia percentuale globale)."""
    bando = bando_minimo(
        titolo="Bando Digitalizzazione PMI",
        ente="Regione Lombardia",
        data_pubblicazione="2026-01-15",
        data_scadenza="2099-12-31",
        contributo_max=100_000.0,
        percentuale_fondo_perduto=50.0,
        codici_ateco_ammessi=["62.01"],
        regioni_ammesse=["Lombardia"],
        spese_ammissibili=["Consulenza", "Formazione"],
        link_fonte_ufficiale="https://example.org/bando",
        fatturato_max=5_000_000.0,
        dimensione_impresa={"micro": True, "piccola": True, "media": False, "grande": False},
    )
    assert should_review_manually(bando) is False


def test_should_review_manually_campo_critico_mancante_anche_con_pochi_null(bando_minimo):
    """Anche con la maggior parte dei campi valorizzati, l'assenza del titolo
    (campo critico) deve comunque far scattare la revisione manuale."""
    bando = bando_minimo(
        titolo=None,
        ente="Regione Lombardia",
        data_scadenza="2099-12-31",
        contributo_max=100_000.0,
        percentuale_fondo_perduto=50.0,
        codici_ateco_ammessi=["62.01"],
        regioni_ammesse=["Lombardia"],
        spese_ammissibili=["Consulenza"],
        link_fonte_ufficiale="https://example.org/bando",
        dimensione_impresa={"micro": True, "piccola": True, "media": False, "grande": False},
    )
    assert should_review_manually(bando) is True
    assert "titolo" in critical_gaps(bando)


def test_finanziamento_strutturato_non_richiede_contributo_max(bando_minimo):
    bando = bando_minimo(
        titolo="Nuovo Fondo Futuro",
        data_scadenza=None,
        tipo_agevolazione=["finanziamento_agevolato"],
        agevolazioni=[{
            "tipo": "finanziamento_agevolato",
            "importo_max": 25000,
            "rimborso_richiesto": True,
        }],
        attivita_ammesse=["Investimenti produttivi"],
    )
    gaps = critical_gaps(bando, "Misura a sportello continuo")
    assert "contributo_max/percentuale_fondo_perduto" not in gaps


def test_massimale_prestito_in_contributo_max_genera_warning_e_revisione(bando_minimo):
    data = {"bando": bando_minimo(
        titolo="Nuovo Fondo Futuro",
        data_scadenza="2099-12-31",
        contributo_max=25000,
        tipo_agevolazione=["finanziamento_agevolato"],
        agevolazioni=[{
            "tipo": "finanziamento_agevolato",
            "importo_max": 25000,
            "rimborso_richiesto": True,
        }],
        codici_ateco_ammessi=["62.01"],
    )}
    result = validate_bando(data)
    assert any("massimale del prestito" in warning for warning in result["warnings"])
    assert result["data"]["bando"]["contributo_max"] is None
    assert result["needs_manual_review"] is True


def test_finanziamento_con_rimborso_false_genera_warning(bando_minimo):
    data = {"bando": bando_minimo(
        titolo="Prestito Test",
        data_scadenza="2099-12-31",
        tipo_agevolazione=["finanziamento_agevolato"],
        agevolazioni=[{
            "tipo": "finanziamento_agevolato",
            "importo_max": 25000,
            "rimborso_richiesto": False,
        }],
        codici_ateco_ammessi=["62.01"],
    )}
    result = validate_bando(data)
    assert any("rimborso_richiesto è false" in warning for warning in result["warnings"])


def test_abbuono_citato_ma_non_collocabile_richiede_revisione(bando_minimo):
    data = {"bando": bando_minimo(
        titolo="Bando con abbuono",
        data_scadenza="2099-12-31",
        contributo_max=10000,
        codici_ateco_ammessi=["62.01"],
        agevolazioni=[],
    )}
    result = validate_bando(data, raw_text="È previsto un Abbuono delle ultime 6 rate mensili.")
    assert any("Completezza economica" in warning for warning in result["warnings"])
    assert result["needs_manual_review"] is True


def test_fonte_ente_incoerente_richiede_revisione(bando_minimo):
    data = {"bando": bando_minimo(
        titolo="Nuovo Fondo Futuro",
        ente="Regione Lazio",
        data_scadenza="2099-12-31",
        tipo_agevolazione=["finanziamento_agevolato"],
        agevolazioni=[{
            "tipo": "finanziamento_agevolato",
            "importo_max": 25000,
            "rimborso_richiesto": True,
        }],
        codici_ateco_ammessi=["62.01"],
        fonti=[{
            "campo": "ente",
            "pagina": 4,
            "testo": "La gestione è affidata a Banca Nazionale del Lavoro",
        }],
    )}
    result = validate_bando(data)
    assert any("fonte associata a ente" in warning for warning in result["warnings"])
    assert result["needs_manual_review"] is True
