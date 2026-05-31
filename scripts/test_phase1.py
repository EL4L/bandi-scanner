"""
Test Fase 1 sui PDF in data/test_pdfs/.
Uso: dalla root del progetto
  python scripts/test_phase1.py
  python scripts/test_phase1.py --with-api
  python scripts/test_phase1.py --with-api --verify
"""

from __future__ import annotations

import argparse
import sys
import json
from datetime import datetime
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


def run_full(pdf_path: Path, verify: bool = False) -> None:
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
            
        # =======================================================
        # NUOVA LOGICA: MODALITÀ VERIFICA (Richiesta Fase 4)
        # =======================================================
        if verify:
            print("\n" + "="*50)
            print(f" INIZIO VERIFICA MANUALE ACCURATEZZA: {pdf_path.name}")
            print("="*50)
            
            campi_schema = [
                "titolo", "ente", "data_pubblicazione", "data_scadenza", 
                "codici_ateco_ammessi", "ateco_aperto_a_tutti", "regioni_ammesse", 
                "dimensione_impresa", "fatturato_max", "contributo_max", 
                "percentuale_fondo_perduto", "spese_ammissibili", 
                "link_fonte_ufficiale", "note_esclusioni", "attivita_ammesse"
            ]
            
            bando_data = data.get("bando", data) # Gestisce sia struttura piatta che annidata
            dettagli = {}
            campi_corretti = 0
            totale_campi = len(campi_schema)
            
            for campo in campi_schema:
                valore = bando_data.get(campo, "N/D (null)")
                print(f"\n▶ Campo: {campo.upper()}")
                print(f"  Valore estratto dall'AI: {valore}")
                scelta = input("  È corretto rispetto al PDF originale? (s/n): ").strip().lower()
                
                if scelta == 's':
                    campi_corretti += 1
                    esito = "✅ corretto"
                else:
                    esito = "❌ errato/mancante"
                    
                dettagli[campo] = {"valore_estratto": valore, "esito": esito}
                
            accuratezza = campi_corretti / totale_campi
            
            # Salvataggio del report JSON
            dir_risultati = ROOT / "data" / "test_results"
            dir_risultati.mkdir(parents=True, exist_ok=True)
            
            file_output = dir_risultati / f"{pdf_path.stem}_accuracy.json"
            
            report = {
                "pdf_name": pdf_path.name,
                "data_test": datetime.now().isoformat(),
                "accuracy_percent": f"{accuratezza:.2%}",
                "campi_corretti": campi_corretti,
                "totale_campi": totale_campi,
                "dettagli": dettagli
            }
            
            with open(file_output, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=4, ensure_ascii=False)
                
            print("\n" + "="*50)
            print(f" RISULTATO FINALE: ACCURATEZZA {accuratezza:.2%} ({campi_corretti}/{totale_campi})")
            print(f" Report salvato con successo in: {file_output}")
            print("="*50)

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
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Attiva la verifica manuale dell'accuratezza",
    )
    args = parser.parse_args()

    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"Nessun PDF in {PDF_DIR}.")
        sys.exit(0)

    print(f"Trovati {len(pdfs)} PDF in {PDF_DIR}")
    for pdf in pdfs:
        print(f"Analizzando: {pdf.name}")
        if args.with_api:
            run_full(pdf, verify=args.verify)
        else:
            run_text_only(pdf)

    print("\nFatto. Risultati API registrati in logs/PROMPT_LOG.md")


if __name__ == "__main__":
    main()