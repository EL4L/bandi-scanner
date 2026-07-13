# CLAUDE.md — Bandi Scanner

Documento di riferimento per ogni nuova sessione. Contiene tutto il contesto necessario per lavorare su questo progetto senza esplorazioni iniziali.

---
## Roadmap attiva
Vedi `ROADMAP.md` in root. Gli interventi sono numerati #1–#22 e ordinati per priorità.
Partire sempre dal primo ☐ non spuntato. Dopo ogni intervento aggiornare la checkbox in ROADMAP.md.

Implementa l'intervento #1 della ROADMAP.md.

Contesto: in `modules/schema.py`, la funzione `normalize_response` esegue
`bool(val)` su `ateco_aperto_a_tutti` — questo fa sì che la stringa "false"
diventi True. Stessa cosa per valori numerici come "50000" o "50%" che arrivano
come stringhe dal modello LLM e non vengono coerciti.

Cosa fare:
1. Aggiungere funzioni `_to_bool(val)` e `_to_number(val)` in `schema.py`
2. Usarle in `normalize_response` per `ateco_aperto_a_tutti`, `contributo_max`,
   `fatturato_max`, `percentuale_fondo_perduto`, `spesa_minima_ammissibile`,
   `spesa_massima_ammissibile`, e i mesi in `anzianita_impresa`
3. Aggiungere un test in `tests/` che verifica che "false" → False e "50000" → 50000
4. Spuntare #1 in ROADMAP.md


## Stack tecnologico

| Layer | Tecnologie |
|---|---|
| Backend API | FastAPI + Uvicorn (porta 8000) |
| Database | PostgreSQL serverless (Neon cloud) via psycopg2 |
| PDF extraction | PyMuPDF (fitz) |
| LLM | OpenRouter API → modello `deepseek/deepseek-v4-flash` |
| Validazione | Pydantic (schema), modulo interno `validator.py` |
| Retry | tenacity |
| Frontend | React 19 + TypeScript + Vite + React Router v7 |
| Build | Docker multi-stage (Node 20 builder → Python 3.11 runtime) |
| Deployment | Render.com (render.yaml) |

---

## Architettura

```
bandi-scanner/
├── main.py                     # FastAPI app (entry point produzione)
├── requirements.txt
├── Dockerfile                  # Multi-stage: Node build → Python runtime
├── render.yaml                 # Config Render.com
├── .env                        # NON in git — vedi .env.example
├── modules/
│   ├── database.py             # Connessione PostgreSQL + CRUD
│   ├── extractor.py            # PDF → testo → chiamata LLM → JSON
│   ├── matcher.py              # Scoring bando/cliente + generazione schede
│   ├── validator.py            # Validazione JSON estratto
│   ├── schema.py               # BANDO_SCHEMA + normalize_response
│   ├── log_utils.py            # log_error, log_incident, log_prompt_run
│   └── date_infer.py           # Estrazione fallback data scadenza da testo
├── db/
│   └── init_db.py              # SQL schema + init_database()
├── prompts/
│   └── system_extraction.md   # System prompt per il LLM
├── frontend/                   # React SPA
│   ├── src/
│   │   ├── App.tsx             # Router + layout
│   │   └── components/
│   │       ├── Dashboard.tsx
│   │       ├── Bandi.tsx
│   │       ├── Clienti.tsx
│   │       └── CaricaBando.tsx
│   └── dist/                   # Build statico servito da FastAPI
└── logs/
    ├── INCIDENTS.md
    └── PROMPT_LOG.md
```

**Flusso produzione:** Docker avvia `uvicorn main:app --host 0.0.0.0 --port $PORT`. FastAPI serve sia le API `/api/*` sia la SPA React da `frontend/dist/`.

---

## Variabili d'ambiente richieste

```env
OPENROUTER_API_KEY=   # Chiave OpenRouter per DeepSeek
DATABASE_URL=          # Stringa connessione Neon PostgreSQL
ANTHROPIC_API_KEY=     # Facoltativo — non usato in produzione
```

---

## Schema database (PostgreSQL)

### Tabella `clienti`
| Colonna | Tipo | Note |
|---|---|---|
| id | SERIAL PK | |
| ragione_sociale | TEXT NOT NULL | |
| p_iva | TEXT | 11 cifre |
| codice_ateco | TEXT | Formato "XX.XX" o "XX.XX.XX" |
| descrizione_attivita | TEXT | |
| regione | TEXT | Una delle 20 regioni italiane |
| fatturato | REAL | Euro annui |
| dimensione_impresa | TEXT | "micro" / "piccola" / "media" / "grande" |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### Tabella `bandi`
| Colonna | Tipo | Note |
|---|---|---|
| id | SERIAL PK | |
| titolo | TEXT | |
| ente | TEXT | Ente erogatore |
| data_scadenza | TEXT | Formato YYYY-MM-DD |
| codici_ateco | TEXT | Array JSON serializzato come stringa |
| regioni | TEXT | Array JSON serializzato come stringa |
| dimensione | TEXT | Stringa CSV: "micro,piccola,media,grande" |
| contributo_max | REAL | Euro |
| json_completo | TEXT NOT NULL | Payload completo dell'estrazione |
| created_at | TIMESTAMP | |

### Tabella `match_results`
| Colonna | Tipo | Note |
|---|---|---|
| id | SERIAL PK | |
| cliente_id | INTEGER FK → clienti | |
| bando_id | INTEGER FK → bandi | |
| score | REAL | 0-100 |
| data_match | TIMESTAMP | |

---

## Endpoint API (FastAPI su porta 8000)

### Dashboard
| Metodo | Path | Descrizione |
|---|---|---|
| GET | `/api/dashboard` | Tutti i bandi con match, schede e summary |
| POST | `/api/bandi/recalc` | Ricalcola tutti i match |
| POST | `/api/bandi/deduplica` | Rimuove bandi duplicati. Body opzionale: `{"strict": true}` (default). `strict=false` → confronto solo su titolo (ignora ente) |

### Bandi
| Metodo | Path | Descrizione |
|---|---|---|
| GET | `/api/bandi` | Lista bandi con urgenza e giorni alla scadenza |
| GET | `/api/bandi/{id}/scheda` | Scheda bando in JSON |
| GET | `/api/bandi/{id}/scheda.md` | Scarica scheda come markdown |
| DELETE | `/api/bandi/{id}` | Elimina bando e relativi match |
| POST | `/api/bandi/{id}/rigenera-scheda` | Rigenera la scheda markdown cached |

### Estrazione
| Metodo | Path | Descrizione |
|---|---|---|
| POST | `/api/estrazione` | Upload PDF → estrazione AI → validazione → salvataggio |

Risposta `POST /api/estrazione`:
```json
{
  "filename": "...",
  "size_kb": 123,
  "raw_text_preview": "...",
  "data": { "bando": {...} },
  "errors": [],
  "warnings": [],
  "bando_id": 42
}
```

### Matching
| Metodo | Path | Descrizione |
|---|---|---|
| POST | `/api/match/run` | Esegui matching. Body: `{"soglia_minima": 0}` |

### Clienti
| Metodo | Path | Descrizione |
|---|---|---|
| GET | `/api/clienti` | Lista clienti + regioni + dimensioni disponibili |
| GET | `/api/clienti/{id}` | Singolo cliente |
| POST | `/api/clienti` | Crea cliente (avvia matching automatico) |
| PUT | `/api/clienti/{id}` | Aggiorna cliente |
| DELETE | `/api/clienti/{id}` | Elimina cliente |
| GET | `/api/clienti/{id}/bandi` | Lista bandi compatibili per un cliente con score, breakdown e scadenza |

### Export
| Metodo | Path | Descrizione |
|---|---|---|
| GET | `/api/export/matching.csv` | Scarica tutti i match in CSV |

**SPA fallback:** qualsiasi path non `/api/*` restituisce `frontend/dist/index.html`.

---

## Stato componenti React

| Componente | Responsabilità |
|---|---|
| `Dashboard.tsx` | Card per ogni bando con deduplicazione visiva; filtro attivi/scaduti con sezione collassabile; KPI row (totale bandi, match attivi, clienti); modal scheda bando on-demand |
| `Bandi.tsx` | Tabella bandi sortable per colonna; filtro a tab Tutti / Attivi / Scaduti; apertura modal scheda on-demand per ogni riga |
| `Clienti.tsx` | CRUD completo clienti con modal form per creazione e modifica; delete con conferma inline prima di procedere |
| `CaricaBando.tsx` | Upload PDF con drag&drop; gestione duplicati con banner giallo di avviso; anteprima JSON estratto prima del salvataggio |

---

## Algoritmo di scoring (matcher.py)

Score 0-100, calcolato da `calculate_score(bando, cliente)`:

| Criterio | Peso | Logica |
|---|---|---|
| Regione | 30 | 30 pt se nessun vincolo O regione cliente in regioni_ammesse |
| ATECO | 40 | 40 pt se `ateco_aperto_a_tutti=True`; 40 pt se codice esatto; 20 pt se prime 2 cifre match; 15-30 pt se match testuale su `attivita_ammesse`; **20 pt se nessun dato estratto (ambiguo)**; 0 pt se escluso |
| Dimensione | 20 | 20 pt se nessun vincolo O dimensione cliente ammessa |
| Fatturato | 10 | 10 pt se `fatturato_max` assente O fatturato cliente ≤ max; 0 pt se supera il limite |

---

## Struttura JSON bando (in `bandi.json_completo`)

```json
{
  "bando": {
    "titolo": "string | null",
    "ente": "string | null",
    "data_pubblicazione": "YYYY-MM-DD | null",
    "data_scadenza": "YYYY-MM-DD | null",
    "codici_ateco_ammessi": ["XX.XX"],
    "attivita_ammesse": ["string"],
    "ateco_aperto_a_tutti": false,
    "regioni_ammesse": ["Lombardia"],
    "dimensione_impresa": {
      "micro": true,
      "piccola": true,
      "media": false,
      "grande": false
    },
    "fatturato_max": null,
    "numero_dipendenti_min": null,
    "numero_dipendenti_max": null,
    "contributo_max": 100000.0,
    "percentuale_fondo_perduto": 50.0,
    "spese_ammissibili": ["string"],
    "link_fonte_ufficiale": "string | null",
    "spesa_minima_ammissibile": null,
    "spesa_massima_ammissibile": null,
    "anzianita_impresa": {
      "mesi_minimi_dalla_costituzione": null,
      "mesi_massimi_dalla_costituzione": null
    },
    "forme_giuridiche_ammesse": [],
    "note_esclusioni": {
      "lista_testuale": "string",
      "sezioni_ateco_escluse": [],
      "attivita_vietate": []
    },
    "urgenza": "alta | media | bassa | scaduto | null"
  }
}
```

---

## Flussi principali

### Estrazione PDF
1. Upload PDF via `POST /api/estrazione`
2. `extract_text_from_pdf()` — PyMuPDF, lancia `EmptyPDFException` se < 50 caratteri; l'estrazione AI usa blocchi sovrapposti da circa 60.000 caratteri e copertura integrale del documento
3. `extract_bando_data()` — chiama DeepSeek via OpenRouter (retry 3x con 5 min tra tentativi)
4. `validate_bando()` — struttura + formato + logica; se >50% null → `needs_manual_review`
5. Fallback: se `data_scadenza` vuota, `date_infer.py` cerca date nel testo tramite regex + pesi keyword
6. `save_bando_from_json()` — salva in DB; se duplicato (stesso titolo+ente) → segnalazione senza salvataggio
7. `run_matching_for_bando()` — calcola e salva score per tutti i clienti

### Matching batch
1. `POST /api/match/run` con `soglia_minima` (default 0)
2. Per ogni coppia bando/cliente → `calculate_score()` → salva in `match_results`

### Visualizzazione dashboard
1. `GET /api/dashboard` → `load_dashboard_rows()` (JOIN match_results + bandi + clienti)
2. React Dashboard.tsx renderizza card per bando con breakdown score

---

## Comandi di sviluppo locale

```powershell
# Backend FastAPI
uvicorn main:app --reload --port 8000

# Frontend React (sviluppo separato — Vite su porta 5173)
cd frontend
npm install
npm run dev          # Vite dev server → http://localhost:5173
npm run build        # Build in frontend/dist/

# Database — init schema
python db/init_db.py
```

---

## Regole da seguire sempre

1. **Non usare librerie UI esterne nel frontend** — niente Material UI, Ant Design, Chakra, ecc. Solo React + CSS custom.
2. **Il backend gira sempre su porta 8000** — non cambiare la porta di default senza motivo esplicito.
3. **Non usare ORM** — il database si gestisce con psycopg2 diretto e query SQL raw in `database.py`.
4. **Il sistema prompt del LLM è in `prompts/system_extraction.md`** — non hardcodarlo nel codice Python.
5. **Qualsiasi modifica tecnica rilevante va loggata** — aggiungere righe in `logs/INCIDENTS.md` e `logs/PROMPT_LOG.md` usando le funzioni in `log_utils.py`.
6. **Il modello LLM usato è `deepseek/deepseek-v4-flash` via OpenRouter** — non passare ad Anthropic direttamente senza valutare costi/benefici.
7. **I duplicati bandi si rilevano per titolo+ente (case-insensitive)** — default `strict=True`. Usare `strict=False` solo per deduplicazioni manuali esplicite (confronta solo titolo, ignorando ente).
8. **I placeholder SQL sono `%s`** (PostgreSQL psycopg2), non `?` (SQLite) — non confondere i due.
9. **La SPA React viene builddata e servita da FastAPI** — in produzione non esiste un server Node separato.
10. **Non aggiungere feature non richieste** — il progetto è in produzione su Render e ogni modifica impatta utenti reali.

---

## Stato attuale del progetto

- **Produzione:** Deploy attivo su Render.com (Docker), database Neon PostgreSQL
- **UI principale:** React SPA servita da FastAPI su `/`
- **Anti-duplicato:** Attivo — `strict=True` (titolo+ente) al salvataggio; `strict=False` (solo titolo) disponibile via API per pulizie manuali
- **Bandi scaduti:** Separati visivamente nella dashboard con badge "Scaduto"
- **OCR:** Non supportato — solo PDF con testo selezionabile
- **Autenticazione:** API key statica su tutte le rotte /api/* via header
  `X-API-Key` (variabile d'ambiente `APP_API_KEY`). Il frontend legge la
  chiave da `VITE_APP_API_KEY`.

---

## Bug noti e problemi aperti

- ~~**Score 100% su quasi tutti i match**~~ — **risolto**: `_score_ateco` ora restituisce 20 pt (invece di 40) quando nessun dato settoriale è stato estratto; `_score_fatturato` non usa più `contributo_max` come proxy di fatturato.
- ~~**Falsi duplicati per ente diverso**~~ — **risolto**: `deduplica_bandi(strict=False)` e `find_duplicate_bando(strict=False)` supportano confronto su solo titolo (case-insensitive, TRIM). Esposto via `POST /api/bandi/deduplica` con body `{"strict": false}`.

---

## Note di deployment (Render.com)

- Build: Docker multi-stage (vedi `Dockerfile`)
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Env vars da configurare nel dashboard Render: `OPENROUTER_API_KEY`, `DATABASE_URL`
- `autoDeploy: true` — ogni push su `main` triggera un nuovo deploy

---

## Riferimenti esterni

- **`ROADMAP.md`** — roadmap interventi attiva (22 interventi #1–#22,
  ordinati per priorità P0→P3). Leggerla prima di qualsiasi modifica al codice.
- **`audit-bandi-scanner2.md`** — audit tecnico completo (estrazione, scoring,
  schede, frontend, design). Consultarlo per il dettaglio e il codice
  di ogni intervento.
- **`PROJECT_EVOLUTION_PIPELINE.md`** — roadmap strategica del 2026-06-26,
  superata da ROADMAP.md per la pianificazione operativa. Solo per contesto storico.
