from pathlib import Path

PROMPT_PATH = Path("prompts/system_extraction.md")


def test_regola_vecchia_presunzione_pmi_rimossa():
    """Fix #9 (audit Fable): la vecchia regola presumeva PMI per qualunque
    agevolazione di Stato, causando l'invenzione di micro/piccola/media=true
    senza riscontro testuale (bug reale sul Fondo impresa femminile, che non
    menziona mai queste parole nel testo)."""
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "Le agevolazioni di Stato sono destinate alle PMI" not in text


def test_regola_richiede_riscontro_testuale():
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "presumo PMI" in text
    assert "presumere PMI" in text


def test_regola_esempio_negativo_fondo_femminile_presente():
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "Fondo impresa femminile" in text
    assert '"micro": false, "piccola": false, "media": false, "grande": false' in text


def test_regola_eccezione_riferimento_normativo_pmi_presente():
    """L'eccezione (riferimento esplicito alle PMI, es. raccomandazione UE)
    deve restare per non regredire sui bandi che DICONO davvero "riservato
    alle PMI" — il fix non deve eliminare i veri positivi, solo i falsi."""
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "riservato alle PMI" in text
