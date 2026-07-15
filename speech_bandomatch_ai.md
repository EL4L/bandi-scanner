# Speech — BandoMatch AI

Durata indicativa: 7–9 minuti, prima della demo.

## Slide 1 — Apertura

Buongiorno a tutti. Sono Matteo Pizziconi e oggi vi presento BandoMatch AI, il progetto che ho sviluppato per supportare commercialisti e consulenti nella prima analisi dei bandi destinati alle imprese.

L’obiettivo è trasformare documenti complessi in informazioni strutturate, confrontabili e verificabili, per capire più velocemente quali opportunità meritano un approfondimento per ciascun cliente.

BandoMatch AI non prende una decisione legale e non certifica definitivamente l’ammissibilità. È uno strumento di valutazione preliminare: l’intelligenza artificiale viene utilizzata per comprendere il linguaggio dei bandi, mentre regole software locali rendono il confronto ripetibile e spiegabile. La verifica finale resta sempre al professionista.

## Slide 2 — Il problema

Il problema nasce dal numero e dalla varietà dei bandi da monitorare. Le fonti sono molte, i documenti hanno strutture differenti e le scadenze non sono uniformi.

Leggere il bando è soltanto il primo passaggio. Bisogna individuare destinatari, importi, territori, codici ATECO, forme giuridiche, spese ammissibili ed esclusioni. Successivamente lo stesso controllo deve essere ripetuto cliente per cliente.

Inoltre, la semplice ricerca per parole chiave non è sufficiente: lo stesso requisito può essere espresso in modi diversi e può includere condizioni o eccezioni. Questo rende il lavoro lento e ripetitivo e aumenta il rischio di perdere opportunità o di approfondire casi non pertinenti.

Il vero collo di bottiglia è quindi trasformare il documento in criteri confrontabili.

## Slide 3 — Target e beneficiari

Il target principale è costituito da commercialisti, consulenti d’impresa e piccoli studi di finanza agevolata che gestiscono più clienti e devono stabilire quali bandi approfondire per primi.

La tabella rappresenta proprio un portafoglio clienti: per ogni impresa sono disponibili informazioni come ATECO, regione, dimensione e numero di bandi compatibili rispetto ai dati presenti nel sistema.

Gli utilizzatori diretti sono quindi i professionisti, mentre i beneficiari finali sono le PMI, che possono ricevere segnalazioni più tempestive sulle opportunità da valutare.

Il sistema non sostituisce l’analisi specialistica. Aiuta a ordinare il lavoro, a rendere visibili le motivazioni e a tornare sempre alla fonte ufficiale.

## Slide 4 — Il flusso in quattro passaggi

Il funzionamento può essere riassunto in quattro passaggi.

Il primo è il caricamento: il bando viene inserito tramite un PDF oppure un URL HTTPS.

Il secondo è l’estrazione AI. Il testo viene analizzato per riconoscere importi, requisiti, scadenze, codici ATECO e forme giuridiche, producendo una prima struttura comune.

Il terzo passaggio è il matching. Dopo normalizzazione e validazione, il bando viene confrontato localmente con i profili dei clienti presenti nel sistema.

Infine viene prodotto l’output: una scheda strutturata, un punteggio di compatibilità e uno dei tre esiti operativi — ammissibile rispetto ai dati disponibili, non ammissibile con una motivazione oppure da verificare.

Il PDF originale viene conservato per la consultazione e il download. La fonte ufficiale resta quindi il punto di arrivo della verifica professionale.

## Slide 5 — Dove interviene l’AI

In questa slide è importante distinguere con precisione dove interviene l’intelligenza artificiale e dove interviene invece il software tradizionale.

L’AI svolge tre compiti principali. Prima di tutto converte il testo libero del bando in uno schema JSON comune. Poi interpreta semanticamente formulazioni differenti, quindi non si limita a cercare singole parole chiave. Infine automatizza una parte dell’estrazione e produce una prima scheda da controllare.

L’AI, però, non esegue il matching e non decide l’ammissibilità legale.

Dopo l’estrazione intervengono regole locali che normalizzano date, percentuali e importi, deduplicano gli elenchi, collegano le evidenze e validano i campi critici.

Anche la valutazione preliminare è locale e deterministica. Lo score assegna quaranta punti ad ATECO o attività, trenta alla regione, venti alla dimensione dell’impresa e dieci al fatturato. Serve a ordinare le opportunità: non rappresenta la probabilità di ottenere il finanziamento.

I controlli rigidi disponibili vengono applicati separatamente e la decisione finale rimane al professionista.

## Slide 6 — Stack tecnologico

Dal punto di vista tecnico, il progetto è organizzato in quattro aree.

Il backend utilizza FastAPI e PostgreSQL serverless su Neon. Pydantic gestisce lo schema e la validazione, mentre PyMuPDF estrae il testo e mantiene i riferimenti alle pagine.

Il frontend è una single-page application realizzata con React 19 e TypeScript, costruita con Vite e supportata da React Router e React Query.

Per la parte AI utilizzo DeepSeek attraverso OpenRouter. Claude Haiku 4.5 interviene come modello di fallback se il modello principale non completa correttamente la richiesta.

Il progetto viene distribuito su Render attraverso un’immagine Docker multi-stage, con auto-deploy dal repository GitHub. In produzione FastAPI serve sia le API sia la build del frontend come un unico servizio web.

## Slide 7 — Dati, trasparenza e supervisione

Un aspetto centrale riguarda il confine dei dati.

Il PDF viene elaborato per estrarne il testo e soltanto il testo pubblico del bando viene inviato al provider AI esterno. Il documento originale viene salvato nel database per permettere la consultazione e il download successivi.

I dati dei clienti, invece, non vengono inviati al modello AI. Restano nel sistema perché sono necessari per gestire l’anagrafica e calcolare localmente il matching.

È prevista anche una supervisione umana esplicita: l’AI suggerisce una lettura, ma il commercialista valida sempre. Ogni scheda ricorda inoltre che i dati sono stati estratti con l’AI e possono contenere imprecisioni.

Queste scelte migliorano la trasparenza e la sicurezza del prototipo, ma non rappresentano una certificazione automatica di conformità al GDPR o all’AI Act. Per un prodotto multi-studio sarebbero necessari autenticazione, ruoli e separazione dei dati per organizzazione.

## Slide 8 — Problemi affrontati

Durante lo sviluppo ho affrontato due problemi tecnici importanti.

Il primo riguardava i PDF lunghi. Inizialmente il testo che superava il limite di una singola richiesta poteva essere tagliato senza una segnalazione evidente, facendo perdere informazioni presenti nelle sezioni finali.

Ho risolto il problema introducendo il chunking. Il testo viene diviso in blocchi di circa sessantamila caratteri, con una sovrapposizione di circa duemila caratteri. I blocchi possono essere elaborati in parallelo e i risultati vengono consolidati in un unico JSON. Se il consolidamento tramite AI fallisce, interviene un merge deterministico locale che unisce i risultati seguendo regole fisse. In questo modo tutto il testo estratto entra nel processo, anche se l’interpretazione dell’AI può comunque richiedere una revisione.

Il secondo problema riguardava i falsi positivi sulle esclusioni ATECO. Alcuni divieti erano espressi in forma discorsiva e potevano non essere riconosciuti correttamente. Ho quindi rafforzato il prompt, separato le esclusioni nella struttura dati e aggiunto una normalizzazione locale. Se è presente anche una sola esclusione esplicita, il sistema non può classificare il bando come aperto a tutti.

La stabilità del software è stata verificata con 349 test superati e una copertura complessiva dell’83,32%. Questi numeri misurano il codice, non l’accuratezza semantica dell’AI su ogni possibile bando.

## Slide 9 — Evoluzione futura e passaggio alla demo

Le evoluzioni future seguono quattro direzioni concrete.

La prima è l’OCR, per analizzare anche i PDF costituiti esclusivamente da immagini, che oggi non sono supportati.

La seconda è l’introduzione di login, ruoli e separazione dei dati, necessari per utilizzare il prodotto con più studi professionali.

La terza riguarda la compressione dei file, per ridurre il peso dei PDF durante il caricamento e la conservazione.

La quarta è il miglioramento delle prestazioni, attraverso job asincroni, maggiore parallelismo e ottimizzazione delle chiamate al provider AI.

L’obiettivo è far crescere il progetto senza eliminare il controllo professionale.

A questo punto vorrei passare dalla descrizione al funzionamento concreto. Durante la demo partirò dalla dashboard, aprirò la scheda di un bando, mostrerò il confronto con un cliente e la motivazione del risultato. Infine aprirò il PDF originale, per mostrare che ogni valutazione resta verificabile sulla fonte.

Grazie per l’attenzione. Ora passiamo all’MVP.
