"""
Test Fase 1 sui PDF in data/test_pdfs/.
Uso: dalla root del progetto
  python scripts/test_phase1.py
  python scripts/test_phase1.py --with-api
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.extractor import (
    EmptyPDFException,
    InvalidJSONResponse,
    MissingAPIKeyError,
    extract_bando_data,
    extract_text_from_pdf,
)
from modules.log_utils import log_prompt_run
from modules.validator import fields_status, validate_bando

PDF_DIR = ROOT / "data" / "test_pdfs"


def run_text_only(pdf_path: Path) -> None:
    print(f"\n--- {pdf_path.name} (solo testo) ---")
    try:
        text = extract_text_from_pdf(str(pdf_path))
        print(f"OK: {len(text)} caratteri estratti")
    except EmptyPDFException as exc:
        print(f"FALLITO: {exc}")


def run_full(pdf_path: Path) -> None:
    print(f"\n--- {pdf_path.name} (flusso completo) ---")
    try:
        text = extract_text_from_pdf(str(pdf_path))
        raw = extract_bando_data(text)
        result = validate_bando(raw, raw_text=text)
        data = result["data"]
        ok_fields, null_fields = fields_status(data)
        log_prompt_run(
            filename=pdf_path.name,
            fields_ok=ok_fields,
            fields_null=null_fields,
            notes=(
                f"Test script: {len(result['errors'])} errori, "
                f"revisione manuale={result['needs_manual_review']}"
            ),
        )
        print(f"Campi OK: {len(ok_fields)}, null: {len(null_fields)}")
        print(f"Errori validazione: {result['errors']}")
        if result["needs_manual_review"]:
            print("WARNING: Da revisionare manualmente")
    except EmptyPDFException as exc:
        print(f"PDF illeggibile: {exc}")
    except MissingAPIKeyError as exc:
        print(f"API key mancante: {exc}")
        sys.exit(1)
    except InvalidJSONResponse as exc:
        print(f"JSON invalido: {exc}")
    except Exception as exc:
        print(f"Errore: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Fase 1 bandi-scanner")
    parser.add_argument(
        "--with-api",
        action="store_true",
        help="Esegue anche chiamata Claude (richiede .env)",
    )
    args = parser.parse_args()

    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        print(
            f"Nessun PDF in {PDF_DIR}. "
            "Copia 3-5 PDF di test nella cartella e riesegui."
        )
        sys.exit(0)

    print(f"Trovati {len(pdfs)} PDF in {PDF_DIR}")
    for pdf in pdfs:
        if args.with_api:
            run_full(pdf)
        else:
            run_text_only(pdf)

    print("\nFatto. Risultati API registrati in logs/PROMPT_LOG.md")


if __name__ == "__main__":
    main()
