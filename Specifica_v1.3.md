**TECHNICAL SPECIFICATION: Bandi AI Scanner (v1.3)**

**0. Sintesi del progetto**

Il sistema **monitora i portali della PA ed estrae dati dai bandi** per
aiutare **i consulenti e i commercialisti** a **identificare opportunità
di finanziamento compatibili con i propri clienti**.

-   **Tipo di sistema:** AI-Agent per web-monitoring e matching B2B.

-   **Obiettivo del MVP:** Automatizzare l\'estrazione dati da PDF e il
    matching con profili cliente.

-   **Output principale:** Dashboard di alert con schede sintetiche e
    score di compatibilità.

**1. Obiettivo del sistema**

Il sistema deve trasformare bandi pubblici non strutturati (PDF) in dati
strutturati (JSON) per eseguire un matching automatico con le
anagrafiche aziendali.

-   **Utente:** Consulenti finanziari/Commercialisti.

-   **Output:** Scheda sintetica strutturata (max 1 pagina) e punteggio
    di compatibilità.

-   **Criterio di accettazione:** L\'output è accettabile se estrae
    correttamente scadenze, codici ATECO ammessi e massimali di spesa
    nel 95% dei casi testati.

**2. Problema che risolve**

I consulenti gestiscono numerosi clienti e faticano a monitorare decine
di fonti PA. Oggi lo fanno manualmente o tramite newsletter generiche,
perdendo ore in lettura o mancando scadenze cruciali. L\'AI aggiunge
valore tramite l\'**estrazione** di criteri specifici e il **confronto**
automatico con i requisiti dei clienti.

**3. Utenti target e contesto d\'uso**

-   **Utente primario:** Commercialista/Consulente con competenze
    digitali medie.

-   **Contesto:** Studio professionale, utilizzo post-caricamento
    anagrafiche clienti.

-   **Scenario:** Ogni mattina il sistema notifica i bandi pubblicati
    nelle ultime 24h compatibili con il portfolio clienti.

**4. Perimetro del MVP**

**Funzionalità Core (In Scope)**

  -----------------------------------------------------------------------------------
  **ID**    **Funzionalità**                      **Priorità**   **Note**
  --------- ------------------------------------- -------------- --------------------
  MVP-001   Upload manuale PDF bando (via         Alta           Sostituisce lo
            Streamlit)                                           scraper per il MVP

  MVP-002   Estrazione AI: ATECO, scadenza,       Alta           Core value
            localizzazione, massimale → JSON                     

  MVP-003   Caricamento profilo cliente (ATECO,   Alta           Form Streamlit +
            regione, fatturato)                                  SQLite

  MVP-004   Matching profilo-bando con score di   Alta           Logica Python
            compatibilità 0-100                                  

  MVP-005   Dashboard alert con scheda sintetica  Alta           Visualizzazione
            "Bando in 1 minuto"                                  risultati
  -----------------------------------------------------------------------------------

**Fuori Scope**

-   Integrazione diretta con portali PA per sottomissione domande.

-   Archiviazione cloud di documenti aziendali pesanti.

**5. Flusso operativo**

1.  **Ingestion:** L'utente carica un PDF tramite l'interfaccia Streamlit.

2.  **Processing:** L\'AI estrae i metadati strutturati dal testo
    grezzo.

3.  **Validation:** Un validatore automatico controlla la coerenza dei
    dati (es. date future).

4.  **Matching:** Algoritmo confronta dati bando con DB clienti.

5.  **Output:** Generazione della dashboard alert per l\'utente.

**6. Requisiti funzionali**

  ------------------------------------------------------------------------------------
  **ID**   **Requisito**                  **Priorità**   **Criterio di accettazione**
  -------- ------------------------------ -------------- -----------------------------
  RF-001   Il sistema deve caricare       Alta           Salvataggio corretto nel DB
           profili clienti (ATECO,                       locale
           Regione, Fatturato)                           

  RF-002   Il sistema deve estrarre la    Alta           Formato YYYY-MM-DD
           data di scadenza bando                        standardizzato

  RF-003   Il sistema deve generare uno   Alta           Punteggio basato sulla
           score di compatibilità 0-100                  corrispondenza di almeno 3
                                                         criteri (Area, Settore,
                                                         Dimensione)

  RF-004   Il sistema deve permettere     Alta           PDF testuale → testo estratto
           l\'upload di un PDF bando e                   senza perdita di contenuto
           estrarre il testo                             

  RF-005   Il sistema deve generare una   Alta           Scheda con: titolo, scadenza,
           scheda sintetica "Bando in 1                  chi può accedere, contributo
           minuto"                                       max, link fonte

  RF-006   Il sistema deve mostrare       Alta           Disclaimer visibile in ogni
           disclaimer "Dati estratti da                  scheda + link al PDF
           AI --- verificare sulla fonte                 originale
           ufficiale"                                    

  RF-007   Il sistema deve gestire PDF    Media          Se l'estrazione fallisce o il
           illeggibili con messaggio "Da                 JSON ha \>50% campi null →
           revisionare manualmente"                      warning
  ------------------------------------------------------------------------------------

**7. Stack tecnologico e dipendenze**

-   **Linguaggio:** Python 3.12 (standard per AI e scraping).

-   **Framework:** Streamlit (interfaccia rapida e reattiva).

-   **Provider AI:** Anthropic (Claude 3.5 Sonnet) per capacità di
    lettura PDF superiori.

-   **Database:** SQLite (leggero e portabile per MVP).

-   **Motivazione:** Costi bassi e tempi di sviluppo entro le 4
    settimane.

**8. Architettura e flusso dati**

-   **Componenti:** Scraper Module, AI Extraction Engine, Matching
    Logic, Streamlit UI.

-   **Percorso dati:** Web -\> PDF (Local Storage) -\> JSON (AI) -\>
    SQLite -\> UI.

-   **Schema JSON:** Il sistema restituisce i dati esclusivamente in
    questo formato:

{
  "bando": {
    "titolo": "Voucher Digitalizzazione PMI",
    "ente": "Invitalia",
    "data_pubblicazione": "2026-04-15",
    "data_scadenza": "2026-06-30",
    "codici_ateco_ammessi": ["62.01", "62.02", "63.11"],
    "ateco_aperto_a_tutti": false,
    "regioni_ammesse": ["Lazio", "Campania", "Puglia"],
    "dimensione_impresa": {
      "micro": true,
      "piccola": true,
      "media": true,
      "grande": false
    },
    "fatturato_max": 50000000,
    "contributo_max": 40000,
    "percentuale_fondo_perduto": 50,
    "spese_ammissibili": ["Software", "Hardware", "Consulenza ICT"],
    "link_fonte_ufficiale": "https://www.invitalia.it/...",
    "note_esclusioni": "Escluse ditte individuali senza dipendenti"
  }
}

**9. Comportamento AI e prompt principali**

-   **Task:** Estrazione dati e sintesi.

-   **Input:** Testo estratto dal PDF.

-   **Output richiesto:** Schema JSON predefinito.

-   **Regola:** Se un\'informazione è assente, indicare \"Null\", non
    inventare (no allucinazioni).

-   **Stima dei costi API:** un bando di 30 pagine ≈ 15.000 token di
    testo. Con Claude 3.5 Sonnet (\$3/M token input, \$15/M token
    output): un\'estrazione costa circa \$0.05 di input + \$0.01 di
    output ≈ \$0.06 per bando. 10 bandi/giorno× 30 giorni ≈ \$18/mese.
    Con GPT-4o-mini sarebbe \~10x meno.

-   **Prompt di sistema:**

> \## Ruolo Sei un analista specializzato in bandi di finanziamento
> pubblici italiani. Leggi documenti ufficiali della PA e ne estrai
> informazioni strutturate.

\## Task

Ricevi il testo di un bando pubblico. Devi estrarre le informazioni

chiave e restituirle in formato JSON secondo lo schema fornito.

\## Schema JSON di output

{
  "bando": {
    "titolo": "Voucher Digitalizzazione PMI",
    "ente": "Invitalia",
    "data_pubblicazione": "2026-04-15",
    "data_scadenza": "2026-06-30",
    "codici_ateco_ammessi": ["62.01", "62.02", "63.11"],
    "attività_ammesse": ["noleggio strutture per eventi", "organizzazione fiere"],
    "ateco_aperto_a_tutti": false,
    "regioni_ammesse": ["Lazio", "Campania", "Puglia"],
    "dimensione_impresa": {
      "micro": true,
      "piccola": true,
      "media": true,
      "grande": false
    },
    "fatturato_max": 50000000,
    "contributo_max": 40000,
    "percentuale_fondo_perduto": 50,
    "spese_ammissibili": ["Software", "Hardware", "Consulenza ICT"],
    "link_fonte_ufficiale": "https://www.invitalia.it/...",
    "note_esclusioni": "Escluse ditte individuali senza dipendenti"
  }
}

\## Vincoli

\- Estrai SOLO informazioni esplicitamente presenti nel testo

\- Se un\'informazione non è presente, usa il valore \"null\" --- NON
inventare

\- Le date devono essere in formato YYYY-MM-DD

\- I codici ATECO devono essere nel formato standard (es. \"62.01\")

\- Se il bando dice \"aperto a tutti i settori\", metti
ateco_aperto_a_tutti: true

e codici_ateco_ammessi: \[\]

\- Se il bando specifica esplicitamente settori ESCLUSI, riportali in
note_esclusioni

\- - In "attivita_ammesse", elenca le azioni o le tipologie di business che il bando intende finanziare (es. "Turismo sostenibile", "Commercio al dettaglio").

\## Strategia di analisi

1\. Cerca prima l\'articolo sui \"Soggetti beneficiari\" per
identificare

chi può accedere (dimensione impresa, ATECO, regioni)

2\. Poi cerca l\'articolo sulle \"Spese ammissibili\" per il tipo di
contributo

3\. Poi cerca le date (pubblicazione, apertura sportello, scadenza)

4\. Infine cerca massimali e percentuali di contributo

\## Esclusioni

\- Non interpretare ambiguità --- segnala con nota

\- Non confondere contributi a fondo perduto con finanziamenti agevolati

\- Non inventare codici ATECO non presenti nel testo

\- Non inventare attività ammesse non presenti nel testo

-   

-   **10. Dati, privacy e vincoli normativi**


-   **Dati:** P.IVA e anagrafiche aziendali pubbliche. Nessun dato
    sensibile trattato.

-   **GDPR:** I dati aziendali non sono soggetti a GDPR come le persone
    fisiche, ma verranno protetti tramite variabili .env per le API key.

-   **AI Act:** Categoria a \"Minimo rischio\" (strumento di supporto
    alla decisione B2B).

**11. Validazione e quality control**

-   **Validatore Formato:** Schema JSON per verificare la presenza di
    campi obbligatori.

-   **Validatore Logico:** Controllo che la data di scadenza sia
    successiva alla data odierna.

-   **Revisione umana:** Il consulente può correggere i dati estratti
    manualmente nella UI.

**12. Gestione errori e fallback**

-   **API Down:** Messaggio di errore all\'utente e riprova tra 5 minuti
    (max 3 tentativi).

-   **PDF illeggibile:** Se l\'estrazione fallisce, il sistema segnala
    il bando come \"Da revisionare manualmente\".

**13. Deploy e manutenzione**

-   **Ambiente:** Locale (laptop del consulente).

-   **Avvio:** streamlit run app.py.

-   **Monitoring:** Log degli errori salvati in error_log.txt.

**14. Rischi, assunzioni e decisioni aperte**

-   **Assunzione:** Il formato dei siti PA non cambia drasticamente
    durante il mese di build.

-   **Rischio:** PDF composti solo da immagini (OCR necessario).
    *Mitigazione:* Integrazione modulo pytesseract.

**15. Checklist pre-build**

-   \[x\] Problema chiaro

-   \[x\] MVP delimitato

-   \[x\] Requisiti verificabili

-   \[x\] Stack motivato

-   \[x\] Specifica congelata (v.1.3)

**16. Registro versioni**

  -------------------------------------------------------------------------------
  **Versione**   **Data**     **Modifica**                           **Autore**
  -------------- ------------ -------------------------------------- ------------
  1.0            04/05/2026   Prima bozza completa                   Matteo

  1.1            05/05/2026   Revisione architettonica e normativa   Matteo

  1.2            10/05/2026   Specifica rivista                      Matteo

  1.3            11/05/2026   Specifica congelata                    Matteo
  -------------------------------------------------------------------------------


