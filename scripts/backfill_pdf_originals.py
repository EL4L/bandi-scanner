"""Associa ai bandi esistenti i PDF locali con lo stesso hash del testo.

Non esegue il modello AI e non modifica i dati estratti: salva soltanto il
documento originale quando il relativo bando non possiede ancora un PDF.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.database import (  # noqa: E402
    attach_pdf_to_bando,
    compute_document_hash,
    ensure_database,
    find_duplicate_bando_by_hash,
    get_connection,
)
from modules.extractor import extract_text_from_pdf  # noqa: E402


def main() -> None:
    ensure_database()
    pdf_dir = ROOT / "data" / "test_pdfs"
    associati: list[tuple[int, str]] = []

    for path in sorted(pdf_dir.glob("*.pdf")):
        text = extract_text_from_pdf(str(path))
        document_hash = compute_document_hash(text)
        bando_id = find_duplicate_bando_by_hash(document_hash)
        if bando_id is None:
            continue
        if attach_pdf_to_bando(bando_id, path.read_bytes(), path.name):
            associati.append((bando_id, path.name))

    if associati:
        for bando_id, filename in associati:
            print(f"Bando #{bando_id}: associato {filename}")
    else:
        print("Nessun PDF da associare.")

    with get_connection() as conn:
        status = conn.execute(
            """
            SELECT COUNT(*) AS totale,
                   COUNT(pdf_original) AS con_pdf
            FROM bandi
            """
        ).fetchone()
        senza_pdf = conn.execute(
            "SELECT id FROM bandi WHERE pdf_original IS NULL ORDER BY id"
        ).fetchall()
    missing_ids = [int(row["id"]) for row in senza_pdf]
    print(f"PDF disponibili: {status['con_pdf']}/{status['totale']}")
    print(f"Bandi senza PDF originale: {missing_ids or 'nessuno'}")


if __name__ == "__main__":
    main()
