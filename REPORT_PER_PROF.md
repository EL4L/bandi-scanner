# Report di avanzamento per il progetto "bandi-scanner"

Data: 26/05/2026

Questo documento sintetizza a che punto siamo, cosa è stato implementato nelle ultime modifiche, i problemi riscontrati e i passi successivi raccomandati.

## Stato attuale — cosa è stato implementato

- Tema grafico completo e automatico:
  - `assets/styles/theme.css` creato e iniettato automaticamente all'avvio tramite `app.py`.
  - Migliorata leggibilità globale (contrasto, colori link, stili per tabelle, expander, codice e JSON).

- Migliorie alla visualizzazione del JSON estratto:
  - Stili CSS per `div[data-testid="stJson"]`, `.stJson` / `.st-json` (sfondo scuro, padding, font monospaziato, scroll).

- Correzioni e miglioramenti al matching (modules/matcher.py):
  - Nuova protezione: se il JSON del bando è vuoto o non contiene vincoli espliciti (regioni / ATECO / dimensione / contributo), il sistema non assegna punteggi massimi automaticamente: ora imposta score = 0 e logga l'evento.
  - Introdotta funzione `_bando_has_constraints` e wrapper pubblico `bando_has_constraints`.
  - Cambiato comportamento: se il bando non specifica dimensioni o limiti economici, non vengono più assegnati i pesi pieni per dimensione (20) e fatturato (10). Ora questi pesi vengono assegnati solo se il bando specifica i vincoli.
  - Aggiunta funzione `get_score_breakdown` che ritorna il breakdown per regione/ateco/dimensione/fatturato + totale.

- UI: dettaglio e diagnostic
  - La Dashboard ora mostra per ogni match il breakdown dei contributi (Regione / ATECO / Dimensione / Fatturato).
  - Se il bando non ha vincoli espliciti viene mostrato un avviso in Dashboard.
  - Se lo score salvato in DB differisce dal ricalcolo dinamico viene mostrato un warning e viene offerta la possibilità di ricalcolare il matching per quel bando.

- Script di supporto per testing locale:
  - `scripts/generate_test_pdfs.py` — crea 4 PDF di test (ATECO specifico, aperto a tutti, regioni, senza vincoli) usando PyMuPDF.
  - `scripts/simulate_matching.py` — esegue localmente il matching su alcuni JSON campione e stampa breakdown usando i clienti presenti nel DB (non chiama l'API AI).

- Piccole robustezze e fix:
  - `app.py` inietta il CSS in modo sicuro e migliora la visualizzazione della barra di compatibilità.
  - I file script aggiustati per essere eseguibili dalla root (`sys.path` patch sui script).

## File principali modificati/aggiunti

- Modificati:
  - `app.py` — iniezione CSS, visualizzazione breakdown, pulsante ricalcolo matching, miglioramenti UI.
  - `modules/matcher.py` — logica matching, _bando_has_constraints, get_score_breakdown, cambi di default sui pesi dimensione/fatturato.
  - `assets/styles/theme.css` — tema scuro, regole per JSON, tabelle, expander, bottoni, contrasto.

- Aggiunti:
  - `assets/styles/theme.css` (nuovo file CSS)
  - `scripts/generate_test_pdfs.py` (genera PDF di test)
  - `scripts/simulate_matching.py` (simulazione matching locale)

## Test eseguiti

- Verifiche statiche:
  - `get_errors` su file modificati: nessun errore Python segnalato per i file toccati.

- Test manuale consigliato (da eseguire localmente):
  1. Generare PDF di test:
	  ```powershell
	  python scripts/generate_test_pdfs.py
	  ```
  2. Avviare l'app Streamlit:
	  ```powershell
	  streamlit run app.py
	  ```
  3. Caricare un PDF (es.: `data/test_pdfs/bando_ateco_specifico.pdf`) in **Estrazione bandi**, premere "Estrai dati bando con AI" (se hai la chiave Anthropic).
  4. Salvare il bando e controllare la Dashboard: breakdown e avvisi appaiono sotto l'expander del bando.
  5. Se non vuoi chiamare l'API, usa la simulazione:
	  ```powershell
	  python scripts/simulate_matching.py
	  ```

## Problemi riscontrati / note

- L'estrazione automatica tramite Claude (Anthropic) richiede la chiave API e va testata con i PDF reali. Se l'API non è disponibile, non si può valutare in automatico l'accuratezza degli estratti.
- Alcuni match salvati in `match_results` potrebbero essere residui di logiche precedenti: ora c'è il pulsante per ricalcolare, ma potrebbe essere necessario eseguire un ricalcolo globale per allineare i dati storici.
- PROMPT_LOG.md e INCIDENTS.md non sono stati popolati automaticamente: va fatto manualmente in fase di test delle estrazioni.

## Cosa manca / priorità

1. Fase 1 (completa QA dell'estrazione AI)
	- Testare le estrazioni reali con Claude su tutto il dataset di PDF e aggiornare `PROMPT_LOG.md` con i risultati (campi OK / campi null / correzioni al prompt).
	- Gestire fallback OCR per PDF scannerizzati (pytesseract) se rilevi PDF senza testo.

2. Fase 4 — Documentazione e pulizia
	- Completare `README.md` con istruzioni, dipendenze, screenshot.
	- Generare `.env.example` e aggiornare `.gitignore` per evitare commit di segreti e del DB.
	- Rifinire `requirements.txt` (rimuovere pacchetti inutili e pin versioni se servono).

3. Allineamento dati e ricalcolo
	- Eseguire ricalcolo matching per tutti i bandi esistenti (script o bottone globale) per normalizzare gli score dopo le modifiche alla logica.

4. Migliorie UI/UX
	- Rendere il breakdown più leggibile (tabella o expander dedicato) invece della caption.
	- Aggiungere alert/indicatori nella lista bandi quando lo score deriva da inferenze (campo "inferred").

5. Test automatici
	- Aggiungere test unitari minimi per `modules/matcher.calculate_score` e per `_bando_has_constraints`.

## Prossimi passi raccomandati (con comandi)

1. Se non l'hai già fatto, installa dipendenze:
	```powershell
	pip install -r requirements.txt
	```

2. Genera i PDF di test e prova la simulazione senza chiamata API:
	```powershell
	python scripts/generate_test_pdfs.py
	python scripts/simulate_matching.py
	```

3. Se vuoi allineare tutti i match esistenti (consigliato dopo le modifiche al punteggio):
	- apri una sessione Python o crea uno script che chiami `run_matching_for_all_bandi(get_connection())` oppure usa l'interfaccia (da implementare: pulsante "Ricalcola tutti i bandi").

4. Eseguire i test di estrazione reali con la chiave Anthropic e popolare `PROMPT_LOG.md` con i risultati ottenuti.

---

Se vuoi, posso:
- generare il `README.md` base e `.env.example` ora;
- aggiungere uno script per ricalcolare automaticamente tutti i match e salvarlo in `scripts/`;
- trasformare il breakdown in una tabella più leggibile nella UI.

Dimmi quale dei tre preferisci e procedo ad implementarlo.

