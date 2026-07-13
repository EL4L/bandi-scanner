"""Estrae i PDF della demo e salva il JSON completo in Markdown.

Lo script non accede al database: usa direttamente le funzioni del modulo
extractor e le credenziali del provider configurate nel file .env.
"""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

from modules.extractor import extract_bando_data, extract_text_from_pdf
from modules.schema import MAX_TEXT_CHARS


ROOT = Path(__file__).resolve().parent
PDF_PATHS = (
    ROOT / "data" / "test_pdfs" / "Complesso.pdf",
    ROOT / "data" / "test_pdfs" / "esclusioni.pdf",
)
OUTPUT_PATH = ROOT / "demo_pdf_check.md"
SUMMARY_FIELDS = (
    "titolo",
    "ente",
    "data_pubblicazione",
    "data_scadenza",
    "contributo_max",
    "percentuale_fondo_perduto",
    "dimensione_impresa",
    "note_esclusioni",
)


def extract_pdf(pdf_path: Path) -> tuple[int, dict]:
    raw_text = extract_text_from_pdf(str(pdf_path))
    text_chars = len(raw_text)
    result = extract_bando_data(raw_text)
    bando = result.get("bando", {})
    coverage = bando.get("copertura_estrazione", {}) if isinstance(bando, dict) else {}
    if (
        not isinstance(coverage, dict)
        or coverage.get("completa") is not True
        or coverage.get("caratteri_analizzati") != text_chars
    ):
        raise RuntimeError(
            f"{pdf_path.name}: copertura integrale non confermata "
            f"({coverage!r})."
        )
    return text_chars, result


def main() -> None:
    load_dotenv(ROOT / ".env")

    extracted = [
        (pdf_path, *extract_pdf(pdf_path))
        for pdf_path in PDF_PATHS
    ]

    sections = [
        "# Verifica estrazione PDF demo",
        "",
        "Generato chiamando direttamente `extract_text_from_pdf()` e "
        "`extract_bando_data()`. Nessun dato è stato salvato nel database.",
        "",
    ]
    for pdf_path, text_chars, result in extracted:
        sections.extend(
            (
                f"## {pdf_path.name}",
                "",
                f"- Caratteri estratti e analizzati integralmente: {text_chars}",
                f"- Soglia per singola chiamata: {MAX_TEXT_CHARS}",
                "",
                "```json",
                json.dumps(result, indent=2, ensure_ascii=False, default=str),
                "```",
                "",
            )
        )

    OUTPUT_PATH.write_text("\n".join(sections), encoding="utf-8")

    print(f"Output completo: {OUTPUT_PATH.name}")
    for pdf_path, text_chars, result in extracted:
        bando = result.get("bando", {})
        summary = {field: bando.get(field) for field in SUMMARY_FIELDS}
        print(f"\n{pdf_path.name} ({text_chars}/{MAX_TEXT_CHARS} caratteri analizzati)")
        print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
