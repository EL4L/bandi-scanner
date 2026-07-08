from modules.schema import _to_bool, _to_number, normalize_response


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
        data = {"bando": {"percentuale_fondo_perduto": "50%"}}
        result = normalize_response(data)
        assert result["bando"]["percentuale_fondo_perduto"] == 50

    def test_anzianita_mesi_string(self):
        data = {"bando": {"anzianita_impresa": {
            "mesi_minimi_dalla_costituzione": "12",
            "mesi_massimi_dalla_costituzione": None,
        }}}
        result = normalize_response(data)
        anz = result["bando"]["anzianita_impresa"]
        assert anz["mesi_minimi_dalla_costituzione"] == 12
        assert isinstance(anz["mesi_minimi_dalla_costituzione"], int)
