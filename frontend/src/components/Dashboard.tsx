import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from '../toast'
import { apiHref, withApiKey } from '../apiKey'
import { useApiMutation, useDashboard } from '../lib/queries'
import {
  type DashboardBandoCard,
  type DashboardCategory,
  type DashboardData,
  bestMatch,
  dashboardCategory,
} from '../lib/dashboard-shared'

type DashboardFilter = 'tutti' | DashboardCategory
type DashboardSort = 'score' | 'scadenza' | 'titolo'

const PAGE_SIZE = 10
const EMPTY_CARDS: DashboardBandoCard[] = []

function IconRefresh() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
}

function IconDownload() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
}

function IconDedup() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><path d="M9 6h8a2 2 0 0 1 2 2v1M15 18H7a2 2 0 0 1-2-2v-1"/><line x1="3" y1="21" x2="9" y2="15"/><line x1="15" y1="9" x2="21" y2="3"/></svg>
}

function IconSearch() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
}

function IconChevron() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
}

function categoryLabel(category: DashboardCategory): string {
  if (category === 'ammissibili') return 'Ammissibile'
  if (category === 'da_verificare') return 'Da verificare'
  if (category === 'non_ammissibili') return 'Senza clienti ammissibili'
  return 'Scaduto'
}

function formatContributo(card: DashboardBandoCard): string {
  return card.contributo_max && card.contributo_max !== 'N/D' ? card.contributo_max : 'Non rilevato'
}

function DashboardBandoRow({ card, onOpen }: { card: DashboardBandoCard; onOpen: () => void }) {
  const category = dashboardCategory(card)
  const match = bestMatch(card)
  const showScore = category === 'ammissibili' && match

  return (
    <button className="dashboard-bando-row" type="button" onClick={onOpen}>
      <span className={`dashboard-bando-status-rail dashboard-bando-status-rail--${category}`} aria-hidden="true" />
      <span className="dashboard-bando-identity">
        <strong>{card.titolo || `Bando #${card.id}`}</strong>
        <small>{card.ente || 'Ente non rilevato'}</small>
      </span>
      <span className="dashboard-bando-data dashboard-bando-data--scadenza">
        <small>Scadenza</small>
        <strong>{card.scadenza && card.scadenza !== 'N/D' ? card.scadenza : 'Non rilevata'}</strong>
        {card.giorni_alla_scadenza !== null && card.giorni_alla_scadenza >= 0 && <em>{card.giorni_alla_scadenza} giorni</em>}
      </span>
      <span className="dashboard-bando-data dashboard-bando-data--contributo">
        <small>Contributo massimo</small>
        <strong>{formatContributo(card)}</strong>
      </span>
      <span className="dashboard-bando-match">
        {showScore ? (
          <>
            <span><small>Miglior cliente</small><strong>{match.nome}</strong></span>
            <b className="dashboard-score-pill">{match.score}%</b>
          </>
        ) : (
          <span className={`dashboard-status-badge dashboard-status-badge--${category}`}>{categoryLabel(category)}</span>
        )}
      </span>
      <span className="dashboard-bando-chevron"><IconChevron /></span>
    </button>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { data, isLoading: loading, error: queryError } = useDashboard<DashboardData>()
  const [filter, setFilter] = useState<DashboardFilter>('tutti')
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<DashboardSort>('score')
  const [page, setPage] = useState(1)

  const recalcMutation = useApiMutation(() => fetch('/api/bandi/recalc', withApiKey({ method: 'POST' })))
  const deduplicaMutation = useApiMutation(async () => {
    const response = await fetch('/api/bandi/deduplica', withApiKey({ method: 'POST' }))
    return response.json()
  })

  const cards = data?.cards ?? EMPTY_CARDS
  const duplicatesCount = data?.duplicates_count ?? 0

  const counts = useMemo(() => {
    const result: Record<DashboardCategory, number> = {
      ammissibili: 0,
      da_verificare: 0,
      non_ammissibili: 0,
      scaduti: 0,
    }
    cards.forEach(card => { result[dashboardCategory(card)] += 1 })
    return result
  }, [cards])

  const filteredCards = useMemo(() => {
    const normalizedSearch = search.trim().toLocaleLowerCase('it')
    const result = cards.filter(card => {
      if (filter !== 'tutti' && dashboardCategory(card) !== filter) return false
      if (!normalizedSearch) return true
      return `${card.titolo} ${card.ente || ''}`.toLocaleLowerCase('it').includes(normalizedSearch)
    })

    return [...result].sort((a, b) => {
      if (sort === 'titolo') return a.titolo.localeCompare(b.titolo, 'it')
      if (sort === 'scadenza') {
        const aDays = a.giorni_alla_scadenza ?? Number.MAX_SAFE_INTEGER
        const bDays = b.giorni_alla_scadenza ?? Number.MAX_SAFE_INTEGER
        return aDays - bDays
      }
      return (bestMatch(b)?.score ?? 0) - (bestMatch(a)?.score ?? 0)
    })
  }, [cards, filter, search, sort])

  const totalPages = Math.max(1, Math.ceil(filteredCards.length / PAGE_SIZE))
  const visibleCards = filteredCards.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  useEffect(() => { setPage(1) }, [filter, search, sort])
  useEffect(() => { if (page > totalPages) setPage(totalPages) }, [page, totalPages])

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
      const result = await deduplicaMutation.mutateAsync()
      if (result.eliminati > 0) toast.success(`${result.eliminati} duplicati eliminati.`)
      else toast.info('Nessun duplicato trovato.')
    } catch {
      toast.error('Deduplica non riuscita. Riprova.')
    }
  }

  if (loading) return <div className="loading-center"><div className="spinner" /> Caricamento dashboard…</div>

  if (queryError) {
    return <div><div className="page-header"><h1 className="page-title">Dashboard</h1></div><div className="alert alert-danger">Impossibile caricare la dashboard.</div></div>
  }

  const filters: Array<{ key: DashboardFilter; label: string; count: number }> = [
    { key: 'tutti', label: 'Tutti', count: cards.length },
    { key: 'ammissibili', label: 'Ammissibili', count: counts.ammissibili },
    { key: 'da_verificare', label: 'Da verificare', count: counts.da_verificare },
    { key: 'non_ammissibili', label: 'Senza clienti ammissibili', count: counts.non_ammissibili },
    { key: 'scaduti', label: 'Scaduti', count: counts.scaduti },
  ]

  return (
    <div>
      <div className="topbar dashboard-topbar">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Panoramica bandi e compatibilità clienti</p>
        </div>
        <div className="topbar-actions">
          {data?.has_export_data && <a href={apiHref('/api/export/matching.csv')} download className="btn"><IconDownload /> Esporta CSV</a>}
          <button className="btn" onClick={handleDeduplica} disabled={deduplicaMutation.isPending}>
            {deduplicaMutation.isPending ? <div className="spinner spinner--small" /> : <IconDedup />}
            Deduplica{duplicatesCount > 0 && <span className="dashboard-action-count">{duplicatesCount}</span>}
          </button>
          <button className="btn btn-primary" onClick={handleRecalc} disabled={recalcMutation.isPending}>
            {recalcMutation.isPending ? <div className="spinner spinner--small" /> : <IconRefresh />} Ricalcola match
          </button>
        </div>
      </div>

      <div className="dashboard-filter-tabs" role="tablist" aria-label="Filtra i bandi per stato">
        {filters.map(item => (
          <button key={item.key} type="button" role="tab" aria-selected={filter === item.key}
            className={`dashboard-filter-tab dashboard-filter-tab--${item.key}${filter === item.key ? ' active' : ''}`}
            onClick={() => setFilter(item.key)}>
            {item.label}<span>{item.count}</span>
          </button>
        ))}
      </div>

      <div className="dashboard-list-toolbar">
        <label className="dashboard-search">
          <IconSearch />
          <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Cerca per titolo o ente…" aria-label="Cerca bando" />
        </label>
        <label className="dashboard-sort">
          <span>Ordina per</span>
          <select value={sort} onChange={event => setSort(event.target.value as DashboardSort)}>
            <option value="score">Miglior score</option>
            <option value="scadenza">Scadenza</option>
            <option value="titolo">Titolo</option>
          </select>
        </label>
      </div>

      <div className="dashboard-list-summary">
        <strong>{filteredCards.length}</strong> {filteredCards.length === 1 ? 'bando' : 'bandi'}
      </div>

      {visibleCards.length > 0 ? (
        <div className="dashboard-bando-list">
          {visibleCards.map(card => <DashboardBandoRow key={card.id} card={card} onOpen={() => navigate(`/dashboard/bandi/${card.id}`)} />)}
        </div>
      ) : (
        <div className="dashboard-empty-filter"><strong>Nessun bando trovato</strong><span>Modifica il filtro o il testo di ricerca.</span></div>
      )}

      {filteredCards.length > PAGE_SIZE && (
        <div className="dashboard-pagination">
          <span>{(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, filteredCards.length)} di {filteredCards.length}</span>
          <div>
            <button className="btn btn-sm" disabled={page === 1} onClick={() => setPage(value => value - 1)}>Precedente</button>
            <span>Pagina {page} di {totalPages}</span>
            <button className="btn btn-sm" disabled={page === totalPages} onClick={() => setPage(value => value + 1)}>Successiva</button>
          </div>
        </div>
      )}
    </div>
  )
}
