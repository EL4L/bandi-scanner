export interface ScoreBreakdown {
  total: number
  ateco: number
  regione: number
  dimensione: number
  fatturato: number
  status?: 'ok' | 'da_verificare'
}

export interface Ammissibilita {
  ammissibile: boolean | null
  motivi_esclusione: string[]
  criteri_verificati: string[]
  errore?: boolean
}

export interface DashboardMatch {
  cliente_id?: number | null
  nome: string
  score: number
  score_badge_class: string
  breakdown: ScoreBreakdown
  settore_da_verificare: boolean
  spiegazione_score: string | null
  ammissibilita?: Ammissibilita
}

export interface DashboardBandoCard {
  id: number
  titolo: string
  ente: string | null
  contributo_max: string
  contributo_max_valore?: number | null
  scadenza: string
  giorni_alla_scadenza: number | null
  urgenza: string | null
  max_score: number
  raw_max_score?: number
  nessun_cliente_ammissibile?: boolean
  color_class: string
  has_constraints: boolean
  matches: DashboardMatch[]
  scheda: string
  fonte_url: string | null
  has_pdf: boolean
}

export interface DashboardData {
  n_bandi: number
  totale_abbinamenti: number
  has_export_data: boolean
  cards: DashboardBandoCard[]
  duplicates_count: number
}

export type DashboardCategory = 'ammissibili' | 'da_verificare' | 'non_ammissibili' | 'scaduti'

export function isExpiredCard(card: DashboardBandoCard): boolean {
  return card.giorni_alla_scadenza !== null && card.giorni_alla_scadenza < 0
}

export function hasEligibleClient(card: DashboardBandoCard): boolean {
  return card.matches.some(match =>
    match.ammissibilita?.ammissibile === true
    && match.breakdown.status !== 'da_verificare'
  )
}

export function needsReview(card: DashboardBandoCard): boolean {
  if (hasEligibleClient(card)) return false
  return card.matches.some(match =>
    match.ammissibilita?.errore === true
    || match.ammissibilita?.ammissibile === null
    || match.breakdown.status === 'da_verificare'
  )
}

export function dashboardCategory(card: DashboardBandoCard): DashboardCategory {
  if (isExpiredCard(card)) return 'scaduti'
  if (hasEligibleClient(card)) return 'ammissibili'
  if (needsReview(card)) return 'da_verificare'
  return 'non_ammissibili'
}

export function bestMatch(card: DashboardBandoCard): DashboardMatch | null {
  const eligible = card.matches
    .filter(match => match.ammissibilita?.ammissibile === true && match.breakdown.status !== 'da_verificare')
    .sort((a, b) => b.score - a.score)
  if (eligible.length > 0) return eligible[0]
  return [...card.matches].sort((a, b) => b.score - a.score)[0] ?? null
}
