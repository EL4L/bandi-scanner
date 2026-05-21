# INCIDENTS — Bandi Scanner

Registro incidenti tecnici: problema, impatto, causa, fix applicato.

| Data | Descrizione | Impatto | Causa | Fix |
|------|-------------|---------|-------|-----|
| 2026-05-21 | Contenuto log copiato da altro progetto (MLPG) | `PROMPT_LOG.md` / `INCIDENTS.md` non riflettevano bandi-scanner | File template errati nella cartella `logs/` | Sostituzione completa con documentazione bandi-scanner |
| 2026-05-21 | API key esposta in `.env.example` | Rischio sicurezza se committata su Git | Chiave reale inserita per errore nel template | Sostituita con `ANTHROPIC_API_KEY=` vuoto; ruotare chiave su console Anthropic se già pushata |
| 2026-05-21 | `test_phase1.py` non trova PDF | Test Fase 1 fallito con messaggio “Nessun PDF” | PDF in `data/` ma script legge solo `data/test_pdfs/` | Copia PDF in `data/test_pdfs/` (`Complesso.pdf`, `Semplice.pdf`) |
| 2026-05-21 | `streamlit` / `python` non riconosciuti in PowerShell | Impossibile avviare app da terminale | venv non attivato o PATH senza Scripts | `.\venv\Scripts\Activate.ps1` oppure `.\venv\Scripts\streamlit.exe run app.py` |
| 2026-05-21 | `Activate.ps1` bloccato | Errore ExecutionPolicy | Policy script disabilitata su Windows | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| 2026-05-21 | Typo comando (`stremalit`, `treamlit`) | Comando non trovato | Errore battitura | Usare `streamlit run app.py` |
| 2026-05-21 | `data_scadenza` vuota in UI nonostante data nel PDF | RF-002 non soddisfatto; utente vede campo null | Prompt troppo prudente (“usa \"\" se non certo”); Claude non estrae; PDF lunghi troncati | Prompt v1.1/v2.0; modulo `date_infer.py`; inferenza post-estrazione in `validate_bando()` |
| 2026-05-21 | Costo API a ogni upload PDF | ~0,05 € per caricamento | `extract_bando_data()` chiamata automaticamente dopo upload | Estrazione AI solo su pulsante dedicato in `app.py` |
| 2026-05-21 | JSON Claude non parsabile | Estrazione fallita, `InvalidJSONResponse` | Risposta con markdown o testo extra | `_clean_json_response()` rimuove fence ```json |
| 2026-05-21 | API Anthropic down / rate limit | Estrazione bando fallita dopo attesa | Errore rete o 5xx | Retry 3× con attesa 300 s (`tenacity`); log su `error_log.txt` e riga in questo file |
| 2026-05-21 | PDF illeggibile (scan senza testo) | Messaggio errore upload | Testo estratto <100 caratteri | `EmptyPDFException` + messaggio UI; mitigazione futura: OCR (Fase 5) |
| 2026-05-21 | Validatore non collegato all’app (Fase 1 iniziale) | JSON mostrato senza warning RF-007 | `validate_bando()` non importato in `app.py` | Integrazione validazione + warning “Da revisionare manualmente” |
| 2026-05-21 | Schema JSON cambiato (v2 `bando`) | Log e test vecchi con nomi campo obsoleti (`link_fonte`, `codici_ateco`) | Migrazione schema Melanie | `modules/schema.py`, prompt 2.0, validatore aggiornato |
| 2026-05-21 | Progetto spostato su disco locale | Possibile venv rotto / path errati | Spostamento cartella da sync cloud | Verificare `cd` su `C:\bandi-scanner` o percorso attuale; ritestare `venv\Scripts\python.exe` |
| 2026-05-21 | `ModuleNotFoundError: anthropic` fuori venv | Script test fallito | Python di sistema invece del venv | Usare `.\venv\Scripts\python.exe scripts\test_phase1.py` |

---

## Incidenti noti ancora aperti

| ID | Problema | Workaround |
|----|----------|------------|
| O-01 | PDF **Complesso** troncati a 120k caratteri in API | Estrazione mirata sezioni “scadenza” o aumento limite con attenzione ai costi |
| O-02 | **Semplice.pdf**: scadenze solo relative | `data_scadenza` = `null` corretto; revisione manuale |
| O-03 | Accuratezza ATECO / massimale non verificata al 95% | Completare task 4.1 Breakdown su 3–5 PDF |

---

## File di log correlati

- `error_log.txt` — errori runtime append-only (API, PDF, salvataggio)
- `logs/PROMPT_LOG.md` — versioni prompt e risultati test PDF

---

## Fase 2 — Profilo cliente (RF-001)

| Data | Descrizione | Impatto | Causa | Fix |
|------|-------------|---------|-------|-----|
| 2026-05-21 | DB non inizializzato | Salvataggio clienti fallito | `init_db.py` era stub | Implementato schema `clienti`, `bandi`, `match_results` in `db/init_db.py`; `ensure_database()` all’avvio app |

---

*Aggiornare questa tabella a ogni bug risolto o comportamento anomalo osservato in produzione/test.*
