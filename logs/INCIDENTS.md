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
| 2026-05-26 | Matching restituisce 100% per tutti i clienti su bando privo di vincoli (es. `Semplice.pdf`) | Dashboard con falsi positivi; possibile invio di alert errati | Logica precedente assegnava pesi pieni per dimensione/fatturato/regioni per default quando il bando non specificava vincoli | Introdotta `_bando_has_constraints` e wrapper `bando_has_constraints`; se bando vuoto o senza vincoli ora score=0 e log diagnostico; cambiati default di `_score_dimensione` e `_score_fatturato` per non assegnare peso pieno se campo assente |
| 2026-05-26 | Discrepanze tra score salvati in DB e ricalcolo dinamico (breakdown) | Visualizzazione incoerente in dashboard, confusione operativa | Score salvati in `match_results` erano prodotti da logiche precedenti e/o breakdown costruito con dati parziali | Aggiornata UI per calcolare breakdown usando il record cliente completo dal DB; aggiunto warning e pulsante per ricalcolo matching; script `scripts/simulate_matching.py` per debug |
2026-05-31 | API provider (DeepSeek/OpenRouter) instabile e in timeout multiplo | Blocco dei test di estrazione AI in UI | Disservizio lato server OpenRouter (Connection Error) | Aggiunto mock manuale di JSON temporaneo per continuare sviluppo UI. Migrazione a provider stabile completata. |
| 2026-05-31 | Risoluzione Incidente O-01 (Troncamento PDF severo) | Perdita di data di scadenza ed esclusioni nei bandi >40 pag. | La funzione `_truncate_text` scartava i paragrafi se le keywords non combaciavano esattamente. | Implementato chunking intelligente in `extractor.py`: ampliate le keywords (`"termin"`, `"domanda"`, `"presentazione"`, `"esclusion"`). |
| 2026-06-03 | Crash del `Validator` per Schema Mismatch | Blocco app: `Tipo non valido per bando.note_esclusioni` | Il prompt è stato migliorato per restituire un JSON Strutturato (`dict`), ma `schema.py` richiedeva ancora `str`. | Aggiornato `BANDO_SCHEMA` per accettare formati flessibili: `(dict, str, type(None))`. |
| 2026-06-03 | Falsi positivi sul Matching ATECO (Risoluzione parziale O-03) | Score 100% per clienti con settori vietati | Claude impostava `ateco_aperto_a_tutti: true` in mancanza di elenchi positivi, ignorando i divieti. | Regola rigida introdotta nel prompt. Logica UI modificata per intercettare le esclusioni e stampare alert/liste puntate in dashboard. |
| 2026-06-25 | Query N+1 nel rendering della Dashboard | Una `SELECT * FROM clienti WHERE id = ?` eseguita ad ogni iterazione del loop sui match (per ogni cliente, per ogni bando), invece di un'unica query | `load_dashboard_rows()` in `modules/matcher.py` non includeva `regione`/`fatturato`/`dimensione_impresa` del cliente, costringendo `app.py` a una query aggiuntiva per riga dentro l'expander "Vedi Clienti Compatibili" | Estesa la JOIN in `load_dashboard_rows()` per includere `c.regione`, `c.fatturato`, `c.dimensione_impresa`; rimossa la query per-riga in `app.py`, ora i dati cliente sono letti direttamente dalla riga già caricata |
| 2026-06-25 | `ModuleNotFoundError: openai` all'avvio dell'app | App in crash all'apertura della pagina (`modules/extractor.py` importa `openai`) | Package `openai` non installato nel venv e assente da `requirements.txt`, nonostante l'uso nel codice | Installato `openai` nel venv (`pip install openai`) e aggiunto a `requirements.txt` |
| 2026-06-25 | Predisposizione deploy su Render | `db/bandi.db` su path hardcoded relativo al progetto, incompatibile con filesystem effimero di Render | Nessuna astrazione del path DB tramite env var; nessun Dockerfile/render.yaml nel repo | Aggiunta variabile `DB_PATH` (override in `modules/database.py`, fallback al path locale esistente); creati `Dockerfile`, `render.yaml` (Persistent Disk su `/var/data`) e `.dockerignore`. Superato dalla migrazione a Neon (riga successiva) |
| 2026-06-25 | Migrazione da SQLite a Postgres (Neon) | Su Render senza disco persistente (piano Free) i dati in SQLite venivano persi ad ogni redeploy/restart del container | Filesystem del container effimero; SQLite scrive su file locale al container | Riscritti `db/init_db.py` (schema Postgres: `SERIAL`, `TIMESTAMP DEFAULT NOW()`, `information_schema` per migrazioni) e `modules/database.py` (driver `psycopg2`, wrapper `_PGConnection` compatibile con l'API `conn.execute(...)` esistente, placeholder `?`→`%s`, `RETURNING id` al posto di `lastrowid`); adattate query in `modules/matcher.py` (`datetime('now')`→`NOW()`, `COLLATE NOCASE`→`LOWER(...)`). Richiede env var `DATABASE_URL` (connection string Neon). `render.yaml` aggiornato: piano `free`, niente Persistent Disk. Testato end-to-end in locale contro Neon: init schema, insert/select/delete cliente, query dashboard — tutti OK |

---

## Incidenti noti ancora aperti

| ID | Problema | Workaround |
|----|----------|------------|
| O-02 | **Semplice.pdf**: scadenze solo relative | `data_scadenza` = `null` corretto; revisione manuale |
| O-03 | Integrazione logica DB su Esclusioni ATECO | Gestione visiva (UI) implementata. Necessario completare task 4.1 per l'abbattimento automatico dello score in presenza di `ateco_escluse` strutturate. |
 |



---

## File di log correlati

- `error_log.txt` — errori runtime append-only (API, PDF, salvataggio)
- `logs/PROMPT_LOG.md` — versioni prompt e risultati test PDF

---
