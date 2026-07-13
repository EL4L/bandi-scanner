// Tipi, formattazione e icone condivisi tra Clienti.tsx e ClienteDetailPage.tsx.
// Centralizzati qui per evitare un import circolare tra i due componenti
// (piccolo passo verso il refactoring lib/icons + lib/format previsto in ROADMAP #20).

export interface Cliente {
  id: number
  ragione_sociale: string
  p_iva: string
  codice_ateco: string
  regione: string
  fatturato: number
  dimensione_impresa: string
  descrizione_attivita: string
  data_costituzione?: string | null
  numero_dipendenti?: number | null
  forma_giuridica?: string | null
  match_count: number
}

export interface Ammissibilita {
  // #2 (audit Fable): null = la verifica non è riuscita (errore lato server),
  // da NON confondere con true/false. Va sempre controllato il flag `errore`
  // prima di trattare un valore mancante come "ammissibile per default".
  ammissibile: boolean | null
  motivi_esclusione: string[]
  criteri_verificati: string[]
  errore?: boolean
}

export interface BandoMatch {
  bando_id: number
  titolo: string | null
  ente: string | null
  score: number
  breakdown: {
    regione: number
    ateco: number
    dimensione: number
    fatturato: number
    total: number
    status?: 'ok' | 'da_verificare'
  }
  scadenza: string | null
  giorni_alla_scadenza: number | null
  ammissibilita?: Ammissibilita
  fonte_url?: string | null
  has_pdf?: boolean
}

export function formatEuro(val: number) {
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(val)
}

const FORMA_GIURIDICA_LABELS: Record<string, string> = {
  srl: 'S.r.l.',
  spa: 'S.p.A.',
  snc: 'S.n.c.',
  sas: 'S.a.s.',
  'ditta individuale': 'Ditta individuale',
  cooperativa: 'Cooperativa',
  associazione: 'Associazione',
}

export function formatFormaGiuridica(val?: string | null): string | null {
  if (!val) return null
  return FORMA_GIURIDICA_LABELS[val] ?? val
}

export function formatDataCostituzione(val?: string | null): string | null {
  if (!val) return null
  const parts = val.split('T')[0].split('-')
  if (parts.length !== 3) return val
  const [year, month, day] = parts
  return `${day}/${month}/${year}`
}

export function matchCountBadgeClass(count: number): string {
  if (count > 5) return 'count-badge-high'
  if (count > 0) return 'count-badge-mid'
  return 'count-badge-low'
}

export function stripColorByGiorni(giorni: number | null): string {
  if (giorni === null || giorni < 0) return 'var(--color-border-strong)'
  if (giorni < 30) return 'var(--status-low)'
  if (giorni <= 90) return 'var(--status-mid)'
  return 'var(--status-high)'
}

export function scoreCircleClass(score: number): string {
  if (score > 70) return 'score-green'
  if (score >= 40) return 'score-yellow'
  return 'score-red'
}

export function giorniColorClass(giorni: number): string {
  if (giorni < 30) return 'scadenza-giorni-red'
  if (giorni <= 90) return 'scadenza-giorni-orange'
  return 'scadenza-giorni-green'
}

function pillClass(score: number, max: number): string {
  if (score === max) return 'breakdown-pill-full'
  if (score >= max / 2) return 'breakdown-pill-partial'
  return 'breakdown-pill-zero'
}

// ── Icone (niente emoji: pallino/spunta/triangolo/x come SVG) ──────────────

export function IconCheck() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}
export function IconAlert() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  )
}
export function IconInfo() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  )
}
export function IconBan() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
    </svg>
  )
}
export function IconEdit() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  )
}
export function IconTrash() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  )
}
export function IconClose() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}
export function IconSearch() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  )
}
export function IconChevronRight() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  )
}
export function IconArrowLeft() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
    </svg>
  )
}
export function IconPlus() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
}
export function IconDownload() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  )
}
export function IconExternal() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  )
}

export function BreakdownBar({ label, score, max }: { label: string; score: number; max: number }) {
  const pct = max > 0 ? Math.round((score / max) * 100) : 0
  const cls = pillClass(score, max)
  const Icon = cls === 'breakdown-pill-full' ? IconCheck : cls === 'breakdown-pill-partial' ? IconAlert : IconBan
  return (
    <div className={`breakdown-bar-row ${cls}`}>
      <span className="breakdown-bar-label">
        <span className="breakdown-bar-icon"><Icon /></span> {label}
      </span>
      <div className="breakdown-bar-track" role="img" aria-label={`${label}: ${score} su ${max} punti`}>
        <div className="breakdown-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="breakdown-bar-value">{score}/{max}</span>
    </div>
  )
}
