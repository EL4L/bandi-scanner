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

### bando.pdf — 2026-07-09 17:06:29
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.anzianita_impresa
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### bando.pdf — 2026-07-10 15:54:05
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### bando.pdf — 2026-07-10 16:51:22
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### esempio.it — 2026-07-10 16:51:22
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### esempio.it — 2026-07-10 16:51:22
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### bando.pdf — 2026-07-10 16:53:05
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### esempio.it — 2026-07-10 16:53:05
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### esempio.it — 2026-07-10 16:53:05
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### bando.pdf — 2026-07-10 16:54:17
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### esempio.it — 2026-07-10 16:54:18
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### esempio.it — 2026-07-10 16:54:18
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### bando.pdf — 2026-07-10 17:35:03
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.modalita_presentazione, bando.tipo_agevolazione, bando.cumulabilita, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### esempio.it — 2026-07-10 17:35:03
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.modalita_presentazione, bando.tipo_agevolazione, bando.cumulabilita, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

---

## Registro interazioni di sviluppo

Questa sezione registra le interazioni tra la persona utente e gli assistenti AI. Gli orari indicano il fuso `Europe/Rome`. Quando l'orario originale del messaggio non è esposto dall'interfaccia, viene riportato l'orario di registrazione e la voce è marcata come retroattiva. Le esecuzioni automatiche del prompt possono essere intercalate perché `log_prompt_run()` appende sempre a fine file; i record conversazionali sono identificati in modo univoco dal prefisso `INT-`.

### INT-20260710-001 — 2026-07-10 18:42:21 +02:00
- **Persona/autore:** Utente (persona umana; nome non dichiarato)
- **Modello:** —
- **Tipo:** Richiesta
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Richiesto audit completo del progetto per knowledge base e validazione, diagnosi del caricamento infinito della dashboard mostrato nello screenshot e verifica delle ultime modifiche attribuite a Claude Code. Richiesto inoltre di registrare metodicamente ogni interazione nel prompt log con data, ora, modello e persona/autore, e di fermarsi per chiedere conferma in caso di dubbi.

### INT-20260710-002 — 2026-07-10 18:42:21 +02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Risposta operativa
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Avviato audit conservativo e read-only: ricostruzione di struttura, cronologia, avvio, prompt log e causa del caricamento infinito; dichiarato che ogni scelta potenzialmente invasiva sarebbe stata sottoposta prima all'utente.

### INT-20260710-003 — 2026-07-10 18:42:21 +02:00
- **Persona/autore:** Utente (persona umana; nome non dichiarato)
- **Modello:** —
- **Tipo:** Richiesta di stato
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** «Stai ancora lavorando in background?»

### INT-20260710-004 — 2026-07-10 18:42:21 +02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Aggiornamento di stato
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Confermata l'attività in corso; segnalati modifiche locali non committate, inclusi Dashboard.tsx e PROMPT_LOG.md, e il commit di migrazione a React Query del 10 luglio come primo candidato da verificare. Confermato che non era ancora stato modificato alcun file.

### INT-20260710-005 — 2026-07-10 18:42:21 +02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Aggiornamento metodologico
- **Registrazione:** Contestuale
- **Contenuto:** Verificato che PROMPT_LOG.md era dedicato alle esecuzioni del prompt di estrazione; adottata una sezione separata nello stesso file per registrare le conversazioni senza alterare lo storico.

### esempio.it — 2026-07-10 17:35:03
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.modalita_presentazione, bando.tipo_agevolazione, bando.cumulabilita, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### INT-20260710-006 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Aggiornamento diagnostico
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Identificato che lo spinner React Query può restare attivo su una richiesta pending e avviata verifica di processi, porte, backend e database per distinguere frontend da API sospesa.
- **Azioni/esito:** Nessun listener iniziale sulle porte 5173/5174/8000; fetch senza timeout confermata.

### INT-20260710-007 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Utente (persona umana; nome non dichiarato)
- **Modello:** —
- **Tipo:** Approvazione tramite popup
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Autorizzato test read-only `SELECT 1` verso il database Neon, con timeout di 5 secondi.
- **Azioni/esito:** DB raggiungibile; risposta in circa 1,09 secondi.

### INT-20260710-008 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Aggiornamento diagnostico
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Escluso un guasto attuale di Neon e segnalata la dipendenza `trafilatura` dichiarata ma non installata nel venv locale come causa candidata primaria.
- **Azioni/esito:** `venv\\Scripts\\python.exe -c "import main"` ha riprodotto `ModuleNotFoundError: trafilatura`.

### INT-20260710-009 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Diagnosi causa radice
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Correlato il crash al commit `1fae20c`, co-firmato Claude Sonnet 5: nuovo import top-level di `url_extractor` e venv non sincronizzato. Richiesta autorizzazione prima di modificare l'ambiente locale.

### INT-20260710-010 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Utente (persona umana; nome non dichiarato)
- **Modello:** —
- **Tipo:** Approvazione tramite popup
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Autorizzata sincronizzazione del venv tramite `venv\\Scripts\\python.exe -m pip install -r requirements.txt`.
- **Azioni/esito:** Installata `trafilatura==2.1.0` con dipendenze transitive.

### INT-20260710-011 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Aggiornamento validazione
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Confermata la sincronizzazione e avviati import backend, suite Python, build e lint per distinguere la rottura ambientale da regressioni del codice.

### INT-20260710-012 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Nuovo finding bloccante
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Scoperto che `trafilatura -> jusText -> lxml 6.1.1` richiede anche `lxml_html_clean`, non presente in requirements e non rilevato da `pip check`. Richiesta nuova autorizzazione.

### INT-20260710-013 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Utente (persona umana; nome non dichiarato)
- **Modello:** —
- **Tipo:** Approvazione tramite popup
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Autorizzata installazione diagnostica di `lxml_html_clean` nel venv.
- **Azioni/esito:** Installata versione 0.4.5; `import main` successivamente riuscito.

### INT-20260710-014 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Aggiornamento validazione
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Rieseguiti import, pytest, build e lint. La prima esecuzione ha separato errori reali da errori dovuti al sandbox in sola lettura.
- **Azioni/esito:** Import riuscito; lint 0 errori/5 warning; test/build da ripetere con scrittura temporanea.

### INT-20260710-015 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Spiegazione richiesta permessi
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Spiegato che 7 failure e 4 error pytest dipendevano dai divieti di scrittura su file temporanei, mentre 263 test erano già passati; la build era bloccata solo sui file incrementali TypeScript.

### INT-20260710-016 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Utente (persona umana; nome non dichiarato)
- **Modello:** —
- **Tipo:** Approvazione tramite popup
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Autorizzata suite pytest con scrittura esclusivamente temporanea.
- **Azioni/esito:** 274/274 test passati; 2 warning di deprecazione FastAPI.

### INT-20260710-017 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Utente (persona umana; nome non dichiarato)
- **Modello:** —
- **Tipo:** Approvazione tramite popup
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Autorizzata build frontend con scrittura degli artefatti TypeScript/Vite.
- **Azioni/esito:** Build di produzione completata senza errori.

### INT-20260710-018 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Proposta smoke test
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Proposto avvio backend temporaneo su porta isolata e lettura dashboard per verificare il flusso HTTP reale senza mutazioni applicative.

### INT-20260710-019 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Utente (persona umana; nome non dichiarato)
- **Modello:** —
- **Tipo:** Approvazione tramite popup
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Autorizzato primo smoke test HTTP read-only su porta 8010 con arresto automatico.
- **Azioni/esito:** Primo tentativo partito prima che l'import lento avesse aperto la porta; nessuna modifica dati.

### INT-20260710-020 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Correzione diagnostica
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Chiarito che il primo smoke test aveva atteso solo 4 secondi; proposta ripetizione con polling della porta fino a 30 secondi.

### INT-20260710-021 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Utente (persona umana; nome non dichiarato)
- **Modello:** —
- **Tipo:** Approvazione tramite popup
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Autorizzata ripetizione dello smoke test read-only con attesa controllata.
- **Azioni/esito:** HTTP 200; 11 bandi, 11 card, 55 abbinamenti; server temporaneo arrestato.

### INT-20260710-022 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Esito causa radice
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Dichiarata verificata end-to-end la causa ambientale; segnalato che il repository resta non riproducibile perché `lxml_html_clean` non è ancora in requirements. Avviato consolidamento dei finding senza fix di codice non autorizzati.

### INT-20260710-023 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Utente (persona umana; nome non dichiarato)
- **Modello:** —
- **Tipo:** Approvazione tramite popup
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Autorizzata raccolta coverage della suite pytest.
- **Azioni/esito:** 274 test passati; coverage totale 73,22%, `main.py` 65%, `db/init_db.py` 0%.

### INT-20260710-024 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Utente (persona umana; nome non dichiarato)
- **Modello:** —
- **Tipo:** Approvazione tramite popup
- **Registrazione:** Retroattiva; orario di registrazione
- **Contenuto:** Autorizzata verifica read-only delle vulnerabilità npm di produzione.
- **Azioni/esito:** `npm audit --omit=dev` ha riportato 0 vulnerabilità note.

### INT-20260711-025 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Aggiornamento audit
- **Registrazione:** Contestuale
- **Contenuto:** Consolidati finding frontend: timeout assente, errori HTTP trattati come successi, assenza test UI e regressione informativa nelle modifiche locali della dashboard.

### INT-20260711-026 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Consegna documentale in corso
- **Registrazione:** Contestuale
- **Contenuto:** Avviata creazione della knowledge base separata con baseline Git, architettura, causa, validazione, finding, runbook e piano di rimedio, senza applicare fix applicativi non autorizzati.
- **File correlato:** `AUDIT_KNOWLEDGE_BASE_2026-07-11.md`.

### INT-20260711-027 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Aggiornamento stato scrittura
- **Registrazione:** Contestuale
- **Contenuto:** Segnalata latenza OneDrive durante la materializzazione del documento e mantenuta la scrittura in corso per evitare un file parziale.
- **Azioni/esito:** Documento verificato: 338 righe, 18.664 byte.

### INT-20260711-028 — 2026-07-11T15:59:59+02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Igiene audit log
- **Registrazione:** Contestuale
- **Contenuto:** Identificati e rimossi esclusivamente i record fittizi generati dalle due suite pytest di questa sessione (timestamp 18:49 e 18:58) e i due incidenti duplicati corrispondenti, preservando lo stato preesistente.

### INT-20260711-029 — 2026-07-11T16:03:14+02:00
- **Persona/autore:** Codex (assistente AI)
- **Modello:** GPT-5 / Codex
- **Tipo:** Consegna finale
- **Registrazione:** Contestuale
- **Contenuto:** Concluso audit completo. Comunicata la causa radice (dipendenze installate nel Python globale ma assenti nel venv usato dal backend, introdotte con `1fae20c`) e il ruolo amplificatore delle richieste frontend/DB senza timeout. Confermati riallineamento locale, 274 test verdi, coverage 73,22%, build e lint, npm audit senza vulnerabilità note e smoke dashboard HTTP 200. Consegnata la knowledge base e segnalato che il fix repository resta da autorizzare.
- **File/test correlati:** `AUDIT_KNOWLEDGE_BASE_2026-07-11.md`, `logs/INCIDENTS.md`, `logs/PROMPT_LOG.md`; pytest, coverage, Vite build, oxlint, npm audit, smoke HTTP.

### bando.pdf — 2026-07-11 16:45:26
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.modalita_presentazione, bando.tipo_agevolazione, bando.cumulabilita, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### esempio.it — 2026-07-11 16:45:26
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.modalita_presentazione, bando.tipo_agevolazione, bando.cumulabilita, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### esempio.it — 2026-07-11 16:45:26
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_scadenza, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max
- **Campi null/vuoti:** bando.data_pubblicazione, bando.codici_ateco_ammessi, bando.attivita_ammesse, bando.regioni_ammesse, bando.fatturato_max, bando.numero_dipendenti_min, bando.numero_dipendenti_max, bando.percentuale_fondo_perduto, bando.modalita_presentazione, bando.tipo_agevolazione, bando.cumulabilita, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni, bando.spesa_minima_ammissibile, bando.spesa_massima_ammissibile, bando.anzianita_impresa, bando.forme_giuridiche_ammesse
- **Note:** Validazione OK

### frontend/src/components/Dashboard.tsx + frontend/src/styles.css — 2026-07-11
- **Campi estratti correttamente:** —
- **Campi null/vuoti:** —
- **Note:** Intervento solo frontend, nessun impatto sul prompt/estrazione LLM. Fix della regressione introdotta dal redesign card espandibili (commit `eac1aba`, Codex): ripristinate nella card della Dashboard la riga scadenza/giorni con badge urgenza (#6), la riga "Contributo max" e la KPI "Bandi con clienti". Reintrodotte le helper `isBlank`/`scadenzaTextClass`, aggiunta la sezione `bando-card-quick-info` sempre visibile e la relativa regola CSS; comportamento a fisarmonica preservato. `npm run build` pulito, 274 test Python invariati.
