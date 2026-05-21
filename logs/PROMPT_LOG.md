# PROMPT_LOG — Estrazione bandi

Registro delle estrazioni e dei test Fase 1. Ogni upload o esecuzione di `scripts/test_phase1.py --with-api` aggiunge una voce sotto.

## Prompt di sistema

- **File:** `prompts/system_extraction.md`
- **Versione:** 2.0 (Fase 1)
- **Modifiche:** schema annidato `{"bando": {...}}`, nuovi campi (attivita_ammesse, note_esclusioni, dimensione_impresa oggetto), `null` per dati assenti

## Iterazioni prompt

| Data | Versione | Modifica | Motivo | Risultato test |
|------|----------|----------|--------|----------------|
| 2026-05-21 | 1.0 | Prompt esterno con schema e regole RF-002 | Completamento Fase 1 | Eseguire test su PDF in `data/test_pdfs/` |
| 2026-05-21 | 2.0 | Schema `bando` annidato + vincoli estrazione solo da testo | Allineamento spec Melanie | Ritestare Semplice/Complesso |

## Estrazioni / test PDF

<!-- Le voci vengono aggiunte automaticamente da app.py e scripts/test_phase1.py -->

### Semplice.pdf — 2026-05-21 10:17:40
- **Campi estratti correttamente:** titolo, ente, ateco_aperto_a_tutti, regioni, dimensione_impresa, contributo_max, percentuale_fondo_perduto, spese_ammissibili, link_fonte
- **Campi null/vuoti:** data_scadenza, codici_ateco, fatturato_min, fatturato_max
- **Note:** Validazione: 1 errori, 31% campi vuoti

### Semplice.pdf — 2026-05-21 10:51:31
- **Campi estratti correttamente:** titolo, ente, ateco_aperto_a_tutti, regioni, dimensione_impresa, contributo_max, percentuale_fondo_perduto, spese_ammissibili, link_fonte
- **Campi null/vuoti:** data_scadenza, codici_ateco, fatturato_min, fatturato_max
- **Note:** Validazione: 1 errori, 31% campi vuoti

### Semplice.pdf — 2026-05-21 11:01:45
- **Campi estratti correttamente:** titolo, ente, ateco_aperto_a_tutti, regioni, dimensione_impresa, contributo_max, percentuale_fondo_perduto, spese_ammissibili, link_fonte
- **Campi null/vuoti:** data_scadenza, codici_ateco, fatturato_min, fatturato_max
- **Note:** Validazione: 1 errori, 31% campi vuoti

### Semplice.pdf — 2026-05-21 11:44:46
- **Campi estratti correttamente:** bando.titolo, bando.ente, bando.data_pubblicazione, bando.attivita_ammesse, bando.ateco_aperto_a_tutti, bando.dimensione_impresa, bando.contributo_max, bando.percentuale_fondo_perduto, bando.spese_ammissibili, bando.link_fonte_ufficiale, bando.note_esclusioni
- **Campi null/vuoti:** bando.data_scadenza, bando.codici_ateco_ammessi, bando.regioni_ammesse, bando.fatturato_max
- **Note:** Validazione: 0 errori, 27% campi vuoti
