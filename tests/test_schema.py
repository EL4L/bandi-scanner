from modules.schema import (
    _to_bool,
    _to_enum,
    _to_enum_list,
    _to_number,
    MODALITA_PRESENTAZIONE_VALUES,
    TIPO_AGEVOLAZIONE_VALUES,
    normalize_percentuale_fondo_perduto,
    normalize_response,
)


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
