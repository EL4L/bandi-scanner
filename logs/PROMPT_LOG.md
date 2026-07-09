# PROMPT_LOG — Bandi Scanner

Registro iterazioni del prompt di estrazione (`prompts/system_extraction.md`), test sui PDF e modifiche al flusso AI.

**RF coperti:** RF-002 (date `YYYY-MM-DD`), RF-004 (estrazione PDF), RF-007 (revisione manuale >50% null), RF-005 (match e vincoli settoriali negativi).

---

## Prompt di sistema — file e versioni

| Versione | Data | File | Descrizione |
|----------|------|------|-------------|
| 1.0 | 2026-05-21 | `prompts/system_extraction.md` | Schema piatto iniziale, prompt inline poi esternalizzato |
| 1.1 | 2026-05-21 | idem | Istruzioni esplicite su `data_scadenza` YYYY-MM-DD; rimosso “lascia vuoto se incerto” troppo permissivo |
| 2.0 | 2026-05-21 | idem | Schema annidato `{"bando": {...}}`, vincoli Melanie (solo testo, `null`, `attivita_ammesse`, `note_esclusioni`, strategia di analisi) |
| 3.0 | 2026-06-03 | idem | Destrutturazione `note_esclusioni` in dict JSON (liste ATECO/attività); Regole logiche booleane rigide per `ateco_aperto_a_tutti`. |
| 3.1 | 2026-07-02 | idem | Aggiunto campo `spesa_massima_ammissibile` (tetto massimo spesa per singolo progetto, distinto da `contributo_max`); aggiornato esempio JSON di schema e aggiunta regola esplicita in "Regole Rigide". Sincronizzato con `BANDO_SCHEMA` in `modules/schema.py`. **Nota (2026-07-04):** aggiunte, come integrazione alla stessa versione 3.1, le sezioni "Gestione Ambiguità" (settori esclusi vs ammessi, percentuale fondo perduto implicita, più date di scadenza) ed "Esempi di casi edge" (2 esempi completi) in `prompts/system_extraction.md`. |

**Modello API:** `deepseek/deepseek-v4-flash` via OpenRouter (fallback `claude-haiku-4-5-20251001`) · **Retry:** 3 tentativi, intervallo configurabile via `LLM_RETRY_WAIT_SECONDS` (default 60 s) (`tenacity`).

---

## Iterazioni prompt (dettaglio)

### v1.0 — Fase 1 iniziale
- **Modifica:** Creazione struttura progetto; prompt con schema JSON piatto (`titolo`, `ente`, `data_scadenza`, `codici_ateco`, …).
- **Motivo:** Completare task 1.4 Breakdown (estrazione bandi da PDF).
- **Codice collegato:** `modules/extractor.py`, `modules/validator.py`.

### v1.1 — Rafforzamento date (RF-002)
- **Modifica:** Prompt richiede conversione date in `YYYY-MM-DD`; validatore accetta solo ISO dopo normalizzazione.
- **Motivo:** `data_scadenza` spesso vuota nonostante date nel PDF.
- **Codice collegato:** `modules/date_infer.py` (fallback locale da testo PDF se Claude lascia `null`).

### v2.0 — Schema `bando` annidato (spec Progetto Melanie)
- **Modifica:** Output obbligatorio `{"bando": { ... }}` con campi rinominati.
- **Vincoli:** Estrarre solo dal testo; assenti → `null`; non inventare ATECO/attività; strategia in 4 passi.
- **Motivo:** Allineamento a schema di output definitivo nel Breakdown/spec.
- **Codice collegato:** `modules/schema.py` (`normalize_response`), `modules/validator.py`, `prompts/system_extraction.md`.

### v3.0 — Validazione a vincoli negativi e Dati Strutturati (RF-005)
- **Modifica:** Aggiunta di istruzioni logiche imperative. Il campo `ateco_aperto_a_tutti` ora deve essere `false` alla minima presenza di divieti settoriali. Il campo `note_esclusioni` è passato da un riassunto testuale (`str`) a un oggetto JSON strutturato (`dict` contenente `lista_testuale`, `sezioni_ateco_escluse`, `attivita_vietate`).
- **Motivo:** Risolvere il problema logico per cui l'AI dichiarava "aperti a tutti" i bandi che non avevano una lista di ATECO ammessi, ma che prevedevano esclusioni gravissime (es. armi, tabacco, Sezioni K/L). 
- **Codice collegato:** Aggiornamento `BANDO_SCHEMA` in `modules/schema.py` (passaggio a tipo flessibile `dict`). Implementazione di alert visivi e liste puntate Markdown in `app.py`. Aggiunte keywords in `extractor.py` per ottimizzare il Chunking.

---

## Test PDF — `data/test_pdfs/`

| File | Estrazione testo (PyMuPDF) | Note |
|------|----------------------------|------|
| **Semplice.pdf** | OK (~43.667 caratteri) | Scadenze spesso relative (“entro X giorni”) → `data_scadenza` può restare `null` anche con inferenza |
| **Complesso.pdf** | OK (~204.782 caratteri) | Date esplicite `16/04/2026` nel testo; inferenza locale → `2026-04-16` se Claude non compila |
| **esclusioni.pdf** | OK | Utilizzato per validare l'architettura v3.0 sulle eccezioni ATECO |

---

## Casi anomali documentati

| Caso | Comportamento sistema | Azione consigliata |
|------|----------------------|-------------------|
| PDF solo immagini (scan) | `EmptyPDFException` (<100 caratteri) | OCR in Fase 5 / verificare fonte testuale |
| JSON con markdown ```json | Pulizia in `_clean_json_response()` | — |
| Bando con esclusioni gravi ma nessun ATECO esplicito ammesso | Prima dava `ateco_aperto_a_tutti: true` (falso positivo) | Applicata architettura v3.0: estrazione divieti strutturata in UI. |
| Date “entro 60 giorni” | `null` o solo `data_pubblicazione` se esplicita | Revisione manuale (RF-007) |

---

## Moduli collegati al prompt

| Modulo | Ruolo |
|--------|--------|
| `prompts/system_extraction.md` | Istruzioni e schema per Claude |
| `modules/extractor.py` | Caricamento prompt, API, parsing JSON, logica di Chunking |
| `modules/validator.py` | Formato, logica date, RF-007 |
| `modules/date_infer.py` | Fallback `data_scadenza` dal testo grezzo |
| `modules/schema.py` | Schema, `normalize_response()` e validazione tipi |

---

## Scoring matching (Fase 3 e Architettura v3.0)

| Data | Modifica |
|------|----------|
| 2026-05-21 | Implementazione `calculate_score` in `modules/matcher.py`: regione 30, ATECO 40 (20 se solo prefisso 2 cifre), dimensione 20, fatturato 10. |
| 2026-05-26 | Flag dashboard *compatibilità settore da verificare*. Ricalcolo dinamico match al salvataggio cliente. |
| 2026-06-03 | Integrazione logica UI per vincoli negativi: destrutturazione dict di `note_esclusioni` in `app.py` per stampare liste puntate dei divieti settoriali. |

---

*Le voci con timestamp generate da `app.py` o `scripts/test_phase1.py --with-api` vengono aggiunte automaticamente in fondo a questo file durante l’uso.*

### Semplice.pdf — 2026-05-21 17:46:13
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni
- **Campi null/vuoti:** bando.data_scadenza, bando.codici_ateco_ammessi, bando.regioni_ammesse, bando.fatturato_max
- **Note:** Validazione: 0 errori, 27% campi vuoti

### Complesso.pdf — 2026-05-26 22:27:40
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.data_scadenza, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.regioni_ammesse, bando.dimensione_impresa, bando.fatturato_max, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni
- **Campi null/vuoti:** bando.codici_ateco_ammessi
- **Note:** Validazione: 1 errori, 7% campi vuoti

### bando_ateco_specifico.pdf — 2026-05-26 22:31:00
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.regioni_ammesse
- **Campi null/vuoti:** bando.data_pubblicazione, bando.data_scadenza, bando.dimensione_impresa, bando.fatturato_max, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni
- **Note:** Validazione: 0 errori, 60% campi vuoti

### Semplice.pdf — 2026-05-28 17:00:24
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni
- **Campi null/vuoti:** bando.data_scadenza, bando.codici_ateco_ammessi, bando.regioni_ammesse, bando.fatturato_max
- **Note:** Validazione: 0 errori, 27% campi vuoti

### Complesso.pdf — 2026-05-29 17:17:01
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.data_scadenza, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.regioni_ammesse, bando.dimensione_impresa, bando.fatturato_max, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni
- **Campi null/vuoti:** bando.codici_ateco_ammessi
- **Note:** Validazione: 1 errori, 7% campi vuoti

### esclusioni.pdf — 2026-06-03 16:59:08 (Test Architettura v3.0)
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.data_scadenza, bando.attivita_ammesse, bando.ateco_aperto_a_tutti (flag corretto a FALSE), bando.regioni_ammesse, bando.dimensione_impresa, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni (dict strutturato)
- **Campi null/vuoti:** bando.codici_ateco_ammessi, bando.fatturato_max
- **Note:** Validazione: 0 errori, 13% campi vuoti. Fix di Schema e Chunking perfettamente integrati.
### tabelle_spese_ammissibili.pdf — 2026-06-03 17:33:41
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.regioni_ammesse, bando.fatturato_max, bando.percentuale_fondo_perduto
- **Note:** Validazione: 1 errori, 33% campi vuoti

### 2_tabelle_spese_ammissibili.pdf — 2026-06-06 17:27:30
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.spese_ammissibili, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Campi null/vuoti:** bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.percentuale_fondo_perduto, bando.link_fonte_ufficiale
- **Note:** Validazione: 0 errori, 33% campi vuoti

### Semplice.pdf — 2026-06-10 11:30:41
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.note_esclusioni, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.data_scadenza, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.link_fonte_ufficiale, bando.spesa_minima_ammissibile, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### Semplice.pdf — 2026-06-10 11:37:33
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_scadenza, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.spesa_minima_ammissibile, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### bando_aperto_a_tutti.pdf — 2026-06-10 11:40:44
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.ateco_aperto_a_tutti, bando.note_esclusioni, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.data_scadenza, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.dimensione_impresa, bando.fatturato_max, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.spesa_minima_ammissibile, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### tabelle_spese_ammissibili.pdf — 2026-06-10 11:42:52
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Campi null/vuoti:** bando.data_pubblicazione, bando.data_scadenza, bando.codici_ateco_ammessi, bando.regioni_ammesse, bando.fatturato_max, bando.spesa_minima_ammissibile
- **Note:** Validazione OK

### bando_regioni.pdf — 2026-06-24 17:31:45
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.ateco_aperto_a_tutti, bando.regioni_ammesse, bando.note_esclusioni, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.data_scadenza, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.dimensione_impresa, bando.fatturato_max, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.spesa_minima_ammissibile, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### bando_ateco_specifico.pdf — 2026-06-24 17:33:34
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.regioni_ammesse, bando.dimensione_impresa, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.data_scadenza, bando.fatturato_max, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### nuova_sabatini_esclusioni.pdf — 2026-06-27 19:38:42
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.data_scadenza, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.spese_ammissibili, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Campi null/vuoti:** bando.codici_ateco_ammessi, bando.regioni_ammesse, bando.fatturato_max, bando.contributo_max, bando.percentuale_fondo_perduto, bando.link_fonte_ufficiale
- **Note:** Validazione OK

### nuova_sabatini_esclusioni.pdf — 2026-06-28 00:04:57
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.spese_ammissibili, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.data_scadenza, bando.codici_ateco_ammessi, bando.regioni_ammesse, bando.fatturato_max, bando.contributo_max, bando.percentuale_fondo_perduto, bando.link_fonte_ufficiale, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### complesso_claude.pdf — 2026-06-28 00:12:03
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.regioni_ammesse, bando.dimensione_impresa, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.data_scadenza, bando.fatturato_max, bando.contributo_max, bando.link_fonte_ufficiale, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### nuova_sabatini_esclusioni.pdf — 2026-06-28 00:28:07
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Campi null/vuoti:** bando.data_scadenza, bando.codici_ateco_ammessi, bando.regioni_ammesse, bando.fatturato_max, bando.percentuale_fondo_perduto
- **Note:** Validazione OK

### complesso_claude.pdf — 2026-07-02 19:06:10
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.regioni_ammesse, bando.dimensione_impresa, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Campi null/vuoti:** bando.data_scadenza, bando.fatturato_max
- **Note:** Validazione OK

### complesso_claude.pdf — 2026-07-02 19:39:30
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.regioni_ammesse, bando.dimensione_impresa, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Campi null/vuoti:** bando.data_scadenza, bando.fatturato_max, bando.link_fonte_ufficiale
- **Note:** Validazione OK

### Bando 499 Assistenti informatici.pdf — 2026-07-07 14:46:21
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.ateco_aperto_a_tutti, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.data_scadenza, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.dimensione_impresa, bando.fatturato_max, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### 2_tabelle_spese_ammissibili.pdf — 2026-07-08 10:11:16
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.data_scadenza, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Campi null/vuoti:** bando.codici_ateco_ammessi, bando.regioni_ammesse, bando.fatturato_max, bando.percentuale_fondo_perduto, bando.spesa_massima_ammissibile
- **Note:** Validazione OK

### bando.pdf — 2026-07-08 10:24:50
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### prompts/system_extraction.md — v3.2 — 2026-07-08 16:14:06
- **Campi estratti correttamente:** contributo_max
- **Campi null/vuoti:** —
- **Note:** Corretta la regola contributo_max: ora si calcola da spesa_massima_ammissibile × percentuale_fondo_perduto invece di copiare il massimale spese; istruzione esplicita a non usare il massimale spese come proxy del contributo (intervento #2 ROADMAP).

### modules/date_infer.py — logica di inferenza post-estrazione — 2026-07-08 16:14:06
- **Campi estratti correttamente:** data_scadenza (date in lettere), guardia sportello continuo
- **Campi null/vuoti:** —
- **Note:** Rimosso il fallback che sceglieva la data futura più lontana nel testo senza contesto (rischio di estrarre milestone PNRR o termini di rendicontazione al posto della scadenza domande). Aggiunto riconoscimento date in formato testuale italiano ("31 dicembre 2026") e guardia per misure a sportello continuo/permanenti, che ora restituiscono None invece di una data inventata (intervento #3 ROADMAP).

### modules/extractor.py + prompts/system_extraction.md — 2026-07-09 11:45:48
- **Campi estratti correttamente:** delimitatori <bando_text>, sanitizzazione tag chiusura iniettati, istruzione anti-injection nel prompt
- **Campi null/vuoti:** —
- **Note:** Aggiunti _sanitize_delimiters() e wrapping <bando_text>...</bando_text> in _load_system_prompt(); il template del prompt spiega esplicitamente che il testo delimitato non e mai unistruzione (ROADMAP #10)

### bando.pdf — 2026-07-09 11:48:21
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### main.py + frontend/src/components/Dashboard.tsx — 2026-07-09 11:48:57
- **Campi estratti correttamente:** _dedupe_cards() con merge match, duplicates_count nel payload /api/dashboard
- **Campi null/vuoti:** —
- **Note:** Dedup client-side sostituita da dedup server-side che fonde i match dei bandi duplicati invece di scartarli (ROADMAP #11)

### bando.pdf — 2026-07-09 11:51:42
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### bando.pdf — 2026-07-09 11:52:26
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### main.py + frontend/src/components/Clienti.tsx — 2026-07-09 11:53:02
- **Campi estratti correttamente:** ammissibilita in /api/clienti/{id}/bandi, fonte_url in /api/clienti/{id}/bandi, azioni Scheda/Fonte per riga nel modal Clienti
- **Campi null/vuoti:** —
- **Note:** Coerenza tra Dashboard e Clienti sul verdetto di ammissibilita di un match (ROADMAP #12)

### bando.pdf — 2026-07-09 11:56:09
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### bando.pdf — 2026-07-09 11:57:07
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### modules/matcher.py + main.py + frontend/src/components/{Dashboard,Clienti}.tsx — 2026-07-09 11:59:03
- **Campi estratti correttamente:** bando_ambiguo(), breakdown.status, badge Da verificare in Dashboard e Clienti, attivita_ammesse in bando_has_constraints
- **Campi null/vuoti:** —
- **Note:** Fase 2 (P1) della ROADMAP completata: interventi #7-#13 tutti implementati e testati (ROADMAP #13)

### bando.pdf — 2026-07-09 15:28:46
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### modules/matcher.py + frontend/src/components/ClienteFormModal.tsx — 2026-07-09 16:20:00
- **Campi estratti correttamente:** SOGLIE_DIMENSIONE_UE, valida_coerenza_dimensione(), SOGLIE_UE, validaDimensione()
- **Campi null/vuoti:** —
- **Note:** Non riguarda l'estrazione LLM: aggiunta validazione di coerenza tra `dimensione_impresa` del cliente e le soglie dimensionali UE (dipendenti/fatturato), sia server-side (`modules/matcher.py`) sia client-side nel form clienti. Include soglia `dip_min=250` per "grande". Test in `tests/test_dimensione_ue.py` (8 casi, tutti verdi).

### main.py + frontend/src/components/ClienteFormModal.tsx — 2026-07-09 16:35:00
- **Campi estratti correttamente:** _validate_cliente_form() ora chiama valida_coerenza_dimensione(), validazione dimErrors in tempo reale (useMemo) con bottone Salva disabilitato
- **Campi null/vuoti:** —
- **Note:** Completamento intervento precedente: `valida_coerenza_dimensione()` era isolata e non collegata a nessun endpoint. Ora `POST/PUT /api/clienti` rifiuta con 400 un cliente con dimensione incoerente rispetto a dipendenti/fatturato. Lato client la validazione non è più solo al submit ma ricalcolata ad ogni modifica di dimensione/dipendenti/fatturato, disabilitando il bottone Salva finché incoerente. Aggiunti 3 test di integrazione in `tests/test_dimensione_ue.py` (11 totali, tutti verdi).

### bando.pdf — 2026-07-09 16:20:40
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### bando.pdf — 2026-07-09 16:21:29
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK
