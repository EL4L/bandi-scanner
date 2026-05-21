Fase 1 — Modulo di estrazione AI
Obiettivo: implementare il flusso completo upload → estrazione testo → chiamata Claude → JSON validato. Questo è il blocco critico: tutto il resto dipende da qui.

Durata stimata: 4–6 ore di coding.

RF coperti: RF-004, RF-002, RF-007.

Task:

1.1 — Struttura del progetto e repository GitHub. Prima di scrivere codice, crea la struttura di cartelle e il repository. Struttura consigliata:

bandi-scanner/

├── app.py

├── prompts/ └── system_extraction.md

├── modules/ ├── extractor.py ├── matcher.py └── validator.py

├── data/ └── test_pdfs/

├── db/ └── bandi.db

├── logs/ ├── PROMPT_LOG.md └── INCIDENTS.md

├── error_log.txt

├── .env

├── .gitignore

└── README.md

Aggiungi subito .env e bandi.db al .gitignore. Apri PROMPT_LOG.md e INCIDENTS.md vuoti — inizierai a riempirli da questo momento.

1.2 — Upload PDF (Streamlit file_uploader). In app.py, implementa il componente di upload. Streamlit lo gestisce con st.file_uploader("Carica un bando PDF", type=["pdf"]). Salva il file in una cartella temporanea locale. Mostra un messaggio di conferma con il nome del file caricato.

1.3 — Estrazione testo (PyMuPDF). In modules/extractor.py, scrivi la funzione che riceve il path del PDF e restituisce il testo grezzo. Usa fitz.open() e itera sulle pagine con page.get_text(). Gestisci subito il caso di PDF vuoto o illeggibile: se il testo estratto è sotto una soglia minima (es. meno di 100 caratteri), lancia un'eccezione personalizzata che verrà catturata nel passaggio successivo.

1.4 — Chiamata Claude e parsing JSON. In modules/extractor.py, scrivi la funzione che prende il testo grezzo, carica il prompt da prompts/system_extraction.md, e chiama l'API Anthropic. Usa anthropic.Anthropic() con la chiave da .env. Parsa la risposta e restituisci il dizionario Python. Gestisci il caso in cui la risposta non sia JSON valido (try/except sul parsing).

1.5 — Validatore automatico. In modules/validator.py, scrivi due controlli: (a) validatore di formato — verifica che i campi obbligatori siano presenti e non tutti null; (b) validatore logico — verifica che data_scadenza sia successiva alla data odierna. Definisci la soglia RF-007: se più del 50% dei campi è null, il bando viene marcato come "Da revisionare manualmente" e viene mostrato un warning in UI.

1.6 — Gestione errori e retry. Implementa la logica di retry per API down: max 3 tentativi con attesa di 5 minuti tra uno e l'altro (puoi usare tenacity o un semplice loop con time.sleep). Logga ogni errore in error_log.txt.

1.7 — Test con i PDF reali. Testa il flusso completo con i 3–5 PDF scaricati in fase 0. Per ogni PDF, documenta nel PROMPT_LOG: nome del file, campi estratti correttamente, campi null, comportamento su ambiguità. Se il prompt sbaglia su un caso specifico, aggiusta il prompt e documenta la modifica.

Dipendenze: Fase 0 completata (prompt pronto, PDF disponibili).

Output: modules/extractor.py e modules/validator.py funzionanti, flusso testato sui PDF reali, prime righe nel PROMPT_LOG.

Fase 2 — Profilo cliente
Obiettivo: permettere all'utente di caricare e salvare l'anagrafica dei propri clienti. Tecnicamente indipendente dalla fase 1, ma conviene farla dopo per avere già lo schema del DB definito e non riscriverlo.

Durata stimata: 2–3 ore.

RF coperti: RF-001.

Task:

2.1 — Schema SQLite. In db/, crea lo schema con almeno due tabelle: clienti (id, ragione_sociale, p_iva, codice_ateco, regione, fatturato, dimensione_impresa) e bandi (id, titolo, ente, data_scadenza, codici_ateco, regioni, dimensione, contributo_max, json_completo). Aggiungi una terza tabella match_results (cliente_id, bando_id, score, data_match) per il risultato del matching. Crea lo schema con uno script db/init_db.py che puoi rieseguire senza distruggere i dati esistenti.

2.2 — Form Streamlit. In app.py, aggiungi una sezione "Profilo cliente" con un form Streamlit che raccoglie: ragione sociale, P.IVA, codice ATECO (campo testuale con nota sul formato es. "62.01"), regione (selectbox con le 20 regioni italiane), fatturato annuo (numero), dimensione impresa (radio button: micro/piccola/media/grande). Usa st.form() per raggruppare i campi e inviare tutto in una volta.

2.3 — Salvataggio su SQLite. Al submit del form, salva il profilo nella tabella clienti. Mostra un messaggio di conferma. Aggiungi una sezione "Clienti caricati" che mostra la lista dei profili già salvati con st.dataframe().

2.4 — Modifica e cancellazione. Implementa la possibilità di selezionare un cliente dalla lista e modificarne i dati o cancellarlo. In Streamlit questo si fa con un selectbox e dei pulsanti condizionali. Non è strettamente richiesto dal MVP ma evita di dover resettare il DB ogni volta che inserisci un dato sbagliato durante i test.

Dipendenze: schema DB definito in fase 1 (anche parzialmente).

Output: db/init_db.py, form funzionante, clienti salvati e visualizzati in UI.

Fase 3 — Matching e dashboard
Obiettivo: mettere insieme l'estrazione (fase 1) e il profilo cliente (fase 2) per produrre il risultato finale: score di compatibilità, scheda sintetica, disclaimer, dashboard alert.

Durata stimata: 4–5 ore.

RF coperti: RF-003, RF-005, RF-006, MVP-004, MVP-005.

Questa fase ha un ordine interno rigido: prima il matching, poi la scheda, poi la dashboard.

Task:

3.1 — Logica di matching (score 0–100). In modules/matcher.py, implementa la funzione che prende un dizionario bando e un dizionario cliente e restituisce uno score. La spec dice che lo score deve basarsi su almeno 3 criteri: area geografica, settore (ATECO), dimensione impresa. Proposta di pesi: regione (30 punti) + ATECO (40 punti) + dimensione (20 punti) + fatturato (10 punti). Per l'ATECO: se ateco_aperto_a_tutti è true, assegna il punteggio pieno. Se il codice del cliente è nella lista dei codici ammessi, punteggio pieno. Se la prima parte del codice corrisponde (es. cliente "62.01", bando ammette "62.*"), punteggio parziale. Se nessuna corrispondenza, zero. Documenta i pesi scelti in un commento nel file — saranno discutibili e potresti volerli cambiare.

3.2 — Salva i risultati di matching. Dopo ogni estrazione, esegui il matching contro tutti i clienti in DB e salva i risultati in match_results. Aggiungi un timestamp così puoi tenere traccia di quando è stato fatto il match.

3.3 — Scheda sintetica "Bando in 1 minuto". Implementa la funzione che genera la scheda a partire dal JSON del bando. La scheda deve contenere: titolo, ente, scadenza formattata in italiano (es. "30 giugno 2026"), chi può accedere (regioni + ATECO + dimensione), contributo massimo e percentuale a fondo perduto, spese ammissibili, link alla fonte ufficiale. Tieni la scheda su massimo una pagina — è il criterio di accettazione del RF-005.

3.4 — Disclaimer. Il disclaimer "Dati estratti da AI — verificare sulla fonte ufficiale" deve essere visibile in ogni scheda, con il link al PDF originale. In Streamlit puoi usare st.warning() o un st.info() con il testo del disclaimer. Non nasconderlo, non renderlo opzionale.

3.5 — Dashboard alert. In app.py, aggiungi la sezione principale della dashboard: una lista ordinata per score decrescente dei bandi compatibili con i clienti in portafoglio. Per ogni bando mostra: titolo, score (con una barra di progresso o un colore — verde >70, giallo 40–70, rosso <40), scadenza, i clienti compatibili. Al click su un bando, mostra la scheda sintetica completa. Usa st.expander() per tenere la UI compatta.

Dipendenze: Fase 1 (JSON bandi) + Fase 2 (clienti in DB).

Output: modules/matcher.py, dashboard funzionante end-to-end con almeno un bando reale e un cliente di test.

Fase 4 — Test e documentazione
Obiettivo: verificare che il sistema raggiunga il criterio di accettazione del RF-002 (95% di estrazioni corrette su scadenza, ATECO, massimale) e produrre la documentazione richiesta.

Durata stimata: 3–4 ore distribuite durante tutto il progetto.

Nota importante: questa fase non inizia alla fine — inizia al primo commit. PROMPT_LOG e INCIDENTS vanno tenuti aggiornati durante le fasi 1, 2 e 3.

Task:

4.1 — Test sistematico con i PDF reali. Esegui il flusso completo su tutti i PDF del test set. Per ogni PDF, verifica manualmente l'accuratezza di: data di scadenza (RF-002), codici ATECO, massimale di contributo. Registra i risultati nel PROMPT_LOG con il formato: nome file, campi corretti, campi errati o null, causa dell'errore (ambiguità nel testo? campo assente? formato non standard?), eventuale correzione al prompt.

4.2 — PROMPT_LOG.md. Struttura: una sezione per ogni iterazione del prompt (data, versione, modifica apportata, motivo, risultato sui test). Una sezione per ogni caso anomalo incontrato (es. bando con ATECO descritti a parole invece che con codici, date espresse come "entro 60 giorni dalla pubblicazione", tabelle non estratte correttamente da PyMuPDF).

4.3 — INCIDENTS.md. Struttura: una riga per ogni incident (data, descrizione del problema, impatto, causa, fix applicato). Esempi tipici per questo progetto: API Anthropic non risponde, PDF illeggibile perché composto da immagini scannerizzate, JSON restituito non parsabile, score di matching errato per un caso limite.

4.4 — README.md. Deve contenere: descrizione del progetto in 3 righe, requisiti (Python 3.12, dipendenze), istruzioni di installazione passo passo (pip install -r requirements.txt, configurazione .env, python db/init_db.py, streamlit run app.py), screenshot o GIF della dashboard, nota sui costi API.

4.5 — requirements.txt. Genera con pip freeze > requirements.txt e puliscilo manualmente tenendo solo le dipendenze effettivamente usate: anthropic, streamlit, pymupdf, python-dotenv, eventualmente tenacity per il retry.

4.6 — GitHub. Repository pubblico (o privato se preferisci), con commit significativi per ogni fase — non un unico commit finale. Aggiungi .env.example con le variabili necessarie senza i valori reali.

Dipendenze: Fase 3 completata.

Output: PROMPT_LOG e INCIDENTS completi, README, requirements.txt, repository GitHub in ordine.

Fase 5 — Estensioni v2 (post-MVP)
Tutto ciò che è fuori scope per ora ma già identificato nella spec:

Scraper PA. Crawler automatico sui portali Invitalia, MIMIT, portali regionali. Tecnologie: Scrapy o BeautifulSoup + Playwright per i siti con JavaScript. Da progettare con attenzione ai rate limit e ai cambiamenti di layout.

OCR per PDF scansionati. Integrazione pytesseract per i PDF composti interamente da immagini. Il rischio è già nella spec (sezione 14) — la mitigazione è pronta, va solo implementata.

Notifiche email. Alert automatici ai consulenti quando escono nuovi bandi compatibili con il loro portafoglio. Stack: smtplib o un provider come Resend/SendGrid.

Deploy cloud. Spostamento da locale a un server accessibile da remoto. Opzioni: Streamlit Community Cloud (gratuito, limitato), Railway, Fly.io, o VPS con nginx. Richiede gestione delle variabili d'ambiente in produzione e backup del DB.

Multi-utente. Sistema di login per gestire più consulenti con portafogli clienti separati. Richiede autenticazione (OAuth o semplice email/password) e isolamento dei dati per utente.