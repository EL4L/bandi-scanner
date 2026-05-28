"""Genera PDF di test (usa PyMuPDF / fitz) in data/test_pdfs/.

Esegue 4 scenari:
- bando_ateco_specifico.pdf: contiene un codice ATECO specifico (62.01) e regione 'Abruzzo'
- bando_aperto_a_tutti.pdf: indica 'aperto a tutti i settori'
- bando_regioni.pdf: contiene solo regioni ammesse (Lazio)
- bando_senza_vincoli.pdf: PDF senza informazioni rilevanti (dovrebbe risultare score 0)

Esegui: python scripts/generate_test_pdfs.py
"""
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "test_pdfs"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def make_pdf(path: Path, lines: list[str]):
    doc = fitz.open()
    page = doc.new_page()
    text = "\n".join(lines)
    rect = fitz.Rect(36, 36, 560, 756)
    page.insert_textbox(rect, text, fontsize=11, fontname="helv")
    doc.save(str(path))
    doc.close()


def main():
    # 1. Bando con ATECO specifico
    make_pdf(
        OUT_DIR / "bando_ateco_specifico.pdf",
        [
            "Titolo: Contributi per servizi digitali",
            "Ente: Comune di Pescara",
            "Codici ATECO ammessi: 62.01",
            "Regioni ammesse: Abruzzo",
            "Descrizione: Interventi per sviluppo software e servizi IT.",
        ],
    )

    # 2. Bando aperto a tutti i settori
    make_pdf(
        OUT_DIR / "bando_aperto_a_tutti.pdf",
        [
            "Titolo: Fondo per rilancio locale",
            "Ente: Provincia di Roma",
            "Bando aperto a tutti i settori: aperto a tutti i settori",
            "Descrizione: Sostegno a imprese locali senza limitazioni di settore.",
        ],
    )

    # 3. Bando per regione specifica (Lazio) senza ateco
    make_pdf(
        OUT_DIR / "bando_regioni.pdf",
        [
            "Titolo: Incentivi per turismo in Lazio",
            "Ente: Regione Lazio",
            "Regioni ammesse: Lazio",
            "Descrizione: Progetti per promozione turistica locale.",
        ],
    )

    # 4. Bando senza vincoli (vuoto di informazioni rilevanti)
    make_pdf(
        OUT_DIR / "bando_senza_vincoli.pdf",
        [
            "Avviso pubblico",
            "Si pubblica il presente avviso.",
            "Contattare l'ente per maggiori dettagli.",
        ],
    )

    print(f"PDF generati in: {OUT_DIR}")


if __name__ == "__main__":
    main()
