"""Test del filtro per documenti estranei ai bandi per imprese."""

from modules.document_relevance import (
    NON_COMPATIBLE_DOCUMENT_TYPE,
    classify_non_compatible_document,
)


INPS_COMPETITION_TITLE = (
    "Concorso pubblico, per esami, per l’assunzione a tempo indeterminato "
    "di 499 unità di personale da inquadrare nei ruoli del personale "
    "dell’INPS, nell’Area degli assistenti, famiglia professionale "
    "assistente informatico"
)


def test_riconosce_il_concorso_inps_dal_titolo():
    result = classify_non_compatible_document(
        {"bando": {"titolo": INPS_COMPETITION_TITLE}}
    )

    assert result is not None
    assert result["tipo"] == NON_COMPATIBLE_DOCUMENT_TYPE
    assert "concorso pubblico" in result["motivo"].lower()


def test_riconosce_una_procedura_selettiva_per_reclutamento():
    result = classify_non_compatible_document(
        {"bando": {"titolo": "Procedura selettiva pubblica per il reclutamento di personale"}}
    )

    assert result is not None
    assert result["tipo"] == NON_COMPATIBLE_DOCUMENT_TYPE


def test_riconosce_una_graduatoria_di_idonei():
    result = classify_non_compatible_document(
        {"bando": {"titolo": "Graduatoria finale degli idonei al concorso"}}
    )

    assert result is not None
    assert result["tipo"] == NON_COMPATIBLE_DOCUMENT_TYPE


def test_non_esclude_un_incentivo_alle_imprese_per_nuove_assunzioni():
    result = classify_non_compatible_document(
        {"bando": {"titolo": "Incentivi alle imprese per nuove assunzioni"}},
        raw_text=(
            "Avviso pubblico per la concessione di contributi alle imprese. "
            "Sono ammissibili le spese per l'assunzione di nuovo personale."
        ),
    )

    assert result is None


def test_graduatoria_generica_non_basta_per_escludere_un_bando():
    result = classify_non_compatible_document(
        {"bando": {"titolo": "Graduatoria degli incentivi alle imprese"}},
        raw_text="Graduatoria delle domande di contributo ammesse al finanziamento.",
    )

    assert result is None
