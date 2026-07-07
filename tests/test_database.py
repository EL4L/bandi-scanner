"""Test per la logica Python di modules/database.py.
I test DB-dipendenti usano mock_db dalla fixture conftest.
"""
import pytest
from unittest.mock import MagicMock
from modules.database import find_duplicate_bando, save_bando_from_json, _PGConnection


# ---------------------------------------------------------------------------
# Guard clause: titolo vuoto non tocca il DB
# ---------------------------------------------------------------------------

def test_find_duplicate_bando_titolo_vuoto_ritorna_none():
    result = find_duplicate_bando("", None)
    assert result is None


def test_find_duplicate_bando_solo_spazi_ritorna_none():
    result = find_duplicate_bando("   ", "Ente Test")
    assert result is None


# ---------------------------------------------------------------------------
# _PGConnection: sostituzione placeholder
# ---------------------------------------------------------------------------

def test_pgconnection_passa_query_invariata():
    """_PGConnection.execute passa la query a psycopg2 senza modifiche (usa %s nativo)."""
    raw_conn = MagicMock()
    mock_cur = MagicMock()
    raw_conn.cursor.return_value = mock_cur

    pg_conn = _PGConnection(raw_conn)
    pg_conn.execute("SELECT * FROM bandi WHERE id = %s", (1,))

    mock_cur.execute.assert_called_once_with(
        "SELECT * FROM bandi WHERE id = %s", (1,)
    )


# ---------------------------------------------------------------------------
# find_duplicate_bando con mock DB
# ---------------------------------------------------------------------------

def test_find_duplicate_bando_ritorna_id_da_mock(mock_db):
    mock_db.execute.return_value.fetchone.return_value = {"id": 42}
    result = find_duplicate_bando("Titolo Test", "Ente Test", strict=True)
    assert result == 42


# ---------------------------------------------------------------------------
# save_bando_from_json: conversione dimensione dict → stringa CSV
# ---------------------------------------------------------------------------

def test_save_bando_from_json_dimensione_dict_convertita(mock_db):
    """dimensione_impresa come dict con solo micro=True → INSERT con "micro"."""
    mock_db.execute.return_value.fetchone.return_value = {"id": 5}

    data = {
        "bando": {
            "titolo": "Bando Test",
            "ente": "Ente Test",
            "data_scadenza": "2099-12-31",
            "codici_ateco_ammessi": [],
            "regioni_ammesse": [],
            "dimensione_impresa": {
                "micro": True,
                "piccola": False,
                "media": False,
                "grande": False,
            },
            "contributo_max": None,
        }
    }

    result = save_bando_from_json(data)
    assert result == 5

    # Il parametro dimensione_str nella tuple INSERT deve essere "micro"
    call_args = mock_db.execute.call_args
    params = call_args[0][1]  # secondo argomento posizionale = tuple parametri SQL
    assert "micro" in params
