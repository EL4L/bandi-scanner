import { useEffect, useState } from 'react'
import { toast } from '../toast'
import { apiHref, withApiKey } from '../apiKey'
import { useDashboard, useApiMutation } from '../lib/queries'
import { ModalScheda, type SchedaModalData } from './ModalScheda'

interface Breakdown {
  total: number
  ateco: number
  regione: number
  dimensione: number
  fatturato: number
  status?: 'ok' | 'da_verificare'
}

interface Ammissibilita {
  // #2 (audit Fable): null = verifica non riuscita (errore lato server) — non
  // trattare come "ammissibile per default", controllare sempre `errore`.
  ammissibile: boolean | null
  motivi_esclusione: string[]
  criteri_verificati: string[]
  errore?: boolean
}

interface Match {
  nome: string
  score: number
  score_badge_class: string
  breakdown: Breakdown
  settore_da_verificare: boolean
  spiegazione_score: string | null
  ammissibilita?: Ammissibilita
}

interface BandoCard {
  id: number
  titolo: string
  ente: string | null
  contributo_max: string
  scadenza: string
  giorni_alla_scadenza: number | null
  urgenza: string | null
  max_score: number
  raw_max_score?: number
  nessun_cliente_ammissibile?: boolean
  color_class: string
  has_constraints: boolean
  matches: Match[]
  scheda: string
  fonte_url: string | null
  has_pdf: boolean
}

interface DashboardData {
  n_bandi: number
  totale_abbinamenti: number
  has_export_data: boolean
  cards: BandoCard[]
  duplicates_count: number
}


const BLANK_VALUES = new Set(['n/d', 'null', 'none', 'undefined', ''])
function isBlank(v: string | null | undefined): boolean {
  if (v == null) return true
  return BLANK_VALUES.has(v.trim().toLowerCase())
}

function scoreClass(colorClass: string): string {
  if (colorClass === 'circle-green') return 'score-green'
  if (colorClass === 'circle-yellow') return 'score-yellow'
  return 'score-red'
}

function circleColorClass(score: number): string {
  if (score > 70) return 'circle-green'
  if (score >= 40) return 'circle-yellow'
  return 'circle-red'
}

function matchBadgeClass(cls: string): string {
  if (cls === 'match-score-high') return 'match-badge match-badge-high'
  if (cls === 'match-score-mid') return 'match-badge match-badge-mid'
  return 'match-badge match-badge-low'
}

function IconRefresh() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 4 23 10 17 10" />
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </svg>
  )
}

function IconDownload() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  )
}

function IconExternal() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  )
}

function IconDedup() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="6" cy="6" r="3" /><circle cx="18" cy="18" r="3" />
      <path d="M9 6h8a2 2 0 0 1 2 2v1M15 18H7a2 2 0 0 1-2-2v-1" />
      <line x1="3" y1="21" x2="9" y2="15" /><line x1="15" y1="9" x2="21" y2="3" />
    </svg>
  )
}


function isExpiredCard(card: BandoCard): boolean {
  return card.giorni_alla_scadenza !== null && card.giorni_alla_scadenza < 0
}

function hasOnlyIneligibleClients(card: BandoCard): boolean {
  return card.nessun_cliente_ammissibile === true || (
    card.matches.length > 0
    && card.matches.every(m => m.ammissibilita?.ammissibile === false)
  )
}

function isAllDaVerificare(card: BandoCard): boolean {
  return card.matches.length > 0 && card.matches.every(m =>
    m.ammissibilita?.ammissibile !== false
    && m.ammissibilita?.errore !== true
    && m.breakdown.status === 'da_verificare'
  )
}

function sortCardsVerifiedFirst(cards: BandoCard[]): BandoCard[] {
  return [...cards].sort((a, b) => {
    const aUnverified = isAllDaVerificare(a)
    const bUnverified = isAllDaVerificare(b)
    if (aUnverified === bUnverified) return 0
    return aUnverified ? 1 : -1
  })
}

function stripColorByGiorni(giorni: number | null): string {
  if (giorni === null) return 'var(--color-border-strong, #D1D5DB)'
  if (giorni < 0) return 'var(--color-text-muted, #6b7280)'
  if (giorni < 30) return 'var(--color-danger, #ef4444)'
  if (giorni < 90) return 'var(--color-warning, #f59e0b)'
  return 'var(--color-success, #10b981)'
}

function scadenzaTextClass(giorni: number | null): string {
  if (giorni === null) return ''
  if (giorni < 0) return 'text-muted'
  if (giorni < 30) return 'scadenza-giorni-red'
  if (giorni < 90) return 'scadenza-giorni-orange'
  return 'scadenza-giorni-green'
}

type SchedaModal = SchedaModalData

function IconChevron({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`bando-card-chevron${open ? ' bando-card-chevron--open' : ''}`}
      aria-hidden="true"
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  )
}

function BandoCardItem({
  card,
  onScheda,
}: {
  card: BandoCard
  onScheda: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const validMatches = card.matches.filter(m =>
    m.ammissibilita?.ammissibile === true && m.breakdown.status !== 'da_verificare')
  const allDaVerificare = isAllDaVerificare(card)
  const effectiveMaxScore = validMatches.length > 0
    ? Math.max(...validMatches.map(m => m.score))
    : 0
  const nessunClienteAmmissibile = hasOnlyIneligibleClients(card)
  const hasExpandableContent = card.matches.length > 0

  return (
    <div className={`bando-card${expanded ? ' bando-card--expanded' : ' bando-card--compact'}`}>
      <div
        className="deadline-strip"
        style={{ backgroundColor: stripColorByGiorni(card.giorni_alla_scadenza) }}
      />
      <div className="bando-card-inner">
        <button
          type="button"
          className="bando-card-header"
          onClick={() => hasExpandableContent && setExpanded(v => !v)}
          disabled={!hasExpandableContent}
          aria-expanded={hasExpandableContent ? expanded : undefined}
        >
          <p className="bando-card-title">{card.titolo || `Bando #${card.id}`}</p>
          <div className="bando-card-header-right">
            {nessunClienteAmmissibile || allDaVerificare ? null : (
              <div
                className={`score-circle score-circle--compact ${scoreClass(circleColorClass(effectiveMaxScore))}`}
                style={{ '--score': effectiveMaxScore } as React.CSSProperties}
              >
                <span>{effectiveMaxScore > 0 ? `${effectiveMaxScore}%` : '—'}</span>
              </div>
            )}
            {hasExpandableContent && <IconChevron open={expanded} />}
          </div>
        </button>

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

        {expanded && (
          <div className="bando-card-details">
            {card.matches.length > 0 ? (
              <div className="match-list match-list--static">
                <p className="match-list-label">
                  {card.matches.length} {card.matches.length === 1 ? 'cliente analizzato' : 'clienti analizzati'}
                </p>
                {card.matches.map((m, i) => {
                  const escluso = m.ammissibilita?.ammissibile === false
                  const erroreVerifica = m.ammissibilita?.errore === true
                  const daVerificare = !escluso && !erroreVerifica && m.breakdown.status === 'da_verificare'
                  return (
                    <div key={i} className={`match-row${escluso ? ' match-excluded' : ''}`}>
                      <span className="match-row-name">{m.nome}</span>
                      <div className="match-row-right">
                        {escluso ? (
                          <span
                            className="badge badge-escluso"
                            title={m.ammissibilita?.motivi_esclusione?.join(' · ') || 'Requisito vincolante non rispettato'}
                          >⛔ Non ammissibile</span>
                        ) : erroreVerifica ? (
                          <span className="badge badge-warning" title="Il controllo di ammissibilità non è riuscito per un errore tecnico: verifica manualmente i requisiti">
                            Verifica non riuscita
                          </span>
                        ) : daVerificare ? (
                          <span className="badge badge-warning" title="Il bando non contiene dati sufficienti per valutare la compatibilità">
                            ⚠️ Da verificare
                          </span>
                        ) : (
                          <span className={matchBadgeClass(m.score_badge_class)}>
                            {m.score}%
                          </span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <p className="text-muted text-sm">Nessun cliente compatibile in anagrafica.</p>
            )}

            <div className="bando-card-footer">
              <div className="bando-card-footer-actions">
                <button className="btn btn-sm btn-primary" onClick={onScheda}>
                  Scheda
                </button>
                <a
                  href={apiHref(`/api/bandi/${card.id}/scheda.md`)}
                  download
                  className="btn btn-sm"
                  title="Scarica scheda .md"
                  aria-label={`Scarica scheda di ${card.titolo || `Bando #${card.id}`}`}
                >
                  <IconDownload />
                </a>
                {card.has_pdf ? (
                  <a href={apiHref(`/api/bandi/${card.id}/pdf`)} download className="btn btn-sm">
                    <IconDownload /> PDF
                  </a>
                ) : (
                  <button className="btn btn-sm" disabled title="PDF originale non disponibile: ricarica il documento">PDF</button>
                )}
              </div>
              {card.fonte_url && (
                <a
                  href={card.fonte_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-sm btn-ghost"
                  title="Apri fonte"
                  aria-label={`Apri fonte ufficiale di ${card.titolo || `Bando #${card.id}`}`}
                >
                  <IconExternal />
                </a>
              )}
            </div>
          </div>
        )}

        {!hasExpandableContent && (
          <div className="bando-card-details bando-card-details--always">
            <p className="text-muted text-sm">Nessun cliente compatibile in anagrafica.</p>
            <div className="bando-card-footer">
              <div className="bando-card-footer-actions">
                <button className="btn btn-sm btn-primary" onClick={onScheda}>
                  Scheda
                </button>
                <a
                  href={apiHref(`/api/bandi/${card.id}/scheda.md`)}
                  download
                  className="btn btn-sm"
                  title="Scarica scheda .md"
                  aria-label={`Scarica scheda di ${card.titolo || `Bando #${card.id}`}`}
                >
                  <IconDownload />
                </a>
                {card.has_pdf ? (
                  <a href={apiHref(`/api/bandi/${card.id}/pdf`)} download className="btn btn-sm">
                    <IconDownload /> PDF
                  </a>
                ) : (
                  <button className="btn btn-sm" disabled title="PDF originale non disponibile: ricarica il documento">PDF</button>
                )}
              </div>
              {card.fonte_url && (
                <a
                  href={card.fonte_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-sm btn-ghost"
                  title="Apri fonte"
                  aria-label={`Apri fonte ufficiale di ${card.titolo || `Bando #${card.id}`}`}
                >
                  <IconExternal />
                </a>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { data, isLoading: loading, error: queryError } = useDashboard<DashboardData>()
  const error = queryError ? 'Impossibile caricare la dashboard. Verifica che il server sia in esecuzione.' : null
  const [openScheda, setOpenScheda] = useState<SchedaModal | null>(null)
  const [showExpiredSection, setShowExpiredSection] = useState(false)
  const [showIneligibleSection, setShowIneligibleSection] = useState(false)
  const [showReviewSection, setShowReviewSection] = useState(false)

  const recalcMutation = useApiMutation(() => fetch('/api/bandi/recalc', withApiKey({ method: 'POST' })))
  const deduplicaMutation = useApiMutation(async () => {
    const res = await fetch('/api/bandi/deduplica', withApiKey({ method: 'POST' }))
    return res.json()
  })

  // Dedup e merge dei match per bandi duplicati (titolo+ente) già eseguiti lato server
  const uniqueCards = data?.cards ?? []
  const duplicatesCount = data?.duplicates_count ?? 0

  useEffect(() => {
    if (!openScheda) return
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpenScheda(null) }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [openScheda])

  const handleRecalc = async () => {
    try {
      await recalcMutation.mutateAsync()
      toast.success('Match ricalcolati.')
    } catch {
      toast.error('Ricalcolo non riuscito. Riprova.')
    }
  }

  const handleDeduplica = async () => {
    try {
      const d = await deduplicaMutation.mutateAsync()
      if (d.eliminati > 0) {
        toast.success(`${d.eliminati} duplicat${d.eliminati === 1 ? 'o eliminato' : 'i eliminati'}.`)
      } else {
        toast.info('Nessun duplicato trovato.')
      }
    } catch {
      toast.error('Deduplica non riuscita. Riprova.')
    }
  }

  if (loading) {
    return (
      <div className="loading-center">
        <div className="spinner" />
        Caricamento dashboard…
      </div>
    )
  }

  if (error) {
    return (
      <div>
        <div className="page-header">
          <h1 className="page-title">Dashboard</h1>
        </div>
        <div className="alert alert-danger">{error}</div>
      </div>
    )
  }

  const d = data!

  return (
    <div>
      <div className="topbar">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Panoramica bandi e compatibilità clienti</p>
        </div>
        <div className="topbar-actions">
          {d.has_export_data && (
            <a href={apiHref('/api/export/matching.csv')} download className="btn">
              <IconDownload /> Esporta CSV
            </a>
          )}
          <button
            className="btn"
            onClick={handleDeduplica}
            disabled={deduplicaMutation.isPending}
            title="Rimuove dal DB i bandi con stesso titolo e ente, mantenendo il più recente"
          >
            {deduplicaMutation.isPending
              ? <div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
              : <IconDedup />}
            Deduplica
            {duplicatesCount > 0 && (
              <span style={{
                background: 'var(--color-warning)', color: '#fff',
                borderRadius: 10, fontSize: 'var(--text-xs)', fontWeight: 700,
                padding: '1px 6px', marginLeft: 'var(--space-1)',
              }}>{duplicatesCount}</span>
            )}
          </button>
          <button className="btn btn-primary" onClick={handleRecalc} disabled={recalcMutation.isPending}>
            {recalcMutation.isPending ? <div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> : <IconRefresh />}
            Ricalcola match
          </button>
        </div>
      </div>

      <div className="kpi-row">
        <div className="kpi-card">
          <p className="kpi-label">Bandi in archivio</p>
          <p className="kpi-value">{d.n_bandi}</p>
          {duplicatesCount > 0 && (
            <p className="kpi-delta" style={{ color: 'var(--color-warning)' }}>
              {duplicatesCount} duplicat{duplicatesCount === 1 ? 'o' : 'i'} nascost{duplicatesCount === 1 ? 'o' : 'i'}
            </p>
          )}
        </div>
        <div className="kpi-card">
          <p className="kpi-label">Abbinamenti trovati</p>
          <p className="kpi-value">{d.totale_abbinamenti}</p>
        </div>
        <div className="kpi-card">
          <p className="kpi-label">Bandi con clienti ammissibili</p>
          <p className="kpi-value">{uniqueCards.filter(c =>
            c.matches.some(m => m.ammissibilita?.ammissibile === true)).length}</p>
        </div>
      </div>

      {uniqueCards.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          </div>
          <h3>Nessun bando caricato</h3>
          <p>Carica un bando PDF dalla sezione "Carica Bando" per iniziare l'analisi.</p>
        </div>
      ) : (() => {
        const activeCards = sortCardsVerifiedFirst(uniqueCards.filter(c =>
          !isExpiredCard(c) && !hasOnlyIneligibleClients(c) && !isAllDaVerificare(c)))
        const ineligibleCards = sortCardsVerifiedFirst(uniqueCards.filter(hasOnlyIneligibleClients))
        const reviewCards = sortCardsVerifiedFirst(uniqueCards.filter(c =>
          !hasOnlyIneligibleClients(c) && isAllDaVerificare(c)))
        const expiredCards = sortCardsVerifiedFirst(uniqueCards.filter(c =>
          isExpiredCard(c) && !hasOnlyIneligibleClients(c) && !isAllDaVerificare(c)))
        return (
          <>
            {activeCards.length > 0 && (
              <div className="bando-grid">
                {activeCards.map(card => (
                  <BandoCardItem
                    key={card.id}
                    card={card}
                    onScheda={() => setOpenScheda({ id: card.id, titolo: card.titolo, scheda: card.scheda, fonte_url: card.fonte_url, has_pdf: card.has_pdf })}
                  />
                ))}
              </div>
            )}

            {ineligibleCards.length > 0 && (
              <div className="section-scaduti section-non-ammissibili">
                <button
                  className={`section-scaduti-header${showIneligibleSection ? ' open' : ''}`}
                  onClick={() => setShowIneligibleSection(v => !v)}
                >
                  <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
                    Bandi senza clienti ammissibili
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <span className="scaduti-count">{ineligibleCards.length}</span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14, transition: 'transform 200ms' }}>
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </div>
                </button>
                {showIneligibleSection && (
                  <div className="section-scaduti-body">
                    <div className="bando-grid">
                      {ineligibleCards.map(card => (
                        <BandoCardItem
                          key={card.id}
                          card={card}
                          onScheda={() => setOpenScheda({ id: card.id, titolo: card.titolo, scheda: card.scheda, fonte_url: card.fonte_url, has_pdf: card.has_pdf })}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {reviewCards.length > 0 && (
              <div className="section-scaduti section-da-verificare">
                <button
                  className={`section-scaduti-header${showReviewSection ? ' open' : ''}`}
                  onClick={() => setShowReviewSection(v => !v)}
                >
                  <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
                    Bandi da verificare
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <span className="scaduti-count">{reviewCards.length}</span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14, transition: 'transform 200ms' }}>
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </div>
                </button>
                {showReviewSection && (
                  <div className="section-scaduti-body">
                    <div className="bando-grid">
                      {reviewCards.map(card => (
                        <BandoCardItem
                          key={card.id}
                          card={card}
                          onScheda={() => setOpenScheda({ id: card.id, titolo: card.titolo, scheda: card.scheda, fonte_url: card.fonte_url, has_pdf: card.has_pdf })}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {expiredCards.length > 0 && (
              <div className="section-scaduti">
                <button
                  className={`section-scaduti-header${showExpiredSection ? ' open' : ''}`}
                  onClick={() => setShowExpiredSection(v => !v)}
                >
                  <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
                    Bandi scaduti
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <span className="scaduti-count">{expiredCards.length}</span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14, transition: 'transform 200ms' }}>
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </div>
                </button>
                {showExpiredSection && (
                  <div className="section-scaduti-body">
                    <div className="bando-grid">
                      {expiredCards.map(card => (
                        <div key={card.id} className="bando-card-expired">
                          <BandoCardItem
                            card={card}
                            onScheda={() => setOpenScheda({ id: card.id, titolo: card.titolo, scheda: card.scheda, fonte_url: card.fonte_url, has_pdf: card.has_pdf })}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )
      })()}

      {openScheda && (
        <ModalScheda data={openScheda} onClose={() => setOpenScheda(null)} />
      )}
    </div>
  )
}
