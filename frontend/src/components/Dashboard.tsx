import { useEffect, useState, useCallback, useMemo } from 'react'
import { toast } from '../toast'
import { apiHref, withApiKey } from '../apiKey'
import { ModalScheda, type SchedaModalData } from './ModalScheda'

interface Breakdown {
  total: number
  ateco: number
  regione: number
  dimensione: number
  fatturato: number
}

interface Ammissibilita {
  ammissibile: boolean
  motivi_esclusione: string[]
  criteri_verificati: string[]
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
  color_class: string
  has_constraints: boolean
  matches: Match[]
  scheda: string
  fonte_url: string | null
}

interface DashboardData {
  n_bandi: number
  totale_abbinamenti: number
  has_export_data: boolean
  cards: BandoCard[]
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

type SchedaModal = SchedaModalData

function BandoCardItem({
  card,
  onScheda,
}: {
  card: BandoCard
  onScheda: () => void
}) {
  return (
    <div className="bando-card">
      <div className="bando-card-inner">
      <div className="bando-card-top">
        <div style={{ flex: 1, minWidth: 0 }}>
          <p className="bando-card-title">{card.titolo || `Bando #${card.id}`}</p>
          {card.ente && <p className="bando-card-ente">{card.ente}</p>}
        </div>
        <div
          className={`score-circle ${scoreClass(card.color_class)}`}
          style={{ '--score': card.max_score } as React.CSSProperties}
        >
          <span>{card.max_score > 0 ? `${card.max_score}%` : '—'}</span>
        </div>
      </div>

      {!isBlank(card.contributo_max) && (
        <div className="bando-card-contributo-row">
          <span className="bando-card-contributo-label">Contributo max</span>
          <span className="bando-card-contributo">{card.contributo_max}</span>
        </div>
      )}

      {card.matches.length > 0 && (
        <div className="match-list match-list--static">
          <p className="match-list-label">
            {card.matches.length} {card.matches.length === 1 ? 'cliente compatibile' : 'clienti compatibili'}
          </p>
          {card.matches.map((m, i) => {
            const escluso = m.ammissibilita?.ammissibile === false
            return (
              <div key={i} className={`match-row${escluso ? ' match-excluded' : ''}`}>
                <span className="match-row-name">{m.nome}</span>
                <div className="match-row-right">
                  {escluso ? (
                    <span className="badge badge-escluso">⛔ Non ammissibile</span>
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
      )}

      {card.matches.length === 0 && (
        <p className="text-muted text-sm" style={{ marginTop: 10 }}>
          Nessun cliente compatibile in anagrafica.
        </p>
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
          >
            <IconDownload />
          </a>
        </div>
        {card.fonte_url && (
          <a
            href={card.fonte_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-sm btn-ghost"
            title="Apri fonte"
          >
            <IconExternal />
          </a>
        )}
      </div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [recalcLoading, setRecalcLoading] = useState(false)
  const [deduplicaLoading, setDeduplicaLoading] = useState(false)
  const [openScheda, setOpenScheda] = useState<SchedaModal | null>(null)
  const [showExpiredSection, setShowExpiredSection] = useState(false)

  // Raggruppa per coppia (titolo, ente), mantiene l'id più alto in caso di duplicati
  const uniqueCards = useMemo(() => {
    const cards = data?.cards ?? []
    const seen = new Map<string, BandoCard>()
    for (const card of cards) {
      const key = `${(card.titolo ?? '').toLowerCase().trim()}|||${(card.ente ?? '').toLowerCase().trim()}`
      const existing = seen.get(key)
      if (!existing || card.id > existing.id) seen.set(key, card)
    }
    return Array.from(seen.values()).sort((a, b) => b.max_score - a.max_score)
  }, [data])

  const duplicatesCount = (data?.cards.length ?? 0) - uniqueCards.length

  const fetchDashboard = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/dashboard', withApiKey())
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setData(await res.json())
    } catch {
      setError('Impossibile caricare la dashboard. Verifica che il server sia in esecuzione.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchDashboard() }, [fetchDashboard])

  useEffect(() => {
    if (!openScheda) return
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpenScheda(null) }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [openScheda])

  const handleRecalc = async () => {
    setRecalcLoading(true)
    try {
      await fetch('/api/bandi/recalc', withApiKey({ method: 'POST' }))
      await fetchDashboard()
      toast.success('Match ricalcolati.')
    } catch {
      toast.error('Ricalcolo non riuscito. Riprova.')
    } finally {
      setRecalcLoading(false)
    }
  }

  const handleDeduplica = async () => {
    setDeduplicaLoading(true)
    try {
      const res = await fetch('/api/bandi/deduplica', withApiKey({ method: 'POST' }))
      const d = await res.json()
      if (d.eliminati > 0) {
        toast.success(`${d.eliminati} duplicat${d.eliminati === 1 ? 'o eliminato' : 'i eliminati'}.`)
        await fetchDashboard()
      } else {
        toast.info('Nessun duplicato trovato.')
      }
    } catch {
      toast.error('Deduplica non riuscita. Riprova.')
    } finally {
      setDeduplicaLoading(false)
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
            disabled={deduplicaLoading}
            title="Rimuove dal DB i bandi con stesso titolo e ente, mantenendo il più recente"
          >
            {deduplicaLoading
              ? <div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
              : <IconDedup />}
            Deduplica
            {duplicatesCount > 0 && (
              <span style={{
                background: 'var(--color-warning)', color: '#fff',
                borderRadius: 10, fontSize: '0.65rem', fontWeight: 700,
                padding: '1px 6px', marginLeft: 2,
              }}>{duplicatesCount}</span>
            )}
          </button>
          <button className="btn btn-primary" onClick={handleRecalc} disabled={recalcLoading}>
            {recalcLoading ? <div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> : <IconRefresh />}
            Ricalcola match
          </button>
        </div>
      </div>

      <div className="kpi-row">
        <div className="kpi-card">
          <p className="kpi-label">Bandi in archivio</p>
          <p className="kpi-value">{d.n_bandi}</p>
        </div>
        <div className="kpi-card">
          <p className="kpi-label">Abbinamenti trovati</p>
          <p className="kpi-value">{d.totale_abbinamenti}</p>
        </div>
        <div className="kpi-card">
          <p className="kpi-label">Bandi con clienti</p>
          <p className="kpi-value">{uniqueCards.filter(c => c.matches.length > 0).length}</p>
          {duplicatesCount > 0 && (
            <p className="kpi-delta" style={{ color: 'var(--color-warning)' }}>
              {duplicatesCount} duplicat{duplicatesCount === 1 ? 'o' : 'i'} nascost{duplicatesCount === 1 ? 'o' : 'i'}
            </p>
          )}
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
        const activeCards = uniqueCards.filter(c => !isExpiredCard(c))
        const expiredCards = uniqueCards.filter(isExpiredCard)
        return (
          <>
            {activeCards.length > 0 && (
              <div className="bando-grid">
                {activeCards.map(card => (
                  <BandoCardItem
                    key={card.id}
                    card={card}
                    onScheda={() => setOpenScheda({ id: card.id, titolo: card.titolo, scheda: card.scheda, fonte_url: card.fonte_url })}
                  />
                ))}
              </div>
            )}

            {expiredCards.length > 0 && (
              <div className="section-scaduti">
                <button
                  className={`section-scaduti-header${showExpiredSection ? ' open' : ''}`}
                  onClick={() => setShowExpiredSection(v => !v)}
                >
                  <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                    Bandi scaduti
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
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
                            onScheda={() => setOpenScheda({ id: card.id, titolo: card.titolo, scheda: card.scheda, fonte_url: card.fonte_url })}
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
