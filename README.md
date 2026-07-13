# AI-Bandi Scanner

Analisi automatica di bandi pubblici con AI — estrazione dati da PDF, matching con profili cliente, dashboard di compatibilità.

## Stack

- Backend: FastAPI + Uvicorn (porta 8000)
- Database: PostgreSQL serverless (Neon) via psycopg2
- Estrazione PDF: PyMuPDF (fitz)
- LLM: OpenRouter → `deepseek/deepseek-v4-flash` (fallback `anthropic/claude-haiku-4.5`)
- Frontend: React 19 + TypeScript + Vite + React Router v7
- Deploy: Docker multi-stage (Node 20 → Python 3.11) su Render.com

Dettagli architetturali completi in `CLAUDE.md`.

## Setup locale

1. Clonare il repository
2. Creare virtual environment: `python -m venv venv`
3. Attivare: `.\venv\Scripts\Activate.ps1` (Windows) o `source venv/bin/activate` (Mac/Linux)
4. Installare dipendenze backend: `pip install -r requirements.txt`
5. Copiare `.env.example` in `.env` e compilare almeno `OPENROUTER_API_KEY`, `DATABASE_URL`, `APP_API_KEY`
6. Inizializzare lo schema database: `python db/init_db.py`
7. Avviare il backend: `uvicorn main:app --reload --port 8000`
8. In un secondo terminale, avviare il frontend in sviluppo:
   ```
   cd frontend
   npm install
   npm run dev
   ```
   Il dev server Vite (porta 5173) proxa le chiamate `/api/*` verso il backend su :8000.

In produzione FastAPI serve sia le API `/api/*` sia la build statica React (`frontend/dist/`) sulla stessa origine — non esiste un server Node separato in produzione.

## Autenticazione

Tutte le rotte `/api/*` (tranne `/api/health`) richiedono l'header `X-API-Key` con il valore di `APP_API_KEY`. Il frontend lo inietta a build-time tramite `VITE_APP_API_KEY` (stesso valore). `/api/estrazione` ha inoltre un rate limit per IP configurabile via `ESTRAZIONE_RATE_LIMIT_MAX`/`ESTRAZIONE_RATE_LIMIT_WINDOW_SECONDS`.

## Struttura

- `main.py` — app FastAPI (entry point produzione)
- `modules/extractor.py` — estrazione AI da PDF (PyMuPDF + OpenRouter)
- `modules/matcher.py` — matching bando-cliente e generazione schede
- `modules/validator.py` — validazione del JSON estratto
- `modules/database.py` — connessione PostgreSQL + CRUD
- `prompts/system_extraction.md` — system prompt del LLM
- `db/init_db.py` — schema SQL e inizializzazione database
- `frontend/` — SPA React (sorgenti in `src/`, build in `dist/`)
- `data/test_pdfs/` — PDF di test

## Limiti noti

- PDF scansionati (immagini senza testo selezionabile) non supportati: nessun OCR.
- Scadenze relative ("entro 60 giorni") non convertite in date: richiedono verifica manuale.
- Il limite di sicurezza resta 250.000 caratteri per singolo input al modello, ma i documenti oltre 60.000 caratteri vengono analizzati in blocchi sovrapposti più piccoli e poi consolidati. L'intero testo del PDF viene coperto senza scartare le sezioni finali.
