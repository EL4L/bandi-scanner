"""
Script di esportazione bandi per l'audit estrazione/matching/ammissibilità.

USO:
  1. Metti questo file nella root del progetto (bandi-scanner/), accanto a main.py
  2. Esegui: python export_audit_bandi.py
  3. Ti troverai un file audit_export_bandi.md nella stessa cartella: caricalo in chat

Non modifica nulla, sola lettura. Legge DATABASE_URL dal file .env (stesso
meccanismo usato dall'app).
"""
from __future__ import annotations

import json
import os

import psycopg2
import psycopg2.extras

# Carica .env se esiste (stesso pattern usato altrove nel progetto)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise SystemExit(
        "DATABASE_URL non trovata. Assicurati di eseguire questo script "
        "dalla cartella del progetto, con il file .env presente."
    )

OUTPUT_FILE = "audit_export_bandi.md"

# Limite di bandi esportati: tienilo basso per non esplodere i token della
# sessione di analisi. 8 è un buon compromesso tra varietà e lunghezza.
LIMITE_BANDI = 8


def main() -> None:
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    cur.execute(
        "SELECT id, titolo, ente, data_scadenza, codici_ateco, regioni, "
        "dimensione, contributo_max, json_completo, scheda_cached, created_at "
        "FROM bandi ORDER BY created_at DESC LIMIT %s",
        (LIMITE_BANDI,),
    )
    bandi = cur.fetchall()

    cur.execute("SELECT COUNT(*) AS n FROM bandi")
    totale = cur.fetchone()["n"]

    cur.execute(
        "SELECT id, ragione_sociale, p_iva, codice_ateco, descrizione_attivita, "
        "regione, fatturato, dimensione_impresa, data_costituzione, "
        "numero_dipendenti, forma_giuridica FROM clienti"
    )
    clienti = cur.fetchall()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"# Export bandi per audit — {len(bandi)} di {totale} bandi totali nel DB\n\n")
        f.write(
            "Generato da export_audit_bandi.py. Contiene il JSON COMPLETO "
            "estratto dal LLM per ciascun bando (così com'è salvato nel DB), "
            "così da poterlo confrontare col testo originale del bando "
            "(i PDF sono già nel repo in data/test_pdfs/, se corrispondono) "
            "e valutare se l'estrazione contiene errori o allucinazioni.\n\n"
        )

        f.write("## Clienti in anagrafica (per capire l'universo di match)\n\n")
        f.write("```json\n")
        f.write(json.dumps([dict(c) for c in clienti], indent=2, ensure_ascii=False, default=str))
        f.write("\n```\n\n---\n\n")

        for b in bandi:
            f.write(f"## Bando #{b['id']} — {b['titolo'] or '(senza titolo)'}\n\n")
            f.write(f"- **Ente**: {b['ente']}\n")
            f.write(f"- **Scadenza**: {b['data_scadenza']}\n")
            f.write(f"- **Codici ATECO (colonna denormalizzata)**: {b['codici_ateco']}\n")
            f.write(f"- **Regioni (colonna denormalizzata)**: {b['regioni']}\n")
            f.write(f"- **Dimensione (colonna denormalizzata)**: {b['dimensione']}\n")
            f.write(f"- **Contributo max**: {b['contributo_max']}\n")
            f.write(f"- **Creato il**: {b['created_at']}\n\n")

            f.write("### json_completo (estrazione integrale del LLM)\n\n")
            try:
                parsed = json.loads(b["json_completo"])
                f.write("```json\n")
                f.write(json.dumps(parsed, indent=2, ensure_ascii=False))
                f.write("\n```\n\n")
            except Exception as e:
                f.write(f"_Errore nel parsing JSON: {e}_\n\n")
                f.write("```\n" + str(b["json_completo"])[:3000] + "\n```\n\n")

            f.write("---\n\n")

    print(f"Fatto. Esportati {len(bandi)} bandi (su {totale} totali) e {len(clienti)} clienti in {OUTPUT_FILE}")
    print("Carica quel file in chat.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
