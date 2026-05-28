# PROMPT_LOG — Bandi Scanner

Registro iterazioni del prompt di estrazione (`prompts/system_extraction.md`), test sui PDF e modifiche al flusso AI.

**RF coperti:** RF-002 (date `YYYY-MM-DD`), RF-004 (estrazione PDF), RF-007 (revisione manuale >50% null).

---

## Prompt di sistema — file e versioni

| Versione | Data | File | Descrizione |
|----------|------|------|-------------|
| 1.0 | 2026-05-21 | `prompts/system_extraction.md` | Schema piatto iniziale, prompt inline poi esternalizzato |
| 1.1 | 2026-05-21 | idem | Istruzioni esplicite su `data_scadenza` YYYY-MM-DD; rimosso “lascia vuoto se incerto” troppo permissivo |
| 2.0 | 2026-05-21 | idem | Schema annidato `{"bando": {...}}`, vincoli Melanie (solo testo, `null`, `attivita_ammesse`, `note_esclusioni`, strategia di analisi) |

**Modello API:** `claude-sonnet-4-6` · **max_tokens:** 4000 · **Retry:** 3 tentativi, 300 s tra un tentativo e l’altro (`tenacity`).

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

- **Modifica:** Output obbligatorio `{"bando": { ... }}` con campi rinominati:
  - `codici_ateco_ammessi`, `regioni_ammesse`, `link_fonte_ufficiale`
  - `attivita_ammesse`, `note_esclusioni`, `data_pubblicazione`
  - `dimensione_impresa` come oggetto `{micro, piccola, media, grande}`
- **Vincoli:** Estrarre solo dal testo; assenti → `null`; non inventare ATECO/attività; strategia in 4 passi (beneficiari → spese → date → massimali).
- **Motivo:** Allineamento a schema di output definitivo nel Breakdown/spec.
- **Codice collegato:** `modules/schema.py` (`normalize_response`), `modules/validator.py`, `prompts/system_extraction.md`.

### Ottimizzazione costi API

- **Modifica UI:** L’upload PDF estrae solo testo (gratis); la chiamata Claude avviene solo con il pulsante **“Estrai dati bando con AI”**.
- **Motivo:** Evitare ~0,05 € per ogni caricamento accidentale.

---

## Test PDF — `data/test_pdfs/`

| File | Estrazione testo (PyMuPDF) | Note |
|------|----------------------------|------|
| **Semplice.pdf** | OK (~43.667 caratteri) | Scadenze spesso relative (“entro X giorni”) → `data_scadenza` può restare `null` anche con inferenza |
| **Complesso.pdf** | OK (~204.782 caratteri) | Date esplicite `16/04/2026` nel testo; inferenza locale → `2026-04-16` se Claude non compila |

### Semplice.pdf — estrazioni con AI (schema v1, 2026-05-21)

- **Campi OK:** `titolo`, `ente`, `ateco_aperto_a_tutti`, `regioni`, `dimensione_impresa`, `contributo_max`, `percentuale_fondo_perduto`, `spese_ammissibili`, `link_fonte`
- **Null/vuoti:** `data_scadenza`, `codici_ateco`, `fatturato_min`, `fatturato_max`
- **Validazione:** 1 errore (campo obbligatorio `data_scadenza`), ~31% campi vuoti
- **Causa probabile:** Scadenza non espressa come data assoluta nel testo

### Complesso.pdf — da ritestare con schema v2.0

- **Atteso:** `bando.data_scadenza` = `2026-04-16` (da testo o da Claude)
- **Rischio:** Troncamento testo a 120.000 caratteri prima della chiamata API → porzioni finali del PDF non inviate al modello

---

## Casi anomali documentati

| Caso | Comportamento sistema | Azione consigliata |
|------|----------------------|-------------------|
| PDF solo immagini (scan) | `EmptyPDFException` (<100 caratteri) | OCR in Fase 5 / verificare fonte testuale |
| JSON con markdown ```json | Pulizia in `_clean_json_response()` | — |
| Claude lascia `data_scadenza` null ma data nel PDF | `date_infer` + warning in UI | Verificare manualmente su documento |
| Bando “aperto a tutti i settori” | Prompt: `ateco_aperto_a_tutti: true`, `codici_ateco_ammessi: []` | Validatore segnala se lista ATECO non vuota |
| ATECO descritti a parole, non codici | Spesso `codici_ateco_ammessi: []` o `null` | Eventuale post-processing o nota in `note_esclusioni` |
| Date “entro 60 giorni dalla pubblicazione” | `null` o solo `data_pubblicazione` se esplicita | Revisione manuale (RF-007) |

---

## Moduli collegati al prompt

| Modulo | Ruolo |
|--------|--------|
| `prompts/system_extraction.md` | Istruzioni e schema per Claude |
| `modules/extractor.py` | Caricamento prompt, API, parsing JSON |
| `modules/validator.py` | Formato, logica date, RF-007 |
| `modules/date_infer.py` | Fallback `data_scadenza` dal testo grezzo |
| `modules/schema.py` | Schema e `normalize_response()` |
| `modules/log_utils.py` | Append automatico voci sotto (runtime) |
| `scripts/test_phase1.py` | Test batch: `python scripts/test_phase1.py [--with-api]` |

---

## Scoring matching (Fase 3)

| Data | Modifica |
|------|----------|
| 2026-05-21 | Implementazione `calculate_score` in `modules/matcher.py`: regione 30, ATECO 40 (20 se solo prefisso 2 cifre), dimensione 20, fatturato 10. Regioni vuote o `"tutte"` → pieno; dimensione vuota → pieno; `ateco_aperto_a_tutti` → pieno ATECO. |
| 2026-05-21 | Match su `attivita_ammesse`: senza codici ATECO nel bando, punteggio settore 15 (incerto) / 15 (1 parola) / 30 (≥2 parole) vs `descrizione_attivita` cliente; flag dashboard *compatibilità settore da verificare*. Ricalcolo match al salvataggio cliente (`run_matching_for_all_bandi`). |

---

## Prossimi passi (log)

- [ ] Ritestare **Complesso.pdf** e **Semplice.pdf** con schema v2.0 e registrare esito campo per campo
- [ ] Aggiungere 1–3 PDF al test set (obiettivo 3–5 file, task 1.7)
- [ ] Dopo Fase 3: annotare qui eventuali aggiustamenti prompt per ATECO/massimali

---

*Le voci con timestamp generate da `app.py` o `scripts/test_phase1.py --with-api` vengono aggiunte automaticamente in fondo a questo file durante l’uso.*

### Semplice.pdf — 2026-05-21 17:46:13
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni
- **Campi null/vuoti:** bando.data_scadenza, bando.codici_ateco_ammessi, bando.regioni_ammesse, bando.fatturato_max
- **Note:** Validazione: 0 errori, 27% campi vuoti

### Semplice.pdf — 2026-05-21 17:53:14
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni
- **Campi null/vuoti:** bando.data_scadenza, bando.codici_ateco_ammessi, bando.regioni_ammesse, bando.fatturato_max
- **Note:** Validazione: 0 errori, 27% campi vuoti

### Semplice.pdf — 2026-05-21 19:11:10
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni
- **Campi null/vuoti:** bando.data_scadenza, bando.codici_ateco_ammessi, bando.regioni_ammesse, bando.fatturato_max
- **Note:** Validazione: 0 errori, 27% campi vuoti

### Semplice.pdf — 2026-05-28 17:00:24
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni
- **Campi null/vuoti:** bando.data_scadenza, bando.codici_ateco_ammessi, bando.regioni_ammesse, bando.fatturato_max
- **Note:** Validazione: 0 errori, 27% campi vuoti

### Complesso.pdf — 2026-05-28 18:11:47
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.data_scadenza, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.regioni_ammesse, bando.dimensione_impresa, bando.fatturato_max, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni
- **Campi null/vuoti:** bando.codici_ateco_ammessi
- **Note:** Validazione: 1 errori, 7% campi vuoti
