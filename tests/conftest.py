import pytest
from unittest.mock import MagicMock, patch
from collections import defaultdict, deque


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    import main
    main._rate_limit_hits.clear()
    yield
    main._rate_limit_hits.clear()


# ---------------------------------------------------------------------------
# Mock DB layer
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_cursor():
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    cursor.fetchall.return_value = []
    cursor.rowcount = 0
    return cursor


@pytest.fixture
def mock_conn(mock_cursor):
    conn = MagicMock()
    conn.execute.return_value = mock_cursor
    conn.commit.return_value = None
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn


@pytest.fixture
def mock_db(mock_conn):
    with patch("modules.database.get_connection", return_value=mock_conn):
        with patch("main.get_connection", return_value=mock_conn):
            yield mock_conn


TEST_API_KEY = "test-api-key"


@pytest.fixture
def client(mock_db):
    """TestClient già autenticato: invia sempre l'header X-API-Key atteso da
    main.verify_api_key (vedi audit D-3). Per testare i casi 401/senza chiave
    usare un TestClient separato, senza questo header di default."""
    import main
    from fastapi.testclient import TestClient

    with patch("main.ensure_database"):
        with patch.object(main, "APP_API_KEY", TEST_API_KEY):
            with TestClient(main.app) as c:
                c.headers.update({"X-API-Key": TEST_API_KEY})
                yield c


# ---------------------------------------------------------------------------
# Fixture dati bando/cliente
# ---------------------------------------------------------------------------

@pytest.fixture
def bando_minimo():
    """Restituisce una factory che costruisce un bando con tutti i campi BANDO_SCHEMA."""
    def _factory(**overrides):
        base = {
            "titolo": None,
            "ente": None,
            "data_pubblicazione": None,
            "data_scadenza": None,
            "codici_ateco_ammessi": [],
            "attivita_ammesse": [],
            "ateco_aperto_a_tutti": False,
            "regioni_ammesse": [],
            "dimensione_impresa": {
                "micro": False,
                "piccola": False,
                "media": False,
                "grande": False,
            },
            "fatturato_max": None,
            "contributo_max": None,
            "percentuale_fondo_perduto": None,
            "spese_ammissibili": [],
            "link_fonte_ufficiale": None,
            "note_esclusioni": None,
            "spesa_minima_ammissibile": None,
            "anzianita_impresa": {
                "mesi_minimi_dalla_costituzione": None,
                "mesi_massimi_dalla_costituzione": None,
            },
            "forme_giuridiche_ammesse": [],
        }
        base.update(overrides)
        return base
    return _factory


@pytest.fixture
def bando_con_ateco():
    return {
        "bando": {
            "titolo": "Bando Digitale",
            "ente": "Regione Lombardia",
            "codici_ateco_ammessi": ["62.01"],
            "attivita_ammesse": [],
            "ateco_aperto_a_tutti": False,
            "regioni_ammesse": ["Lombardia"],
            "dimensione_impresa": {
                "micro": False,
                "piccola": True,
                "media": True,
                "grande": False,
            },
            "fatturato_max": None,
        }
    }


@pytest.fixture
def cliente_matching():
    return {
        "id": 1,
        "ragione_sociale": "Acme Srl",
        "codice_ateco": "62.01",
        "regione": "Lombardia",
        "dimensione_impresa": "piccola",
        "fatturato": 100000,
        "descrizione_attivita": "sviluppo software applicativo",
    }
