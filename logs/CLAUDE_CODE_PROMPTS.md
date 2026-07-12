# CLAUDE_CODE_PROMPTS — Bandi Scanner

Log dei prompt preparati (in sessione di analisi con Claude via chat) da
incollare in Claude Code su Cursor per applicare gli interventi della
ROADMAP.md. Usato quando le modifiche sono troppo estese per un semplice
diff/patch, o quando `git apply` fallisce per disallineamento di contesto
tra l'ambiente di analisi e il repo locale reale.

Ogni prompt è autosufficiente: contiene la specifica esatta (cosa cambiare,
dove, con quali valori) così Claude Code non deve indedurre nulla dal solo
titolo dell'intervento roadmap.

---

## #15 — Font-size scale + spacing scale + token colori (2026-07-09)

Prompt principale (token, font-size in styles.css, spacing in styles.css,
migrazione colori, font-size inline nei componenti).

```
Sto implementando l'intervento #15 della ROADMAP.md ("Font-size scale (min
0.75rem) + spacing scale + migrazione token colori"). Ho già la specifica
completa delle modifiche (prodotta in un'altra sessione), ma i tentativi di
applicarla con `git apply` sono falliti su tutti i file con "patch does not
apply" — il contesto delle patch non combacia col nostro stato attuale del
repo (probabilmente per differenze di line-ending o per modifiche nel
frattempo). Non voglio più usare patch: applica le modifiche direttamente
sui file reali del progetto, leggendo prima lo stato attuale di ciascun file
con i tuoi strumenti.

## Scope esatto dell'intervento (approvato: Parte A + B, tutto)

### 1. Nuovi design token in `frontend/src/styles.css`, dentro `:root`

Aggiungi, subito dopo i token `--status-low-border` esistenti (prima della
chiusura di `:root`):

--text-xs: 0.75rem;    /* 12px  — badge, etichette, note */
--text-sm: 0.85rem;    /* 13.6px — testo secondario */
--text-base: 0.95rem;  /* 15.2px — corpo standard */
--text-lg: 1.1rem;     /* 17.6px — titoli di modal/sezione */
--text-xl: 1.4rem;     /* 22.4px — numeri in evidenza (contributo) */
--text-2xl: 1.85rem;   /* 29.6px — titolo pagina */
--text-3xl: 2.5rem;    /* 40px   — valore KPI */

--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 24px;
--space-6: 32px;
--space-7: 64px;

### 2. Rimappa TUTTI i font-size in styles.css a questi token

Tabella di conversione (arrotondamento al valore più vicino tra i 7
gradini sopra — NON toccare il font-size: 15px sul selettore body):

0.62/0.65/0.66/0.68/0.6875/0.7/0.72/0.75/0.76/0.78rem -> var(--text-xs)
0.8/0.8125/0.82/0.84/0.85/0.875/0.88rem -> var(--text-sm)
0.95/0.98/1rem -> var(--text-base)
1.05rem -> var(--text-lg)
1.3rem -> var(--text-xl)
1.75rem -> var(--text-2xl)
2.5rem -> var(--text-3xl)

### 3. Rimappa i valori px di margin/padding/gap (styles.css)

2/4/5px -> var(--space-1)
6/7/8/9px -> var(--space-2)
10/11/12px -> var(--space-3)
14/16/18px -> var(--space-4)
20/22/24px -> var(--space-5)
32px -> var(--space-6)
56/64px -> var(--space-7)

NON toccare 1px e 3px (nudge ottici di allineamento, non spaziatura).
Shorthand con valori multipli: converti ogni valore singolarmente
mantenendo l'ordine.

### 4. Migrazione colori hardcoded (4 punti esatti)

a) Clienti.tsx — stripColorByGiorni:
function stripColorByGiorni(giorni: number | null): string {
  if (giorni === null || giorni < 0) return 'var(--color-border-strong)'
  if (giorni < 30) return 'var(--status-low)'
  if (giorni <= 90) return 'var(--status-mid)'
  return 'var(--status-high)'
}

b) styles.css — .deadline-strip: fallback var(--deadline-color, #D1D5DB)
diventa var(--deadline-color, var(--color-border-strong)).

c) styles.css — .score-green/-yellow/-red e > span:
.score-green  { --ring-color: var(--status-high); }
.score-yellow { --ring-color: var(--status-mid); }
.score-red    { --ring-color: var(--status-low); }
.score-green  > span { color: var(--status-high-text); }
.score-yellow > span { color: var(--status-mid-text); }
.score-red    > span { color: var(--status-low-text); }

d) Bandi.tsx — bottone "Sì, elimina" con style inline hex hardcoded.
Aggiungi in styles.css dopo .btn-danger:hover:
.btn-danger-solid { background: var(--color-danger); color: #fff; border: none; }
.btn-danger-solid:hover { background: #b91c1c; }
Poi nel bottone: rimuovi lo style inline, aggiungi
className="btn btn-sm btn-danger-solid".

e) styles.css — .alert-info:
.alert-info { background: var(--color-accent-soft); color: var(--color-accent); border-color: var(--color-accent); }

### 5. Font-size hardcoded inline nei componenti TSX (stessa tabella del
punto 2), cerca fontSize: in tutti i frontend/src/components/*.tsx:

- Bandi.tsx: 0.75rem (colonna id) -> var(--text-xs)
- Bandi.tsx: 0.85rem (data scadenza) -> var(--text-sm)
- Bandi.tsx: 0.8rem ("Sei sicuro?") -> var(--text-sm)
- CaricaBando.tsx: 0.875rem (warning duplicato) -> var(--text-sm)
- CaricaBando.tsx: 0.9rem (nome file) -> var(--text-base)
- CaricaBando.tsx: 1.1rem (% campi compilati) -> var(--text-lg)
- Clienti.tsx: 0.82rem (P.IVA monospace) -> var(--text-sm)
- Clienti.tsx: 0.78rem (ente bando compatibile) -> var(--text-xs)
- Clienti.tsx: 0.7rem (data scadenza bando compatibile) -> var(--text-xs)
- Dashboard.tsx: 0.65rem (contatore duplicati) -> var(--text-xs)
- Dashboard.tsx: 0.875rem (header bandi scaduti) -> var(--text-sm)

### 6. NON toccare

- index.css/App.css: file morti del template Vite, mai importati
  (verificalo con una ricerca import.*index.css / import.*App.css — solo
  main.tsx importa ./styles.css). Fuori scope.
- I valori numerici inline di margin/padding/gap nei componenti TSX: sono
  un'estensione dello stesso problema ma più ampia, la facciamo come
  intervento a parte (vedi sezione successiva di questo log).

### 7. Aggiorna ROADMAP.md

Trova la riga dell'intervento #15 ([ ]), cambia in [x], aggiungi
changelog nei sotto-punti. Nella tabella riepilogativa in fondo, il
titolo di #15 in ~~barrato~~ (stile già usato per #10-#13).

## Verifica finale

cd frontend && npm run build   # deve essere pulito, zero errori TypeScript
cd .. && pytest -q              # 212 test verdi — intervento solo frontend

Fammi un riepilogo di cosa hai effettivamente cambiato file per file prima
di fare il commit.
```

**Esito**: risultava già interamente applicato nel working tree non
committato (i file erano già `M` in `git status` prima ancora di iniziare).
Nessuna modifica necessaria — solo verifica + commit.

---

### #15 (coda) — spaziature inline nei componenti TSX (2026-07-09)

Prompt per i ~47 valori numerici di margin/padding/gap hardcoded inline
(fuori scope del prompt principale sopra).

```
Coda dell'intervento #15 della ROADMAP.md: durante #15 avevo tokenizzato
tutti i valori px di margin/padding/gap in frontend/src/styles.css con la
scala --space-1..7 già definita in :root, ma avevo lasciato fuori dallo
scope i valori numerici di margin/padding/gap inline negli style={{}} dei
componenti TSX (stesso problema, posto diverso). Chiudiamo anche questo.

## Contesto tecnico importante

In React, un valore numerico in uno style={{ marginTop: 8 }} viene
interpretato automaticamente come px. Quando lo converti in un token CSS
devi cambiarlo in stringa: marginTop: 8 diventa marginTop: 'var(--space-2)'
(non marginTop: var(--space-2) senza apici, che è un errore di sintassi).

## Scala di riferimento (già presente in styles.css, non ricrearla)

--space-1: 4px;  --space-2: 8px;  --space-3: 12px;  --space-4: 16px;
--space-5: 24px; --space-6: 32px; --space-7: 64px;

## Tabella di conversione

2, 4, 5 -> 'var(--space-1)'
6, 7, 8, 9 -> 'var(--space-2)'
10, 11, 12 -> 'var(--space-3)'
14, 16, 18 -> 'var(--space-4)'
20, 22, 24 -> 'var(--space-5)'
32 -> 'var(--space-6)'
56, 64 -> 'var(--space-7)'

Da NON toccare: 1 e 3 (nudge ottici, es. marginLeft: 3), e 0 (margin: 0,
zero non ha bisogno di token).

## Dove intervenire

Cerca in tutti i file frontend/src/components/*.tsx le proprietà margin,
marginTop, marginBottom, marginLeft, marginRight, padding, paddingTop,
paddingBottom, paddingLeft, paddingRight, gap con valore numerico dentro
uno style={{...}}. Censite 47 occorrenze (righe indicative, verifica con
ricerca):

- Bandi.tsx: ~60, 63 (marginLeft: 3 — NON toccare), ~115 (gap: 6), ~377
  (marginBottom: 16), ~429 (marginTop: 8)
- CaricaBando.tsx: ~299, 303, 318, 375, 383, 399, 405, 410, 415, 417, 423,
  431, 432, 456, 458 (margin: 0 NON toccare, paddingLeft: 20), 460
  (marginBottom: 3 — NON toccare), 468, 477
- ClienteFormModal.tsx: ~126 (marginBottom: 16), ~127 (margin: 0 NON
  toccare, paddingLeft: 18)
- Clienti.tsx: ~385, 482, 503, 507, 514, 517 (marginTop: 4 e
  paddingLeft: 18), 525, 531, 568, 571
- Dashboard.tsx: ~231, 385, 453
- ModalScheda.tsx: ~45 (gap: 6)

Totale atteso: ~42 conversioni (47 trovate meno 5 escluse: 2 nudge da 3px,
3 zero).

## Verifica finale

cd frontend && npm run build   # zero errori TypeScript
cd .. && pytest -q              # 212 test verdi

## Aggiornamento ROADMAP.md

Nel sotto-punto changelog di #15 (quello con "- Scala --space-1..7..."),
aggiungi: "Estesa la conversione anche ai ~42 valori numerici di
margin/padding/gap hardcoded inline nei componenti TSX (Bandi.tsx,
CaricaBando.tsx, ClienteFormModal.tsx, Clienti.tsx, Dashboard.tsx,
ModalScheda.tsx)."

Fammi un riepilogo file per file di cosa hai cambiato, con il conteggio
esatto delle sostituzioni fatte, prima di procedere col commit.
```

**Esito**: 42 sostituzioni (Bandi.tsx 3, CaricaBando.tsx 22, Dashboard.tsx
3, Clienti.tsx 11, ModalScheda.tsx 1, ClienteFormModal.tsx 2) — combacia
esattamente con l'atteso (47 trovate − 5 escluse: 2 nudge da 3px, 1
marginBottom:3, 2 margin:0). Build pulito, 212 test verdi. Committato
insieme al resto di #15.

---

<!-- Prossimo prompt (#14 — React Query) verrà aggiunto qui sotto quando pronto. -->

---

## #14 — React Query per fetch, cache e invalidation cross-pagina (2026-07-09)

Scope concordato: solo le 3 fetch di lista (dashboard/bandi/clienti),
invalidation globale (non granulare) su ogni mutazione — vedi motivazione
nel prompt.

```
Sto implementando l'intervento #14 della ROADMAP.md ("React Query per
fetch, cache e invalidation cross-pagina"). Ho già validato in un altro
ambiente che questo scope builda pulito (npm run build) e non tocca il
backend (212 test Python invariati). Applica queste modifiche direttamente
sui file reali, leggendo prima lo stato attuale di ciascuno — non fidarti
ciecamente dei numeri di riga, i file potrebbero essere leggermente
diversi da quanto descritto qui (es. per via di #15 già applicato).

## Scope (deciso esplicitamente, non ampliarlo)

- Migra SOLO le 3 fetch di lista: /api/dashboard (Dashboard.tsx),
  /api/bandi (Bandi.tsx), /api/clienti (Clienti.tsx).
- NON migrare le fetch puntuali (scheda bando on-demand in Dashboard/
  Bandi/Clienti, dettaglio bandi-compatibili-per-cliente in Clienti.tsx):
  restano fetch dirette come oggi, il beneficio della cache lì è marginale.
- Invalidation SEMPRE globale (queryClient.invalidateQueries() senza
  queryKey specifica) su ogni mutazione, non granulare: senza una suite di
  test frontend (non esiste, verificalo con package.json: solo tsc, niente
  vitest/jest) è la strategia più sicura contro dati stantii.

## 1. Aggiungi la dipendenza

In frontend/package.json, sotto "dependencies", aggiungi:
"@tanstack/react-query": "^5.101.2"
(compatibile con React 19, verificato). Poi npm install.

## 2. Crea il file frontend/src/lib/queries.ts (nuovo file, contenuto esatto)

// Hook React Query per le fetch di lista condivise cross-pagina (#14).
// Scope minimo: solo le 3 liste (dashboard/bandi/clienti). Le fetch puntuali
// (scheda bando on-demand, dettaglio bandi-compatibili-per-cliente) restano
// fetch dirette come prima — beneficio marginale dalla cache, non incluse
// per limitare la superficie di modifica.
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { withApiKey } from '../apiKey'

async function fetchJson<T = any>(url: string): Promise<T> {
  const res = await fetch(url, withApiKey())
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

const STALE_TIME = 60_000 // 1 minuto: i dati restano "freschi" per la navigazione istantanea

export const useDashboard = <T = any>() =>
  useQuery<T>({ queryKey: ['dashboard'], queryFn: () => fetchJson<T>('/api/dashboard'), staleTime: STALE_TIME })

export const useBandi = <T = any>() =>
  useQuery<T>({ queryKey: ['bandi'], queryFn: () => fetchJson<T>('/api/bandi'), staleTime: STALE_TIME })

export const useClienti = <T = any>() =>
  useQuery<T>({ queryKey: ['clienti'], queryFn: () => fetchJson<T>('/api/clienti'), staleTime: STALE_TIME })

/** Invalida tutte le query cross-pagina dopo una mutazione (delete bando,
 * salva/elimina cliente, recalc, deduplica, upload bando). Scelta
 * deliberatamente globale (non granulare per singola queryKey): senza una
 * suite di test frontend, è la strategia più sicura contro dati stantii —
 * nel dubbio rifetcha tutto, mai un'invalidazione dimenticata. Da
 * raffinare in futuro solo se il volume di richieste diventa un problema
 * di performance reale. */
export function useInvalidateAll() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries()
}

/** Helper generico per le mutazioni POST/PUT/DELETE che devono invalidare
 * tutte le liste cross-pagina al successo. */
export function useApiMutation<TVariables = void>(
  mutationFn: (vars: TVariables) => Promise<any>
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries(),
  })
}

## 3. App.tsx — avvolgi tutto con QueryClientProvider

Aggiungi l'import:
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

Prima di "export default function App()", aggiungi:
const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, retry: 1 } },
})

Poi avvolgi il JSX ritornato da App() con <QueryClientProvider client={queryClient}>
subito dentro il return, prima di <BrowserRouter>, chiudendolo dopo
</BrowserRouter> (attenzione all'indentazione/chiusura tag corretta).

## 4. Dashboard.tsx

- Import: aggiungi `import { useDashboard, useApiMutation } from '../lib/queries'`,
  rimuovi `useCallback` dall'import di react se non serve più altrove nel file.
- Sostituisci lo state manuale (`useState<DashboardData|null>`, `loading`,
  `error`, il `fetchDashboard` con `useCallback` + `useEffect` che lo chiama)
  con:
  `const { data, isLoading: loading, error: queryError } = useDashboard<DashboardData>()`
  `const error = queryError ? 'Impossibile caricare la dashboard. Verifica che il server sia in esecuzione.' : null`
  (l'interfaccia DashboardData esiste già nel file, riusala come generic).
- `handleRecalc`: sostituisci la fetch diretta + `await fetchDashboard()` con
  `useApiMutation(() => fetch('/api/bandi/recalc', withApiKey({ method: 'POST' })))`
  e chiama `.mutateAsync()` dentro handleRecalc; `recalcLoading` diventa
  `recalcMutation.isPending`.
- `handleDeduplica`: stesso pattern, la mutationFn fa la fetch e ritorna
  `res.json()`; `deduplicaLoading` diventa `deduplicaMutation.isPending`.
- Il resto del componente (JSX, showExpiredSection, openScheda, ecc.) resta
  invariato.

## 5. Bandi.tsx

- Import: aggiungi `import { useBandi, useApiMutation } from '../lib/queries'`.
- Sostituisci `useState<Bando[]>([])` + `loading`/`error` state + il
  `useEffect` che fa fetch('/api/bandi') con:
  `const { data, isLoading: loading, error: queryError } = useBandi<{ bandi: Bando[] }>()`
  `const bandi = data?.bandi ?? []`
  `const error = queryError ? 'Errore nel caricamento dei bandi.' : null`
- ATTENZIONE: NON rimuovere lo state locale `deleting` (number|null) — è UI
  locale (quale riga è in eliminazione), non c'entra col fetching.
- `handleDeleteConfirm`: sostituisci la fetch DELETE + l'update ottimistico
  locale (`setBandi(prev => prev.filter(...))`) con una vera mutation:
  const deleteMutation = useApiMutation((id: number) =>
    fetch(`/api/bandi/${id}`, withApiKey({ method: 'DELETE' })).then(res => {
      if (!res.ok) throw new Error()
    }))
  poi dentro handleDeleteConfirm chiama `await deleteMutation.mutateAsync(id)`
  invece della fetch diretta e del setBandi. Aggiungi `deleteMutation` alle
  dependency del useCallback che contiene handleDeleteConfirm.
- Il debounce/useMemo di ricerca (già fixato in #9) e il resto del
  componente restano invariati.

## 6. Clienti.tsx

- Import: aggiungi `import { useClienti, useApiMutation } from '../lib/queries'`;
  rimuovi `useEffect` dall'import di react se non serve più altrove nel file
  (verifica con una ricerca `useEffect(` — se questa era l'unica occorrenza,
  rimuovilo).
- Sostituisci `useState<Cliente[]>([])`, `useState<string[]>([])` (regioni),
  `useState<string[]>([])` (dimensioni), `loading`/`error` state, la funzione
  `fetchClienti` e il `useEffect(() => { fetchClienti() }, [])` con:
  const { data, isLoading: loading, error: queryError } = useClienti<{
    clienti: Cliente[]; regioni: string[]; dimensioni: string[]
  }>()
  const clienti = data?.clienti ?? []
  const regioni = data?.regioni ?? []
  const dimensioni = data?.dimensioni ?? []
  const error = queryError ? 'Impossibile caricare i clienti.' : null
- Aggiungi due mutation (vicino alle altre dichiarazioni di stato, prima
  di `openAdd`):
  const saveMutation = useApiMutation(async (payload: { url: string; method: string; body: unknown }) => {
    const res = await fetch(payload.url, withApiKey({
      method: payload.method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload.body),
    }))
    const d = await res.json()
    if (!res.ok) throw { errors: d.errors ?? ['Errore sconosciuto.'] }
    return d
  })
  const deleteMutation = useApiMutation((id: number) =>
    fetch(`/api/clienti/${id}`, withApiKey({ method: 'DELETE' })))
- `handleSubmit`: sostituisci il blocco fetch+res.json()+if(!res.ok) con:
  try {
    const url = editId ? `/api/clienti/${editId}` : '/api/clienti'
    const method = editId ? 'PUT' : 'POST'
    const wasEdit = editId !== null
    await saveMutation.mutateAsync({ url, method, body: payload })
    closeModal()
    toast.success(wasEdit ? 'Cliente aggiornato.' : 'Cliente aggiunto.')
  } catch (err) {
    const errors = (err as { errors?: string[] })?.errors
    setFormErrors(errors ?? ['Errore di rete. Riprova.'])
  } finally {
    setSaving(false)
  }
  (il resto di handleSubmit, cioè la validazione client-side prima e
  `setSaving(true)` più la costruzione di `payload`, resta invariato)
- `handleDelete`: sostituisci la fetch DELETE diretta con
  `await deleteMutation.mutateAsync(id)` seguito da `setDeleteConfirm(null)`
  e il toast di successo, dentro lo stesso try/catch/finally esistente.
- Tutto il resto (modal form, dettaglio cliente con bandi compatibili,
  scheda on-demand) resta invariato — quelle fetch puntuali NON vanno
  toccate.

## 7. CaricaBando.tsx

- Import: aggiungi `import { useInvalidateAll } from '../lib/queries'`.
- Dentro il componente, vicino alle altre dichiarazioni di stato, aggiungi:
  `const invalidateAll = useInvalidateAll()`
- Nel punto dove, dopo l'upload riuscito, viene mostrato il toast di
  successo (`else if (data.bando_id && !data.errors?.length) { toast.success('Bando salvato con successo.') }`),
  aggiungi subito dopo `toast.success(...)` la chiamata `invalidateAll()`
  — SOLO in questo ramo (bando_id presente e nessun errore), non negli
  altri rami (duplicato, pdf vuoto, errori di validazione).

## Verifica finale

cd frontend && npm install && npm run build   # zero errori TypeScript
cd .. && pytest -q                             # 212 test verdi — intervento
                                                # solo frontend, non deve
                                                # impattare il backend Python

Controlla anche con una ricerca che non restino fetch dirette a
'/api/dashboard', '/api/bandi' o '/api/clienti' fuori dagli hook nuovi
(grep "fetch('/api/dashboard'" ecc. nei 4 componenti — non deve trovare
nulla).

## Aggiornamento ROADMAP.md

Trova la riga dell'intervento #14 ([ ]), cambia in [x], aggiungi un breve
changelog: nuovo file lib/queries.ts con useDashboard/useBandi/useClienti/
useApiMutation/useInvalidateAll, migrazione delle 3 fetch di lista,
invalidation globale su tutte e 6 le mutazioni (recalc, deduplica, delete
bando, save cliente, delete cliente, upload bando), scope esplicitamente
limitato (fetch puntuali di scheda/dettaglio-cliente non toccate).
Nella tabella riepilogativa in fondo, titolo di #14 in ~~barrato~~.

## Nota per la revisione (non richiede azione, solo consapevolezza)

Durante l'analisi ho notato (audit-bandi-scanner2.md riga 487) che
modificare un cliente via PUT /api/clienti/{id} NON innesca un ricalcolo
automatico dei match lato server (solo la creazione via POST lo fa). Con
React Query la Dashboard rifletterà correttamente qualsiasi match_results
esista nel DB, ma se quei match_results sono a loro volta non aggiornati
lato server dopo un edit cliente, il problema persiste finché non si preme
"Ricalcola match" — non è un bug che #14 possa risolvere, è un gap
separato nel backend. Non toccarlo in questo intervento.

Fammi un riepilogo file per file di cosa hai effettivamente cambiato prima
di fare il commit.
```

**Esito**: applicato esattamente come da specifica (verificato file per
file). 238 test verdi (212 + 20 + 6), npm run build pulito. Nessuna
modifica alla logica di sicurezza di fetch_url_safely rispetto alla
specifica fornita. Committato come 1fae20c, pushato su origin/main.

---

## #17 — Nuovi campi estrazione: modalità, tipo agevolazione, % per fascia, cumulabilità (2026-07-09)

Scope: 4 nuovi campi nello schema di estrazione. Il più delicato è
`percentuale_fondo_perduto`, che passa da numero singolo a oggetto per
fascia dimensionale **con retrocompatibilità** per i bandi già salvati
prima di questo intervento. Nessuna modifica frontend necessaria (verificato
che nessun componente TSX referenzia questi campi direttamente — solo la
scheda Markdown pre-generata viene mostrata). Validato in sandbox: 274 test
verdi (238 + 36 nuovi), nessun impatto sul build frontend.

```
Sto implementando l'intervento #17 della ROADMAP.md ("Nuovi campi
estrazione: modalità, tipo agevolazione, % per fascia"). Ho già validato in
un altro ambiente che questo scope passa 274 test (238 preesistenti + 36
nuovi). Applica queste modifiche direttamente sui file reali, leggendo
prima lo stato attuale di ciascuno — non fidarti ciecamente dei numeri di
riga. Non è previsto nessun cambiamento al frontend (verificato: nessun
componente TSX legge questi campi direttamente).

## Contesto importante: retrocompatibilità

`percentuale_fondo_perduto` passa da numero singolo a oggetto
`{"micro", "piccola", "media", "default"}`. I bandi già salvati nel
database PRIMA di questo intervento hanno ancora il vecchio formato
(numero semplice) dentro `json_completo`, e l'endpoint
`POST /api/bandi/{id}/rigenera-scheda` legge quel JSON grezzo chiamando
`genera_scheda()` DIRETTAMENTE, senza ripassare da `normalize_response`
(l'ho verificato in main.py). Quindi `genera_scheda` deve gestire
ENTRAMBI i formati (vecchio numero e nuovo oggetto) — non solo il nuovo.
La funzione `normalize_percentuale_fondo_perduto()` fa esattamente questo
ed è condivisa tra estrazione (schema.py) e rendering scheda (matcher.py).

## 1. modules/schema.py

### 1a. Nuove costanti, subito dopo DEFAULT_DIMENSIONE_IMPRESA (prima di
"# Campi dentro bando" / BANDO_SCHEMA):

# Fasce dimensionali per percentuale_fondo_perduto (#17): non includono "grande"
# di proposito (le grandi imprese raramente accedono a fondo perduto graduato
# per fascia) e aggiungono "default" per il caso di percentuale unica non
# differenziata, o per retrocompatibilità con bandi salvati prima di #17
# (quando il campo era un numero singolo).
PERCENTUALE_FASCE_KEYS: tuple[str, ...] = ("micro", "piccola", "media", "default")

MODALITA_PRESENTAZIONE_VALUES: frozenset[str] = frozenset({
    "sportello", "click_day", "graduatoria", "mista",
})

TIPO_AGEVOLAZIONE_VALUES: frozenset[str] = frozenset({
    "fondo_perduto", "finanziamento_agevolato", "garanzia", "credito_imposta", "voucher",
})

### 1b. In BANDO_SCHEMA, tre modifiche:
- cambia `"percentuale_fondo_perduto": (int, float, type(None)),` in
  `"percentuale_fondo_perduto": dict,`
- aggiungi, subito dopo la riga di percentuale_fondo_perduto, queste tre
  righe (prima di "spese_ammissibili"):
  "modalita_presentazione": (str, type(None)),
  "tipo_agevolazione": list,
  "cumulabilita": (str, type(None)),

### 1c. In NUMERIC_FIELDS, rimuovi la riga "percentuale_fondo_perduto,"
(non è più uno scalare a livello di BANDO_SCHEMA — i suoi sotto-valori
vengono coercizzati separatamente dalla nuova funzione).

### 1d. Subito dopo la funzione _to_number esistente (prima di
normalize_response), aggiungi queste tre funzioni:

def _to_enum(val: object, allowed: frozenset[str]) -> str | None:
    """Normalizza a una delle stringhe enum consentite (case-insensitive).
    Un valore non riconosciuto (allucinazione LLM, refuso) diventa None
    invece di salvare rumore non filtrabile a valle."""
    if not isinstance(val, str):
        return None
    v = val.strip().lower()
    return v if v in allowed else None


def _to_enum_list(val: object, allowed: frozenset[str]) -> list[str]:
    """Normalizza a lista di sole stringhe enum consentite (case-insensitive,
    dedup mantenendo l'ordine di prima occorrenza)."""
    if not isinstance(val, list):
        return []
    seen: list[str] = []
    for item in val:
        if not isinstance(item, str):
            continue
        v = item.strip().lower()
        if v in allowed and v not in seen:
            seen.append(v)
    return seen


def normalize_percentuale_fondo_perduto(value: object) -> dict[str, float | int | None]:
    """Restituisce sempre {"micro", "piccola", "media", "default"}.

    Gestisce sia il nuovo formato (oggetto per fascia dimensionale, #17)
    sia il formato legacy (numero singolo, bandi salvati/estratti prima di
    #17): il numero legacy viene letto come "default", così `genera_scheda`
    può leggere qualunque bando — vecchio o nuovo — con la stessa funzione.
    """
    if isinstance(value, dict):
        return {key: _to_number(value.get(key)) for key in PERCENTUALE_FASCE_KEYS}
    numero = _to_number(value)
    return {"micro": None, "piccola": None, "media": None, "default": numero}

### 1e. In normalize_response, dentro il ciclo "for key in BANDO_SCHEMA",
subito dopo il branch `elif key == "ateco_aperto_a_tutti": bando[key] = _to_bool(val)`,
aggiungi questi 4 nuovi branch (prima del branch "anzianita_impresa"):

        elif key == "percentuale_fondo_perduto":
            bando[key] = normalize_percentuale_fondo_perduto(val)
        elif key == "modalita_presentazione":
            bando[key] = _to_enum(val, MODALITA_PRESENTAZIONE_VALUES)
        elif key == "tipo_agevolazione":
            bando[key] = _to_enum_list(val, TIPO_AGEVOLAZIONE_VALUES)
        elif key == "cumulabilita":
            bando[key] = val.strip() if isinstance(val, str) and val.strip() else None

## 2. modules/matcher.py

### 2a. Import: cambia
  from modules.schema import DIMENSIONE_IMPRESA_KEYS
in
  from modules.schema import DIMENSIONE_IMPRESA_KEYS, normalize_percentuale_fondo_perduto

### 2b. Subito prima di "def genera_scheda(bando: dict[str, Any]) -> str:",
aggiungi:

MODALITA_PRESENTAZIONE_LABELS: dict[str, str] = {
    "sportello": "Sportello (a esaurimento fondi)",
    "click_day": "Click day",
    "graduatoria": "Graduatoria a valutazione",
    "mista": "Mista (sportello + graduatoria)",
}

TIPO_AGEVOLAZIONE_LABELS: dict[str, str] = {
    "fondo_perduto": "Fondo perduto",
    "finanziamento_agevolato": "Finanziamento agevolato",
    "garanzia": "Garanzia",
    "credito_imposta": "Credito d'imposta",
    "voucher": "Voucher",
}

def _format_pct(value: Any) -> str | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f"{f:.0f}%" if f == int(f) else f"{f}%"

### 2c. Dentro genera_scheda, trova questo blocco (dopo "if forme:
requisiti.append(...)" e prima di "if requisiti: lines.append(...)"):
aggiungi, subito dopo la riga `if forme: requisiti.append(...)` e PRIMA
della riga `if requisiti: lines.append("## Requisiti di accesso...`:

    modalita = MODALITA_PRESENTAZIONE_LABELS.get(b.get("modalita_presentazione") or "")
    if modalita:
        requisiti.append(f"**Modalità di presentazione:** {modalita}")
    cumulabilita = _norm_str(b.get("cumulabilita"))
    if cumulabilita:
        requisiti.append(f"**Cumulabilità:** \u201c{cumulabilita}\u201d")

### 2d. Subito dopo, trova il blocco che costruisce "contributo" e "pct" e
la sezione "## Contributi" — sostituiscilo interamente con:

    contributo = _format_euro(b.get("contributo_max"))
    pct_fasce = normalize_percentuale_fondo_perduto(b.get("percentuale_fondo_perduto"))
    econ_parts = []
    if contributo: econ_parts.append(f"**Contributo massimo:** {contributo}")
    fasce_valorizzate = [
        (label, pct_fasce.get(chiave)) for chiave, label in (
            ("micro", "Micro"), ("piccola", "Piccola"), ("media", "Media"),
        ) if pct_fasce.get(chiave) is not None
    ]
    if fasce_valorizzate:
        dettaglio = "; ".join(f"{label} {_format_pct(val)}" for label, val in fasce_valorizzate)
        econ_parts.append(f"**Fondo perduto per fascia:** {dettaglio}")
    elif pct_fasce.get("default") is not None:
        econ_parts.append(f"**Fondo perduto:** {_format_pct(pct_fasce['default'])}")
    tipo_ag = [TIPO_AGEVOLAZIONE_LABELS[t] for t in _norm_list(b.get("tipo_agevolazione")) if t in TIPO_AGEVOLAZIONE_LABELS]
    if tipo_ag:
        econ_parts.append(f"**Tipo di agevolazione:** {', '.join(tipo_ag)}")
    if econ_parts: lines.append("## Contributi\n\n" + "\n\n".join(econ_parts))

(il blocco PRECEDENTE che stai sostituendo calcolava `pct = b.get("percentuale_fondo_perduto")`
e faceva un try/except con float(pct) — quello va rimosso, sostituito
integralmente da questo nuovo blocco.)

## 3. prompts/system_extraction.md

### 3a. Nell'esempio JSON schema in cima al file, sostituisci la riga
  "percentuale_fondo_perduto": 50,
con:
    "percentuale_fondo_perduto": {
      "micro": 60,
      "piccola": 50,
      "media": 40,
      "default": null
    },
    "modalita_presentazione": "sportello",
    "tipo_agevolazione": ["fondo_perduto"],
    "cumulabilita": null,

### 3b. Sostituisci il blocco regola "percentuale_fondo_perduto" esistente
(quello con "REGOLE MATEMATICHE... agevolazione mista...") con:

* "percentuale_fondo_perduto": (oggetto JSON con chiavi "micro", "piccola", "media", "default" — tutte numero o null).
  - Molti bandi prevedono percentuali diverse per fascia dimensionale (es. micro 60%, piccola 50%, media 40%): in questo caso valorizza SOLO le chiavi "micro"/"piccola"/"media" corrispondenti, lasciando "default" a `null`.
  - Se il bando prevede un'unica percentuale valida per tutte le imprese (nessuna differenziazione per fascia), valorizza SOLO la chiave "default" con quel numero, lasciando "micro"/"piccola"/"media" a `null`.
  - Se non c'è alcuna percentuale indicata né deducibile con certezza, lascia tutte e quattro le chiavi a `null`.
  - REGOLE MATEMATICHE: se il bando prevede un'agevolazione "mista" (es. 80% diviso a metà tra fondo perduto e tasso zero), calcola la percentuale effettiva del solo fondo perduto rispetto al totale del progetto (es. in questo caso 40) e mettila nella chiave pertinente ("default", o nella fascia giusta se differenziata). Aggiungi anche una nota in `note_esclusioni.lista_testuale` sulla quota di finanziamento agevolato (es. "Il restante 40% è erogato come finanziamento agevolato a tasso zero").
  - Non confondere questo campo con `tipo_agevolazione`: qui va SOLO il numero percentuale, non il tipo di strumento finanziario.

* "modalita_presentazione": (stringa enum o null). Uno tra: "sportello", "click_day", "graduatoria", "mista".
  - "sportello": il bando usa espressioni come "a sportello", "fino ad esaurimento fondi", "in base all'ordine cronologico di presentazione delle domande".
  - "click_day": le domande si presentano tutte in una finestra temporale molto breve e ristretta (es. "dalle ore 10:00 del giorno X"), spesso con invio simultaneo.
  - "graduatoria": le domande vengono valutate e ordinate per punteggio/merito prima dell'assegnazione dei fondi (parole chiave: "graduatoria", "punteggio", "valutazione di merito").
  - "mista": il bando combina più modalità (es. prima fase a sportello, poi graduatoria per i fondi residui).
  - Usa `null` se il testo non specifica la modalità di presentazione delle domande.

* "tipo_agevolazione": (lista di stringhe enum). Valori ammessi: "fondo_perduto", "finanziamento_agevolato", "garanzia", "credito_imposta", "voucher".
  - Un bando può prevedere più tipi contemporaneamente (es. parte a fondo perduto + parte come finanziamento agevolato): includi tutti quelli effettivamente presenti nel testo.
  - Non inventare un tipo se il testo non lo specifica esplicitamente o implicitamente in modo chiaro. Se il tipo non è determinabile, lascia la lista vuota `[]`.

* "cumulabilita": (stringa o null).
  - Estrai LETTERALMENTE (senza riassumere o interpretare) la clausola del testo che parla di cumulabilità con altre agevolazioni, regole "de minimis", o divieto di cumulo. Copia la frase così com'è nel testo.
  - Se il bando non menziona esplicitamente la cumulabilità, usa `null`. Non dedurre né riassumere: questo campo deve riportare solo testo realmente presente nel documento.

(queste tre nuove regole vanno subito dopo la regola "percentuale_fondo_perduto" riscritta e PRIMA della regola "dimensione_impresa" esistente)

### 3c. Nella sezione "## Gestione Ambiguità", sostituisci il paragrafo
"### Percentuale fondo perduto implicita" esistente con:

### Percentuale fondo perduto implicita
Se la percentuale di fondo perduto non è espressa come numero ma si ricava dal contesto (es. "il contributo a fondo perduto è pari al 50% delle spese ammissibili", "agevolazione non rimborsabile del 40%"), estraila comunque come numero nella chiave pertinente di `percentuale_fondo_perduto` (di solito "default", se il bando non differenzia per fascia dimensionale). Non lasciare tutte le chiavi a `null` se il dato è deducibile con certezza dal testo.

### 3d. Nella sezione "## Esempi di casi edge", subito dopo l'Esempio 2
(quello sulla data di scadenza relativa) e PRIMA di "## Strategia di
analisi", aggiungi:

---

### Esempio 3 — Percentuale di fondo perduto differenziata per fascia dimensionale
Testo: *"Il contributo a fondo perduto è pari al 60% delle spese ammissibili per le micro imprese, al 50% per le piccole imprese e al 40% per le medie imprese."*

Estrazione corretta:
```json
{
  "percentuale_fondo_perduto": {
    "micro": 60,
    "piccola": 50,
    "media": 40,
    "default": null
  }
}
```
Nota: quando il bando differenzia esplicitamente la percentuale per fascia dimensionale, valorizza le chiavi corrispondenti e lascia `default` a `null` — non fare una media né sceglierne una sola.

### 3e. Nella sezione "## Strategia di analisi", punto 4 (quello che
inizia con "Poi cerca massimali, percentuali di contributo..."), sostituisci
con:

4. Poi cerca massimali, percentuali di contributo (anche differenziate per fascia dimensionale), tipo di agevolazione (fondo perduto/finanziamento agevolato/garanzia/credito d'imposta/voucher) e soglie di investimento minimo

## 4. tests/test_schema.py

Cambia l'import in cima al file da:
  from modules.schema import _to_bool, _to_number, normalize_response
a:
  from modules.schema import (
      _to_bool,
      _to_enum,
      _to_enum_list,
      _to_number,
      MODALITA_PRESENTAZIONE_VALUES,
      TIPO_AGEVOLAZIONE_VALUES,
      normalize_percentuale_fondo_perduto,
      normalize_response,
  )

Trova il test esistente "test_percentuale_fondo_perduto_percent_string"
(dentro la classe che testa normalize_response, verifica "50%" -> 50) e
sostituiscilo con:

    def test_percentuale_fondo_perduto_percent_string(self):
        """Formato legacy (numero/stringa singola, come prima di #17): viene
        letto come chiave "default" del nuovo oggetto per fascia."""
        data = {"bando": {"percentuale_fondo_perduto": "50%"}}
        result = normalize_response(data)
        assert result["bando"]["percentuale_fondo_perduto"] == {
            "micro": None, "piccola": None, "media": None, "default": 50,
        }

Poi aggiungi in coda al file (dopo l'ultimo test esistente,
test_anzianita_mesi_string) tutto questo blocco:

# ---------------------------------------------------------------------------
# #17 — nuovi campi: percentuale per fascia, modalità, tipo agevolazione, cumulabilità
# ---------------------------------------------------------------------------

class TestNormalizePercentualeFondoPerduto:
    def test_formato_oggetto_per_fascia(self):
        value = {"micro": 60, "piccola": "50%", "media": None, "default": None}
        result = normalize_percentuale_fondo_perduto(value)
        assert result == {"micro": 60, "piccola": 50, "media": None, "default": None}

    def test_formato_legacy_numero_singolo(self):
        """Retrocompatibilità: bandi salvati prima di #17 avevano un numero
        semplice — deve finire nella chiave "default"."""
        assert normalize_percentuale_fondo_perduto(50) == {
            "micro": None, "piccola": None, "media": None, "default": 50,
        }

    def test_formato_legacy_stringa_percentuale(self):
        assert normalize_percentuale_fondo_perduto("40%") == {
            "micro": None, "piccola": None, "media": None, "default": 40,
        }

    def test_none(self):
        assert normalize_percentuale_fondo_perduto(None) == {
            "micro": None, "piccola": None, "media": None, "default": None,
        }

    def test_oggetto_con_chiavi_mancanti(self):
        """Un oggetto parziale (solo alcune fasce) non deve sollevare KeyError."""
        result = normalize_percentuale_fondo_perduto({"micro": 60})
        assert result == {"micro": 60, "piccola": None, "media": None, "default": None}

    def test_ignora_chiave_grande(self):
        """La fascia 'grande' non fa parte di questo campo (solo PMI)."""
        result = normalize_percentuale_fondo_perduto({"micro": 60, "grande": 10})
        assert "grande" not in result


class TestNormalizeResponseNuoviCampi:
    def test_percentuale_fondo_perduto_per_fascia_via_normalize_response(self):
        data = {"bando": {"percentuale_fondo_perduto": {"micro": 60, "piccola": 50, "media": 40}}}
        result = normalize_response(data)
        assert result["bando"]["percentuale_fondo_perduto"] == {
            "micro": 60, "piccola": 50, "media": 40, "default": None,
        }

    def test_modalita_presentazione_valore_valido(self):
        data = {"bando": {"modalita_presentazione": "sportello"}}
        result = normalize_response(data)
        assert result["bando"]["modalita_presentazione"] == "sportello"

    def test_modalita_presentazione_case_insensitive(self):
        data = {"bando": {"modalita_presentazione": "Click_Day"}}
        result = normalize_response(data)
        assert result["bando"]["modalita_presentazione"] == "click_day"

    def test_modalita_presentazione_valore_non_riconosciuto_diventa_none(self):
        """Un'allucinazione LLM (valore fuori enum) non deve essere salvata
        come rumore non filtrabile a valle."""
        data = {"bando": {"modalita_presentazione": "boh"}}
        result = normalize_response(data)
        assert result["bando"]["modalita_presentazione"] is None

    def test_modalita_presentazione_none(self):
        data = {"bando": {"modalita_presentazione": None}}
        result = normalize_response(data)
        assert result["bando"]["modalita_presentazione"] is None

    def test_tipo_agevolazione_lista_valida(self):
        data = {"bando": {"tipo_agevolazione": ["fondo_perduto", "finanziamento_agevolato"]}}
        result = normalize_response(data)
        assert result["bando"]["tipo_agevolazione"] == ["fondo_perduto", "finanziamento_agevolato"]

    def test_tipo_agevolazione_scarta_valori_non_enum(self):
        data = {"bando": {"tipo_agevolazione": ["fondo_perduto", "boh", "voucher"]}}
        result = normalize_response(data)
        assert result["bando"]["tipo_agevolazione"] == ["fondo_perduto", "voucher"]

    def test_tipo_agevolazione_dedup(self):
        data = {"bando": {"tipo_agevolazione": ["voucher", "Voucher", "VOUCHER"]}}
        result = normalize_response(data)
        assert result["bando"]["tipo_agevolazione"] == ["voucher"]

    def test_tipo_agevolazione_non_lista_diventa_vuota(self):
        data = {"bando": {"tipo_agevolazione": "fondo_perduto"}}
        result = normalize_response(data)
        assert result["bando"]["tipo_agevolazione"] == []

    def test_cumulabilita_stringa_valida(self):
        data = {"bando": {"cumulabilita": "Non cumulabile con altre agevolazioni de minimis."}}
        result = normalize_response(data)
        assert result["bando"]["cumulabilita"] == "Non cumulabile con altre agevolazioni de minimis."

    def test_cumulabilita_stringa_vuota_diventa_none(self):
        data = {"bando": {"cumulabilita": "   "}}
        result = normalize_response(data)
        assert result["bando"]["cumulabilita"] is None

    def test_cumulabilita_none(self):
        data = {"bando": {"cumulabilita": None}}
        result = normalize_response(data)
        assert result["bando"]["cumulabilita"] is None


class TestToEnum:
    def test_valore_valido(self):
        assert _to_enum("sportello", MODALITA_PRESENTAZIONE_VALUES) == "sportello"

    def test_case_insensitive_e_spazi(self):
        assert _to_enum("  Graduatoria  ", MODALITA_PRESENTAZIONE_VALUES) == "graduatoria"

    def test_valore_non_riconosciuto(self):
        assert _to_enum("qualcosa_altro", MODALITA_PRESENTAZIONE_VALUES) is None

    def test_non_stringa(self):
        assert _to_enum(123, MODALITA_PRESENTAZIONE_VALUES) is None

    def test_none(self):
        assert _to_enum(None, MODALITA_PRESENTAZIONE_VALUES) is None


class TestToEnumList:
    def test_lista_mista_filtra_non_validi(self):
        result = _to_enum_list(["fondo_perduto", "boh", "garanzia"], TIPO_AGEVOLAZIONE_VALUES)
        assert result == ["fondo_perduto", "garanzia"]

    def test_non_lista(self):
        assert _to_enum_list("fondo_perduto", TIPO_AGEVOLAZIONE_VALUES) == []

    def test_none(self):
        assert _to_enum_list(None, TIPO_AGEVOLAZIONE_VALUES) == []

    def test_elementi_non_stringa_ignorati(self):
        result = _to_enum_list(["fondo_perduto", 123, None, "voucher"], TIPO_AGEVOLAZIONE_VALUES)
        assert result == ["fondo_perduto", "voucher"]

## 5. tests/test_matcher.py

Aggiungi in coda al file (dopo l'ultimo test esistente,
test_genera_scheda_scadenza_passata_mostra_scaduto) tutto questo blocco:

# ---------------------------------------------------------------------------
# #17 — nuovi campi in scheda: percentuale per fascia, modalità, tipo
# agevolazione, cumulabilità
# ---------------------------------------------------------------------------

def test_genera_scheda_percentuale_per_fascia():
    bando = {"bando": {
        "titolo": "Bando Test",
        "percentuale_fondo_perduto": {"micro": 60, "piccola": 50, "media": 40, "default": None},
    }}
    result = genera_scheda(bando)
    assert "Fondo perduto per fascia" in result
    assert "Micro 60%" in result
    assert "Piccola 50%" in result
    assert "Media 40%" in result


def test_genera_scheda_percentuale_default_singola():
    bando = {"bando": {
        "titolo": "Bando Test",
        "percentuale_fondo_perduto": {"micro": None, "piccola": None, "media": None, "default": 50},
    }}
    result = genera_scheda(bando)
    assert "**Fondo perduto:** 50%" in result
    assert "per fascia" not in result


def test_genera_scheda_percentuale_formato_legacy_numero():
    """Bando salvato prima di #17 (percentuale_fondo_perduto come numero
    semplice, non ancora passato da normalize_response): genera_scheda deve
    comunque renderizzarlo correttamente, non andare in errore."""
    bando = {"bando": {"titolo": "Bando Test", "percentuale_fondo_perduto": 35}}
    result = genera_scheda(bando)
    assert "**Fondo perduto:** 35%" in result


def test_genera_scheda_percentuale_assente_non_mostra_sezione_vuota():
    bando = {"bando": {"titolo": "Bando Test", "contributo_max": None, "percentuale_fondo_perduto": None}}
    result = genera_scheda(bando)
    assert "Contributi" not in result


def test_genera_scheda_modalita_presentazione():
    bando = {"bando": {"titolo": "Bando Test", "modalita_presentazione": "click_day"}}
    result = genera_scheda(bando)
    assert "Modalità di presentazione:** Click day" in result


def test_genera_scheda_modalita_presentazione_none_non_mostrata():
    bando = {"bando": {"titolo": "Bando Test", "modalita_presentazione": None}}
    result = genera_scheda(bando)
    assert "Modalità di presentazione" not in result


def test_genera_scheda_tipo_agevolazione():
    bando = {"bando": {
        "titolo": "Bando Test",
        "tipo_agevolazione": ["fondo_perduto", "finanziamento_agevolato"],
    }}
    result = genera_scheda(bando)
    assert "Tipo di agevolazione:** Fondo perduto, Finanziamento agevolato" in result


def test_genera_scheda_cumulabilita_tra_virgolette():
    bando = {"bando": {
        "titolo": "Bando Test",
        "cumulabilita": "Non cumulabile con altre misure a valere sullo stesso investimento",
    }}
    result = genera_scheda(bando)
    assert "Cumulabilità:** \u201cNon cumulabile con altre misure a valere sullo stesso investimento\u201d" in result


def test_genera_scheda_cumulabilita_assente_non_mostrata():
    bando = {"bando": {"titolo": "Bando Test", "cumulabilita": None}}
    result = genera_scheda(bando)
    assert "Cumulabilità" not in result

## Verifica finale

pytest -q   # 274 test verdi (238 + 36 nuovi)

Il frontend NON va toccato per questo intervento — verificalo comunque con
una ricerca di "percentuale_fondo_perduto", "modalita_presentazione",
"tipo_agevolazione", "cumulabilita" in frontend/src/ prima di concludere:
non deve trovare nulla (questi campi non sono mai letti/mostrati
direttamente da nessun componente, solo tramite la scheda Markdown
pre-generata da genera_scheda).

## Aggiornamento ROADMAP.md

Trova la riga dell'intervento #17 ([ ]), cambia in [x], aggiungi un breve
changelog: percentuale_fondo_perduto -> oggetto per fascia con
retrocompatibilità, modalita_presentazione e tipo_agevolazione con
normalizzazione enum (valori non riconosciuti scartati), cumulabilita come
estratto testuale letterale, genera_scheda aggiornata, prompt LLM aggiornato
con nuovo Esempio 3, +36 test, nessuna modifica frontend necessaria. Nella
tabella riepilogativa in fondo, titolo di #17 in ~~barrato~~.

## Nota per la revisione

Il punto più delicato è la retrocompatibilità di
normalize_percentuale_fondo_perduto(): deve funzionare identicamente sia
per il nuovo formato oggetto sia per il vecchio numero singolo, perché
`genera_scheda` la userà anche su bandi già salvati nel database PRIMA di
questo intervento (letti via /api/bandi/{id}/rigenera-scheda, che bypassa
normalize_response). Se tocchi questa funzione, verifica che
test_genera_scheda_percentuale_formato_legacy_numero continui a passare.

Fammi un riepilogo file per file di cosa hai effettivamente cambiato, con
il conteggio esatto dei test eseguiti, prima di fare il commit.
```

**Esito**: applicato come da specifica (schema.py, matcher.py, prompt di
sistema, test_schema.py, test_matcher.py). `normalize_percentuale_fondo_perduto()`
gestisce sia il nuovo formato oggetto per fascia sia il vecchio numero
singolo, condivisa tra schema.py e matcher.py per garantire retrocompatibilità
anche via `/api/bandi/{id}/rigenera-scheda`. Nessuna modifica al frontend
necessaria (verificato: nessun campo referenziato in frontend/src/).
274 test verdi (238 preesistenti + 36 nuovi), ROADMAP.md aggiornata.

#16 — Campo URL bando in CaricaBando + endpoint /api/estrazione-url (2026-07-09)

Scope: nuovo modulo modules/url_extractor.py (fetch sicuro anti-SSRF +
estrazione testo HTML), refactoring di main.py per condividere la
pipeline LLM→validazione→salvataggio→matching tra upload PDF e URL, nuovo
endpoint, tab "Da URL" nel frontend. Validato in sandbox: 238 test verdi
(212 + 20 nuovi in test_url_extractor.py + 6 in test_endpoints.py),
npm run build pulito.

Sto implementando l'intervento #16 della ROADMAP.md ("Campo URL bando in
CaricaBando + endpoint /api/estrazione-url"). Ho già validato in un altro
ambiente che questo scope builda pulito e passa 238 test (212 preesistenti
+ 26 nuovi). Applica queste modifiche direttamente sui file reali,
leggendo prima lo stato attuale di ciascuno — non fidarti ciecamente dei
numeri di riga.

## Contesto di sicurezza (importante, non semplificare)

L'allow-list dello schema (solo https) da sola NON basta a prevenire SSRF:
un URL può reindirizzare verso un host interno (es. il metadata endpoint
cloud 169.254.169.254) pur partendo da un host pubblico legittimo. Per
questo i redirect vanno seguiti MANUALMENTE (mai `allow_redirects=True`),
rivalidando schema e host a ogni hop.

## 1. Aggiungi due dipendenze a requirements.txt

requests==2.34.2
trafilatura==2.1.0

Poi pip install -r requirements.txt (o pip install requests==2.34.2 trafilatura==2.1.0 --break-system-packages).

## 2. Crea modules/url_extractor.py (nuovo file, contenuto esatto)

"""Fetch sicuro di risorse da URL esterni per l'estrazione bando (#16).

Espone due funzioni principali:
- fetch_url_safely(url): scarica il contenuto validando schema/host a ogni
  hop di redirect (protezione SSRF), con limite di dimensione e timeout.
- extract_text_from_html(html): estrae il testo "pulito" (senza nav/footer/
  script) da una pagina HTML, per poi riusare extract_bando_data() esistente.

Nota di sicurezza: l'allow-list dello schema (solo https) da sola non basta
a prevenire SSRF, perché un URL può reindirizzare verso un host interno
(es. il metadata endpoint di un cloud provider, 169.254.169.254) pur
partendo da uno schema/host pubblico legittimo. Per questo motivo i redirect
NON sono delegati alla libreria `requests` (allow_redirects=True) ma seguiti
manualmente, uno alla volta, rivalidando schema e host a ogni hop.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import requests
import trafilatura

from modules.schema import MIN_TEXT_CHARS

ALLOWED_URL_SCHEMES = {"https"}
URL_FETCH_TIMEOUT_SECONDS = 15
URL_FETCH_MAX_BYTES = 10_000_000  # 10 MB, stesso limite dell'upload PDF
URL_FETCH_MAX_REDIRECTS = 3
URL_FETCH_CHUNK_SIZE = 65536
USER_AGENT = "BandiScannerBot/1.0 (+estrazione automatica bandi)"


class InvalidUrlException(Exception):
    """URL non valido o non consentito (schema, host privato, troppo grande,
    troppi redirect). Il messaggio è pensato per essere mostrato all'utente."""


def _is_public_hostname(hostname: str) -> bool:
    """True se l'hostname risolve solo a indirizzi IP pubblici.

    Rifiuta risoluzioni verso IP privati/loopback/link-local/riservati per
    prevenire SSRF verso servizi interni. Un hostname che risolve a più IP
    (round-robin DNS) è considerato pubblico solo se TUTTI gli IP lo sono.
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except (socket.gaierror, UnicodeError):
        return False
    if not infos:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


def validate_bando_url(url: str) -> None:
    """Valida schema e host di un URL fornito dall'utente.

    Solleva InvalidUrlException con un messaggio adatto a essere mostrato
    all'utente se l'URL non è valido o non è consentito.
    """
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise InvalidUrlException("URL non valido.") from exc

    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        raise InvalidUrlException("Sono supportati solo link che iniziano con https://.")
    if not parsed.hostname:
        raise InvalidUrlException("URL non valido: host mancante.")
    if not _is_public_hostname(parsed.hostname):
        raise InvalidUrlException("URL non consentito: punta a un host interno o non raggiungibile.")


def fetch_url_safely(url: str) -> tuple[bytes, str, str | None, str]:
    """Scarica una risorsa da URL, seguendo i redirect manualmente e
    rivalidando schema/host a ogni hop.

    Ritorna (contenuto, content_type, encoding, url_finale).
    Solleva InvalidUrlException (URL/redirect non validi, risorsa troppo
    grande, troppi redirect) o requests.RequestException (errori di rete).
    """
    current_url = url

    for _ in range(URL_FETCH_MAX_REDIRECTS + 1):
        validate_bando_url(current_url)

        resp = requests.get(
            current_url,
            timeout=URL_FETCH_TIMEOUT_SECONDS,
            stream=True,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=False,
        )
        try:
            if resp.is_redirect or resp.is_permanent_redirect:
                location = resp.headers.get("location")
                if not location:
                    raise InvalidUrlException("Il link reindirizza senza indicare una destinazione valida.")
                current_url = urljoin(current_url, location)
                continue

            content = bytearray()
            for chunk in resp.iter_content(chunk_size=URL_FETCH_CHUNK_SIZE):
                content.extend(chunk)
                if len(content) > URL_FETCH_MAX_BYTES:
                    raise InvalidUrlException(
                        f"Risorsa troppo grande (limite {URL_FETCH_MAX_BYTES // 1_000_000} MB)."
                    )

            content_type = resp.headers.get("content-type", "")
            encoding = resp.encoding
            return bytes(content), content_type, encoding, current_url
        finally:
            resp.close()

    raise InvalidUrlException("Troppi redirect (limite superato).")


def extract_text_from_html(html: str) -> str:
    """Estrae il testo principale da una pagina HTML, scartando
    navigazione/footer/script. Ritorna stringa vuota se l'estrazione fallisce
    (il chiamante decide come trattare il caso, in analogia a un PDF vuoto)."""
    text = trafilatura.extract(html, favor_recall=True) or ""
    return text if len(text.strip()) >= MIN_TEXT_CHARS else ""

## 3. Crea tests/test_url_extractor.py (nuovo file, contenuto esatto)

"""Test per modules/url_extractor.py — fetch sicuro URL e estrazione HTML (#16)."""
from unittest.mock import MagicMock, patch

import pytest
import requests

from modules.url_extractor import (
    InvalidUrlException,
    URL_FETCH_MAX_BYTES,
    URL_FETCH_MAX_REDIRECTS,
    extract_text_from_html,
    fetch_url_safely,
    validate_bando_url,
)


def test_validate_bando_url_https_pubblico_ok():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        validate_bando_url("https://www.example.com/bando.pdf")


def test_validate_bando_url_rifiuta_http():
    with pytest.raises(InvalidUrlException, match="https"):
        validate_bando_url("http://www.example.com")


def test_validate_bando_url_rifiuta_ftp():
    with pytest.raises(InvalidUrlException, match="https"):
        validate_bando_url("ftp://www.example.com")


def test_validate_bando_url_rifiuta_file_scheme():
    with pytest.raises(InvalidUrlException):
        validate_bando_url("file:///etc/passwd")


def test_validate_bando_url_rifiuta_host_mancante():
    with pytest.raises(InvalidUrlException, match="host mancante"):
        validate_bando_url("https:///percorso-senza-host")


def test_validate_bando_url_rifiuta_loopback():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 0))]):
        with pytest.raises(InvalidUrlException, match="non consentito"):
            validate_bando_url("https://localhost/")


def test_validate_bando_url_rifiuta_ip_privato_10():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.5", 0))]):
        with pytest.raises(InvalidUrlException):
            validate_bando_url("https://intranet.aziendale.local/")


def test_validate_bando_url_rifiuta_ip_privato_192():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("192.168.1.1", 0))]):
        with pytest.raises(InvalidUrlException):
            validate_bando_url("https://router.local/")


def test_validate_bando_url_rifiuta_link_local_metadata_cloud():
    """169.254.169.254 è il metadata endpoint standard su AWS/GCP/Azure —
    un bersaglio SSRF classico se non bloccato esplicitamente."""
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("169.254.169.254", 0))]):
        with pytest.raises(InvalidUrlException):
            validate_bando_url("https://metadata.internal/")


def test_validate_bando_url_rifiuta_se_dns_non_risolve():
    import socket as socket_module
    with patch("socket.getaddrinfo", side_effect=socket_module.gaierror("nome a dominio inesistente")):
        with pytest.raises(InvalidUrlException):
            validate_bando_url("https://dominio-che-non-esiste-xyz123.test/")


def test_validate_bando_url_rifiuta_se_uno_dei_multi_ip_e_privato():
    """DNS round-robin: se anche solo uno degli IP risolti è privato, l'host
    non è considerato pubblico (difesa in profondità)."""
    with patch("socket.getaddrinfo", return_value=[
        (2, 1, 6, "", ("93.184.216.34", 0)),
        (2, 1, 6, "", ("10.0.0.1", 0)),
    ]):
        with pytest.raises(InvalidUrlException):
            validate_bando_url("https://misto.example.com/")


def _make_response(*, status_ok=True, is_redirect=False, location=None,
                    chunks=(b"contenuto",), headers=None):
    resp = MagicMock()
    resp.is_redirect = is_redirect
    resp.is_permanent_redirect = False
    resp.headers = headers or {}
    if is_redirect and location:
        resp.headers = {**resp.headers, "location": location}
    resp.iter_content = MagicMock(return_value=iter(chunks))
    resp.encoding = "utf-8"
    resp.close = MagicMock()
    return resp


def test_fetch_url_safely_scarica_contenuto_semplice():
    resp = _make_response(chunks=(b"hello ", b"world"), headers={"content-type": "text/html"})
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        with patch("requests.get", return_value=resp) as mock_get:
            content, content_type, encoding, final_url = fetch_url_safely("https://www.example.com/bando")
    assert content == b"hello world"
    assert content_type == "text/html"
    assert final_url == "https://www.example.com/bando"
    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs["allow_redirects"] is False


def test_fetch_url_safely_segue_un_redirect_e_rivalida():
    redirect_resp = _make_response(is_redirect=True, location="https://www.example.com/finale")
    final_resp = _make_response(chunks=(b"pagina finale",))
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        with patch("requests.get", side_effect=[redirect_resp, final_resp]) as mock_get:
            content, _, _, final_url = fetch_url_safely("https://www.example.com/vecchio")
    assert content == b"pagina finale"
    assert final_url == "https://www.example.com/finale"
    assert mock_get.call_count == 2


def test_fetch_url_safely_rifiuta_redirect_verso_ip_privato():
    """Il caso critico SSRF: il primo hop è pubblico, il redirect punta a un
    host privato — deve essere rifiutato comunque, non solo il primo hop."""
    redirect_resp = _make_response(is_redirect=True, location="https://intranet.local/segreto")

    def fake_getaddrinfo(hostname, *_args, **_kwargs):
        if hostname == "intranet.local":
            return [(2, 1, 6, "", ("10.0.0.1", 0))]
        return [(2, 1, 6, "", ("93.184.216.34", 0))]

    with patch("socket.getaddrinfo", side_effect=fake_getaddrinfo):
        with patch("requests.get", return_value=redirect_resp):
            with pytest.raises(InvalidUrlException):
                fetch_url_safely("https://www.example.com/vecchio")


def test_fetch_url_safely_rifiuta_troppi_redirect():
    redirect_resp = _make_response(is_redirect=True, location="https://www.example.com/loop")
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        with patch("requests.get", return_value=redirect_resp) as mock_get:
            with pytest.raises(InvalidUrlException, match="redirect"):
                fetch_url_safely("https://www.example.com/loop")
    assert mock_get.call_count == URL_FETCH_MAX_REDIRECTS + 1


def test_fetch_url_safely_rifiuta_risorsa_troppo_grande():
    chunk = b"x" * (URL_FETCH_MAX_BYTES // 4 + 1)
    resp = _make_response(chunks=(chunk, chunk, chunk, chunk, chunk))
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        with patch("requests.get", return_value=resp):
            with pytest.raises(InvalidUrlException, match="grande"):
                fetch_url_safely("https://www.example.com/file-enorme")


def test_fetch_url_safely_propaga_errori_di_rete():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        with patch("requests.get", side_effect=requests.ConnectionError("timeout")):
            with pytest.raises(requests.RequestException):
                fetch_url_safely("https://www.example.com/irraggiungibile")


def test_extract_text_from_html_scarta_nav_e_footer():
    html = (
        "<html><body>"
        "<nav>Home Chi siamo Contatti</nav>"
        "<article><h1>Bando Innovazione</h1><p>"
        + ("Contenuto informativo del bando. " * 15)
        + "</p></article>"
        "<footer>Copyright 2026 Tutti i diritti riservati</footer>"
        "</body></html>"
    )
    text = extract_text_from_html(html)
    assert "Bando Innovazione" in text
    assert "Contenuto informativo" in text
    assert "Copyright" not in text
    assert "Chi siamo" not in text


def test_extract_text_from_html_ritorna_stringa_vuota_se_troppo_corto():
    html = "<html><body><p>Ciao</p></body></html>"
    assert extract_text_from_html(html) == ""


def test_extract_text_from_html_ritorna_stringa_vuota_se_pagina_vuota():
    assert extract_text_from_html("<html><body></body></html>") == ""

## 4. tests/conftest.py — reset del rate limit tra un test e l'altro

Il rate limit di /api/estrazione* è un contatore in-process condiviso per
IP (per design). Aggiungendo 6 nuovi test che chiamano /api/estrazione-url
si rischia di sforare la soglia di 10/ora condivisa con gli altri test
della sessione. Aggiungi, subito dopo gli import in cima al file, questa
fixture autouse (prima della sezione "Mock DB layer"):

import pytest
from unittest.mock import MagicMock, patch
from collections import defaultdict, deque


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    import main
    main._rate_limit_hits.clear()
    yield
    main._rate_limit_hits.clear()

(Nota: `from collections import defaultdict, deque` potrebbe già essere
importato altrove nel file per altri test — se sì, non duplicare l'import,
aggiungi solo la fixture.)

## 5. main.py — refactoring + nuovo endpoint

### 5a. Import (in cima al file)

Aggiungi, vicino agli altri import stdlib:
from urllib.parse import urlparse
import requests

Aggiungi, subito dopo il blocco `from modules.extractor import (...)`:
from modules.url_extractor import (
    InvalidUrlException,
    extract_text_from_html,
    fetch_url_safely,
)

### 5b. Refactoring dell'endpoint /api/estrazione esistente

Trova la funzione `api_estrazione_submit` (decorata con
`@app.post("/api/estrazione", ...)`). Il blocco che va da
`result["raw_text_preview"] = text[:1000]` fino a poco prima di
`return result` / `finally: file_path.unlink(...)` (cioè tutta la logica
di extract_bando_data → validate_bando → controllo duplicati → salvataggio
→ matching → log_prompt_run) va estratta in una funzione condivisa, perché
il nuovo endpoint /api/estrazione-url deve fare esattamente la stessa cosa
partendo da un testo diverso.

Crea questa funzione PRIMA di `api_estrazione_submit` (subito dopo
`PDF_MAGIC = b"%PDF"`):

def _process_and_save_bando(text: str, source_label: str) -> dict:
    """Pipeline condivisa post-estrazione testo: LLM -> validazione -> dedup
    -> salvataggio -> matching. Usata sia da /api/estrazione (upload PDF)
    sia da /api/estrazione-url (#16), per non duplicare questa logica.

    Nota sul caso duplicato: a differenza della versione precedente (che
    ricostruiva una risposta minimale), qui il risultato include anche i
    campi già raccolti prima del controllo duplicati (raw_text_preview,
    data, bando_info, warnings, errors) — dati extra innocui per il
    frontend, che legge solo i campi che già conosce.
    """
    result: dict = {"raw_text_preview": text[:1000]}
    try:
        raw_data = extract_bando_data(text)
        validation = validate_bando(raw_data, raw_text=text)
        data = validation["data"]
        bando_info = data.get("bando", {})

        result["data"] = data
        result["bando_info"] = bando_info
        result["warnings"] = validation.get("warnings", [])
        result["errors"] = validation.get("errors", [])

        if bando_info.get("ateco_aperto_a_tutti") is False:
            escl = bando_info.get("note_esclusioni", {})
            if isinstance(escl, dict):
                result["sezioni_escluse"] = escl.get("sezioni_ateco_escluse", [])
                result["attivita_vietate"] = escl.get("attivita_vietate", [])
            else:
                result["note_esclusioni_raw"] = str(escl)

        if not validation["errors"]:
            try:
                existing_id = find_duplicate_bando(bando_info.get("titolo"), bando_info.get("ente"))
                if existing_id:
                    result["status"] = "duplicato"
                    result["messaggio"] = "Bando già presente in archivio"
                    result["bando_id"] = existing_id
                    result["scheda"] = genera_scheda(data)
                    return result

                scheda = genera_scheda(data)
                bando_id = save_bando_from_json(data, scheda=scheda)
                with get_connection() as conn:
                    run_matching_for_bando(bando_id, conn)

                result["bando_id"] = bando_id
                result["scadenza_estratta"] = bando_info.get("data_scadenza")
                result["null_percentage"] = validation.get("null_percentage", 0)

                ok_fields, null_fields = fields_status(data)
                log_prompt_run(filename=source_label, fields_ok=ok_fields, fields_null=null_fields, notes="Validazione OK")

                result["scheda"] = scheda
            except Exception as exc:
                log_error(f"_process_and_save_bando: salvataggio bando '{source_label}' fallito: {exc}")
                result["save_error"] = "Impossibile salvare il bando estratto. Riprova."
    except Exception as exc:
        log_error(f"_process_and_save_bando: estrazione/validazione '{source_label}' fallita: {exc}")
        result["extraction_error"] = "Errore durante l'estrazione dei dati. Riprova o contatta l'assistenza."

    return result

Poi, dentro `api_estrazione_submit`, sostituisci tutto il blocco da
`result["raw_text_preview"] = text[:1000]` fino a subito prima di
`return result` (quello che chiude il try/finally esterno) con una singola
riga:

        result.update(_process_and_save_bando(text, safe_name))
        return result

(il resto della funzione — lettura file, controllo magic bytes PDF,
scrittura file temporaneo, extract_text_from_pdf con i suoi except
EmptyPDFException/PDFTroppoGrandeException/PDFInvalidoException, e il
`finally: file_path.unlink(missing_ok=True)` — resta com'è, invariato).

### 5c. Nuovo endpoint /api/estrazione-url

Aggiungi subito dopo la fine di `api_estrazione_submit` (dopo il suo
`finally: file_path.unlink(missing_ok=True)`):

class EstrazioneUrlIn(BaseModel):
    url: str


@app.post("/api/estrazione-url", dependencies=[Depends(verify_api_key), Depends(rate_limit_estrazione)])
def api_estrazione_url_submit(payload: EstrazioneUrlIn):
    """Estrazione bando da URL (#16): scarica la risorsa (PDF o pagina HTML),
    ne estrae il testo e riusa la stessa pipeline dell'upload PDF.

    Sicurezza: allow-list schema (solo https), blocco host privati/interni
    anche sui redirect, timeout e limite dimensione — vedi modules/url_extractor.py.
    """
    try:
        content_bytes, content_type, encoding, final_url = fetch_url_safely(payload.url)
    except InvalidUrlException as exc:
        return JSONResponse(status_code=400, content={"errors": [str(exc)]})
    except requests.RequestException as exc:
        log_error(f"api_estrazione_url_submit: fetch '{payload.url}' fallito: {exc}")
        return JSONResponse(status_code=400, content={
            "errors": ["Impossibile scaricare la pagina. Verifica il link e riprova."]
        })

    filename = urlparse(final_url).hostname or payload.url
    result = {"filename": filename, "size_kb": len(content_bytes) / 1024}

    is_pdf = content_bytes.startswith(PDF_MAGIC) or "application/pdf" in content_type
    file_path: Path | None = None
    try:
        if is_pdf:
            file_path = TEMP_DIR / f"{uuid.uuid4().hex}_estrazione_url.pdf"
            with open(file_path, "wb") as f:
                f.write(content_bytes)
            try:
                text = extract_text_from_pdf(str(file_path))
            except EmptyPDFException:
                result["empty_pdf"] = True
                return result
            except PDFTroppoGrandeException as exc:
                log_error(f"api_estrazione_url_submit: '{final_url}' rifiutato, PDF troppo esteso: {exc}")
                return JSONResponse(status_code=400, content={
                    "errors": ["Il PDF ha troppe pagine. Riduci il documento (o dividilo) e riprova."]
                })
            except PDFInvalidoException as exc:
                log_error(f"api_estrazione_url_submit: '{final_url}' PDF corrotto/non leggibile: {exc}")
                return JSONResponse(status_code=400, content={
                    "errors": ["Il PDF risulta corrotto o non leggibile. Verifica il link e riprova."]
                })
        else:
            try:
                html_text = content_bytes.decode(encoding or "utf-8", errors="replace")
            except (LookupError, UnicodeDecodeError):
                html_text = content_bytes.decode("utf-8", errors="replace")
            text = extract_text_from_html(html_text)
            if not text:
                result["empty_pdf"] = True
                return result
    finally:
        if file_path is not None:
            file_path.unlink(missing_ok=True)

    result.update(_process_and_save_bando(text, filename))
    return result

## 6. tests/test_endpoints.py — nuovi test per /api/estrazione-url

Aggiungi in coda al file (dopo l'ultimo test esistente,
test_estrazione_rate_limit_oltre_soglia_ritorna_429):

def test_post_estrazione_url_rifiuta_url_non_valido(client):
    from modules.url_extractor import InvalidUrlException

    with patch("main.fetch_url_safely", side_effect=InvalidUrlException("Sono supportati solo link https://.")):
        response = client.post("/api/estrazione-url", json={"url": "http://esempio.it/bando"})
    assert response.status_code == 400
    assert "https" in response.json()["errors"][0]


def test_post_estrazione_url_errore_di_rete(client):
    import requests

    with patch("main.fetch_url_safely", side_effect=requests.ConnectionError("timeout")):
        response = client.post("/api/estrazione-url", json={"url": "https://esempio.it/bando"})
    assert response.status_code == 400
    assert "scaricare" in response.json()["errors"][0]


def test_post_estrazione_url_pagina_html_vuota(client):
    html = b"<html><body><p>pagina troppo corta</p></body></html>"
    with patch("main.fetch_url_safely", return_value=(html, "text/html", "utf-8", "https://esempio.it/bando")), \
         patch("main.extract_text_from_html", return_value=""):
        response = client.post("/api/estrazione-url", json={"url": "https://esempio.it/bando"})
    assert response.status_code == 200
    assert response.json()["empty_pdf"] is True


def test_post_estrazione_url_successo_html(client, mock_db):
    html = b"<html><body><article>contenuto bando</article></body></html>"
    with patch("main.fetch_url_safely", return_value=(html, "text/html", "utf-8", "https://esempio.it/bando")), \
         patch("main.extract_text_from_html", return_value="testo del bando " * 10), \
         patch("main.extract_bando_data", return_value=BANDO_ESTRATTO), \
         patch("main.find_duplicate_bando", return_value=None), \
         patch("main.save_bando_from_json", return_value=321), \
         patch("main.run_matching_for_bando"):
        response = client.post("/api/estrazione-url", json={"url": "https://esempio.it/bando"})
    assert response.status_code == 200
    data = response.json()
    assert data["bando_id"] == 321
    assert data["filename"] == "esempio.it"
    assert "scheda" in data


def test_post_estrazione_url_successo_pdf_diretto(client, mock_db):
    """L'URL punta direttamente a un PDF (Content-Type application/pdf):
    deve passare per extract_text_from_pdf, non extract_text_from_html."""
    with patch("main.fetch_url_safely", return_value=(VALID_PDF_BYTES, "application/pdf", None, "https://esempio.it/bando.pdf")), \
         patch("main.extract_text_from_pdf", return_value="testo del bando " * 10), \
         patch("main.extract_text_from_html") as mock_html, \
         patch("main.extract_bando_data", return_value=BANDO_ESTRATTO), \
         patch("main.find_duplicate_bando", return_value=None), \
         patch("main.save_bando_from_json", return_value=99), \
         patch("main.run_matching_for_bando"):
        response = client.post("/api/estrazione-url", json={"url": "https://esempio.it/bando.pdf"})
    assert response.status_code == 200
    data = response.json()
    assert data["bando_id"] == 99
    mock_html.assert_not_called()


def test_post_estrazione_url_duplicato(client, mock_db):
    html = b"<html><body><article>contenuto bando</article></body></html>"
    with patch("main.fetch_url_safely", return_value=(html, "text/html", "utf-8", "https://esempio.it/bando")), \
         patch("main.extract_text_from_html", return_value="testo del bando " * 10), \
         patch("main.extract_bando_data", return_value=BANDO_ESTRATTO), \
         patch("main.find_duplicate_bando", return_value=42):
        response = client.post("/api/estrazione-url", json={"url": "https://esempio.it/bando"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "duplicato"
    assert data["bando_id"] == 42

(BANDO_ESTRATTO e VALID_PDF_BYTES sono già definiti più in alto nello
stesso file, riusali — non ridefinirli.)

## 7. Frontend: frontend/src/components/CaricaBando.tsx

- Aggiungi state, subito dopo `const fileInputRef = useRef<HTMLInputElement>(null)`:
  const [mode, setMode] = useState<'pdf' | 'url'>('pdf')
  const [bandoUrl, setBandoUrl] = useState('')

- Aggiungi una funzione `IconLink()` vicino alle altre icone (IconUpload,
  IconCheck, IconX):
  function IconLink() {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
      </svg>
    )
  }

- Aggiungi una funzione `handleUploadUrl`, subito dopo `handleUpload`:
  const handleUploadUrl = async () => {
    if (!bandoUrl.trim()) return
    try {
      new URL(bandoUrl.trim())
    } catch {
      setNetworkError('URL non valido. Deve iniziare con https://')
      toast.error('URL non valido.')
      return
    }

    setUploading(true)
    setNetworkError(null)
    setResult(null)

    try {
      const res = await fetch('/api/estrazione-url', withApiKey({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: bandoUrl.trim() }),
      }))
      const data: ExtractionResult = await res.json()
      if (!res.ok) {
        setNetworkError(data.errors?.[0] ?? 'Impossibile elaborare il link.')
        toast.error(data.errors?.[0] ?? 'Impossibile elaborare il link.')
        return
      }
      setResult(data)
      if (data.status === 'duplicato') {
        toast.info('Bando già presente in archivio.')
      } else if (data.bando_id && !data.errors?.length) {
        toast.success('Bando salvato con successo.')
        invalidateAll()
      } else if (data.empty_pdf) {
        toast.error('Pagina vuota o non leggibile.')
      } else if (data.errors?.length) {
        toast.error('Estrazione completata con errori di validazione.')
      }
    } catch {
      setNetworkError('Errore di rete durante il caricamento. Verifica la connessione.')
      toast.error('Errore di rete durante il caricamento.')
    } finally {
      setUploading(false)
    }
  }

- In `handleReset`, aggiungi la pulizia di bandoUrl/mode:
  const handleReset = () => {
    setSelectedFile(null)
    setBandoUrl('')
    setMode('pdf')
    setResult(null)
    setNetworkError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

- Nel JSX, subito dentro `<div className="carica-main">` e prima del
  `<div className="card">` esistente, aggiungi il tab switch:
  <div className="carica-mode-tabs" role="tablist" aria-label="Sorgente del bando">
    <button
      type="button"
      role="tab"
      aria-selected={mode === 'pdf'}
      className={`carica-mode-tab${mode === 'pdf' ? ' active' : ''}`}
      onClick={() => { setMode('pdf'); setNetworkError(null) }}
    >
      <IconUpload /> Carica PDF
    </button>
    <button
      type="button"
      role="tab"
      aria-selected={mode === 'url'}
      className={`carica-mode-tab${mode === 'url' ? ' active' : ''}`}
      onClick={() => { setMode('url'); setNetworkError(null) }}
    >
      <IconLink /> Da URL
    </button>
  </div>

- Dentro `<div className="card">`, la drop-zone esistente (il div con
  className upload-zone) va avvolta in `{mode === 'pdf' ? ( ... ) : ( ... )}`,
  con questo ramo `else` per il form URL:
  <div className="upload-zone-url">
    <label htmlFor="bando-url-input" className="upload-zone-title" style={{ display: 'block', marginBottom: 8 }}>
      Incolla il link alla pagina del bando o al PDF online
    </label>
    <input
      id="bando-url-input"
      type="url"
      inputMode="url"
      placeholder="https://www.regione.esempio.it/bando-innovazione"
      className="upload-url-input"
      value={bandoUrl}
      onChange={e => setBandoUrl(e.target.value)}
      onKeyDown={e => { if (e.key === 'Enter' && bandoUrl.trim()) handleUploadUrl() }}
    />
    <p className="upload-zone-sub" style={{ marginTop: 8 }}>
      Solo link https:// · pagina web o PDF direttamente online
    </p>
  </div>

- Il primo "upload-step" (quello con numero 1) deve mostrare un testo
  diverso in base al mode:
  <p className="upload-step-text">
    {mode === 'pdf'
      ? <><strong>Seleziona il PDF</strong> del bando da analizzare</>
      : <><strong>Incolla il link</strong> alla pagina o al PDF del bando</>}
  </p>

- La condizione che mostra i bottoni "Annulla"/"Estrai e salva" (oggi
  `{selectedFile && (...)}`) diventa:
  {((mode === 'pdf' && selectedFile) || (mode === 'url' && bandoUrl.trim())) && (
    <div style={{ display: 'flex', gap: 10, marginTop: 16, justifyContent: 'flex-end' }}>
      <button className="btn" onClick={handleReset}>Annulla</button>
      <button
        className="btn btn-primary"
        onClick={mode === 'pdf' ? handleUpload : handleUploadUrl}
        disabled={uploading}
      >
        {uploading
          ? <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Analisi in corso…</>
          : <><IconUpload /> Estrai e salva</>}
      </button>
    </div>
  )}

## 8. CSS: frontend/src/styles.css

Subito dopo la riga `.upload-zone-sub { font-size: var(--text-sm); color: var(--color-text-muted); }`
(fine del blocco "UPLOAD ZONE"), aggiungi:

/* Tab switch "Carica PDF" / "Da URL" (#16) */
.carica-mode-tabs {
    display: flex; gap: var(--space-2); margin-bottom: var(--space-4);
}
.carica-mode-tab {
    display: flex; align-items: center; gap: var(--space-2);
    padding: var(--space-2) var(--space-4); border-radius: 10px;
    border: 1px solid var(--color-border); background: #fff;
    color: var(--color-text-muted); font-size: var(--text-sm); font-weight: 600;
    cursor: pointer; transition: border-color 150ms, background 150ms, color 150ms;
}
.carica-mode-tab svg { width: 16px; height: 16px; }
.carica-mode-tab:hover { border-color: var(--color-accent); color: var(--color-text); }
.carica-mode-tab.active {
    border-color: var(--color-accent); background: var(--color-accent-soft); color: var(--color-accent);
}
.carica-mode-tab:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }

.upload-zone-url {
    border: 2px solid var(--color-border); border-radius: 16px;
    padding: var(--space-6); background: #fafbfc;
}
.upload-url-input {
    width: 100%; padding: var(--space-3) var(--space-4);
    border: 1px solid var(--color-border-strong); border-radius: 10px;
    font-size: var(--text-base); color: var(--color-text);
}
.upload-url-input:focus-visible {
    outline: 2px solid var(--color-accent); outline-offset: 1px; border-color: var(--color-accent);
}

## Verifica finale

pip install -r requirements.txt
pytest -q                                      # 238 test verdi (212 + 26)
cd frontend && npm run build                   # zero errori TypeScript

## Aggiornamento ROADMAP.md

Trova la riga dell'intervento #16 ([ ]), cambia in [x], aggiungi un breve
changelog: nuovo modules/url_extractor.py (protezione SSRF, redirect
manuali rivalidati ad ogni hop), refactoring main.py con
_process_and_save_bando condiviso, nuovo endpoint /api/estrazione-url,
tab "Da URL" nel frontend, +26 test, nuove dipendenze requests/trafilatura.
Nella tabella riepilogativa in fondo, titolo di #16 in ~~barrato~~.

## Nota per la revisione

Ho scelto di seguire manualmente i redirect (invece di
`requests.get(..., allow_redirects=True)`) specificamente per poter
rivalidare l'host ad ogni hop — è la parte più delicata di questo
intervento dal punto di vista della sicurezza. Se modifichi
fetch_url_safely, verifica che questa proprietà resti vera: nessun
redirect deve mai essere seguito senza essere prima passato da
validate_bando_url().

Fammi un riepilogo file per file di cosa hai effettivamente cambiato,
incluso il conteggio esatto dei test eseguiti, prima di fare il commit.

**Esito**: applicato come da specifica. `pip install requests==2.34.2
trafilatura==2.1.0` eseguito prima dei test. `pytest -q` → 238 test verdi
(212 preesistenti + 20 in `test_url_extractor.py` + 6 in
`test_endpoints.py`); `npm run build` pulito. Nessuna modifica al contenuto
di `fetch_url_safely()` rispetto alla specifica (redirect seguiti
manualmente, rivalidati a ogni hop). ROADMAP #16 spuntato, changelog
aggiunto.
Fix regressione card Dashboard (scadenza/urgenza/contributo max spariti) (2026-07-11)

Contesto: nel commit eac1aba (redesign card espandibili, lavoro fatto con
Codex) sono spariti dalla card della Dashboard: la riga "Scade DD/MM/YYYY ·
N gg" con badge urgenza (introdotta in #6, uno dei P0 originari), la riga
"Contributo max", e la KPI "Bandi con clienti". Validato in sandbox: build
pulito, 274 test Python invariati (intervento solo frontend).

Nel commit eac1aba (redesign delle card della Dashboard in versione
espandibile/collassabile) sono sparite tre informazioni che c'erano prima
e che vanno ripristinate, senza toccare il nuovo comportamento a
fisarmonica (che va bene tenerlo):

1. La riga "Scade DD/MM/YYYY · N gg" con badge urgenza (introdotta in #6)
2. La riga "Contributo max"
3. La KPI card "Bandi con clienti" nella parte alta della Dashboard

Apri frontend/src/components/Dashboard.tsx e applica queste modifiche:

## 1. Ripristina le funzioni isBlank e scadenzaTextClass (rimosse nel
redesign, servono di nuovo)

Subito prima di "function scoreClass(colorClass: string): string {",
aggiungi:

const BLANK_VALUES = new Set(['n/d', 'null', 'none', 'undefined', ''])
function isBlank(v: string | null | undefined): boolean {
  if (v == null) return true
  return BLANK_VALUES.has(v.trim().toLowerCase())
}

Subito prima di "type SchedaModal = SchedaModalData", aggiungi:

function scadenzaTextClass(giorni: number | null): string {
  if (giorni === null) return ''
  if (giorni < 0) return 'text-muted'
  if (giorni < 30) return 'scadenza-giorni-red'
  if (giorni < 90) return 'scadenza-giorni-orange'
  return 'scadenza-giorni-green'
}

## 2. Aggiungi la sezione "quick info" sempre visibile nella card

Dentro BandoCardItem, trova la chiusura del bottone header (il tag
</button> che chiude il bottone con className="bando-card-header") e
subito dopo, PRIMA di "{expanded && (", aggiungi:

        {((card.scadenza && card.scadenza !== 'N/D') || !isBlank(card.contributo_max)) && (
          <div className="bando-card-quick-info">
            {card.scadenza && card.scadenza !== 'N/D' && (
              <div className="bando-card-scadenza-row">
                <span className={`scadenza-label ${scadenzaTextClass(card.giorni_alla_scadenza)}`}>
                  Scade {card.scadenza}
                  {card.giorni_alla_scadenza !== null && card.giorni_alla_scadenza >= 0 &&
                    ` · ${card.giorni_alla_scadenza} gg`}
                </span>
                {card.urgenza && card.urgenza !== 'scaduto' && (
                  <span className={`badge badge-${card.urgenza}`}>{card.urgenza}</span>
                )}
              </div>
            )}
            {!isBlank(card.contributo_max) && (
              <div className="bando-card-contributo-row">
                <span className="bando-card-contributo-label">Contributo max</span>
                <span className="bando-card-contributo">{card.contributo_max}</span>
              </div>
            )}
          </div>
        )}

IMPORTANTE: chiama la classe del div "bando-card-quick-info" e NON
"bando-card-meta" — esiste già una regola CSS .bando-card-meta in
styles.css (attualmente non usata da nessun componente, quindi CSS morto,
ma non toccarla/riusarla) con uno stile diverso (border-top, padding), che
andrebbe in conflitto/collisione di nome con quella nuova.

## 3. Ripristina la KPI "Bandi con clienti"

Trova, dentro il div "kpi-row", la kpi-card "Abbinamenti trovati" (quella
con {d.totale_abbinamenti}) e aggiungi subito dopo la sua chiusura </div>:

        <div className="kpi-card">
          <p className="kpi-label">Bandi con clienti</p>
          <p className="kpi-value">{uniqueCards.filter(c => c.matches.length > 0).length}</p>
        </div>

(quindi ci saranno di nuovo 3 kpi-card in fila: Bandi in archivio,
Abbinamenti trovati, Bandi con clienti)

## 4. frontend/src/styles.css — nuova regola CSS

Subito dopo la regola ".bando-card-details--always { ... }" (cercala, è
vicino alle regole ".bando-card-chevron" e ".bando-card-details"),
aggiungi:

.bando-card-quick-info {
    margin-top: var(--space-2);
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
}

Le classi CSS che riusi qui (.bando-card-scadenza-row, .scadenza-label,
.scadenza-giorni-red/orange/green, .bando-card-contributo-row,
.bando-card-contributo-label, .bando-card-contributo) esistono già nel
file, non ricrearle.

## Verifica finale

cd frontend && npm run build   # zero errori TypeScript
cd .. && pytest -q              # 274 test verdi (intervento solo frontend,
                                 # non deve impattare il backend)

Fammi un riepilogo di cosa hai cambiato prima di fare il commit.