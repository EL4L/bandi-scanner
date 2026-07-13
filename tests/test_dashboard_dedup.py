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


def _eligible(nome, score):
    return {
        "nome": nome,
        "score": score,
        "ammissibilita": {"ammissibile": True},
        "breakdown": {"status": "ok"},
    }


def test_nessun_duplicato_restituisce_tutte_le_card():
    cards = [
        _card(1, "Bando A", "Ente A", 80, [_eligible("Cliente 1", 80)]),
        _card(2, "Bando B", "Ente B", 60, [_eligible("Cliente 1", 60)]),
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
        _card(1, "Bando A", "Ente A", 50, [_eligible("Cliente 1", 50)]),
        _card(2, "Bando A", "Ente A", 30, [_eligible("Cliente 2", 30)]),
    ]
    merged, duplicates_count = _dedupe_cards(cards)
    assert duplicates_count == 1
    assert len(merged) == 1
    nomi = {m["nome"] for m in merged[0]["matches"]}
    assert nomi == {"Cliente 1", "Cliente 2"}


def test_duplicato_stesso_cliente_tiene_score_piu_alto():
    cards = [
        _card(1, "Bando A", "Ente A", 40, [_eligible("Cliente 1", 40)]),
        _card(2, "Bando A", "Ente A", 90, [_eligible("Cliente 1", 90)]),
    ]
    merged, duplicates_count = _dedupe_cards(cards)
    assert duplicates_count == 1
    assert len(merged[0]["matches"]) == 1
    assert merged[0]["matches"][0]["score"] == 90
    assert merged[0]["max_score"] == 90


def test_duplicato_con_soli_clienti_esclusi_non_mostra_score_positivo():
    excluded = {
        "nome": "Cliente escluso",
        "score": 55,
        "ammissibilita": {"ammissibile": False},
        "breakdown": {"status": "ok"},
    }
    cards = [
        _card(1, "Bando A", "Ente A", 55, [excluded]),
        _card(2, "Bando A", "Ente A", 55, [excluded]),
    ]
    merged, _ = _dedupe_cards(cards)
    assert merged[0]["max_score"] == 0
    assert merged[0]["nessun_cliente_ammissibile"] is True
