# Roadmap interventi — Bandi Scanner

Analisi completa: vedi `AUDIT_BANDI_SCANNER.md`.

**Legenda effort:** `XS` < 1h · `S` mezza giornata · `M` 1–3 giorni · `L` 1+ settimana

---

## Fase 1 — P0 · Dati sbagliati
> Il prodotto comunica informazioni false o fuorvianti al commercialista. Da risolvere prima di qualsiasi altra cosa.

- [x] **#1 — Fix bool/numeri stringa in `normalize_response`** `S` `Estrazione`
  `bool("false")` restituisce `True` → tutti i clienti ricevono 40/40 punti ATECO per errore. Coercizione di booleani e numerici (con `%`, `€`) in `normalize_response` e nei mesi di `anzianita_impresa`.

- [x] **#2 — Correggi la regola `contributo_max` nel prompt** `S` `Estrazione`
  Il prompt istruisce a usare il massimale spese come `contributo_max`: la card mostra €5M quando il contributo reale è €2,5M. Cambiare la regola: calcola la % oppure lascia `null` se manca la percentuale.

- [x] **#3 — `date_infer`: rimuovi fallback max-data-futura, aggiungi date in lettere** `S` `Estrazione`
  Il fallback prende la data PNRR più lontana come scadenza. Rimuoverlo o degradarlo a warning. Aggiungere regex per date testuali ("31 dicembre 2026"). Aggiungere guardia per sportello continuo.

- [x] **#4 — Scheda: renderizza `note_esclusioni`, urgenza/giorni, disclaimer** `S` `Schede`
  Le esclusioni (il dato che un commercialista controlla per primo) non compaiono nella scheda. Mancano anche giorni alla scadenza, badge urgenza e disclaimer AI — che deve stare nel `.md` scaricabile, non solo in UI.

- [x] **#5 — Fix parser Markdown: link `[x](y)` + file unico condiviso** `S` `Frontend`
  La sezione "Fonte ufficiale" appare con parentesi quadre raw. Il parser è duplicato identico in `CaricaBando.tsx` e `ModalScheda.tsx` — basta che uno dei due riceva il fix e l'altro no. Estrarre in `lib/renderMarkdown.tsx`.

- [x] **#6 — Scadenza + badge urgenza + deadline-strip sulla card Dashboard** `S` `UX/Design`
  Scadenza, giorni e urgenza arrivano già dall'API ma non sono renderizzati nella card. Le classi CSS `badge-alta/media/bassa` e `deadline-strip` esistono e non sono usate. Aggiungere la riga JSX con `card.scadenza`, `card.giorni_alla_scadenza` e `card.urgenza`.

---

## Fase 2 — P1 · Incoerenze tra pagine
> Verdetti, dati e comportamenti che cambiano a seconda di dove guardi. Minano la fiducia nel tool.

- [x] **#7 — Esclusioni ATECO nello scoring: mappa sezioni → divisioni** `M` `Scoring`
  `sezioni_ateco_escluse` non è mai letto dal matcher. Un cliente in Sez. K su un bando che esclude la Sez. K prende 20/40 invece di 0. Implementare la mappa sezione→divisioni e usarla in `_score_ateco` e `check_ammissibilita`.

- [x] **#8 — Dimensione + fatturato come esclusioni binarie in `check_ammissibilita`** `S` `Scoring`
  Un'impresa "grande" su un bando solo-PMI può totalizzare 80% e apparire in verde. Spostare questi criteri (quando il dato cliente è noto) in `check_ammissibilita` come criteri di esclusione, non pesi. La spesa minima da esclusione definitiva a warning.
  - Aggiunto Criterio 8: regione come esclusione binaria (analogo a dimensione/fatturato)

- [x] **#9 — Fix debounce ricerca `Bandi.tsx`** `XS` `Frontend`
  Il `useMemo` ha `query` nelle deps ma usa `debouncedQuery` dentro: il filtro applica sempre il valore precedente. Cambiare la dipendenza a `debouncedQuery` e rimuovere `query`.

- [x] **#10 — Prompt injection: delimitatori attorno a `{raw_text}`** `S` `Estrazione`
  Il testo del PDF ha la stessa autorità delle regole nel prompt. Aggiungere tag `<bando_text>` con istruzione anti-override e, idealmente, separare le regole in `role: system` e il testo in `role: user`.

- [x] **#11 — Dedup lato server in `_dashboard_payload` con merge dei match** `M` `Frontend`
  La dedup client (titolo+ente) non combacia con quella server, produce KPI incoerenti e può nascondere match di un duplicato. Spostare il raggruppamento nel server e restituire `duplicates_count` come campo.

- [x] **#12 — Ammissibilità + motivi esclusione visibili nel modal Clienti** `S` `UX/Design`
  Lo stesso cliente escluso appare con ⛔ in Dashboard e con score normale in Clienti. Propagare `ammissibilita` nell'API `/clienti/{id}/bandi` e mostrare motivi di esclusione e azioni Scheda/Fonte sulle righe.

- [x] **#13 — Stato "Da verificare" per bandi ambigui al posto dello score 0** `M` `Scoring`
  Score 0 comunica "incompatibile", non "dati insufficienti". Fix anche per `bando_has_constraints` che ignora le `attivita_ammesse` testuali, generando falsi ambigui. Restituire uno stato terzo esplicito con badge dedicato in UI.
  - Affinamento UX: badge Da verificare sostituisce lo score (non affianca)

---

## Fase 3 — P2 · Qualità e robustezza
> Miglioramenti all'esperienza, alla solidità tecnica e alla copertura dei casi reali. Non urgenti ma importanti.

- [ ] **#14 — React Query per fetch, cache e invalidation cross-pagina** `M` `Frontend`
  Oggi ogni pagina rifetcha a ogni mount (spinner full-page a ogni navigazione). React Query fornisce cache, navigazione istantanea e `invalidateQueries` per allineare tutte le viste dopo una modifica.

- [ ] **#15 — Font-size scale (min 0.75rem) + spacing scale + migrazione token colori** `M` `UX/Design`
  Oltre 20 font-size diverse nel CSS, alcune a 9–11px (sotto il minimo leggibile per il target 40–55 anni). Colori hardcoded in `Clienti.tsx`, `Bandi.tsx` e nel `.score-circle` invece dei token `--status-*` già creati.

- [ ] **#16 — Campo URL bando in `CaricaBando` + endpoint `/api/estrazione-url`** `M` `UX/Design`
  Molti bandi regionali esistono solo come pagina web. Aggiungere tab "Da URL" con input, endpoint backend che scarica e converte HTML→testo, poi riusa la pipeline esistente. Richiede allow-list schemi e timeout.

- [ ] **#17 — Nuovi campi estrazione: modalità, tipo agevolazione, % per fascia** `L` `Estrazione`
  Mancano: `modalita_presentazione` (sportello/click day/graduatoria), `tipo_agevolazione` (enum), `percentuale_fondo_perduto` per fascia dimensionale (micro/piccola/media separati), `cumulabilita`. Richiede schema + prompt + scheda + UI.

- [x] **#18 — Soglia revisione su campi critici + fix `_is_empty` su dict** `S` `Estrazione`
  La soglia 50% conta tutti i campi con lo stesso peso e sottostima i null perché i dict con valori tutti null passano come "pieni". Usare soglie su campi critici (titolo, scadenza, contributo, ATECO) e correggere `_is_empty`.
  - `_is_empty` ora considera vuoto un dict generico se tutti i suoi valori sono a loro volta vuoti (fix per `anzianita_impresa`, `note_esclusioni`); invariato il caso speciale `dimensione_impresa`.
  - Nuova `critical_gaps()`: segnala mancanza di titolo, data_scadenza (salvo sportello continuo rilevato nel testo), contributo_max/percentuale_fondo_perduto, ATECO (codici/aperto_a_tutti/attività) — indipendentemente dalla % globale, che resta come segnale secondario.
  - Rimossa la `calcola_null_percentage()` duplicata in `extractor.py` (bug: non gestiva affatto i campi dict) e il relativo `result["warning"]`, mai letto da `main.py`: `validate_bando()` in `validator.py` resta l'unica fonte di verità.
  - +12 test in `tests/test_validator.py` (_is_empty su dict, critical_gaps, should_review_manually). Suite: 212 test verdi.

- [ ] **#19 — A11y: sort tastierabile, `aria-expanded`, `aria-label` score circle** `S` `Frontend`
  Header ordinabili senza bottone (non raggiungibili da tastiera, nessun `aria-sort`). Toggle collassabili senza `aria-expanded`/`aria-controls`. Score circle muto per screen reader (mostra "92%" senza contesto).

---

## Fase 4 — P3 · Evoluzione
> Refactoring e nuove feature che non cambiano l'esperienza attuale. Da fare quando le fasi 1–3 sono stabili.

- [ ] **#20 — Refactoring: `lib/icons`, `lib/format`, cartelle componenti** `M` `Frontend`
  Icone SVG duplicate in ~20 punti, `formatEuro`/`giorniColorClass` in 2–3 file. Estrarre in `lib/icons.tsx`, `lib/format.ts`. Poi separare i componenti monolitici per cartella pagina (`dashboard/`, `bandi/`, `clienti/`, `carica/`, `shared/`).

- [ ] **#21 — Colonna match/score e regioni nella tabella Bandi** `M` `UX/Design`
  La tabella non risponde a "questo bando interessa ai miei clienti?". Aggiungere colonne N. match + miglior score (join su `match_results`) e Regioni compatta. Filtro "solo con match" e sort per score.

- [ ] **#22 — Vista cliente come route dedicata + stepper onesto in `CaricaBando`** `M` `UX/Design`
  Il modal cliente non è linkabile né navigabile col tasto back. Promuovere a `/clienti/:id`. Lo stepper upload promette granularità che non c'è (3 fasi, 1 sola chiamata): mostrarlo solo a upload completato, come riepilogo.

---

## Riepilogo

| # | Titolo | Area | Effort | Fase |
|---|--------|------|--------|------|
| 1 | Fix bool/numeri stringa in `normalize_response` | Estrazione | S | P0 |
| 2 | Correggi regola `contributo_max` nel prompt | Estrazione | S | P0 |
| 3 | `date_infer`: fallback + date in lettere | Estrazione | S | P0 |
| 4 | Scheda: `note_esclusioni`, urgenza, disclaimer | Schede | S | P0 |
| 5 | Parser Markdown: link + file unico | Frontend | S | P0 |
| 6 | Scadenza + urgenza sulla card Dashboard | UX/Design | S | P0 |
| 7 | Esclusioni ATECO nello scoring | Scoring | M | P1 |
| 8 | Dimensione + fatturato come esclusioni binarie | Scoring | S | P1 |
| 9 | Fix debounce ricerca `Bandi.tsx` | Frontend | XS | P1 |
| 10 | ~~Prompt injection: delimitatori `{raw_text}`~~ | Estrazione | S | P1 |
| 11 | ~~Dedup lato server con merge dei match~~ | Frontend | M | P1 |
| 12 | ~~Ammissibilità visibile nel modal Clienti~~ | UX/Design | S | P1 |
| 13 | ~~Stato "Da verificare" per bandi ambigui~~ | Scoring | M | P1 |
| 14 | React Query per fetch e cache | Frontend | M | P2 |
| 15 | Font-size scale + spacing + token colori | UX/Design | M | P2 |
| 16 | Campo URL bando + `/api/estrazione-url` | UX/Design | M | P2 |
| 17 | Nuovi campi estrazione: modalità, tipo, % fascia | Estrazione | L | P2 |
| 18 | ~~Soglia revisione su campi critici + `_is_empty`~~ | Estrazione | S | P2 |
| 19 | A11y: sort, `aria-expanded`, score circle | Frontend | S | P2 |
| 20 | Refactoring `lib/icons`, `lib/format`, cartelle | Frontend | M | P3 |
| 21 | Colonna match/score e regioni in tabella Bandi | UX/Design | M | P3 |
| 22 | Vista cliente come route + stepper onesto | UX/Design | M | P3 |
