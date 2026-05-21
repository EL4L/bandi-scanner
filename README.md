# Bandi Scanner

Applicazione Streamlit per analizzare bandi pubblici italiani in PDF: estrazione del testo, estrazione strutturata via Claude API e validazione automatica del JSON (RF-004, RF-002, RF-007).

## Requisiti

- Python 3.10+
- Chiave API Anthropic

## Installazione

```bash
cd bandi-scanner
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Modifica `.env` e imposta `ANTHROPIC_API_KEY`.

## Database (Fase 2)

```bash
python db/init_db.py
```

Crea o aggiorna le tabelle in `db/bandi.db` (clienti, bandi, match_results).

## Avvio

```bash
streamlit run app.py
```

- **Estrazione bandi:** upload PDF → testo → (opzionale) estrazione AI → validazione JSON.
- **Profilo cliente:** form anagrafica, lista clienti, modifica ed eliminazione (RF-001).

## Test Fase 1 (PDF in `data/test_pdfs/`)

```bash
python scripts/test_phase1.py
python scripts/test_phase1.py --with-api
```

Il secondo comando richiede `.env` configurato e registra i risultati in `logs/PROMPT_LOG.md`.

## Struttura

- `app.py` — interfaccia Streamlit
- `modules/extractor.py` — PDF + API Anthropic (retry 3×, attesa 5 min)
- `modules/validator.py` — validazione formato e logica
- `prompts/system_extraction.md` — prompt di estrazione
- `logs/PROMPT_LOG.md`, `logs/INCIDENTS.md`, `error_log.txt` — log operativi

## Costi API

Ogni bando invia il testo estratto (fino a 120.000 caratteri) a Claude Sonnet. Monitora l’uso dal dashboard Anthropic.
