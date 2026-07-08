from pathlib import Path

PROMPT_PATH = Path("prompts/system_extraction.md")

def test_prompt_exists():
    assert PROMPT_PATH.is_file()

def test_regola_sbagliata_rimossa():
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "usa il massimale di spese ammissibili come contributo_max" not in text

def test_regola_calcolo_presente():
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "spesa_massima" in text and "percentuale" in text

def test_campi_distinti():
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "NON usare il massimale" in text or "due campi distinti" in text
