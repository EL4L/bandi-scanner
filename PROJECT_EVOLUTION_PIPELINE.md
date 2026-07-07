# PROJECT_EVOLUTION_PIPELINE.md
> Documento di roadmap tecnica e strategica — aggiornato il 2026-06-26.
> Prospettiva: CTO di un prodotto B2B SaaS in fase early-traction.

---

## 1. Stato Attuale

### 1.1 Architettura reale (non dichiarativa)

```
Browser (React SPA)
       │  REST JSON
       ▼
FastAPI (main.py) ── monolith sincrono, porta 8000
       │
       ├── modules/extractor.py     ← PyMuPDF + OpenRouter/DeepSeek (sincrono, bloccante)
       ├── modules/validator.py     ← validazione struttura + logica + date fallback
       ├── modules/matcher.py       ← scoring 0-100 + generazione schede in-memory
       ├── modules/database.py      ← psycopg2 diretto, wrapper _PGConnection
       └── modules/log_utils.py     ← write-to-file su INCIDENTS.md / PROMPT_LOG.md
              │
              ▼
       PostgreSQL serverless (Neon, free tier)
              │
       Docker multi-stage (Node 20 build → Python 3.11 runtime)
              │
       Render.com (free tier, autoDeploy su push main)
```

**Nessun processo asincrono.** L'endpoint `POST /api/estrazione` blocca il thread FastAPI per tutto il tempo della chiamata LLM (potenzialmente 10-30 secondi). Con più utenti simultanei, questo è un collo di bottiglia immediato.

### 1.2 Punti di forza

| Area | Punto di forza | Impatto |
|---|---|---|
| Estrazione AI | Prompt system_extraction.md ben strutturato, retry tenacity (3x/5min) | Alta affidabilità su connessioni instabili |
| Scoring | Pesi documentati, logica ATECO multi-livello (esatto/prefisso/testuale/ambiguo) | Risultati coerenti e spiegabili |
| Anti-duplicato | Modalità strict (titolo+ente) e loose (solo titolo), esposte via API | Zero duplicati accidentali al caricamento |
| Data fallback | `date_infer.py` con regex + pesi keyword recupera scadenze mancanti dall'LLM | Riduce significativamente i bandi senza data |
| Frontend | React 19 + TypeScript strict, zero dipendenze esterne, toast, urgency rail, conic score ring | UX professionale senza lock-in su librerie |
| Deploy | Docker multi-stage riproducibile, `autoDeploy: true`, schema DB idempotente | CI/CD funzionante dal giorno 1 |
| Logging | INCIDENTS.md + PROMPT_LOG.md con funzioni dedicate in log_utils.py | Tracciabilità per ogni modifica al prompt |

### 1.3 Debolezze strutturali

| # | Problema | File/Linea | Gravità |
|---|---|---|---|
| D1 | `_PGConnection` wrapper sostituisce `?` → `%s` con `str.replace()`: fragile su stringhe SQL che contengono `?` dentro valori letterali | `database.py:52` | Media |
| D2 | `POST /api/estrazione` è sincrono e bloccante: tutta la chiamata LLM (fino a 30s) tiene occupato un worker FastAPI | `main.py:338` | Alta |
| D3 | `GET /api/dashboard` ricalcola `genera_scheda()` e `genera_spiegazione_score()` per ogni bando+cliente ad ogni richiesta, anche a dati invariati | `main.py:131` | Alta |
| D4 | I file PDF in `temp/` non vengono mai eliminati dopo l'elaborazione | `main.py:349` | Bassa (ora), Media (col tempo) |
| D5 | `calculate_score()` ritorna 0 se `!bando_has_constraints()`: bandi senza vincoli non appaiono nei match e non nella dashboard | `matcher.py:141` | Media |
| D6 | Neon free tier: cold-start fino a 3-5s sulla prima connessione dopo un periodo di inattività | `database.py:71` | Bassa |
| D7 | Render free tier: il servizio va in sleep dopo 15 min, il primo request post-sleep può impiegare 30-50s | `render.yaml:5` | Media |
| D8 | Zero test automatizzati: nessun pytest, nessun test di integrazione, nessun test E2E | intero progetto | Alta |
| D9 | Nessuna autenticazione: l'app è completamente aperta | `main.py` | Alta (se multi-utente) |
| D10 | `log_error()` scrive su file locale in Docker: i log vengono persi ad ogni redeploy | `log_utils.py` | Media |

### 1.4 Debito tecnico specifico

| Item | Descrizione | Effort per risolvere |
|---|---|---|
| Placeholder SQL | Usare `%s` nativamente invece del wrapper `?→%s` | 2h — refactor database.py e matcher.py |
| Cleanup temp/ | `os.unlink(file_path)` dopo estrazione, con try/finally | 30min |
| Scheda cached | Serializzare `scheda` nel campo `json_completo` al salvataggio invece di ricalcolarla | 3h — migration + logica |
| Logging strutturato | Passare da write-file a logging stdlib + stdout (catturato da Render) | 2h |
| Bandi senza vincoli | Decidere comportamento corretto: score neutro (50?) o escludi dall'abbinamento | 1h — decisione + test |

---

## 2. Visione Finale

### 2.1 Architettura target (orizzonte 12-18 mesi)

```
Browser (React SPA)
       │  REST + EventSource (SSE per job progress)
       ▼
FastAPI (API Layer) — stateless, scalabile orizzontalmente
       │
       ├── /api/auth        ← JWT + sessions (multi-tenant)
       ├── /api/bandi       ← CRUD + estrazione (task asincrono)
       ├── /api/clienti     ← CRUD isolato per tenant
       ├── /api/match       ← scoring on-demand + cached
       ├── /api/notifiche   ← registro alert inviati
       └── /api/admin       ← monitoraggio, metriche, log
              │
       Background Worker (Celery o ARQ)
              ├── Estrazione LLM (job asincrono)
              ├── Matching batch (job schedulato)
              ├── Scraper portali PA (cron)
              └── Email digest (cron settimanale)
              │
       PostgreSQL (Neon, piano a pagamento o VPS dedicato)
              │
       Redis (cache dashboard + job queue)
              │
       Object Storage (S3/R2 per PDF originali)
              │
       Email provider (Resend o SendGrid)
              │
       Deploy: Render Starter/Standard, o Railway, o VPS
```

### 2.2 Stack target

| Layer | Attuale | Target |
|---|---|---|
| Task queue | — (sincrono) | ARQ (async Python, Redis-backed) |
| Caching | — | Redis (Upstash free tier → a pagamento) |
| Auth | — | JWT stateless + refresh token |
| Email | — | Resend (API + template) |
| Scraping | — | Playwright (headless) + BeautifulSoup |
| OCR | — | pytesseract o Google Document AI |
| Monitoring | — | Sentry (errori) + UptimeRobot (uptime) |
| Log | write-file | stdout → Render Log Stream |
| Storage PDF | temp/ locale | Cloudflare R2 (S3-compatibile) |
| Test | nessuno | pytest + httpx TestClient + Playwright E2E |

### 2.3 Flusso dati target

```
Utente carica PDF
    → FastAPI accetta il file (< 1ms), salva in R2, crea job in Redis queue
    → restituisce job_id e 202 Accepted
    → Worker preleva job, esegue estrazione LLM (bloccante lato worker, non lato API)
    → Worker aggiorna DB, invalida cache Redis per dashboard tenant
    → SSE notifica browser "estrazione completata" → aggiorna UI senza polling
```

---

## 3. Pipeline di Evoluzione

Le fasi sono sequenziali dove indicato da dipendenze; dove indipendenti possono essere parallelizzate.

| Fase | Nome | Stato | Durata stimata | Dipendenze |
|---|---|---|---|---|
| 0 | MVP Fondamenta (Streamlit) | ✅ Completata | — | — |
| 1 | Produzione Core (FastAPI + React + Docker + Neon) | ✅ Completata | — | Fase 0 |
| 2 | Qualità e UX (anti-dup, fix score, redesign, toast) | ✅ Completata | — | Fase 1 |
| 3 | Stabilità e Osservabilità | 🔲 Da fare | 2-3 settimane | Fase 2 |
| 4 | Autenticazione Multi-utente | 🔲 Da fare | 3-4 settimane | Fase 3 |
| 5 | Notifiche Email | 🔲 Da fare | 1-2 settimane | Fase 4 |
| 6 | Scraper Portali PA | 🔲 Da fare | 4-6 settimane | Fase 4 |
| 7 | Estrazione Asincrona e Caching | 🔲 Da fare | 2-3 settimane | Fase 4 |
| 8 | OCR e Intelligenza Avanzata | 🔲 Da fare | 3-4 settimane | Fase 7 |
| 9 | Scalabilità e Monetizzazione | 🔲 Da fare | 4-8 settimane | Fase 7 |

---

## 4. Fasi Dettagliate

---

### ✅ Fase 0 — MVP Fondamenta

**Obiettivo:** prova di fattibilità del flusso PDF → AI → matching.
**Stato:** completata in toto.

Deliverable completati:
- Struttura repo e .gitignore
- `modules/extractor.py` (PyMuPDF + Anthropic API → ora OpenRouter)
- `modules/validator.py` con soglia 50% null
- `modules/matcher.py` con pesi regione/ATECO/dimensione/fatturato
- `db/init_db.py` e schema SQLite (poi migrato a Postgres)
- `logs/INCIDENTS.md` e `logs/PROMPT_LOG.md`
- `prompts/system_extraction.md`
- Interfaccia Streamlit base (sostituita in Fase 1)

---

### ✅ Fase 1 — Produzione Core

**Obiettivo:** portare il sistema in produzione su Render con DB cloud.
**Stato:** completata.

Deliverable completati:
- Migrazione SQLite → PostgreSQL Neon serverless
- `_PGConnection` wrapper per compatibilità placeholder
- FastAPI al posto di Streamlit (`main.py`)
- React 19 + TypeScript SPA (`frontend/`)
- Componenti: Dashboard, Bandi, Clienti, CaricaBando
- Docker multi-stage (Node builder + Python runtime)
- `render.yaml` con autoDeploy
- Endpoint API completi (dashboard, bandi, estrazione, clienti, export CSV)

---

### ✅ Fase 2 — Qualità e UX

**Obiettivo:** eliminare i falsi positivi dallo scoring e portare la UX a livello SaaS professionale.
**Stato:** completata.

Deliverable completati:
- Anti-duplicato strict (titolo+ente) e loose (solo titolo)
- Fix score 100%: ATECO ambiguo → 20pt (era 40pt), fatturato non usa contributo_max come proxy
- `modules/date_infer.py` fallback data scadenza da testo PDF
- `modules/schema.py` BANDO_SCHEMA normalizzato
- Toast notification system (singleton pub/sub, nessuna libreria)
- Sidebar navy con accent rail, score conic-gradient, urgency left-rail
- Tabella sticky header + zebra rows
- Empty state con SVG
- `logs/INCIDENTS.md` aggiornato

---

### 🔲 Fase 3 — Stabilità e Osservabilità

**Obiettivo:** eliminare il debito tecnico accumulato, aggiungere test di base e monitoraggio, rendere il sistema affidabile prima di scalarlo.

**Motivazione:** prima di aggiungere feature nuove (auth, scraper) bisogna avere un sistema di cui ci si può fidare. Aggiungere multi-tenancy su fondamenta fragili moltiplica i problemi.

**Prerequisiti:** Fase 2 completata.

**Dipendenze:** nessuna esterna.

#### 3.1 Test Suite Base

| Task | Priorità | Tempo stimato | Difficoltà |
|---|---|---|---|
| Configurare pytest + httpx TestClient | Alta | 2h | Bassa |
| Test unitari `_score_regione`, `_score_ateco`, `_score_dimensione`, `_score_fatturato` con casi limite | Alta | 4h | Bassa |
| Test `validate_bando()` su JSON malformati | Alta | 3h | Bassa |
| Test `find_duplicate_bando()` strict e loose | Alta | 2h | Bassa |
| Test `extract_text_from_pdf()` su PDF fissi in `data/test_pdfs/` | Media | 2h | Media |
| Test endpoint FastAPI (`/api/clienti`, `/api/bandi`, `/api/dashboard`) con DB test isolato | Alta | 5h | Media |
| CI GitHub Actions: `pytest` ad ogni push | Media | 2h | Bassa |

#### 3.2 Refactoring Debito Tecnico

| Task | Priorità | Tempo stimato | Difficoltà |
|---|---|---|---|
| Rimuovere wrapper `?→%s`: usare `%s` nativamente in tutto `database.py` e `matcher.py` | Alta | 3h | Media |
| Cleanup `temp/` dopo estrazione: `try/finally os.unlink(file_path)` | Media | 30min | Bassa |
| Logging stdout: sostituire `log_error()` con `logging.getLogger()` → catturato da Render | Media | 2h | Bassa |
| Health endpoint: `GET /api/health` → `{"status":"ok","db":"ok","version":"..."}` | Alta | 1h | Bassa |
| Caching scheda: serializzare `scheda` in un campo DB al salvataggio bando, non ricalcolare ad ogni richiesta | Alta | 4h | Media |

#### 3.3 Monitoraggio

| Task | Priorità | Tempo stimato | Difficoltà |
|---|---|---|---|
| UptimeRobot su `/api/health` (alert email se down) | Alta | 30min | Bassa |
| Sentry SDK per cattura errori Python in produzione | Media | 1h | Bassa |
| Aggiungere `X-Request-ID` header per tracciabilità log | Bassa | 1h | Bassa |

**Rischi Fase 3:**
| Rischio | Impatto | Probabilità | Mitigazione |
|---|---|---|---|
| Refactoring `?→%s` introduce regressioni | Alta | Media | Test di integrazione prima del deploy |
| Cache scheda desincronizzata se bando aggiornato | Media | Bassa | Invalidare cache ad ogni re-estrazione |

**Criteri di completamento Fase 3:**
- `pytest` passa senza errori su almeno 20 test unitari
- `GET /api/health` risponde 200 in produzione
- Sentry configurato e riceve il primo evento di test
- `temp/` viene pulita dopo ogni estrazione

---

### 🔲 Fase 4 — Autenticazione Multi-utente

**Obiettivo:** permettere a più consulenti di usare la stessa istanza con dati isolati per account.

**Motivazione:** attualmente l'app è single-tenant senza auth. Un secondo consulente vedrebbe i clienti del primo. Questo blocca qualsiasi acquisizione cliente.

**Prerequisiti:** Fase 3 (test suite e DB stabile).

**Dipendenze:** schema DB modificato (aggiunta colonna `user_id` a `clienti`, `bandi`, `match_results`).

#### 4.1 Backend Auth

| Task | Priorità | Tempo stimato | Difficoltà |
|---|---|---|---|
| Schema DB: tabella `users` (id, email, password_hash, created_at, is_active) | Alta | 1h | Bassa |
| Aggiungere `user_id` (FK → users) a tabelle `clienti`, `bandi`, `match_results` | Alta | 2h | Media |
| Migration DB idempotente in `db/init_db.py` (ALTER TABLE IF NOT EXISTS) | Alta | 2h | Media |
| Endpoint `POST /api/auth/register` (email + password, bcrypt hash) | Alta | 2h | Bassa |
| Endpoint `POST /api/auth/login` (restituisce JWT access token + refresh token) | Alta | 3h | Media |
| Endpoint `POST /api/auth/refresh` (rinnova access token da refresh token) | Alta | 2h | Media |
| Middleware FastAPI `get_current_user`: verifica JWT e inietta `user_id` | Alta | 3h | Media |
| Filtrare tutte le query DB per `user_id` del token | Alta | 4h | Media |
| Rate limiting su `/api/auth/login` (max 5 tentativi / 15min per IP) | Media | 2h | Media |

#### 4.2 Frontend Auth

| Task | Priorità | Tempo stimato | Difficoltà |
|---|---|---|---|
| Componente `Login.tsx`: form email/password, salva JWT in localStorage | Alta | 3h | Media |
| Componente `Register.tsx` | Alta | 2h | Bassa |
| Interceptor fetch: aggiunge `Authorization: Bearer <token>` ad ogni richiesta API | Alta | 2h | Media |
| Redirect a `/login` se 401, refresh automatico su 401 con refresh token | Alta | 3h | Media |
| Navbar: mostra email utente, logout | Media | 1h | Bassa |

**Rischi Fase 4:**
| Rischio | Impatto | Probabilità | Mitigazione |
|---|---|---|---|
| Migration `user_id` rompe dati esistenti | Alta | Alta | Migration con `DEFAULT NULL`, poi dati esistenti assegnati a un utente admin seed |
| JWT compromesso (localStorage vulnerabile a XSS) | Alta | Bassa | HTTPOnly cookie per refresh token; access token short-lived (15min) |
| Utenti dimenticano password (no reset inizialmente) | Media | Media | Aggiungere reset-via-email in Fase 5 come prima priorità |

**Criteri di completamento Fase 4:**
- Due utenti distinti vedono solo i propri clienti e bandi
- Login/logout funziona senza errori di stato
- Token scaduto → redirect automatico a `/login`
- Test di integrazione isolamento tenant

---

### 🔲 Fase 5 — Notifiche Email

**Obiettivo:** alertare i consulenti quando viene caricato un bando compatibile con i loro clienti.

**Motivazione:** senza notifiche, il valore del matching si realizza solo quando l'utente ricorda di aprire l'app. L'email converte la discovery passiva in azione attiva.

**Prerequisiti:** Fase 4 (auth, user_id sui clienti).

#### 5.1 Backend Email

| Task | Priorità | Tempo stimato | Difficoltà |
|---|---|---|---|
| Scegliere provider: Resend (gratuito 3000/mese, API moderna) | Alta | 30min | Bassa |
| Template email: "Nuovo bando compatibile con [cliente]" con score e link | Alta | 3h | Media |
| Tabella `notification_log` (user_id, bando_id, cliente_id, tipo, inviata_at) | Alta | 1h | Bassa |
| Funzione `send_match_notification()`: invia email solo se score > soglia e non già inviata | Alta | 3h | Media |
| Hook in `run_matching_for_bando()`: dopo salvataggio score, chiama `send_match_notification()` | Alta | 1h | Bassa |
| Endpoint `PUT /api/utente/preferenze`: soglia_notifica (default 60), frequenza (immediata/digest) | Media | 2h | Media |
| Email digest settimanale (cron domenica mattina): riepilogo nuovi bandi della settimana | Media | 4h | Media |

**Rischi Fase 5:**
| Rischio | Impatto | Probabilità | Mitigazione |
|---|---|---|---|
| Spam invii multipli per stesso bando/cliente | Alta | Media | `notification_log` come deduplicazione |
| Provider email blocca account per bassa reputazione | Media | Bassa | Configurare SPF/DKIM sul dominio |
| Utente non vuole notifiche | Bassa | Alta | Preferenze granulari e unsubscribe immediato |

**Criteri di completamento Fase 5:**
- Email inviata entro 60 secondi dal caricamento di un bando con match > 60
- Nessun invio duplicato per stessa coppia bando/cliente
- Utente può disattivare notifiche dal profilo

---

### 🔲 Fase 6 — Scraper Portali PA

**Obiettivo:** eliminare il lavoro manuale di caricamento PDF. Lo scanner diventa proattivo.

**Motivazione:** il valore massimo del prodotto è "ti trovo i bandi senza che tu li cerchi". Finché l'upload è manuale, il consulente deve già sapere che un bando esiste.

**Prerequisiti:** Fase 4 (auth per associare bandi al tenant corretto o a un pool condiviso).

**Durata stimata:** 4-6 settimane (la variabilità è alta perché dipende dalla stabilità dei siti PA).

#### 6.1 Architettura Scraper

| Task | Priorità | Tempo stimato | Difficoltà |
|---|---|---|---|
| Definire lista iniziale portali target (Invitalia, MIMIT, Simest, 5 portali regionali) | Alta | 4h | Bassa |
| Struttura base: `scrapers/base.py` con interfaccia `get_pdf_list() → list[PDFSource]` | Alta | 3h | Media |
| Scraper Invitalia: Playwright + BeautifulSoup, estrazione lista bandi + URL PDF | Alta | 8h | Alta |
| Scraper MIMIT: simile a Invitalia | Alta | 6h | Alta |
| Scraper generico per portali statici (solo HTML, no JS) con BeautifulSoup | Media | 4h | Media |
| Cron job: esegue tutti gli scraper ogni 24h, scarica PDF nuovi | Alta | 3h | Media |
| Pipeline auto-estrazione: PDF scaricato → stessa pipeline `extract_bando_data()` → salvataggio | Alta | 2h | Bassa |
| Gestione rate limit: max 1 req/3s per portale, retry esponenziale | Alta | 2h | Media |
| Fingerprint PDF: hash SHA-256 per evitare re-elaborazione dello stesso file | Alta | 2h | Bassa |

**Rischi Fase 6:**
| Rischio | Impatto | Probabilità | Mitigazione |
|---|---|---|---|
| I siti PA cambiano layout → scraper si rompe silenziosamente | Alta | Alta | Alert se nessun PDF nuovo dopo 7gg da portale attivo |
| PDF di bandi scaduti vengono ri-estratti | Media | Alta | Filtro data_scadenza prima di processare |
| Render free tier non supporta processi lunghi / cron | Alta | Alta | Upgrade piano Render o usare GitHub Actions come cron esterno |
| LLM cost spike: centinaia di PDF/settimana | Alta | Media | Limit giornaliero configurabile, alert se cost > soglia |

**Criteri di completamento Fase 6:**
- Almeno 2 portali PA scraper funzionanti e stabili per 4 settimane consecutive
- Zero duplicati introdotti dallo scraper
- Alert funzionante se scraper non produce output per 48h

---

### 🔲 Fase 7 — Estrazione Asincrona e Caching

**Obiettivo:** disaccoppiare la chiamata LLM dal ciclo richiesta-risposta HTTP. Prerequisito tecnico per gestire volumi più alti (scraper + multi-utente).

**Motivazione:** con lo scraper attivo e più utenti, le chiamate LLM sincrone saturerebbero i worker FastAPI. Un sistema asincrono con job queue è l'unica architettura sostenibile.

**Prerequisiti:** Fase 4 (auth). Può essere parallelizzata con Fase 5 e 6 se si lavora in parallelo.

#### 7.1 Job Queue (ARQ + Redis)

| Task | Priorità | Tempo stimato | Difficoltà |
|---|---|---|---|
| Aggiungere Redis (Upstash, free tier) come broker | Alta | 2h | Bassa |
| Installare ARQ (async Python worker, senza Celery overhead) | Alta | 2h | Bassa |
| Convertire `extract_bando_data()` in task ARQ asincrono | Alta | 4h | Media |
| `POST /api/estrazione` ritorna 202 + `job_id` invece di bloccare | Alta | 3h | Media |
| SSE endpoint `GET /api/jobs/{job_id}/stream` per notifica completamento | Alta | 4h | Alta |
| Frontend: polling o SSE su job_id → aggiorna UI quando estrazione completata | Alta | 4h | Media |
| Dashboard job: `GET /api/jobs` lista job dell'utente (in-queue, processing, done, failed) | Media | 3h | Media |

#### 7.2 Cache Dashboard

| Task | Priorità | Tempo stimato | Difficoltà |
|---|---|---|---|
| Cache Redis per `_dashboard_payload()` con TTL 5min, chiave per `user_id` | Alta | 3h | Media |
| Invalidare cache quando nuovo bando/cliente viene aggiunto | Alta | 2h | Bassa |
| Cache per `genera_scheda()`: serializzare al salvataggio bando (rimuovere calcolo on-the-fly) | Alta | 3h | Media |

**Rischi Fase 7:**
| Rischio | Impatto | Probabilità | Mitigazione |
|---|---|---|---|
| Redis Upstash free tier (10k cmd/giorno) superato | Bassa | Media | Upgrade $7/mese o self-host su VPS |
| SSE non supportato da alcuni proxy/CDN | Media | Bassa | Fallback a polling ogni 3s se SSE non disponibile |
| Job falliti senza retry visibile all'utente | Alta | Media | UI mostra stato "Errore" con possibilità di ri-tentare |

**Criteri di completamento Fase 7:**
- Upload PDF ritorna 202 entro 500ms (non più 10-30s)
- Dashboard carica in < 200ms con cache calda
- Job falliti sono visibili e re-tentabili dall'utente

---

### 🔲 Fase 8 — OCR e Intelligenza Avanzata

**Obiettivo:** supportare PDF scansionati (immagini) e migliorare l'accuratezza dell'estrazione.

**Prerequisiti:** Fase 7 (estrazione asincrona, indispensabile perché OCR è più lento di PyMuPDF).

#### 8.1 OCR

| Task | Priorità | Tempo stimato | Difficoltà |
|---|---|---|---|
| Rilevamento PDF-immagine: se PyMuPDF estrae < 100 char, fallback OCR | Alta | 2h | Bassa |
| Integrazione pytesseract (open source, locale, zero costo) per OCR base | Alta | 4h | Media |
| Valutazione Google Document AI vs pytesseract su un test set di 20 PDF reali | Media | 8h | Media |
| Pre-processing immagine: deskew, denoise prima di OCR (Pillow + OpenCV) | Bassa | 6h | Alta |

#### 8.2 Prompt Engineering Avanzato

| Task | Priorità | Tempo stimato | Difficoltà |
|---|---|---|---|
| Benchmark attuale: testare il prompt su 50 PDF reali, misurare accuracy per campo | Alta | 8h | Media |
| Versioning prompt: `prompts/system_extraction_v2.md` con A/B test | Alta | 4h | Media |
| Few-shot examples nel prompt: 3-5 esempi di bandi difficili con output atteso | Alta | 6h | Media |
| Confidence score per campo: chiedere all'LLM "quanto sei sicuro di X?" (0-1) | Media | 4h | Alta |
| Campo `needs_ocr` nel JSON estrazione: segnala se il PDF era probabilmente scansionato | Media | 2h | Bassa |

**Criteri di completamento Fase 8:**
- PDF scansionati producono output invece di `EmptyPDFException`
- Accuracy data_scadenza > 90% su test set di 50 PDF
- Confidence score visibile nell'UI per i campi incerti

---

### 🔲 Fase 9 — Scalabilità e Monetizzazione

**Obiettivo:** rendere il prodotto commercialmente sostenibile.

**Prerequisiti:** Fase 4 (auth multi-utente), Fase 7 (architettura asincrona).

| Task | Priorità | Tempo stimato | Difficoltà |
|---|---|---|---|
| Piani: Free (3 clienti, 10 bandi/mese), Pro (illimitato, €29/mese) | Alta | — | Business |
| Billing: Stripe Checkout per upgrade piano | Alta | 8h | Media |
| Tabella `subscriptions` (user_id, piano, scade_il, stripe_customer_id) | Alta | 2h | Bassa |
| Limiti automatici: middleware che blocca se over-quota | Alta | 4h | Media |
| Upgrade piano Render: Starter ($7/mese, no sleep) o Standard ($25/mese) | Alta | 1h | Bassa |
| Neon upgrade: piano Launch ($19/mese) per connection pooling e nessun cold-start | Alta | 1h | Bassa |
| Landing page pubblica con pricing | Media | 8h | Media |
| Admin panel: metriche globali (bandi totali, utenti, estrazioni/giorno, LLM cost) | Media | 8h | Alta |

---

## 5. Task Dettagliati — Fase Prioritaria (Fase 3)

*Fase 3 è il prossimo step da eseguire. Tutti i task riportati con stima realistica.*

| # | Task | Priorità | Dipendenze | Tempo | Difficoltà | Stato |
|---|---|---|---|---|---|---|
| 3.1.1 | Configurare pytest + `conftest.py` con fixture DB test in-memory | P1 | — | 2h | Bassa | 🔲 |
| 3.1.2 | Test unitari scorer (16 casi limite per ATECO, regione, dimensione, fatturato) | P1 | 3.1.1 | 4h | Bassa | 🔲 |
| 3.1.3 | Test `validate_bando()` su 10 casi: JSON valido, chiavi mancanti, date passate, null>50% | P1 | 3.1.1 | 3h | Bassa | 🔲 |
| 3.1.4 | Test `find_duplicate_bando()` strict e loose | P1 | 3.1.1 | 2h | Bassa | 🔲 |
| 3.1.5 | Test endpoint FastAPI con `httpx.AsyncClient` + DB test isolato | P1 | 3.1.1 | 5h | Media | 🔲 |
| 3.1.6 | GitHub Actions: workflow `pytest` su push a `main` e PR | P2 | 3.1.5 | 2h | Bassa | 🔲 |
| 3.2.1 | Refactoring `database.py`: sostituire `?` con `%s` e rimuovere wrapper replace | P1 | 3.1.5 | 3h | Media | 🔲 |
| 3.2.2 | Refactoring `matcher.py`: allineare placeholder dopo 3.2.1 | P1 | 3.2.1 | 1h | Bassa | 🔲 |
| 3.2.3 | Cleanup `temp/`: `try/finally os.unlink(file_path)` in `main.py:349` | P2 | — | 30min | Bassa | 🔲 |
| 3.2.4 | `GET /api/health` endpoint con check DB ping | P1 | — | 1h | Bassa | 🔲 |
| 3.2.5 | Logging stdout con `logging.getLogger()`, rimuovere write-file da `log_utils.py` | P2 | — | 2h | Bassa | 🔲 |
| 3.2.6 | Caching scheda bando: serializzare in DB al `save_bando_from_json()` | P1 | 3.1.5 | 4h | Media | 🔲 |
| 3.3.1 | UptimeRobot monitor su `/api/health` con alert email | P1 | 3.2.4 | 30min | Bassa | 🔲 |
| 3.3.2 | Sentry SDK: `pip install sentry-sdk`, init in `main.py` on_startup | P2 | — | 1h | Bassa | 🔲 |

---

## 6. Matrice delle Dipendenze

```
Fase 3 ──────────────────────────────────────────────────────────┐
    (stabilità, test, refactor DB)                               │
         │                                                        │
         ▼                                                        │
Fase 4 (auth multi-utente) ──────────────────────────────────────┤
         │                                                        │
         ├──────────────────────────────────────────────────────►Fase 9 (monetizzazione)
         │
         ├──────────────► Fase 5 (email) ──────────────────────►(può essere parallelizzata)
         │
         ├──────────────► Fase 6 (scraper) ─────────────────────►(richiede infra stabile)
         │
         └──────────────► Fase 7 (async + cache) ──────────────► Fase 8 (OCR + AI avanzato)
```

**Cosa blocca cosa — tabella sintetica:**

| Fase bloccante | Fase bloccata | Motivo |
|---|---|---|
| Fase 3 (DB refactor + test) | Fase 4 | Auth introduce migration DB; farlo su fondamenta non testate è ad alto rischio |
| Fase 4 (user_id su tabelle) | Fase 5 | Le notifiche richiedono sapere a quale utente inviarle |
| Fase 4 (user_id su tabelle) | Fase 6 | I bandi dello scraper devono essere associati a un tenant o a un pool globale — decisione impossibile senza auth |
| Fase 4 (auth) | Fase 9 | Il billing richiede identità utente e piani per account |
| Fase 7 (async) | Fase 8 | OCR richiede estrazione asincrona (OCR + LLM = 60-120s) |
| Fase 3 (scheda cached) | Fase 7 | Non ha senso aggiungere Redis se il calcolo a valle è già ottimizzato |

---

## 7. Piano dei Test

### 7.1 Test per Fase

| Fase | Tipo | Descrizione | Strumento |
|---|---|---|---|
| 3 | Unitario | `_score_*` con casi limite ATECO (esatto, prefisso, no match, ambiguo), regione (match, no match, nessun vincolo), dimensione, fatturato | pytest |
| 3 | Unitario | `validate_bando()`: JSON valido, null>50%, data passata, struttura mancante | pytest |
| 3 | Integrazione | Endpoint CRUD clienti: crea, leggi, modifica, elimina via httpx TestClient | pytest + httpx |
| 3 | Integrazione | `find_duplicate_bando()` strict/loose su DB test | pytest |
| 3 | Regressione | Score fisso su bando/cliente di riferimento dopo refactoring placeholder | pytest |
| 4 | Sicurezza | Endpoint protetto restituisce 401 senza token valido | pytest |
| 4 | Sicurezza | Utente A non può leggere clienti di utente B | pytest |
| 4 | Integrazione | Flusso register → login → JWT → richiesta protetta | pytest |
| 5 | Integrazione | Email inviata dopo caricamento bando con match > 60 | Mock provider (mailhog) |
| 5 | Regressione | Nessuna email duplicata per stessa coppia bando/cliente | pytest |
| 6 | Funzionale | Scraper Invitalia restituisce almeno 1 PDF in ambiente staging | playwright |
| 6 | Regressione | Hash SHA-256 impedisce re-elaborazione dello stesso PDF | pytest |
| 7 | Performance | `GET /api/dashboard` con cache calda < 200ms (10 bandi, 5 clienti) | pytest + time |
| 7 | Performance | `POST /api/estrazione` risponde entro 500ms (job accodato) | pytest + time |
| 8 | AI accuracy | data_scadenza estratta correttamente su 50 PDF del test set | script manuale |
| 8 | Funzionale | PDF scansionato non lancia EmptyPDFException dopo OCR | pytest |

### 7.2 Test AI (Prompt Regression)

Nessun test automatizzato può sostituire la review umana sull'LLM, ma si può limitare la deriva:

| Test | Frequenza | Come |
|---|---|---|
| Accuracy test set 20 PDF fissi | Ogni modifica al prompt | Script Python che confronta output LLM con ground truth manuale |
| Distribuzione null_percentage | Settimanale | Query DB: `AVG(null_percentage) GROUP BY date_trunc('week', created_at)` |
| Frequenza `needs_manual_review` | Settimanale | Alert se supera 30% delle estrazioni recenti |

### 7.3 Test UX

| Test | Strumento | Quando |
|---|---|---|
| Upload PDF → estrazione → scheda visibile in dashboard | Playwright E2E | Ogni deploy |
| Crea cliente → match calcolato automaticamente | Playwright E2E | Ogni deploy |
| Login → cambio pagina → sessione persistente | Playwright E2E | Dopo Fase 4 |
| Toast visibile dopo azione e scompare dopo 4s | Playwright E2E | Ogni deploy |

---

## 8. Rischi — Matrice Completa

| # | Fase | Problema | Impatto | Probabilità | Mitigazione |
|---|---|---|---|---|---|
| R1 | 3 | Refactoring placeholder DB rompe query con `?` in valori stringa | Alta | Media | Test di integrazione completi prima di deploy; rollback facile con git |
| R2 | 4 | Migration `ALTER TABLE ADD COLUMN user_id` su tabelle con dati esistenti | Alta | Alta | `DEFAULT NULL` + script seed che assegna dati a utente admin; testare in staging |
| R3 | 4 | JWT rubato da localStorage (XSS) | Alta | Bassa | Content Security Policy header; refresh token in HttpOnly cookie |
| R4 | 6 | Siti PA cambiano layout senza preavviso | Alta | Alta (certezza) | Monitoring alert + design modulare degli scraper (1 file = 1 portale) |
| R5 | 6 | Costi LLM esplodono con scraper automatico (100+ PDF/giorno) | Alta | Media | Limite configurabile per tenant; alert se cost > €10/giorno; modello cheaper per triage |
| R6 | 7 | Redis Upstash free tier (10k cmd/giorno) esaurito in produzione | Media | Media | Upgrade $7/mese anticipato al primo utente pagante |
| R7 | 8 | OCR pytesseract di bassa qualità su documenti PA scansionati male | Alta | Alta | Test su campione reale prima del rollout; fallback a errore esplicito "PDF non leggibile" |
| R8 | 9 | Render free tier va in sleep → primo utente ha esperienza terribile | Alta | Certezza | Upgrade a Starter ($7/mese) prima di qualsiasi acquisizione utente |
| R9 | Trasversale | Deepseek v4-flash deprecato o degradato da OpenRouter | Alta | Media | Astrarre il modello in variabile d'ambiente; testare su claude-haiku-4-5 come fallback |
| R10 | Trasversale | Neon free tier raggiunge limite connessioni (max 10) con più utenti | Alta | Media | Neon Launch ($19/mese) ha connection pooling e max 100 conn |

---

## 9. Priorità — Matrice Impatto/Costo

| Feature | Impatto Business | Qualità Tecnica | Scalabilità | Costo Dev | ROI Stimato | Priorità |
|---|---|---|---|---|---|---|
| Test suite (Fase 3) | Medio | Critico | Critico | Basso (2gg) | Altissimo (previene regressioni) | **P0** |
| Refactoring placeholder DB (Fase 3) | Basso | Critico | Medio | Basso (1gg) | Alto (elimina bug latente) | **P0** |
| Health endpoint + UptimeRobot (Fase 3) | Medio | Alto | Basso | Basso (0.5gg) | Alto | **P0** |
| Auth multi-utente (Fase 4) | Critico | Alto | Critico | Alto (3gg BE + 2gg FE) | Altissimo (sblocca clienti) | **P1** |
| Notifiche email (Fase 5) | Alto | Medio | Medio | Medio (1.5gg) | Alto (retention) | **P2** |
| Cache dashboard Redis (Fase 7) | Medio | Alto | Critico | Basso (2gg) | Alto | **P2** |
| Estrazione asincrona (Fase 7) | Alto | Critico | Critico | Alto (3gg) | Alto | **P2** |
| Scraper portali PA (Fase 6) | Critico | Basso | Medio | Molto alto (4-6gg) | Altissimo (ma fragile) | **P3** |
| OCR (Fase 8) | Medio | Medio | Basso | Alto (3gg) | Medio | **P3** |
| Billing Stripe (Fase 9) | Critico | Basso | Medio | Alto (4gg) | Critico per revenue | **P4** |
| Upgrade Render/Neon (infra) | Alto | Alto | Critico | Minimo (1h) | Altissimo (nessun cold-start) | **Subito** |

---

## 10. Milestone

| Milestone | Criteri di completamento | Fasi coinvolte | Stima data |
|---|---|---|---|
| **M0 — MVP validato** ✅ | Flusso PDF→AI→match funzionante, almeno 5 bandi reali estratti | 0,1,2 | Completato |
| **M1 — Base solida** | 20+ test pytest verdi, health endpoint live, DB refactoring fatto, Sentry attivo | 3 | +3 settimane |
| **M2 — Multi-tenant** | 2+ utenti con dati isolati, login/logout stabile, migration fatta senza perdita dati | 4 | +7 settimane |
| **M3 — Prodotto commercializzabile** | Email notifiche funzionanti, cache dashboard < 200ms, upgrade piano Render | 5,7 (parziale) | +10 settimane |
| **M4 — Automazione** | Scraper attivo su 2+ portali PA, estrazione asincrona, zero intervento manuale per nuovi bandi | 6,7 | +16 settimane |
| **M5 — Revenue** | Billing Stripe, piano Free/Pro, landing page pubblica, 5+ clienti paganti | 9 | +24 settimane |

---

*Fine documento. Aggiornare questo file ad ogni milestone completata o quando cambiano le priorità business.*
