from modules.schema import (
    _to_bool,
    _to_enum,
    _to_enum_list,
    _to_number,
    MODALITA_PRESENTAZIONE_VALUES,
    TIPO_AGEVOLAZIONE_VALUES,
    deduplicate_semantic_phrases,
    normalize_agevolazioni,
    normalize_duration_months,
    normalize_enti_coinvolti,
    normalize_fonti,
    normalize_percentuale_fondo_perduto,
    normalize_response,
)


def test_deduplica_semantica_esclusioni_mantiene_la_voce_piu_completa():
    result = deduplicate_semantic_phrases([
        "smantellamento o costruzione di centrali nucleari",
        "smantellamento, gestione, adeguamento o costruzione di centrali nucleari",
        "gioco d'azzardo",
    ])
    assert result == [
        "smantellamento, gestione, adeguamento o costruzione di centrali nucleari",
        "gioco d'azzardo",
    ]


def test_deduplica_semantica_non_unisce_condizioni_diverse_sui_combustibili():
    result = deduplicate_semantic_phrases([
        "estrazione, trasformazione e stoccaggio di combustibili fossili",
        "trasporto, distribuzione e combustione di combustibili fossili",
    ])
    assert len(result) == 2


def test_normalizza_categorie_esclusione_separate():
    result = normalize_response({"bando": {"note_esclusioni": {
        "lista_testuale": None,
        "sezioni_ateco_escluse": [],
        "attivita_vietate": ["tabacco"],
        "soggetti_esclusi": ["imprese in liquidazione"],
        "spese_non_ammissibili": ["beni usati", "beni usati"],
        "altre_esclusioni": ["progetti già conclusi"],
    }}})["bando"]["note_esclusioni"]
    assert result["soggetti_esclusi"] == ["imprese in liquidazione"]
    assert result["spese_non_ammissibili"] == ["beni usati"]
    assert result["altre_esclusioni"] == ["progetti già conclusi"]


class TestToBool:
    def test_string_false(self):
        assert _to_bool("false") is False

    def test_string_true(self):
        assert _to_bool("true") is True

    def test_bool_false(self):
        assert _to_bool(False) is False

    def test_bool_true(self):
        assert _to_bool(True) is True

    def test_string_zero(self):
        assert _to_bool("0") is False

    def test_string_one(self):
        assert _to_bool("1") is True


class TestToNumber:
    def test_plain_string(self):
        assert _to_number("50000") == 50000

    def test_percent_string(self):
        assert _to_number("50%") == 50

    def test_euro_string(self):
        assert _to_number("€ 40.000") == 40000

    def test_none(self):
        assert _to_number(None) is None

    def test_int_passthrough(self):
        assert _to_number(50000) == 50000

    def test_float_passthrough(self):
        assert _to_number(50.5) == 50.5

    def test_comma_decimal(self):
        assert _to_number("1.500,50") == 1500.5


class TestNormalizeResponse:
    def test_ateco_aperto_false_string(self):
        data = {"bando": {"ateco_aperto_a_tutti": "false"}}
        result = normalize_response(data)
        assert result["bando"]["ateco_aperto_a_tutti"] is False

    def test_contributo_max_string(self):
        data = {"bando": {"contributo_max": "50000"}}
        result = normalize_response(data)
        assert result["bando"]["contributo_max"] == 50000

    def test_percentuale_fondo_perduto_percent_string(self):
        """Formato legacy (numero/stringa singola, come prima di #17): viene
        letto come chiave "default" del nuovo oggetto per fascia."""
        data = {"bando": {"percentuale_fondo_perduto": "50%"}}
        result = normalize_response(data)
        assert result["bando"]["percentuale_fondo_perduto"] == {
            "micro": None, "piccola": None, "media": None, "default": 50,
        }

    def test_anzianita_mesi_string(self):
        data = {"bando": {"anzianita_impresa": {
            "mesi_minimi_dalla_costituzione": "12",
            "mesi_massimi_dalla_costituzione": None,
        }}}
        result = normalize_response(data)
        anz = result["bando"]["anzianita_impresa"]
        assert anz["mesi_minimi_dalla_costituzione"] == 12
        assert isinstance(anz["mesi_minimi_dalla_costituzione"], int)


# ---------------------------------------------------------------------------
# #17 — nuovi campi: percentuale per fascia, modalità, tipo agevolazione, cumulabilità
# ---------------------------------------------------------------------------

class TestNormalizePercentualeFondoPerduto:
    def test_formato_oggetto_per_fascia(self):
        value = {"micro": 60, "piccola": "50%", "media": None, "default": None}
        result = normalize_percentuale_fondo_perduto(value)
        assert result == {"micro": 60, "piccola": 50, "media": None, "default": None}

    def test_formato_legacy_numero_singolo(self):
        """Retrocompatibilità: bandi salvati prima di #17 avevano un numero
        semplice — deve finire nella chiave "default"."""
        assert normalize_percentuale_fondo_perduto(50) == {
            "micro": None, "piccola": None, "media": None, "default": 50,
        }

    def test_formato_legacy_stringa_percentuale(self):
        assert normalize_percentuale_fondo_perduto("40%") == {
            "micro": None, "piccola": None, "media": None, "default": 40,
        }

    def test_none(self):
        assert normalize_percentuale_fondo_perduto(None) == {
            "micro": None, "piccola": None, "media": None, "default": None,
        }

    def test_oggetto_con_chiavi_mancanti(self):
        """Un oggetto parziale (solo alcune fasce) non deve sollevare KeyError."""
        result = normalize_percentuale_fondo_perduto({"micro": 60})
        assert result == {"micro": 60, "piccola": None, "media": None, "default": None}

    def test_ignora_chiave_grande(self):
        """La fascia 'grande' non fa parte di questo campo (solo PMI)."""
        result = normalize_percentuale_fondo_perduto({"micro": 60, "grande": 10})
        assert "grande" not in result


class TestNormalizeResponseNuoviCampi:
    def test_percentuale_fondo_perduto_per_fascia_via_normalize_response(self):
        data = {"bando": {"percentuale_fondo_perduto": {"micro": 60, "piccola": 50, "media": 40}}}
        result = normalize_response(data)
        assert result["bando"]["percentuale_fondo_perduto"] == {
            "micro": 60, "piccola": 50, "media": 40, "default": None,
        }

    def test_modalita_presentazione_valore_valido(self):
        data = {"bando": {"modalita_presentazione": "sportello"}}
        result = normalize_response(data)
        assert result["bando"]["modalita_presentazione"] == "sportello"

    def test_modalita_presentazione_case_insensitive(self):
        data = {"bando": {"modalita_presentazione": "Click_Day"}}
        result = normalize_response(data)
        assert result["bando"]["modalita_presentazione"] == "click_day"

    def test_modalita_presentazione_valore_non_riconosciuto_diventa_none(self):
        """Un'allucinazione LLM (valore fuori enum) non deve essere salvata
        come rumore non filtrabile a valle."""
        data = {"bando": {"modalita_presentazione": "boh"}}
        result = normalize_response(data)
        assert result["bando"]["modalita_presentazione"] is None

    def test_modalita_presentazione_none(self):
        data = {"bando": {"modalita_presentazione": None}}
        result = normalize_response(data)
        assert result["bando"]["modalita_presentazione"] is None

    def test_tipo_agevolazione_lista_valida(self):
        data = {"bando": {"tipo_agevolazione": ["fondo_perduto", "finanziamento_agevolato"]}}
        result = normalize_response(data)
        assert result["bando"]["tipo_agevolazione"] == ["fondo_perduto", "finanziamento_agevolato"]

    def test_tipo_agevolazione_scarta_valori_non_enum(self):
        data = {"bando": {"tipo_agevolazione": ["fondo_perduto", "boh", "voucher"]}}
        result = normalize_response(data)
        assert result["bando"]["tipo_agevolazione"] == ["fondo_perduto", "voucher"]

    def test_tipo_agevolazione_dedup(self):
        data = {"bando": {"tipo_agevolazione": ["voucher", "Voucher", "VOUCHER"]}}
        result = normalize_response(data)
        assert result["bando"]["tipo_agevolazione"] == ["voucher"]

    def test_tipo_agevolazione_non_lista_diventa_vuota(self):
        data = {"bando": {"tipo_agevolazione": "fondo_perduto"}}
        result = normalize_response(data)
        assert result["bando"]["tipo_agevolazione"] == []

    def test_cumulabilita_stringa_valida(self):
        data = {"bando": {"cumulabilita": "Non cumulabile con altre agevolazioni de minimis."}}
        result = normalize_response(data)
        assert result["bando"]["cumulabilita"] == "Non cumulabile con altre agevolazioni de minimis."

    def test_cumulabilita_stringa_vuota_diventa_none(self):
        data = {"bando": {"cumulabilita": "   "}}
        result = normalize_response(data)
        assert result["bando"]["cumulabilita"] is None

    def test_cumulabilita_none(self):
        data = {"bando": {"cumulabilita": None}}
        result = normalize_response(data)
        assert result["bando"]["cumulabilita"] is None


class TestToEnum:
    def test_valore_valido(self):
        assert _to_enum("sportello", MODALITA_PRESENTAZIONE_VALUES) == "sportello"

    def test_case_insensitive_e_spazi(self):
        assert _to_enum("  Graduatoria  ", MODALITA_PRESENTAZIONE_VALUES) == "graduatoria"

    def test_valore_non_riconosciuto(self):
        assert _to_enum("qualcosa_altro", MODALITA_PRESENTAZIONE_VALUES) is None

    def test_non_stringa(self):
        assert _to_enum(123, MODALITA_PRESENTAZIONE_VALUES) is None

    def test_none(self):
        assert _to_enum(None, MODALITA_PRESENTAZIONE_VALUES) is None


class TestToEnumList:
    def test_lista_mista_filtra_non_validi(self):
        result = _to_enum_list(["fondo_perduto", "boh", "garanzia"], TIPO_AGEVOLAZIONE_VALUES)
        assert result == ["fondo_perduto", "garanzia"]

    def test_non_lista(self):
        assert _to_enum_list("fondo_perduto", TIPO_AGEVOLAZIONE_VALUES) == []

    def test_none(self):
        assert _to_enum_list(None, TIPO_AGEVOLAZIONE_VALUES) == []

    def test_elementi_non_stringa_ignorati(self):
        result = _to_enum_list(["fondo_perduto", 123, None, "voucher"], TIPO_AGEVOLAZIONE_VALUES)
        assert result == ["fondo_perduto", "voucher"]


class TestAgevolazioniStrutturate:
    def test_finanziamento_non_diventa_contributo(self):
        result = normalize_response({"bando": {
            "contributo_max": None,
            "tipo_agevolazione": ["finanziamento_agevolato"],
            "agevolazioni": [{
                "tipo": "finanziamento_agevolato",
                "importo_min": "€ 5.000",
                "importo_max": "€ 25.000",
                "tasso_interesse_percentuale": "0%",
                "durata_mesi": "72",
                "rimborso_richiesto": True,
                "fonti": [{"pagina": 6, "testo": "importo massimo: 25.000 euro"}],
            }],
        }})
        bando = result["bando"]
        assert bando["contributo_max"] is None
        assert bando["agevolazioni"][0]["importo_max"] == 25000
        assert bando["agevolazioni"][0]["durata_mesi"] == 72
        assert bando["agevolazioni"][0]["rimborso_richiesto"] is True

    def test_durate_con_unita_vengono_convertite_in_mesi(self):
        assert normalize_duration_months("16 semestri") == 96
        assert normalize_duration_months("2 trimestri") == 6
        assert normalize_duration_months("1 anno") == 12
        assert normalize_duration_months("18 mesi") == 18
        assert normalize_duration_months("72") == 72

        result = normalize_agevolazioni([{
            "tipo": "finanziamento_agevolato",
            "durata_mesi": "fino a 16 semestri",
            "preammortamento_mesi": "2 semestri",
        }])[0]
        assert result["durata_mesi"] == 96
        assert result["preammortamento_mesi"] == 12

    def test_tipo_agevolazione_non_valido_viene_scartato(self):
        assert normalize_agevolazioni([{"tipo": "premio_magico"}]) == []

    def test_massimale_prestito_rimosso_da_contributo_max(self):
        result = normalize_response({"bando": {
            "contributo_max": 25000,
            "tipo_agevolazione": ["finanziamento_agevolato"],
            "agevolazioni": [{
                "tipo": "finanziamento_agevolato",
                "importo_max": 25000,
                "rimborso_richiesto": True,
            }],
        }})["bando"]
        assert result["contributo_max"] is None
        assert result["agevolazioni"][0]["importo_max"] == 25000

    def test_fonti_deduplicate_e_pagina_normalizzata(self):
        source = {"campo": "contributo_max", "pagina": "8", "testo": "massimo 40.000 euro"}
        result = normalize_fonti([source, source])
        assert result == [{
            "campo": "contributo_max",
            "pagina": 8,
            "testo": "massimo 40.000 euro",
            "certezza": None,
        }]


def test_normalizza_enti_coinvolti_con_ruoli_distinti():
    result = normalize_enti_coinvolti([
        {"nome": "BNL S.p.A.", "ruolo": "gestore", "fonti": []},
        {"nome": "Mediocredito Centrale", "ruolo": "gestore", "fonti": []},
    ])
    assert [(item["nome"], item["ruolo"]) for item in result] == [
        ("BNL S.p.A.", "gestore"),
        ("Mediocredito Centrale", "gestore"),
    ]


def test_normalizza_enti_unifica_stesso_nome_e_sceglie_ruolo_piu_specifico():
    result = normalize_enti_coinvolti([
        {"nome": "Lazio Innova SpA", "ruolo": "gestore", "fonti": []},
        {"nome": "Lazio Innova S.p.A.", "ruolo": "ente_attuatore", "fonti": []},
        {"nome": "Banca Nazionale del Lavoro S.p.A.", "ruolo": "intermediario_finanziario", "fonti": []},
        {"nome": "Banca Nazionale del Lavoro S.p.A.", "ruolo": "gestore", "fonti": []},
    ])
    assert [(item["nome"], item["ruolo"]) for item in result] == [
        ("Lazio Innova S.p.A.", "ente_attuatore"),
        ("Banca Nazionale del Lavoro S.p.A.", "gestore"),
    ]


def test_spese_ammissibili_elimina_voci_brevi_gia_comprese_in_una_voce_completa():
    result = normalize_response({"bando": {"spese_ammissibili": [
        "Acquisto di arredi, impianti, macchinari e attrezzature",
        "Arredi",
        "Impianti",
        "Macchinari",
        "Attrezzature",
    ]}})["bando"]["spese_ammissibili"]
    assert result == ["Acquisto di arredi, impianti, macchinari e attrezzature"]


def test_esclusioni_settoriali_forzano_ateco_non_aperto_a_tutti():
    result = normalize_response({"bando": {
        "ateco_aperto_a_tutti": True,
        "note_esclusioni": {
            "sezioni_ateco_escluse": [],
            "attivita_vietate": ["attività finanziarie"],
        },
    }})["bando"]
    assert result["ateco_aperto_a_tutti"] is False
