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
    assert "NON usare MAI il massimale" in text or "campi concettualmente distinti" in text

def test_regola_finanziamento_agevolato_presente():
    """Fix #1 (audit Fable): il tetto di un finanziamento/prestito non è il
    contributo_max — bug reale trovato sulla Nuova Sabatini (estratto 4.000.000,
    tetto del prestito, invece del vero beneficio o null)."""
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "tetto del finanziamento" in text or "tetto del prestito" in text
    assert "Nuova Sabatini" in text

def test_regola_importo_esplicito_priorita_presente():
    """Fix #1 (audit Fable): un importo massimo dell'agevolazione dichiarato
    esplicitamente nel testo va sempre preferito al piano di spesa — bug reale
    trovato sul Fondo impresa femminile (estratto 400.000, piano di spesa,
    invece di 320.000, l'incentivo dichiarato esplicitamente)."""
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "piano di spesa" in text
    assert "Fondo impresa femminile" in text
