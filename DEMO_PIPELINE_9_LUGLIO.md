# BandiScanner — Pipeline modifiche per demo del 9 luglio 2026

Generato il 2 luglio 2026. Registra tutte le modifiche pianificate e il loro stato di avanzamento.

---

## Legenda

| Simbolo | Stato |
|---------|-------|
| ✅ | Completato |
| ⬜ | Da fare |

**Priorità:** P0 = demo-breaker · P1 = alta visibilità · P2 = migliorativo · P3 = post-demo

---

## AREA 1 — BACKEND

### ✅ B1 · Dockerfile: logs/ e PORT fallback `P0`
**File:** `Dockerfile`
Aggiunto `RUN mkdir -p /app/logs` e cambiato CMD in `--port ${PORT:-8000}`.
Senza questa fix: crash al primo log nel container e possibile fallimento avvio se Render non inietta `$PORT`.

### ✅ B2 · Dashboard: caching scheda bando `P0`
**File:** `main.py` → `_dashboard_payload()`
Già implementato correttamente: `scheda_cached` usata come priorità, `genera_scheda()` solo come fallback.

### ✅ B3 · extractor.py: RETRY_WAIT_SECONDS configurabile `P0`
**File:** `modules/extractor.py`
`RETRY_WAIT_SECONDS` ora letto da env var `LLM_RETRY_WAIT_SECONDS` (default 60s).
Prima era fisso a 300s: se DeepSeek falliva durante la demo, blocco di 15 minuti.

### ✅ B4 · /api/estrazione: validazione file size server-side `P1`
**File:** `main.py` → `POST /api/estrazione`
Check `len(file_bytes) > 10_000_000` inserito subito dopo la lettura dei byte, prima di salvare su disco o chiamare il LLM. Risposta 400 con messaggio che include la dimensione effettiva del file.

### ⬜ B5 · /api/estrazione: campo bando_url nella risposta `P2`
**File:** `main.py`
Aggiungere `"bando_url": f"/bandi/{bando_id}"` nella risposta JSON.
Dipende da: F4.

### ✅ B6 · requirements.txt: pinning versioni `P2`
**File:** `requirements.txt`
Pinnate tutte le dipendenze alle versioni del venv di sviluppo (pip freeze). Riproducibilità deploy garantita.

### ✅ B7 · spesa_massima_ammissibile: aggiungere allo schema `P1`
**File:** `modules/schema.py` → `BANDO_SCHEMA`
Aggiunto `"spesa_massima_ammissibile": (int, float, type(None))` dopo `spesa_minima_ammissibile`.

### ✅ B8 · matcher.py: score 0 per bandi senza vincoli `P2`
**File:** `modules/matcher.py`
Fix: `bando_has_constraints=False` + `ateco_aperto_a_tutti=False` → score 0 (bando ambiguo/vuoto). `bando_has_constraints=False` + `ateco_aperto_a_tutti=True` → scoring normale (~100). Stessa logica in `get_score_breakdown`. Distingue bandi genuinamente aperti da bandi con dati mancanti.

---

## AREA 2 — FRONTEND

### ✅ F1 · Dashboard: rimosso limite 5 match per bando `P0`
**File:** `frontend/src/components/Dashboard.tsx` riga 274
Rimosso `.slice(0, 5)` — ora mostra tutti i clienti abbinati al bando.

### ✅ F2 · CaricaBando: rimosso blocco JSON debug `P0`
**File:** `frontend/src/components/CaricaBando.tsx`
Rimosso il blocco `<details>Raw JSON estratti (debug)</details>` visibile agli utenti.

### ✅ F3 · CaricaBando: validazione client-side file size `P1`
**File:** `frontend/src/components/CaricaBando.tsx`
Check `file.size > 10_000_000` in `handleFile()` — copre sia drag-and-drop che click. Mostra dimensione effettiva nel toast e nel banner rosso.

### ✅ F4 · CaricaBando: link al bando dopo successo upload `P1`
**File:** `frontend/src/components/CaricaBando.tsx`
Aggiunto pulsante "Vai ai Bandi →" mostrato solo dopo successo, affiancato al link "Vai alla Dashboard". I bandi sono ordinati per `id DESC` → il nuovo è in cima. Non ha richiesto B5.

### ✅ F5 · Clienti: validazione client-side P.IVA e ATECO `P1`
**File:** `frontend/src/components/Clienti.tsx`
Validazione in `handleSubmit` prima della chiamata API: P.IVA `/^\d{11}$/`, ATECO `/^\d{2}\.\d{2}(\.\d{2})?$/`. Errori mostrati in `formErrors` (banner già esistente), submit bloccato e `setSaving` non chiamato.

### ✅ F6 · Estrazione componente ModalScheda (DRY) `P2`
**File:** `frontend/src/components/ModalScheda.tsx` (nuovo)
Creato componente `ModalScheda` con `renderMarkdown` condiviso. `Dashboard.tsx` e `Bandi.tsx` ora importano da `ModalScheda.tsx`. Rimosso ~80 righe di codice duplicato. TypeScript: 0 errori.

### ✅ F7 · Bandi: debounce su search `P2`
**File:** `frontend/src/components/Bandi.tsx`
Debounce 300ms sul campo search con `useState` + `useEffect`. Riduce re-render su digitazione veloce.

---

## AREA 3 — AI / PROMPT

### ✅ A0 · genera_scheda: sezione "Requisiti di accesso" `P1`
**File:** `modules/matcher.py` → `genera_scheda()`
Aggiunta sezione `## Requisiti di accesso` con 5 campi (spesa_min, spesa_max, anzianità min/max, forme giuridiche). Visibili solo se presenti nel JSON del bando.

### ✅ A1 · Aggiungere spesa_massima_ammissibile al prompt `P1`
**File:** `prompts/system_extraction.md`
Aggiunto campo nell'esempio JSON e regola esplicita nelle Regole Rigide: tetto massimo di spesa per il singolo progetto, distinto da `contributo_max`. Versione prompt → v3.1.

### ✅ A2 · Few-shot examples per casi edge `P2`
**File:** `prompts/system_extraction.md`
Aggiunti 2 esempi nella sezione `## Esempi di casi edge`: (1) bando con esclusioni settoriali senza lista ATECO ammessi, (2) data scadenza relativa ("entro 60 giorni"). Prompt → v3.1.

### ✅ A3 · Fallback modello se DeepSeek non risponde `P2`
**File:** `modules/extractor.py`
Dopo fallimento primario (`LLM_MODEL`), ritenta su `LLM_FALLBACK_MODEL` (default `claude-haiku-4-5-20251001`). Entrambi configurabili via env var. `MissingAPIKeyError` non viene catchata (rethrow diretto).

---

## AREA 4 — DATABASE

### ✅ D1 · Verifica colonne opzionali clienti su DB live `P0`
Eseguito `check_db.py` sul DB Neon di produzione.
Risultato: `data_costituzione` (date) ✅ · `numero_dipendenti` (integer) ✅ · `forma_giuridica` (text) ✅

### ✅ D2 · spesa_massima_ammissibile: nessuna migrazione necessaria `P1`
Campo contenuto in `json_completo` (TEXT). `genera_scheda()` usa `.get()` con default None — nessun crash su bandi già salvati.

### ✅ D3 · Endpoint rigenera scheda_cached `P2`
**File:** `main.py`
Aggiunto `POST /api/bandi/{id}/rigenera-scheda`: legge `json_completo`, chiama `genera_scheda()`, salva in `scheda_cached`. Utile dopo modifiche al prompt per aggiornare le schede esistenti senza re-upload PDF.

---

## Calendario

| Data | Modifiche |
|------|-----------|
| **2 lug** ✅ | B1, B2✓, B3, B4, D1✓, D2✓, F1, F2, A0 |
| **3 lug** ✅ | B7 + A1, F3, F4 |
| **4 lug** ✅ | F5, A2 |
| **5 lug** ✅ | A3, B8 |
| **6 lug** ✅ | B6, F6, F7, D3 |
| 7 lug | Buffer e fix urgenti |
| 8 lug | Test end-to-end, deploy staging, smoke test demo |
| **9 lug** | **DEMO** |

---

## Checklist pre-demo (8 luglio)

- [ ] `GET /api/health` → 200 OK dopo deploy su Render
- [ ] Upload PDF reale → estrazione con `spesa_massima_ammissibile` popolato
- [ ] Demo flow: crea cliente → match → scheda bando → sezione "Requisiti di accesso" → download .md
- [ ] Upload bando duplicato → banner giallo, nessun crash
- [ ] `check_db.py` → tutte le colonne clienti presenti
- [ ] Verifica che tutti i match siano visibili (no troncamento a 5)
- [ ] Verifica che il blocco JSON debug non appaia in CaricaBando
