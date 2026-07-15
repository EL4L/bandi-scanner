"""Test per la logica Python di modules/database.py.
I test DB-dipendenti usano mock_db dalla fixture conftest.
"""
import pytest
from unittest.mock import MagicMock
from modules.database import (
    _PGConnection,
    attach_pdf_to_bando,
    compute_document_hash,
    find_duplicate_bando,
    find_duplicate_bando_by_hash,
    save_bando_from_json,
)


# ---------------------------------------------------------------------------
# Guard clause: titolo vuoto non tocca il DB
# ---------------------------------------------------------------------------

def test_find_duplicate_bando_titolo_vuoto_ritorna_none():
    result = find_duplicate_bando("", None)
    assert result is None


def test_find_duplicate_bando_solo_spazi_ritorna_none():
    result = find_duplicate_bando("   ", "Ente Test")
    assert result is None


def test_compute_document_hash_ignora_spazi_e_maiuscole():
    assert compute_document_hash("  Testo   DEL bando\n") == compute_document_hash("testo del BANDO")
    assert compute_document_hash("   ") is None


def test_find_duplicate_bando_by_hash_vuoto_non_tocca_db():
    assert find_duplicate_bando_by_hash(None) is None


def test_find_duplicate_bando_by_hash_ritorna_id(mock_db):
    mock_db.execute.return_value.fetchone.return_value = {"id": 73}
    assert find_duplicate_bando_by_hash("a" * 64) == 73


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

    pdf_bytes = b"%PDF-1.4 test"
    result = save_bando_from_json(
        data,
        document_hash="a" * 64,
        pdf_bytes=pdf_bytes,
        pdf_filename="bando.pdf",
    )
    assert result == 5

    # Il parametro dimensione_str nella tuple INSERT deve essere "micro"
    call_args = mock_db.execute.call_args
    params = call_args[0][1]  # secondo argomento posizionale = tuple parametri SQL
    assert "micro" in params
    assert params[9] == "validato"
    assert params[10] == 0.0
    assert params[11] == "[]"
    assert params[-3] == "a" * 64
    assert params[-2] == pdf_bytes
    assert params[-1] == "bando.pdf"


def test_attach_pdf_to_bando_associa_solo_pdf_valido(mock_db):
    mock_db.execute.return_value.rowcount = 1

    assert attach_pdf_to_bando(12, b"%PDF-1.7 originale", "originale.pdf") is True
    query, params = mock_db.execute.call_args.args
    assert "pdf_original IS NULL" in query
    assert params == (b"%PDF-1.7 originale", "originale.pdf", 12)
    mock_db.commit.assert_called_once()


def test_attach_pdf_to_bando_rifiuta_bytes_non_pdf(mock_db):
    assert attach_pdf_to_bando(12, b"non un pdf", "file.pdf") is False
    mock_db.execute.assert_not_called()
