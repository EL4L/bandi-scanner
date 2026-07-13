# Audit indipendente — Bandi Scanner (Estrazione, Matching, Schede, Ammissibilità)

Revisore: Fable 5 (analisi indipendente su richiesta). Materiali esaminati: `modules/matcher.py`,
`modules/schema.py`, `modules/extractor.py`, `modules/validator.py` (parziale), `main.py` (punti di
integrazione), `prompts/system_extraction.md`, `audit_export_bandi.md` (8 bandi + 5 clienti),
testo integrale dei 3 PDF sorgente (`nuova_sabatini_esclusioni.pdf`, `tabelle_spese_ammissibili.pdf`,
`bando_a_cascata_pe1_spoke_5_beneficiari_imprese.pdf`), `data/test_pdfs/test_results/*.json`.

Metodo: confronto diretto testo-sorgente ↔ JSON estratto per i 3 bandi con PDF; verifica di
plausibilità interna per gli altri 5; lettura del codice per B/C/D; una verifica strumentale
(lunghezza testo PDF Sapienza con PyMuPDF, la stessa libreria usata da `extract_text_from_pdf`).

---

## Sintesi (le 5 scoperte più importanti, in ordine di gravità)

**1. `contributo_max` è semanticamente sbagliato in 2 dei 3 bandi verificabili — il numero più
visibile dell'app è inaffidabile per le misure "a leva".** Per la Nuova Sabatini l'estrazione salva
`contributo_max: 4.000.000`, ma il testo dice che 4 milioni è il tetto del **finanziamento
bancario**; il contributo ministeriale è il valore degli interessi convenzionali (2,75–5,5% su 5
anni), cioè nell'ordine di poche centinaia di migliaia di euro al massimo. Per il Fondo impresa
femminile salva `contributo_max: 400.000`, ma 400.000 è il tetto del **piano di spesa**: l'incentivo
massimo è 320.000 (80%), scritto esplicitamente nella slide 10 ("Importo max € 320.000"). In
entrambi i casi il prompt vieta esattamente questo errore ("NON usare il massimale di spese
ammissibili come contributo_max"), ma la regola non regge sui casi reali. Un commercialista che
legge la card vede un beneficio gonfiato di 10x (Sabatini) o del 25% (femminile). Questo problema
non era nel documento preliminare, che sul femminile segnalava solo l'appiattimento delle fasce.

**2. Il `percentuale_fondo_perduto: 25` del Fondo femminile non è un "appiattimento": è una
mislettura.** Nel documento sorgente il 25% è il **tetto del capitale circolante** sul piano di
spesa per imprese >36 mesi ("25% pari a € 100.000"), non una percentuale di fondo perduto. La
percentuale corretta secondo la regola matematica del prompt (80% coperto, metà fondo perduto e
metà tasso zero) sarebbe 40. Inoltre l'estrazione **omette le cooperative** dalle
`forme_giuridiche_ammesse` benché il testo le ammetta esplicitamente ("Cooperative o società di
persone: con almeno il 60% di donne socie"): poiché la forma giuridica è un criterio di esclusione
*duro* in `check_ammissibilita`, un cliente cooperativa verrebbe **escluso a torto**. È il primo
falso negativo di ammissibilità documentabile con la fonte alla mano.

**3. Il bando Sapienza è stato troncato silenziosamente e il vincolo minimo di agevolazione è
andato perso.** Il PDF produce 134.106 caratteri con PyMuPDF, sopra il limite `MAX_TEXT_CHARS =
120.000`: gli ultimi ~14.000 caratteri (parte delle definizioni, Allegato B) non sono mai arrivati
all'LLM, il troncamento finisce solo in `error_log` e il JSON salvato non ne porta traccia. Il
range "agevolazione richiesta compresa tra 200.000 e 238.000 euro" è diventato solo
`contributo_max: 238.000` (soglia minima persa — confermo il preliminare); le intensità GBER
presenti nel testo (RI 70/60/50%, SS fino a 45/35/25% con maggiorazioni) non sono state estratte, e
comunque lo schema attuale non potrebbe rappresentarle (fasce solo micro/piccola/media, nessuna
distinzione Ricerca Industriale vs Sviluppo Sperimentale, niente "grande").

**4. L'ammissibilità è fail-open, e nel DB convivono tre generazioni di schema senza un
meccanismo di ri-estrazione.** In `main.py`, se `check_ammissibilita` solleva un'eccezione il
risultato diventa `{"ammissibile": True, motivi: []}` senza alcun segnale all'utente: un bug nel
controllo di esclusione produce silenziosamente "ammissibile". Sul versioning: negli 8 bandi
esportati si riconoscono tre generazioni (senza `numero_dipendenti_*`; con quelli ma senza
`modalita/tipo/cumulabilita`; completa), e l'unico strumento esistente (`/api/rigenera-scheda`)
rigenera la scheda dal JSON salvato, non ri-estrae. Confermo e rafforzo il punto 4 del preliminare:
senza una colonna `schema_version` e un endpoint di ri-estrazione, ogni evoluzione futura dello
schema aumenta l'entropia del DB.

**5. I vincoli di compagine (impresa femminile, giovanile, startup) sono invisibili al matching.**
Il Fondo impresa femminile è *per definizione* riservato a imprese a prevalenza femminile, ma né lo
schema bando né l'anagrafica cliente hanno un campo per la compagine: qualunque S.r.l. a titolarità
maschile risulta compatibile a punteggio pieno, e l'ammissibilità non la esclude. In Italia le
misure riservate per compagine (femminile, under 36, startup innovative) sono una fetta rilevante
dei bandi: è il buco strutturale più grande dello schema, più del tasso di interesse.

Nota positiva, per onestà: diverse parti sono ben fatte. Il riconoscimento del concorso INPS come
non pertinente senza forzature; la sanificazione anti prompt-injection del delimitatore; la
normalizzazione a enum che scarta le allucinazioni invece di salvarle; la retrocompatibilità del
`percentuale_fondo_perduto` legacy; il matching per categoria delle forme giuridiche con fail-safe
"non riconosciuta → verifica manuale" (esclude solo quando sa classificare); il flag
`bando_ambiguo` che intercetta proprio il caso INPS. Il disclaimer in calce alla scheda è
appropriato.

---

## A. Estrazione dati

### A.1 Confronto campo-per-campo sui 3 bandi con PDF

**Nuova Sabatini (bando #16)** — fonte: circolare di uno studio professionale (non testo
ministeriale — vedi A.4).

| Campo | Estratto | Testo sorgente | Giudizio |
|---|---|---|---|
| dimensione_impresa | micro/piccola/media = true, grande = false | "le micro, piccole e medie imprese (PMI)" | ✔ corretto |
| note_esclusioni (Sez. K, esportazione) | Sez. K + attività export | "attività finanziarie e assicurative; attività connesse all'esportazione…" | ✔ corretto, sezione K giusta |
| contributo_max | 4.000.000 | 4M è il tetto del **finanziamento** ("deliberato per un valore compreso tra 20.000 euro e 4 milioni"); il contributo è il valore degli interessi al 2,75–5,5% | ✘ **errore semantico grave** |
| spesa_minima_ammissibile | 20.000 | 20.000 è il minimo del finanziamento; poiché il finanziamento è "di importo uguale all'investimento", è accettabile come proxy | ~ accettabile |
| data_scadenza | null | misura a sportello permanente | ✔ corretto (regola del prompt rispettata) |
| tasso agevolato | assente dallo schema | 2,75% ordinario; 3,575% 4.0/green; **5,5% Sud**; capitalizzazione 5%/3,575% | ✘ non rappresentabile (il preliminare citava due tassi: sono almeno cinque varianti) |
| tipo_agevolazione | assente (bando pre-#17) | contributo in conto impianti + finanziamento bancario | — campo mancante per generazione schema |

**Fondo impresa femminile (bando #12)** — fonte: slide webinar Invitalia (fonte secondaria).

| Campo | Estratto | Testo sorgente | Giudizio |
|---|---|---|---|
| contributo_max | 400.000 | "Progetti fino a € 400.000, **Importo max € 320.000**, copertura 80%" | ✘ 400k è il piano di spesa; l'incentivo max è 320k |
| percentuale_fondo_perduto | 25 | il 25% è la quota max di **capitale circolante** (>36 mesi); il mix è 50/50 fondo perduto/tasso zero sull'80% → valore corretto secondo la regola del prompt: 40 | ✘ **mislettura**, non appiattimento |
| forme_giuridiche_ammesse | capitali, persone, ditte individuali, lavoratrici autonome | il testo ammette anche **"Cooperative"** (60% donne socie) | ✘ omissione → falso negativo duro in ammissibilità per clienti cooperativa |
| dimensione_impresa | micro/piccola/media = true | il testo **non menziona mai** micro/piccola/media/PMI (verificato con grep: zero occorrenze) | ✘ inferenza non ancorata al testo — risponde alla domanda aperta del preliminare: è deduzione generica, non campionamento parziale |
| anzianita (mesi_min 12) | 12 | "imprese esistenti (da più di 12 mesi)" per la linea Sviluppo | ✔ corretto |
| attivita_ammesse / esclusioni | produzione/servizi/commercio/turismo; escluse agricoltura primaria, pesca ecc. | conforme | ✔ corretto |
| cumulabilita | assente (pre-#17) | la slide 25 ha una clausola esplicita (de minimis, 200.000 €/3 anni) | — perso per generazione schema, non per errore LLM |

**Bando a cascata Sapienza (bando #22)** — fonte: avviso ufficiale, 52 pagine.

| Campo | Estratto | Testo sorgente | Giudizio |
|---|---|---|---|
| contributo_max | 238.000 | "agevolazione richiesta compresa tra 200.000 e 238.000" | ~ tetto giusto, **soglia minima 200.000 persa** (nessun campo per contenerla) |
| riserva Mezzogiorno 145.372,68 € | verbatim in lista_testuale | identico | ✔ corretto, cifra esatta |
| percentuale_fondo_perduto | tutte null | intensità GBER presenti (RI 70/60/50; SS con maggiorazioni fino a 80% cap) | ✘ incompletezza; ma lo schema non potrebbe comunque rappresentare RI vs SS né la fascia "grande" |
| dimensione grande = true | true | intensità previste anche per grandi imprese | ✔ plausibile e coerente |
| cumulabilita | clausola verbatim sul divieto di doppio finanziamento | presente nel testo | ✔ corretto |
| esclusioni DNSH/Hub/Spoke/spin-off | riportate in dettaglio | presenti | ✔ corretto e ricco |
| **troncamento input** | — | 134.106 caratteri (PyMuPDF) > MAX_TEXT_CHARS 120.000: ~14k caratteri finali mai inviati all'LLM | ✘ troncamento **silenzioso** per l'utente; nessun flag nel JSON |

### A.2 Plausibilità interna degli altri 5 bandi

Nessuna allucinazione evidente. #19 (INPS) è il caso migliore: nessuna forzatura, nota esplicita,
tutti i vincoli a zero — e il flag `bando_ambiguo` lo marca correttamente "da verificare". #11
(Fondo rilancio locale, fixture sintetica) coerente col suo PDF di 4 righe. #20 e #21 internamente
coerenti (per #21: contributo 5M al 50% implica spese ~10M, spesa minima 3,5M compatibile). #18
nota: la regola matematica del prompt è stata applicata bene (35% fondo perduto con nota sul 40% a
tasso zero in lista_testuale) — segno che la regola funziona quando il testo è esplicito.

Rilievo trasversale sull'export: **l'anagrafica clienti contiene dati incoerenti** che inquinano
qualunque valutazione del matching — cliente #6 "micro" con 120 dipendenti, cliente #3 "piccola"
con 200 dipendenti. `valida_coerenza_dimensione` esiste ed è corretta rispetto alle soglie UE, ma
evidentemente non è applicata (o non lo era) ai record esistenti. Garbage in, garbage out: il
punteggio "dimensione" di questi clienti non significa nulla.

### A.3 Completezza dello schema (24 campi)

Il caso "tasso di interesse" è reale ma è il sintomo di un problema più generale: **lo schema
modella bene il fondo perduto e male tutto il resto**. Per `finanziamento_agevolato` mancano tasso,
durata, quota di copertura; per il contributo in conto interessi/impianti (Sabatini) non esiste
nemmeno un tipo enum adeguato; per i mix (femminile, #18) la ripartizione vive solo come testo
libero in `lista_testuale`. Su 8 bandi in archivio, almeno 3 (Sabatini, femminile, #18) sono misure
a leva o miste: non è un caso isolato. Secondo buco strutturale: i **requisiti di compagine**
(femminile/giovanile/startup) — vedi sintesi, punto 5. Terzo: nessun campo per il **minimo di
agevolazione richiesta** (Sapienza).

Non consiglio invece di strutturare subito scaglioni per anzianità (tabella femminile): su questo
campione è comparso una volta sola, e la fonte era secondaria. Da riesaminare se ricorre su un
campione più ampio — concordo con la cautela del preliminare.

### A.4 Solidità di system_extraction.md

Il prompt è sopra la media: regole anti-allucinazione esplicite, esempi di edge case, correzione
Sez. K/L, gestione delle esclusioni senza inversione. Tre debolezze:

1. La regola su `contributo_max` copre il caso "percentuale × massimale spese" ma **non** il caso
   "tetto del finanziamento ≠ contributo" (Sabatini) né "piano di spesa ≠ incentivo" (femminile).
   Serve una regola esplicita: *"nei finanziamenti agevolati e nelle misure con copertura
   percentuale, l'importo massimo del finanziamento o del piano di spesa NON è il contributo; se il
   contributo massimo non è esprimibile come cifra certa, usa null"*, con un esempio negativo su
   Sabatini.
2. La regola matematica sul fondo perduto "misto" presuppone che l'LLM identifichi correttamente la
   percentuale di partenza: nel femminile ha agganciato il 25% del circolante. Un esempio negativo
   ("il tetto del capitale circolante NON è la percentuale di fondo perduto") costerebbe poco.
3. La `REGOLA DI DOMINIO` su `dimensione_impresa` ("le agevolazioni di Stato sono destinate alle
   PMI… imposta SEMPRE grande: false salvo autorizzazione esplicita") **incoraggia attivamente
   l'inferenza non ancorata al testo** che si vede nel femminile (micro/piccola/media = true senza
   alcuna menzione nel testo). È in tensione diretta con "Estrai SOLO informazioni esplicitamente
   presenti". Andrebbe riformulata: il default per un testo muto sulle dimensioni dovrebbe essere
   tutto false + bando segnalato ambiguo, non "true sulle tre fasce PMI".

### A.5 Test di accuratezza

Confermo integralmente il punto 5 del preliminare, verificato sui JSON: 7 file, tutti "100.00%",
3–5 campi controllati (titolo, ente, regione/ambito/descrizione), datati 2026-06-02, con 3 fixture
sintetiche. Nessun controllo su date, importi, percentuali, esclusioni, forme, dimensioni. Il
"100%" dichiarato non misura nulla di ciò che questo audit ha trovato rotto: i due errori di
`contributo_max` passerebbero entrambi. La cosa più produttiva emersa da questo audit è che ora
esistono **tre ground truth verificate a mano** (le tabelle in A.1) pronte per diventare un golden
set.

---

## B. Logica di matching e punteggio

### B.1 Pesi e regole

I pesi (ATECO 40, Regione 30, Dimensione 20, Fatturato 10) sono difendibili per l'obiettivo: il
settore è davvero il discriminante principale nei bandi italiani, la regione il secondo. Due
osservazioni:

- La distinzione a tre livelli in `_score_ateco` (match esatto 40, match di divisione 20, attività
  testuali 30/15/15) è ragionevole; l'overlap di token ≥4 caratteri su `attivita_ammesse` è
  grezzo ma dichiaratamente tale, e il flag `settore_da_verificare` lo compensa.
- **Correzione al preliminare**: non è vero che "il dato mancante vale quasi sempre punteggio
  pieno" in modo uniforme. Per l'ATECO il codice dà già `WEIGHT_ATECO // 2` (20/40) quando non c'è
  alcun dato settoriale — un punteggio parziale, esattamente il trattamento che il preliminare
  propone. Sono regione, dimensione e fatturato a dare punteggio pieno su dato bando mancante. La
  scelta "ottimista" resta discutibile, ma il pattern non è coerente nemmeno internamente: allineare
  i quattro criteri (pieno, parziale, o pieno + marcatore) è più importante di quale delle tre
  politiche si scelga.

### B.2 Fatturato cliente mancante = 10/10

Confermato: `float(cliente.get("fatturato") or 0)` fa sì che un fatturato non compilato passi
sempre la soglia. Peggio: 0 e "non compilato" sono indistinguibili. `check_ammissibilita` invece
tratta correttamente il caso ("non verificabile"). Da allineare: fatturato cliente `None` con
vincolo bando presente → punteggio 0 o parziale + "non verificabile", non 10.

### B.3 Doppio controllo dimensione — ridimensiono la gravità

Confermo la divergenza nel codice (`_dimensioni_ammesse` gestisce str/dict/list;
`check_ammissibilita` solo dict), ma in pratica il rischio è **basso**: tutto ciò che entra nel DB
passa da `normalize_response`, che forza `dimensione_impresa` a dict sempre. La divergenza
scatterebbe solo su payload manipolati a mano o percorsi che bypassano la normalizzazione. Vale
comunque la pena unificare (una riga: usare `_dimensioni_ammesse` anche nell'ammissibilità) perché
è gratis e elimina una classe di bug futuri — ma non è un P0/P1 come il preliminare lascia
intendere.

Un caso semantico più interessante, visibile nell'export: il dict **tutto-false** (INPS, #19).
`_dimensioni_ammesse` lo legge come "nessun vincolo" → 20/20 di punteggio dimensione a chiunque.
Per l'INPS è innocuo perché `bando_ambiguo` lo marca "da verificare", ma "tutte false = nessuna
dimensione ammessa" e "tutte false = dato non estratto" sono due significati opposti compressi
nello stesso valore. Con la regola di dominio attuale del prompt (A.4) questa ambiguità crescerà.

### B.4 Fail-open dell'ammissibilità (nuovo, non nel preliminare)

In `main.py` (due punti: lista match e dettaglio cliente), `except Exception → {"ammissibile":
True, ...}`. Un'eccezione nel controllo di esclusione produce "ammissibile" senza distinzione da
un vero esito positivo. Per uno strumento il cui valore è *filtrare* clienti non eleggibili, il
default in errore deve essere "non verificabile / errore", mai "sì".

---

## C. Schede sintetiche

`genera_scheda()` è ben organizzata e il disclaimer finale è giusto. Tre rilievi:

1. **Emoji**: confermato, ⛔🔴🟡🟢 sono generate server-side nel Markdown della scheda. Ma non solo
   lì: `genera_spiegazione_score` usa ✅⚠️❌ e il messaggio del Criterio 4 in `check_ammissibilita`
   contiene ⚠️. Se l'obiettivo del redesign è eliminare le emoji dai testi, vanno rimosse in tutti
   e tre i punti, sostituendole con etichette testuali ("SCADUTO", "urgenza alta"…). Attenzione:
   le schede sono cachate (`scheda_cached`) — dopo la modifica va lanciata la rigenerazione
   (esiste già `/api/rigenera-scheda`, nessuna chiamata LLM necessaria).
2. **Sezioni mancanti**: (a) il tipo di procedura e le date operative (apertura sportello) finiscono
   in `lista_testuale` solo se l'LLM ce le mette — per un commercialista "quando e come si
   presenta" è la sezione più operativa; (b) per le misure a leva la scheda mostra il
   `contributo_max` senza contesto: finché il punto 1 della sintesi non è risolto, la scheda
   amplifica l'errore; (c) manca una sezione "Adempimenti da verificare" (DURC, antimafia,
   procedure concorsuali) alimentabile da `lista_testuale` — vedi D.3.
3. `contributo_max` a scheda con etichetta fissa "Contributo massimo" è fuorviante per Sabatini
   ("Contributo massimo: € 4.000.000"): quando `tipo_agevolazione` contiene
   `finanziamento_agevolato` e non `fondo_perduto`, l'etichetta dovrebbe cambiare o il campo essere
   accompagnato da una qualifica.

---

## D. Ammissibilità / criteri di esclusione

### D.1 Correttezza degli 8 criteri

Implementazione complessivamente corretta e prudente: i casi "dato cliente assente" producono
"non verificabile" invece di escludere (giusto), il matching delle forme giuridiche per categoria è
ben progettato, con il fail-safe "forma non riconosciuta → verifica manuale" (esclude solo quando
sa classificare — ottima scelta). Il calcolo mesi in `check_ammissibilita` (anni×12 + delta mesi)
ignora il giorno del mese: un'impresa costituita il 31 del mese risulta "1 mese" già il 1° del mese
successivo. Impreciso ma marginale.

Nota di coerenza: il Criterio 6 (fatturato max) esclude duramente in ammissibilità, mentre lo score
dà 10/10 al fatturato mancante (B.2). Lo stesso cliente può quindi apparire "100 punti" e "ESCLUSO"
contemporaneamente — tecnicamente coerente (score = affinità, ammissibilità = veto) ma da
comunicare bene in UI, e comunque il veto dovrebbe pesare visivamente più del punteggio.

### D.2 Asimmetria della spesa minima — concordo che resti soft

L'asimmetria è, a mio giudizio, **corretta nel merito**: la spesa minima è un vincolo sul progetto,
non sull'impresa — un fatturato inferiore alla spesa minima non impedisce l'investimento (capitale
proprio, finanziamento, soci). Escludere duramente produrrebbe falsi negativi sistematici, il
contrario della missione dello strumento. Il difetto è solo che la scelta non è documentata: basta
un commento nel codice e un'etichetta chiara nel messaggio ("avviso, non esclusione"). Non
trasformarla in esclusione.

### D.3 Criteri comuni non gestiti

DURC, antimafia, assenza di procedure concorsuali, "impresa non in difficoltà" (RGEC) compaiono in
quasi tutti i bandi reali dell'export come testo libero. **Sconsiglio di strutturarli come criteri
binari verificabili**: l'anagrafica cliente non ha (né potrà ragionevolmente avere aggiornati) quei
dati, quindi un criterio strutturato non potrebbe mai né escludere né confermare — solo generare
"non verificabile" in serie. La forma giusta è una checklist statica "Adempimenti da verificare a
cura del professionista" nella scheda, eventualmente spuntabile. Diverso il discorso per la
**compagine** (femminile/giovanile): quella è verificabile dal commercialista in anagrafica ed è un
criterio di esclusione vero per una classe intera di bandi — è lì che vale la pena investire (punto
5 della sintesi).

---

## Tabella delle modifiche proposte

Legenda ultima riga di ogni cella "Aree/file": **[RI-ESTRAZIONE]** = richiede ri-estrazione LLM dei
bandi in archivio per avere effetto sui dati esistenti; **[SOLO CODICE]** = nessun impatto sui dati
salvati (o rigenerabile senza LLM).

| # | Modifica proposta | Problema che risolve | Effetto sulla web app | Aree/file coinvolti | Priorità | Rischio di regressione |
|---|---|---|---|---|---|---|
| 1 | Regole prompt su `contributo_max` per misure a leva: "il tetto del finanziamento o del piano di spesa NON è il contributo; se il contributo massimo non è una cifra certa nel testo, usa null" + esempio negativo Sabatini + esempio femminile (320k vs 400k) | Contributo gonfiato 10x (Sabatini) e +25% (femminile): il numero più visibile della card/scheda è sbagliato per finanziamenti agevolati e misure a copertura percentuale | Le card e le schede dei bandi a leva mostreranno null (con eventuale dicitura "vedi fonte") o la cifra corretta invece di un beneficio inesistente. **I bandi già estratti restano sbagliati finché non ri-estratti** (#16 e #12 in primis) | `prompts/system_extraction.md` **[RI-ESTRAZIONE]** | **P0** | Basso sul codice; medio sui dati: dopo ri-estrazione alcuni bandi passeranno da una cifra a null (percepibile come "perdita" di dato, in realtà rimozione di un dato falso) |
| 2 | Eliminare il fail-open dell'ammissibilità: in `main.py`, su eccezione restituire `{"ammissibile": null, "errore": true}` e mostrarlo in UI come "verifica non riuscita" | Un bug nel controllo di esclusione oggi produce silenziosamente "ammissibile: True" | Il commercialista vede "verifica non riuscita" invece di un falso via-libera; nessun cambiamento nei casi sani | `main.py` (2 punti), componente frontend che legge `ammissibilita` **[SOLO CODICE]** | **P0** | Basso: cambia solo il ramo d'errore; il frontend deve gestire il nuovo stato null |
| 3 | Versioning + ri-estrazione: colonna `schema_version` su `bandi`, endpoint `POST /api/riestrai/{id}` (riusa la pipeline `_process_and_save_bando` dal testo/PDF originario o dall'URL), badge "schema obsoleto" in UI | Tre generazioni di schema convivono nel DB; ogni evoluzione futura (incluse le modifiche #1, #5, #6, #7 di questa tabella) resta lettera morta sui bandi esistenti | Compare un'azione "Ri-estrai" sui bandi vecchi; dopo l'uso, i bandi pre-#17 acquisiscono modalità/tipo/cumulabilità e le correzioni del prompt. Richiede conservare testo sorgente o file originale (oggi non salvato: da aggiungere al salvataggio) | `db` (migrazione), `main.py`, `modules/extractor.py`, frontend **[SOLO CODICE]** (abilita le ri-estrazioni; ogni ri-estrazione è poi una chiamata LLM) | **P0** | Medio: tocca pipeline di salvataggio; la ri-estrazione sovrascrive `json_completo` → prevedere backup del JSON precedente per rollback |
| 4 | Golden set di regressione dall'audit: trasformare le 3 tabelle di confronto (A.1) in test che verificano ~15 campi ciascuno (importi, percentuali, forme, esclusioni, date) sui 3 PDF reali; ritirare i "100%" superficiali | I test attuali (3–5 campi superficiali, fixture sintetiche) non intercettano nessuno degli errori trovati | Nessun effetto diretto per l'utente; ogni futura modifica al prompt (#1, #7) diventa misurabile invece che a sensazione | `tests/`, `data/test_pdfs/test_results/` **[SOLO CODICE]** (i test chiamano l'LLM: eseguirli on-demand, non in CI a ogni commit) | **P0** | Nullo sul prodotto |
| 5 | Flag di troncamento: quando `_tronca_testo` taglia, salvare `testo_troncato: true` (+ caratteri persi) nel JSON e mostrare un avviso su card/scheda | Il bando Sapienza è stato troncato di ~14k caratteri in totale silenzio verso l'utente | I bandi lunghi mostrano "documento analizzato parzialmente — verificare la fonte". Vale solo per le nuove estrazioni; i bandi già troncati non sono identificabili retroattivamente (a meno di ri-estrazione con #3) | `modules/extractor.py`, `modules/schema.py` (campo di servizio), frontend **[SOLO CODICE]** | **P1** | Basso: campo additivo, nessun consumer esistente da modificare |
| 6 | Campo `agevolazione_min` (o `contributo_min`) nello schema + regola prompt sui range "agevolazione compresa tra X e Y" + visualizzazione in scheda | Il vincolo "tra 200.000 e 238.000" del bando Sapienza perde la soglia minima: un cliente che pianifica una richiesta sotto soglia appare compatibile | La scheda mostra "Agevolazione richiesta: da X a Y"; opzionale un check soft in ammissibilità. Bandi esistenti senza il dato finché non ri-estratti | `modules/schema.py`, `prompts/system_extraction.md`, `modules/matcher.py` (scheda), frontend **[RI-ESTRAZIONE]** | **P1** | Basso: campo nuovo nullable, `normalize_response` già tollera assenze |
| 7 | Blocco `dettaglio_finanziamento` nello schema: `{tasso_percento, tasso_varianti[], durata_max_mesi, quota_copertura_percento}` per `finanziamento_agevolato`/misure miste; etichetta della scheda condizionata al tipo (non "Contributo massimo" per un tetto di finanziamento) | Per i finanziamenti agevolati il beneficio (tasso, durata, copertura) è oggi invisibile: Sabatini ha 5 varianti di tasso, tutte perse; il confronto tra due finanziamenti è impossibile nello strumento | Le card/schede dei finanziamenti mostrano tasso e condizioni; i bandi a leva smettono di sembrare fondo perduto. Bandi esistenti invariati finché non ri-estratti | `modules/schema.py`, `prompts/system_extraction.md`, `modules/matcher.py` (genera_scheda), frontend **[RI-ESTRAZIONE]** | **P1** | Medio: nuovo dict nello schema → aggiornare `normalize_response` e validator; stesso pattern già rodato con `anzianita_impresa`, retrocompatibilità gestibile con default a null |
| 8 | Requisiti di compagine: campo bando `requisiti_compagine` (enum: femminile, giovanile, startup_innovativa, nessuno) + campo cliente corrispondente in anagrafica + criterio duro in `check_ammissibilita` (con "non verificabile" se il dato cliente manca) | Il Fondo impresa femminile risulta compatibile a punteggio pieno per qualunque impresa; classe intera di bandi riservati non filtrabile | I bandi riservati escludono (o marcano "da verificare") i clienti senza requisito; nuovo campo nel form cliente. Bandi esistenti da ri-estrarre; clienti esistenti avranno il campo vuoto → "non verificabile", mai esclusione retroattiva | `modules/schema.py`, `prompts/system_extraction.md`, `modules/matcher.py`, `db` (migrazione clienti), frontend (form cliente + badge) **[RI-ESTRAZIONE]** + migrazione anagrafica | **P1** | Medio: tocca schema bando, schema cliente e ammissibilità insieme; mitigato dal default "non verificabile" |
| 9 | Riformulare la REGOLA DI DOMINIO su `dimensione_impresa`: se il testo non menziona dimensioni, tutto false (il flag `bando_ambiguo` esiste già per gestirlo), eliminando l'istruzione che spinge a presumere "PMI = micro+piccola+media true" | L'inferenza non ancorata vista nel femminile (3 fasce true senza alcuna menzione nel testo): oggi un vincolo dimensionale inventato è indistinguibile da uno reale | I bandi muti sulle dimensioni risulteranno "da verificare" invece che "aperti alle PMI"; qualche punteggio dimensione scenderà da 20 a 20 (nessun vincolo → resta pieno) ma con flag ambiguo più frequente e onesto | `prompts/system_extraction.md` **[RI-ESTRAZIONE]** | **P1** | Medio sui dati: più bandi finiranno in "da verificare"; è il comportamento corretto ma va comunicato (non è un peggioramento, è fine di una finta certezza) |
| 10 | Fatturato cliente mancante ≠ 10/10: se il bando ha `fatturato_max` e il cliente non ha fatturato, punteggio 0 (o metà) + nota "non verificabile" in `genera_spiegazione_score` | Un campo non compilato oggi vale quanto un requisito verificato | I clienti con anagrafica incompleta vedranno punteggi più bassi sui bandi con tetto di fatturato — incentivo a completare l'anagrafica. **Cambia i punteggi salvati in `match_results`**: serve rilanciare `run_matching_for_all_bandi` | `modules/matcher.py` (`_score_fatturato`, spiegazione) **[SOLO CODICE]** + ricalcolo match | **P2** | Medio-percepito: score esistenti si abbassano; nessun rischio tecnico ma prevedere il ricalcolo globale contestuale al deploy |
| 11 | Unificare il controllo dimensione: `check_ammissibilita` Criterio 5 usa `_dimensioni_ammesse` invece del ramo solo-dict | Divergenza potenziale score/ammissibilità su payload non normalizzati (rischio pratico basso: `normalize_response` forza dict — ridimensiono la gravità indicata nel preliminare) | Nessun effetto visibile sui dati attuali; elimina una classe di bug per payload legacy/manipolati | `modules/matcher.py` **[SOLO CODICE]** | **P2** | Molto basso: una sostituzione di funzione già testata nello score |
| 12 | Rimozione emoji server-side in tutti e tre i punti: `genera_scheda` (⛔🔴🟡🟢), `genera_spiegazione_score` (✅⚠️❌), messaggio Criterio 4 (⚠️) → etichette testuali; poi rigenerazione schede cachate via `/api/rigenera-scheda` | Emoji residue nel testo generato lato backend, incoerenti col redesign Radar (indipendenti da quelle già rimosse nei componenti React) | Schede scaricabili/stampabili e spiegazioni score senza emoji; coerenza visiva col nuovo design. Le schede cachate vecchie restano con emoji finché non rigenerate (nessuna chiamata LLM necessaria) | `modules/matcher.py` **[SOLO CODICE]** + rigenerazione schede | **P2** | Basso: se il frontend fa parsing delle emoji per gli stati (verificare i componenti che leggono `spiegazione_score`), aggiornare in coppia — pattern già visto nella regressione card Dashboard |
| 13 | Documentare l'asimmetria della spesa minima: commento esplicito nel codice + etichetta "Avviso (non esclude)" nel messaggio; **non** trasformarla in esclusione | L'eccezione al pattern degli altri 7 criteri è corretta nel merito (vincolo sul progetto, non sull'impresa) ma non dichiarata | Il messaggio in UI chiarisce che è un avviso; nessun cambiamento di esiti | `modules/matcher.py` **[SOLO CODICE]** | **P2** | Nullo |
| 14 | Sezione "Adempimenti da verificare" in `genera_scheda` (checklist statica: DURC, antimafia, procedure concorsuali, impresa non in difficoltà) — in alternativa allo strutturarli come criteri binari, che sarebbero perennemente "non verificabili" | DURC/antimafia/difficoltà oggi vivono solo dentro `lista_testuale` e si perdono nel testo | La scheda stampabile include la checklist operativa che il commercialista comunque deve fare; nessun impatto su score/ammissibilità | `modules/matcher.py` (genera_scheda) **[SOLO CODICE]** | **P2** | Nullo |
| 15 | Bonifica coerenza anagrafica: eseguire `valida_coerenza_dimensione` sui clienti esistenti (script una tantum + warning non bloccante in UI sui record incoerenti) | Nel DB ci sono clienti impossibili (micro con 120 dipendenti, piccola con 200): il punteggio "dimensione" su questi record è privo di significato | Badge "dati incoerenti" sui clienti da sistemare; il matching diventa attendibile su quei profili solo dopo la correzione manuale | `scripts/`, `main.py`, frontend **[SOLO CODICE]** | **P2** | Basso: warning non bloccante, nessuna modifica automatica ai dati |

**Sequenza consigliata**: #2 e #11 subito (mezz'ora totale, solo codice); #4 prima di #1 (senza il
golden set non si misura se la modifica al prompt migliora o peggiora); #3 prima di ogni modifica
allo schema (#6, #7, #8), altrimenti si aggiunge una quarta generazione di dati al DB; #12
coordinandolo con la pausa Codex sul frontend già concordata.

---

## Punti del documento preliminare su cui dissento o ridimensiono

1. **"Dato mancante = punteggio quasi sempre pieno"**: impreciso — l'ATECO dà già punteggio parziale
   (20/40) quando manca il dato. Il problema vero è l'incoerenza tra i quattro criteri, non una
   politica uniforme sbagliata.
2. **Doppio controllo dimensione**: la divergenza esiste nel codice ma `normalize_response` forza il
   dict in tutto ciò che entra nel DB — rischio pratico basso, fix comunque a costo zero (P2, non
   prioritario).
3. **Fondo femminile / percentuale 25**: non è un appiattimento di una tabella a scaglioni — è la
   cifra sbagliata proprio (quota circolante scambiata per fondo perduto). E la lacuna più grave su
   quel bando non è la percentuale ma l'omissione delle cooperative (falso negativo duro) e il
   `contributo_max` a 400k invece di 320k.
4. **Tasso di interesse**: confermo, ma è il sintomo di una modellazione debole di tutte le misure a
   leva (tasso + durata + copertura + etichette di scheda), non un singolo campo mancante. E i tassi
   Sabatini sono cinque varianti, non due.
5. **Domanda aperta sul femminile ("inferenza generica o parte non campionata?")**: risolta —
   verificato sull'intero testo, micro/piccola/media/PMI non compaiono mai. È inferenza generica,
   incoraggiata dalla REGOLA DI DOMINIO del prompt (modifica #9).
