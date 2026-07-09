import pytest

pytest.importorskip("fastapi")

from main import _dedupe_cards


def _card(id_, titolo, ente, max_score, matches):
    return {
        "id": id_,
        "titolo": titolo,
        "ente": ente,
        "max_score": max_score,
        "color_class": "circle-red",
        "matches": matches,
    }


def test_nessun_duplicato_restituisce_tutte_le_card():
    cards = [
        _card(1, "Bando A", "Ente A", 80, [{"nome": "Cliente 1", "score": 80}]),
        _card(2, "Bando B", "Ente B", 60, [{"nome": "Cliente 1", "score": 60}]),
    ]
    merged, duplicates_count = _dedupe_cards(cards)
    assert duplicates_count == 0
    assert {c["id"] for c in merged} == {1, 2}


def test_duplicato_titolo_ente_case_insensitive_mantiene_id_piu_alto():
    cards = [
        _card(1, "Bando A", "Ente A", 80, []),
        _card(5, "bando a", "ente a", 80, []),
    ]
    merged, duplicates_count = _dedupe_cards(cards)
    assert duplicates_count == 1
    assert len(merged) == 1
    assert merged[0]["id"] == 5


def test_duplicato_fonde_match_di_clienti_diversi():
    cards = [
        _card(1, "Bando A", "Ente A", 50, [{"nome": "Cliente 1", "score": 50}]),
        _card(2, "Bando A", "Ente A", 30, [{"nome": "Cliente 2", "score": 30}]),
    ]
    merged, duplicates_count = _dedupe_cards(cards)
    assert duplicates_count == 1
    assert len(merged) == 1
    nomi = {m["nome"] for m in merged[0]["matches"]}
    assert nomi == {"Cliente 1", "Cliente 2"}


def test_duplicato_stesso_cliente_tiene_score_piu_alto():
    cards = [
        _card(1, "Bando A", "Ente A", 40, [{"nome": "Cliente 1", "score": 40}]),
        _card(2, "Bando A", "Ente A", 90, [{"nome": "Cliente 1", "score": 90}]),
    ]
    merged, duplicates_count = _dedupe_cards(cards)
    assert duplicates_count == 1
    assert len(merged[0]["matches"]) == 1
    assert merged[0]["matches"][0]["score"] == 90
    assert merged[0]["max_score"] == 90
