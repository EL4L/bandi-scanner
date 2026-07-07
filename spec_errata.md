**TECHNICAL SPECIFICATION: Bandi AI Scanner (stato reale — post v1.3)**

**0. Sintesi del progetto**

Il sistema **monitora bandi PA caricati manualmente ed estrae dati dai PDF** per
aiutare **i consulenti e i commercialisti** a **identificare opportunità
di finanziamento compatibili con i propri clienti**.

-   **Tipo di sistema:** applicazione web full-stack (FastAPI + React SPA) per estrazione dati da bandi e matching B2B.

-   **Stato:** applicazione in **produzione su Render.com**, non più MVP locale. Deploy Docker, database Neon PostgreSQL cloud.

-   **Output principale:** Dashboard React con card per bando, score di compatibilità, verifica di ammissibilità binaria, scheda sintetica markdown scaricabile.

**1. Obiettivo del sistema**

Il sistema trasforma bandi pubblici non strutturati (PDF) in dati
strutturati (JSON) per eseguire un matching automatico con le
anagrafiche aziendali, e verifica ulteriormente l'ammissibilità di ogni cliente tramite criteri binari di esclusione.

-   **Utente:** Consulenti finanziari/Commercialisti.

-   **Output:** Scheda sintetica in markdown (con sezione "Requisiti di accesso"), punteggio di compatibilità 0-100 e verdetto di ammissibilità (ammissibile / escluso con motivazione).

-   **Criterio di accettazione :** L'output è accettabile se estrae correttamente scadenze, codici ATECO ammessi e massimali di spesa nella maggioranza dei casi testati.

**2. Problema che risolve**

I consulenti gestiscono numerosi clienti e faticano a monitorare fonti PA disperse. Il sistema riduce il lavoro manuale tramite estrazione automatica e confronto sistematico con i requisiti dei clienti, aggiungendo ora anche un controllo di ammissibilità che va oltre il semplice punteggio di affinità.

**3. Utenti target e contesto d'uso**

-   **Utente primario:** Commercialista/Consulente con competenze digitali medie.

-   **Contesto:** Uso interno, senza autenticazione, accessibile via browser (SPA React servita da FastAPI).

-   **Scenario reale:** Il consulente carica manualmente un PDF di bando tramite drag&drop, il sistema estrae i dati via AI, calcola il matching con l'intera anagrafica clienti e mostra i risultati nella Dashboard, con la possibilità di scaricare una scheda `.md` per ogni bando.

**4. Perimetro effettivo (implementato)**

**Funzionalità Core (Implementate)**

  --------------------------------------------------------------------------------------------
  **ID**    **Funzionalità**                                          **Stato**
  --------- ---------------------------------------------------------- ------------------------
  MVP-001     Upload manuale PDF bando via React SPA (drag&drop)         ✅ Implementato

  MVP-002     Estrazione AI: ATECO, scadenza, regioni, contributo,       ✅ Implementato
            requisiti di ammissibilità → JSON strutturato

  MVP-003     Gestione profilo cliente (CRUD completo) con campi         ✅ Implementato
            estesi: data_costituzione, numero_dipendenti,
            forma_giuridica, descrizione_attivita

  MVP-004     Matching bando-cliente con score 0-100 (Regione/ATECO/     ✅ Implementato
            Dimensione/Fatturato)

  MVP-005     Verifica ammissibilità binaria (anzianità, forma           ✅ Implementato
            giuridica, spesa minima) — indipendente dallo score

  MVP-006     Dashboard React con card, KPI, filtro attivi/scaduti,      ✅ Implementato
            deduplicazione visiva e reale

  MVP-007     Anti-duplicato al salvataggio (titolo+ente) e deduplica    ✅ Implementato
            manuale via API (strict true/false)

  MVP-008     Scheda sintetica markdown con sezione "Requisiti di        ✅ Implementato
            accesso", scaricabile e cacheable in DB

  MVP-009     Export CSV di tutti i match                                ✅ Implementato

  MVP-010     Fallback modello LLM (DeepSeek → Claude Haiku) su          ✅ Implementato
            fallimento del modello primario
  --------------------------------------------------------------------------------------------

**Fuori Scope**

-   Scraping/monitoraggio automatico dei portali PA (upload resta manuale).
-   Integrazione diretta con portali PA per sottomissione domande.
-   OCR per PDF scansionati (solo testo selezionabile supportato).
-   Autenticazione utenti.

**5. Flusso operativo (reale)**

1.  **Ingestion:** L'utente carica un PDF tramite la SPA React (`CaricaBando.tsx`), drag&drop o file picker. Validazione client-side (formato `.pdf`, size ≤ 10 MB) e server-side (size ≤ 10 MB) prima di procedere.

2.  **Processing:** `extract_text_from_pdf()` estrae il testo con PyMuPDF (max 120.000 caratteri, minimo 50 per considerarlo leggibile). `extract_bando_data()` invia il testo a DeepSeek via OpenRouter, con fallback automatico su Claude Haiku se il modello primario fallisce.

3.  **Validation:** `validate_bando()` controlla struttura, formati e coerenza logica; se >50% dei campi sono null, il bando è marcato per revisione manuale.

4.  **Anti-duplicato:** `find_duplicate_bando()` verifica titolo+ente (case-insensitive) prima del salvataggio; se duplicato, restituisce l'id esistente senza salvare nuovamente.

5.  **Matching:** `run_matching_for_bando()` calcola lo score per ogni cliente in anagrafica e salva in `match_results`.

6.  **Output:** Dashboard React (`/`) e pagina Bandi (`/bandi`) mostrano i risultati; per ogni match, oltre allo score, viene calcolato un verdetto di ammissibilità binaria (`check_ammissibilita()`).

**6. Requisiti funzionali (aggiornati)**

  --------------------------------------------------------------------------------------------------
  **ID**    **Requisito**                                          **Stato**
  --------- ------------------------------------------------------- --------------------------------
  RF-001    Gestione profili clienti (CRUD, non solo caricamento)   ✅ Implementato — validazione P.IVA (11 cifre) e ATECO (XX.XX o XX.XX.XX) client-side e server-side
  RF-002    Estrazione data di scadenza in formato YYYY-MM-DD, con  ✅ Implementato — fallback regex in `date_infer.py` se il LLM non estrae la data
            fallback testuale
  RF-003    Score di compatibilità 0-100 su 4 criteri pesati        ✅ Implementato — Regione 30, ATECO 40, Dimensione 20, Fatturato 10
  RF-004    Upload PDF ed estrazione testo senza perdita             ✅ Implementato — PyMuPDF, limite 120.000 caratteri
  RF-005    Scheda sintetica con titolo, scadenza, chi può           ✅ Implementato — sezione aggiuntiva "Requisiti di accesso" (anzianità, forme giuridiche, spese min/max)
            accedere, contributo max, link fonte
  RF-006    Disclaimer "Dati estratti da AI — verificare sulla       ✅ Implementato — banner fisso in `CaricaBando.tsx`
            fonte ufficiale"
  RF-007    Gestione PDF illeggibili → "Da revisionare               ✅ Implementato — `EmptyPDFException` e flag `needs_manual_review` su >50% campi null
            manualmente"
  RF-008    Verifica ammissibilità binaria per anzianità impresa,    ✅ Nuovo — `check_ammissibilita()` in `matcher.py`, indipendente dallo score
            forma giuridica e spesa minima ammissibile
  RF-009    Deduplicazione bandi (automatica al salvataggio e        ✅ Nuovo — endpoint `POST /api/bandi/deduplica`, modalità strict/non-strict
            manuale via API)
  RF-010    Fallback su modello LLM secondario in caso di            ✅ Nuovo — `LLM_FALLBACK_MODEL`, default `claude-haiku-4-5-20251001`
            indisponibilità del modello primario
  --------------------------------------------------------------------------------------------------

**7. Stack tecnologico effettivo**

| Layer | Tecnologia |
|---|---|
| Backend API | FastAPI + Uvicorn (porta 8000) |
| Database | PostgreSQL serverless (Neon cloud) via psycopg2, nessun ORM |
| PDF extraction | PyMuPDF (fitz) |
| LLM primario | OpenRouter API → `deepseek/deepseek-v4-flash` |
| LLM fallback | `claude-haiku-4-5-20251001`, configurabile via `LLM_FALLBACK_MODEL` |
| Retry | tenacity — 3 tentativi, attesa configurabile via `LLM_RETRY_WAIT_SECONDS` (default 60s) |
| Validazione | modulo interno `validator.py` + `schema.py` (no Pydantic per il bando; Pydantic usato solo per i modelli delle request FastAPI) |
| Frontend | React 19 + TypeScript + Vite + React Router v7 |
| Build | Docker multi-stage (Node 20 builder → Python 3.11 runtime) |
| Deployment | Render.com (Docker, `autoDeploy: true`) |

**Motivazione (aggiornata):** rispetto al MVP originario (Streamlit + SQLite + Claude 3.5 Sonnet), il progetto è evoluto verso un'architettura production-ready: React SPA al posto di Streamlit per un'interfaccia più reattiva e personalizzabile, PostgreSQL Neon al posto di SQLite per persistenza cloud, DeepSeek via OpenRouter al posto di Claude diretto per ridurre i costi di estrazione, con fallback su Claude Haiku per resilienza.

**8. Architettura e flusso dati (reale)**

```
bandi-scanner/
├── main.py                     # FastAPI app — tutti gli endpoint /api/*
├── requirements.txt             # Versioni pinnate (pip freeze)
├── Dockerfile                   # Multi-stage: Node build → Python runtime
├── modules/
│   ├── database.py              # Connessione PostgreSQL (wrapper _PGConnection) + CRUD
│   ├── extractor.py              # PDF → testo → chiamata LLM (con fallback) → JSON
│   ├── matcher.py                # Scoring, check_ammissibilita(), genera_scheda()
│   ├── validator.py               # Validazione struttura/formato/logica
│   ├── schema.py                  # BANDO_SCHEMA + normalize_response
│   ├── log_utils.py                # log_error, log_incident, log_prompt_run
│   └── date_infer.py                # Estrazione fallback data scadenza da testo
├── db/
│   └── init_db.py                   # Schema SQL idempotente + migrazioni automatiche colonne
├── prompts/
│   └── system_extraction.md         # Prompt v3.1, con esempi di casi edge
├── frontend/
│   ├── src/
│   │   ├── App.tsx                    # Router + Sidebar
│   │   └── components/
│   │       ├── Dashboard.tsx            # Card bando, KPI, ammissibilità, dedup visiva
│   │       ├── Bandi.tsx                 # Tabella sortable, filtro tab, debounce ricerca
│   │       ├── Clienti.tsx                # CRUD, dettaglio bandi compatibili per cliente
│   │       ├── CaricaBando.tsx             # Upload drag&drop, progress steps, anteprima scheda
│   │       └── ModalScheda.tsx             # Componente condiviso per la scheda (DRY)
│   └── dist/                        # Build statico servito da FastAPI
└── logs/
    ├── INCIDENTS.md
    └── PROMPT_LOG.md
```

**Percorso dati:** Upload PDF (browser) → FastAPI (`/api/estrazione`) → PyMuPDF → OpenRouter/DeepSeek (fallback Claude Haiku) → JSON normalizzato → validazione → PostgreSQL Neon (`bandi`) → matching su tutti i clienti (`match_results`) → React SPA (Dashboard/Bandi/Clienti).

**Schema JSON aggiornato (bando):**

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

Rispetto alla v1.3, sono stati aggiunti: `attivita_ammesse`, `spesa_minima_ammissibile`, `spesa_massima_ammissibile`, `anzianita_impresa`, `forme_giuridiche_ammesse`, `urgenza` (calcolato dal sistema, mai dal LLM); `note_esclusioni` è passato da stringa a oggetto strutturato (`lista_testuale`, `sezioni_ateco_escluse`, `attivita_vietate`).

**9. Comportamento AI e prompt principali (aggiornato — prompt v3.1)**

-   **Task:** Estrazione dati e sintesi da testo bando.
-   **Input:** Testo estratto dal PDF (fino a 120.000 caratteri).
-   **Output richiesto:** Schema JSON come sopra, restituito SOLO come JSON senza markdown o testo prosa.
-   **Regola invariata:** Se un'informazione è assente, `null`, mai inventare.
-   **Regole rigide aggiunte rispetto alla v1.3:**
    -   `ateco_aperto_a_tutti` forzato a `false` se il bando contiene QUALSIASI esclusione settoriale esplicita, anche con platea ampia.
    -   `data_scadenza` deve essere sempre la scadenza finale (non date di apertura sportello o pubblicazione); se relativa (es. "60 giorni dalla pubblicazione") o assente → `null`.
    -   `contributo_max`: se il bando non ha un contributo fisso ma un massimale di spesa, usare quel massimale come proxy.
    -   `percentuale_fondo_perduto`: per agevolazioni miste, calcolare solo la quota effettiva a fondo perduto, annotando il resto in `note_esclusioni.lista_testuale`.
    -   `dimensione_impresa.grande` sempre `false` a meno che il testo autorizzi esplicitamente le grandi imprese.
    -   `sezioni_ateco_escluse`: le attività finanziarie/assicurative vanno in Sezione K (non L).
    -   Il prompt include ora esempi di casi edge (esclusioni settoriali senza lista ammessi, date relative) per guidare l'estrazione.
-   **Fallback modello:** se il modello primario (`LLM_MODEL`, default `deepseek/deepseek-v4-flash`) fallisce con errore retryable, il sistema ritenta automaticamente su `LLM_FALLBACK_MODEL` (default `claude-haiku-4-5-20251001`) prima di segnalare fallimento e loggare un incidente.
-   **Retry:** 3 tentativi per modello, attesa configurabile via `LLM_RETRY_WAIT_SECONDS` (default 60s, non più fisso a 300s come in v1.3).

**10. Dati, privacy e vincoli normativi**

Invariato rispetto alla v1.3: P.IVA e anagrafiche aziendali pubbliche, nessun dato sensibile su persone fisiche. Le API key sono gestite tramite variabili d'ambiente (`.env`, non versionato). Categoria AI Act: rischio minimo (supporto decisionale B2B).

**11. Validazione e quality control**

-   **Validatore struttura/formato:** `validator.py` verifica presenza campi obbligatori secondo `BANDO_SCHEMA`.
-   **Validatore logico:** controlli di coerenza sui formati data e sui valori.
-   **Percentuale di campi null:** se >50%, il bando è marcato per revisione manuale (`needs_manual_review`).
-   **Nuovo — verifica ammissibilità binaria:** `check_ammissibilita()` in `matcher.py` controlla, per ogni coppia bando/cliente, criteri di esclusione netta (non punteggio graduale):
    -   Anzianità minima/massima dalla data di costituzione dell'impresa.
    -   Forma giuridica ammessa/esclusa.
    -   Spesa minima ammissibile rispetto al fatturato dichiarato.
    -   Se uno di questi criteri fallisce, il cliente è marcato "non ammissibile" con motivazione testuale, indipendentemente dallo score di compatibilità.
-   **Revisione umana:** possibile tramite rigenerazione della scheda (`POST /api/bandi/{id}/rigenera-scheda`), utile dopo modifiche al prompt.

**12. Gestione errori e fallback**

-   **API LLM down:** retry automatico 3x con attesa configurabile; se il modello primario fallisce, tentativo automatico su modello fallback; se entrambi falliscono, errore riportato all'utente e incidente loggato in `logs/INCIDENTS.md`.
-   **PDF illeggibile:** `EmptyPDFException` se il testo estratto è sotto la soglia minima (50 caratteri); messaggio "PDF vuoto o non leggibile" mostrato in UI.
-   **File troppo grande:** validazione sia client-side (`CaricaBando.tsx`) sia server-side (`main.py`), limite 10 MB, con messaggio esplicito sulla dimensione effettiva.
-   **Bando duplicato:** nessun errore, ma segnalazione con banner giallo e link al bando già esistente, senza creare un duplicato in DB.
-   **JSON non valido dal LLM:** `InvalidJSONResponse`, loggato come errore.

**13. Deploy e manutenzione (aggiornato)**

-   **Ambiente:** Render.com, container Docker, non più locale.
-   **Avvio produzione:** `uvicorn main:app --host 0.0.0.0 --port $PORT` (con fallback `${PORT:-8000}` se Render non inietta la variabile).
-   **Build:** Docker multi-stage — build del frontend React (Node 20) seguito da runtime Python 3.11 che serve sia le API sia i file statici della SPA.
-   **Deploy automatico:** `autoDeploy: true` — ogni push su `main` triggera un nuovo deploy.
-   **Monitoring:** `logs/INCIDENTS.md` e `logs/PROMPT_LOG.md`, popolati tramite funzioni dedicate in `log_utils.py` (`log_error`, `log_incident`, `log_prompt_run`).
-   **Endpoint di health check:** `GET /api/health`, verifica connessione al database e riporta la versione applicativa corrente (`3.2`).

**14. Rischi, assunzioni e decisioni aperte**

-   **Assunzione (invariata):** il formato dei siti PA e dei bandi non cambia drasticamente.
-   **Rischio (invariato, non mitigato):** PDF composti solo da immagini non sono supportati — OCR non implementato.
-   **Rischio aggiuntivo:** dipendenza da OpenRouter come intermediario per DeepSeek; mitigato parzialmente dal fallback su Claude Haiku, ma un'indisponibilità prolungata di OpenRouter blocca comunque tutte le estrazioni.
-   **Decisione presa:** lo score di ATECO restituisce punteggio parziale (20/40) quando non ci sono dati settoriali estratti, per evitare falsi positivi al 100% (bug noto della v1.3, risolto).
-   **Decisione presa:** un bando senza alcun vincolo dichiarato e non esplicitamente "aperto a tutti" riceve score 0 (ambiguo), per distinguere bandi genuinamente aperti da bandi con estrazione incompleta.

**15. Checklist pre-build (aggiornata a "stato attuale")**

-   [x] Problema chiaro
-   [x] MVP superato — applicazione in produzione
-   [x] Requisiti verificabili
-   [x] Stack aggiornato e motivato
-   [x] Sistema di ammissibilità binaria aggiunto
-   [x] Frontend React completo (Dashboard, Bandi, Clienti, CaricaBando)
-   [x] Anti-duplicato e deduplica manuale
-   [x] Fallback LLM e retry configurabili

**16. Sezioni aggiuntive rispetto alla v1.3**

**16.1 Sistema di ammissibilità (`check_ammissibilita`)**

Funzione indipendente dallo scoring 0-100, in `modules/matcher.py`. Applica tre criteri binari di esclusione:

| Criterio | Logica |
|---|---|
| Anzianità minima/massima | Calcolata dai mesi trascorsi dalla `data_costituzione` del cliente rispetto a `anzianita_impresa.mesi_minimi_dalla_costituzione` / `mesi_massimi_dalla_costituzione` del bando |
| Forma giuridica | Confronto normalizzato (case-insensitive, senza punteggiatura) tra `forma_giuridica` del cliente e `forme_giuridiche_ammesse` del bando |
| Spesa minima ammissibile | Confronto tra `fatturato` del cliente e `spesa_minima_ammissibile` del bando (usato come proxy di capacità di spesa) |

Se un criterio non è verificabile (dato mancante sul cliente), viene segnalato come "non verificabile" senza escludere il cliente. Il risultato (`ammissibile`, `motivi_esclusione`, `criteri_verificati`) è mostrato nella Dashboard con badge "⛔ Non ammissibile" e box esplicativo.

**16.2 Nuovi campi profilo cliente**

Rispetto allo schema clienti della v1.3 (ragione_sociale, p_iva, codice_ateco, regione, fatturato, dimensione_impresa), sono stati aggiunti:

| Campo | Tipo | Uso |
|---|---|---|
| `descrizione_attivita` | TEXT | Migliora il matching quando il bando specifica solo `attivita_ammesse` senza codici ATECO |
| `data_costituzione` | DATE | Calcolo anzianità impresa per `check_ammissibilita` |
| `numero_dipendenti` | INTEGER | Raccolto ma non ancora usato nello scoring/ammissibilità |
| `forma_giuridica` | TEXT | Verifica ammissibilità per forma giuridica |

Tutti opzionali; la migrazione dello schema è gestita automaticamente e idempotentemente da `_migrate_schema()` in `db/init_db.py`.

**16.3 Frontend React — componenti**

| Componente | Responsabilità |
|---|---|
| `Dashboard.tsx` | Card per bando con score, badge urgenza, sezione ammissibilità per cliente, deduplicazione visiva (raggruppamento per titolo+ente), separazione bandi scaduti in sezione collassabile, KPI (bandi totali, abbinamenti, bandi con clienti), export CSV, pulsante "Deduplica" |
| `Bandi.tsx` | Tabella bandi sortable (titolo/scadenza/contributo), tab Tutti/Attivi/Scaduti, filtro per regione, ricerca con debounce 300ms, eliminazione bando con conferma inline |
| `Clienti.tsx` | CRUD completo con validazione P.IVA/ATECO client-side, modale dettaglio con bandi compatibili e breakdown punteggio per singolo cliente |
| `CaricaBando.tsx` | Upload drag&drop con validazione dimensione file, progress steps visivi (caricato/estratto/matchato), banner duplicato, disclaimer AI fisso, link post-successo a Bandi e Dashboard |
| `ModalScheda.tsx` | Componente condiviso (estratto per DRY da Dashboard e Bandi) per il rendering markdown della scheda bando, con azioni download e link fonte |

**16.4 Endpoint API aggiuntivi rispetto alla v1.3**

| Metodo | Path | Descrizione |
|---|---|---|
| POST | `/api/bandi/deduplica` | Rimuove bandi duplicati; body `{"strict": bool}` |
| POST | `/api/bandi/{id}/rigenera-scheda` | Rigenera e ricachea la scheda markdown di un bando |
| GET | `/api/clienti/{id}/bandi` | Bandi compatibili per un singolo cliente, con breakdown score |
| GET | `/api/health` | Health check (DB + versione applicativa) |
| DELETE | `/api/bandi/{id}` | Eliminazione bando (con cascata su match_results) |

**17. Registro versioni**

  -------------------------------------------------------------------------------
  **Versione**   **Data**       **Modifica**                                        **Autore**
  -------------- -------------- --------------------------------------------------- ------------
  1.0            04/05/2026     Prima bozza completa                                Matteo
  1.1            05/05/2026     Revisione architettonica e normativa                Matteo
  1.2            10/05/2026     Specifica rivista                                   Matteo
  1.3            11/05/2026     Specifica congelata (MVP Streamlit + SQLite)        Matteo
  2.0 (errata)   05/07/2026     Riscrittura completa a specchio dello stato reale:  Matteo
                                migrazione a FastAPI + React SPA + PostgreSQL Neon,
                                DeepSeek via OpenRouter con fallback Claude Haiku,
                                sistema di ammissibilità binaria, nuovi campi
                                cliente, anti-duplicato, deploy Render.com
  -------------------------------------------------------------------------------
