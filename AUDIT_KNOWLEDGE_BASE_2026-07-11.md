# Bandi Scanner — audit, knowledge base e validazione

## Metadati

| Campo | Valore |
|---|---|
| Sessione | Audit avviato 2026-07-10 e concluso 2026-07-11 (`Europe/Rome`) |
| Autore | Codex, modello GPT-5 / Codex |
| Baseline Git | `main` = `origin/main` = `1fae20c` |
| Stato baseline | Working tree già sporco all'inizio dell'audit; modifiche dell'utente/Claude preservate |
| Scopo | Knowledge base tecnica, validazione locale, diagnosi caricamento infinito, rischi e piano di rimedio |
| Approccio | Ispezione statica, cronologia Git, test automatizzati, build/lint, test DB read-only e smoke HTTP locale |

Questo documento è uno snapshot verificato. Non sostituisce la specifica di
prodotto, ma è la fonte più aggiornata per capire lo stato tecnico osservato
nella sessione. Il precedente `audit-bandi-scanner2.md` resta utile come storico
dei finding antecedenti.

## Esito esecutivo

Il progetto non si apriva perché il frontend Vite era attivo, ma il backend non
riusciva nemmeno a importare `main.py` e quindi non apriva la porta 8000.

La causa primaria è il commit `1fae20c` del 2026-07-10, co-firmato Claude Sonnet
5, che ha aggiunto l'import top-level di `modules.url_extractor`. Claude ha
installato e testato le nuove dipendenze con il Python globale, mentre il runtime
locale usa `venv\Scripts\python.exe`. Nel virtual environment mancava
`trafilatura`; dopo averla installata è emersa una seconda dipendenza mancante,
`lxml_html_clean`, richiesta dalla catena `trafilatura -> jusText -> lxml`.

La divergenza spiega tutte le evidenze:

- la shell React e la sidebar erano già visibili su `localhost:5174`;
- due processi Vite avevano occupato 5173 e 5174;
- nessun processo ascoltava sulla porta 8000;
- `venv\Scripts\python.exe -c "import main"` falliva prima su `trafilatura`,
  poi su `lxml.html.clean`;
- React Query attendeva `/api/dashboard` senza alcun timeout e manteneva lo
  spinner.

Il virtual environment locale è stato riallineato con autorizzazione esplicita
dell'utente. Dopo il riallineamento:

- `import main` passa;
- 274 test Python su 274 passano;
- coverage backend complessiva: 73,22%;
- build TypeScript/Vite passa;
- lint frontend: 0 errori e 5 warning;
- `npm audit --omit=dev`: 0 vulnerabilità note;
- smoke HTTP read-only: `GET /api/dashboard` -> 200, 11 bandi, 11 card,
  55 abbinamenti.

Il rimedio è però solo locale: `requirements.txt` non dichiara ancora
`lxml_html_clean==0.4.5`. Un ambiente pulito o un deploy Docker possono quindi
riprodurre il crash. Nessuna correzione di codice/configurazione è stata
applicata senza una richiesta esplicita.

## Architettura corrente

| Area | Implementazione | File principali |
|---|---|---|
| Frontend | React 19, TypeScript, Vite, React Router, TanStack React Query | `frontend/src/App.tsx`, `frontend/src/lib/queries.ts`, `frontend/src/components/*` |
| API | FastAPI sincrona servita da Uvicorn | `main.py` |
| Persistenza | PostgreSQL serverless Neon, accesso diretto con psycopg2 | `modules/database.py`, `db/init_db.py` |
| Estrazione PDF | PyMuPDF, limiti su byte e pagine | `modules/extractor.py` |
| Estrazione URL | requests + trafilatura, redirect manuali e filtri SSRF | `modules/url_extractor.py`, `main.py:649-706` |
| LLM | OpenRouter, DeepSeek primario e Claude Haiku fallback | `modules/extractor.py` |
| Normalizzazione | Schema interno, coercizione tipi, validazione e inferenza data | `modules/schema.py`, `modules/validator.py`, `modules/date_infer.py` |
| Matching | Score, ammissibilità binaria, scheda Markdown | `modules/matcher.py` |
| Log | Incidenti tecnici e storico prompt/estrazioni | `modules/log_utils.py`, `logs/INCIDENTS.md`, `logs/PROMPT_LOG.md` |
| Build/deploy | Docker multi-stage su Render, frontend statico servito da FastAPI | `Dockerfile`, `render.yaml` |
| CI | GitHub Actions, Python 3.11, pytest e coverage moduli | `.github/workflows/ci.yml` |

### Flusso dati principale

```text
Browser React
  -> /api/estrazione (PDF) oppure /api/estrazione-url (HTTPS)
  -> testo normalizzato
  -> OpenRouter / modello primario, poi fallback
  -> JSON normalizzato e validato
  -> PostgreSQL: bandi
  -> matching su clienti
  -> PostgreSQL: match_results
  -> /api/dashboard, /api/bandi, /api/clienti
  -> cache React Query e rendering SPA
```

### Dati persistiti

- `clienti`: anagrafica, P.IVA, ATECO, regione, fatturato, dimensione,
  costituzione, dipendenti e forma giuridica.
- `bandi`: metadati indicizzati più `json_completo` come fonte ricca e
  `scheda_cached`.
- `match_results`: coppia cliente/bando, score e timestamp del calcolo.

Lo schema viene creato e migrato in modo idempotente a ogni startup tramite
`ensure_database()` (`main.py:81-83`, `db/init_db.py:79-87`).

### Superficie API

- dashboard, ricalcolo e deduplica;
- lista/dettaglio/eliminazione bandi e download schede;
- upload PDF ed estrazione da URL;
- lista, dettaglio e CRUD clienti;
- matching batch ed export CSV;
- health check pubblico;
- fallback SPA per i path non API.

Tutte le API applicative richiedono una chiave statica condivisa; `/api/health`
è pubblico.

## Diagnosi del caricamento infinito

### Catena causale verificata

1. Alle 16:48 del 2026-07-10 le nuove librerie risultano installate nel Python
   globale, non nel virtual environment del progetto.
2. Alle 17:04 viene creato `1fae20c`, che importa `modules.url_extractor` già
   durante `import main` (`main.py:67-71`).
3. Il runtime locale configurato usa il `venv`, nel quale `trafilatura` non è
   presente.
4. Il backend termina con `ModuleNotFoundError` prima di aprire la porta 8000.
5. Vite resta disponibile su 5174 perché 5173 è già occupata da un altro Vite.
6. La dashboard esegue `fetch('/api/dashboard')` senza timeout
   (`frontend/src/lib/queries.ts:9-18`).
7. `Dashboard.tsx:355-361` mostra lo spinner finché `isLoading` resta vero.

### Perché i log di Claude sembravano corretti

`logs/CLAUDE_CODE_PROMPTS.md:1891-1894` dichiara installazione e 238 test
verdi, ma non registra `sys.executable`. `.claude/settings.local.json` avvia il
backend dal venv, mentre consente comandi `python -m pytest` che risolvono sul
Python globale. La validazione ha quindi controllato un interprete diverso da
quello usato dall'app.

### Seconda rottura della catena pacchetti

`pip install -r requirements.txt` ha installato `trafilatura==2.1.0`, ma
`import main` ha continuato a fallire perché `jusText` importa
`lxml.html.clean.Cleaner`. Con `lxml 6.1.1` quel modulo è nel progetto separato
`lxml_html_clean`. `pip check` ha comunque riportato “No broken requirements”,
quindi non è uno smoke test sufficiente.

## Validazione eseguita

| Controllo | Esito | Nota |
|---|---|---|
| Stato Git e cronologia | PASS | HEAD/origin allineati; working tree sporco preesistente |
| Import backend prima del rimedio | FAIL riprodotto | `trafilatura` assente, poi `lxml_html_clean` assente |
| Connessione Neon read-only | PASS | `SELECT 1` in circa 1,09 s con timeout 5 s |
| Import backend dopo riallineamento venv | PASS | `MAIN_IMPORT_OK` |
| Integrità pacchetti dichiarati | PASS parziale | `pip check` non rileva l'extra mancante |
| Pytest | PASS | 274/274, 2 warning FastAPI deprecation |
| Coverage | PASS soglia | 73,22% totale; `main.py` 65%; `db/init_db.py` 0% |
| TypeScript/Vite production build | PASS | 61 moduli; JS ~337,94 kB, gzip ~99,73 kB |
| Oxlint | PASS con warning | 0 errori, 5 warning |
| npm audit produzione | PASS | 0 vulnerabilità note al 2026-07-11 |
| Smoke API read-only | PASS | dashboard HTTP 200, 11/11/55 |
| Diff whitespace | PASS | `git diff --check` senza errori |

Non sono state eseguite chiamate LLM reali a pagamento, mutazioni intenzionali
del database, test del deploy Render, browser E2E o scansione CVE Python con
`pip-audit` (tool non presente).

## Finding prioritizzati

### P0 — bloccanti

#### P0-1 — installazione non riproducibile e crash backend

- Evidenza: `main.py:67-71`, `modules/url_extractor.py:22-23`,
  `requirements.txt:11-12`, `Dockerfile:16-22`.
- Impatto: backend non avviabile in locale o in un'immagine pulita.
- Stato: corretto solo nel venv locale; repository non corretto.
- Rimedio proposto: dichiarare e pinning di `lxml_html_clean==0.4.5` oppure
  scegliere una combinazione trafilatura/jusText/lxml esplicitamente testata;
  usare sempre `venv\Scripts\python.exe -m pip`; aggiungere `import main` a CI
  e Docker build.

#### P0-2 — richieste dashboard potenzialmente infinite

- Evidenza: `frontend/src/lib/queries.ts:9-24`, `Dashboard.tsx:311,355-361`,
  `modules/database.py:71-75`.
- Impatto: spinner permanente se proxy, backend o DB non concludono.
- Rimedio proposto: `AbortController`/timeout comune sul client, UI di errore
  con retry manuale, `connect_timeout` e `statement_timeout` lato PostgreSQL.

### Alta severità

#### H-1 — errori HTTP trattati come successi nel frontend

Recalc, deduplica, delete cliente e varie fetch puntuali non verificano sempre
`res.ok`. Una risposta 401/500 può produrre toast di successo, cache invalidata
o dati vuoti (`Dashboard.tsx:316-349`, `Clienti.tsx:180-181`,
`frontend/src/lib/queries.ts:40-47`). Centralizzare il parsing HTTP e lanciare
un errore tipizzato su ogni risposta non 2xx.

#### H-2 — upload PDF fragile e consumo memoria prima del limite

`main.py:597-607` legge l'intero upload in memoria e controlla i 10 MB solo
dopo. Il ramo frontend PDF non controlla `res.ok` e può chiamare
`size_kb.toFixed()` su un payload di errore (`CaricaBando.tsx:203-225,537-549`).
Leggere a chunk con limite, uniformare lo schema errore e aggiungere un Error
Boundary.

#### H-3 — errori matching inghiottiti

`modules/matcher.py:591-612` cattura eccezioni, le logga e non le propaga.
Gli endpoint possono quindi rispondere `status: ok` dopo un ricalcolo parziale
o fallito (`main.py:406-445`). Usare transazioni esplicite e far fallire la
richiesta se il matching non è atomico.

#### H-4 — autenticazione statica esposta nel client

`VITE_APP_API_KEY` è incorporata nel bundle (`frontend/src/apiKey.ts:1-17`) e
per i download viene inserita nella query string (`:20-24`), con possibile
presenza in cronologia e log. È una barriera anti-abuso, non autenticazione.
Per dati reali di clienti serve identità per utente/sessione e autorizzazione
server-side; almeno evitare credenziali in query string.

#### H-5 — SSRF con finestra DNS rebinding

`modules/url_extractor.py:40-101` risolve il DNS per validare che l'host sia
pubblico, poi `requests` effettua una seconda risoluzione. Un dominio controllato
può teoricamente cambiare risposta tra le due operazioni. La buona validazione
dei redirect riduce il rischio, ma non pinna l'IP validato. Usare una connessione
all'indirizzo già validato preservando host/SNI, oppure un egress proxy con
policy di rete.

#### H-6 — startup dipendente dal DB senza timeout

Ogni startup esegue DDL/migrazioni e `psycopg2.connect()` senza timeout
(`main.py:81-83`, `db/init_db.py:79-87`). Neon lento o irraggiungibile può
impedire l'ascolto HTTP. Separare le migrazioni dal boot e configurare timeout.

### Media severità

#### M-1 — integrità schema database insufficiente

- nessun vincolo UNIQUE su `(cliente_id, bando_id)`;
- upsert manuale vulnerabile a concorrenza (`matcher.py:602-604`);
- importi in `REAL` anziché `NUMERIC`;
- scadenze in `TEXT` anziché `DATE`.

#### M-2 — bandi senza match assenti dalla dashboard

`load_dashboard_rows()` usa INNER JOIN da `match_results`
(`matcher.py:838-847`). Un bando senza clienti/match non genera una card,
nonostante il frontend contenga uno stato “nessun cliente compatibile”.

#### M-3 — redesign Dashboard locale non documentato

Le modifiche non committate a `Dashboard.tsx` e `styles.css` non causano lo
spinner, ma rimuovono dalla vista ente, data/giorni/urgenza, contributo massimo
e KPI “Bandi con clienti”, lasciando la scadenza quasi solo cromatica. Serve
una decisione di prodotto prima di conservarle o annullarle.

#### M-4 — log contaminati dai test

I test chiamano le funzioni di log reali. `tests/test_extractor.py` genera
incidenti con causa fittizia `giu`; i test endpoint aggiungono record
`bando.pdf`/`esempio.it` al `PROMPT_LOG`. Reindirizzare i path a `tmp_path` con
fixture e aggiungere ID, sessione, autore, modello e versione prompt.

#### M-5 — assenza di test frontend e TypeScript permissivo

Non esiste uno script `test` nel package frontend; `strict` non è abilitato e
gli hook usano `any`. Le regressioni React Query, i payload HTTP incoerenti e il
redesign della dashboard non hanno protezione automatica.

#### M-6 — accessibilità e responsive incompleti

- intestazioni ordinabili non raggiungibili da tastiera e senza `aria-sort`;
- toggle senza stato ARIA completo;
- `frontend/index.html` dichiara `lang="en"` per una UI italiana;
- sidebar e margine principale fissi a 220 px senza navigazione mobile.

#### M-7 — link non limitati a schemi sicuri

Il renderer Markdown usa direttamente l'URL come `href`; la validazione client
del campo URL accetta protocolli diversi da HTTPS, sebbene il backend li rifiuti.
Applicare allow-list `https:`/`http:` in rendering e `https:` nel form.

#### M-8 — health check ambiguo

`/api/health` restituisce HTTP 200 anche quando il DB è in errore e segnala solo
`status: degraded` (`main.py:845-857`). Un orchestratore basato sul solo status
HTTP può considerare sana un'istanza inutilizzabile.

#### M-9 — coverage sbilanciata

Coverage totale adeguata alla soglia, ma `db/init_db.py` è allo 0% e `main.py`
al 65%. Mancano test di startup, migrazioni, timeout e risposta dashboard reale
con DB isolato.

#### M-10 — knowledge base incoerente

- `CLAUDE.md` contiene ancora l'ordine di implementare #1 già completato;
- omette endpoint URL, campi recenti e parti dello stack;
- `frontend/README.md` è boilerplate Vite;
- diversi documenti storici descrivono Streamlit/SQLite/Anthropic senza una
  marcatura evidente;
- riferimenti a `AUDIT_BANDI_SCANNER.md` puntano a un file non più presente;
- `logs/CLAUDE_CODE_PROMPTS.md` attribuisce alcuni esiti al prompt/commit errato.

### Bassa severità

- build Docker usa `npm install` anziché `npm ci`;
- route React importate tutte eager in un unico bundle;
- alcuni link interni usano `<a href>` e perdono la cache SPA;
- FastAPI `@app.on_event("startup")` è deprecato;
- cinque warning lint: Fast Refresh e dipendenze `useMemo` instabili;
- nessuna scansione CVE automatica Python nella CI.

## Stato delle modifiche locali osservate

All'inizio dell'audit erano già modificati:

- `ROADMAP.md`;
- `frontend/src/components/Dashboard.tsx`;
- `frontend/src/styles.css`;
- `logs/CLAUDE_CODE_PROMPTS.md`;
- `logs/INCIDENTS.md`;
- `logs/PROMPT_LOG.md`;
- `modules/matcher.py`;
- `modules/schema.py`;
- `prompts/system_extraction.md`;
- `tests/test_matcher.py`;
- `tests/test_schema.py`.

Le modifiche schema/matcher/prompt/test corrispondono principalmente al lavoro
locale #17 e passano i test. Le modifiche Dashboard/CSS sembrano un cluster
separato e non documentato. Git non consente di attribuire con certezza un
autore a modifiche non committate: non vanno presentate come “di Claude” senza
una prova esterna.

## Runbook locale verificato

### Preparazione ambiente

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# Workaround richiesto finché requirements.txt non viene corretto:
.\venv\Scripts\python.exe -m pip install lxml_html_clean==0.4.5

.\venv\Scripts\python.exe -c "import main; print('MAIN_IMPORT_OK')"
```

Non usare `python` o `pip` senza percorso: su questa macchina risolvono anche a
un interprete globale diverso.

### Avvio

Terminale backend:

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

Terminale frontend:

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev
```

Vite usa 5173 o la prima porta libera successiva. La proxy `/api` punta sempre
a `localhost:8000`.

### Configurazione

Nel `.env` backend devono essere presenti almeno:

- `OPENROUTER_API_KEY`;
- `DATABASE_URL`;
- `APP_API_KEY`.

Il frontend deve ricevere `VITE_APP_API_KEY` con lo stesso valore di
`APP_API_KEY`; non registrarne mai il valore nei log.

### Diagnosi rapida spinner

1. Verificare che 8000 sia in ascolto.
2. Eseguire lo smoke import con il Python del venv.
3. Aprire `/api/health` e controllare sia HTTP sia il campo `db`.
4. Controllare la richiesta `/api/dashboard` in DevTools Network.
5. Se è pending, verificare backend e DB; se è 401, riallineare le API key; se
   è 500, leggere il traceback backend.

## Piano di rimedio proposto

### Immediato

1. Correggere `requirements.txt` e aggiungere smoke import nello stesso
   interprete usato dal runtime.
2. Aggiornare CI e Docker con `python -c "import main"` dopo l'installazione.
3. Aggiungere timeout/abort alla fetch dashboard e timeout DB.
4. Decidere esplicitamente se mantenere o annullare il redesign Dashboard
   non committato.

### Breve termine

1. Centralizzare client HTTP, error handling e schema errori.
2. Rendere upload e matching atomici e limitati a chunk.
3. Isolare i log nei test e adottare record di interazione append-only.
4. Aggiungere test frontend per loading/error/success e mutazioni.
5. Correggere autenticazione, download e link URL.

### Evolutivo

1. Migrazioni versionate separate dallo startup.
2. Pool e timeout PostgreSQL, vincoli DB e tipi monetari/data corretti.
3. Autenticazione per utente e audit trail delle mutazioni.
4. E2E browser e smoke deploy automatico.
5. Consolidamento dei documenti in una knowledge base canonica.

## Regola per il registro interazioni

Ogni turno visibile deve produrre un record `INT-YYYYMMDD-NNN` con:

- timestamp ISO-8601 e fuso;
- fonte del timestamp (originale o registrazione retroattiva);
- sessione;
- persona/autore e ruolo;
- modello/deployment per gli assistenti;
- tipo di messaggio;
- contenuto fedele con segreti redatti;
- azioni/esito e file/test correlati;
- riferimento a un record corretto, se applicabile.

I test di estrazione devono avere categoria distinta e non devono scrivere nei
log operativi reali. Le correzioni vanno aggiunte come nuovi record, mai
riscrivendo retroattivamente gli esiti.

## Decisioni ancora richieste all'utente

1. Autorizzare o meno la correzione repository delle dipendenze e degli smoke
   check.
2. Scegliere il destino del redesign Dashboard locale.
3. Scegliere se ristrutturare subito i log o mantenerli compatibili e migrare
   in una fase dedicata.
4. Stabilire se il prossimo intervento debba limitarsi al P0 o includere anche
   gli finding ad alta severità.
