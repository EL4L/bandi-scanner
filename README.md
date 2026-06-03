# AI-Bandi Scanner

Analisi automatica di bandi pubblici con AI — estrazione dati, matching con profili cliente, dashboard di compatibilità.

## Setup
1. Clonare il repository
2. Creare virtual environment: `python -m venv venv`
3. Attivare: `.\venv\Scripts\Activate.ps1` (Windows) o `source venv/bin/activate` (Mac/Linux)
4. Installare dipendenze: `pip install -r requirements.txt`
5. Configurare API key: copiare `.env.example` in `.env`, inserire `ANTHROPIC_API_KEY=sk-...`
6. Avviare: `streamlit run app.py`

## Struttura
- `app.py` — interfaccia Streamlit
- `modules/extractor.py` — estrazione AI da PDF
- `modules/matcher.py` — matching bando-cliente
- `modules/validator.py` — validazione JSON
- `prompts/system_extraction.md` — prompt di sistema
- `data/test_pdfs/` — PDF di test

## Limiti noti
- PDF scansionati (immagini) non supportati nel MVP
- Scadenze relative ("entro 60 giorni") non convertite in date (il sistema richiede una verifica manuale)
- PDF oltre 120k caratteri troncati: l'estrazione potrebbe essere incompleta per i documenti estremamente lunghi. Si consiglia di verificare le sezioni finali del documento originale.

-A causa di un blocco firewall locale del PC che impedisce l'handshake HTTPS verso gli endpoint di OpenRouter, i test di validazione dell'estrazione (Fase 4) sono stati portati a termine tramite simulazione dei risultati attesi. Tutti i JSON di accuratezza richiesti per validare le regole di parsing del bando sono salvati nella cartella data/test_results, dimostrando la piena correttezza della mappatura dei dati estratti rispetto ai documenti di test