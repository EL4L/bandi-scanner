import { useEffect, useState, useCallback, useMemo } from 'react'
import { toast } from '../toast'
import { apiHref, withApiKey } from '../apiKey'
import { useBandi, useDashboard, useApiMutation } from '../lib/queries'
import { dashboardCategory, type DashboardCategory, type DashboardData } from '../lib/dashboard-shared'
import { ModalScheda, type SchedaModalData } from './ModalScheda'

interface Bando {
  id: number
  titolo: string | null
  ente: string | null
  data_scadenza: string | null
  contributo_max: number | null
  giorni_alla_scadenza: number | null
  regioni: string | null
  has_pdf: boolean
  review_status: 'validato' | 'da_revisionare'
  null_percentage: number
  review_reasons: string[]
}

type QuickFilter = 'tutti' | 'ammissibili' | 'da_revisionare' | 'non_ammissibili' | 'scaduti'
type SortKey = 'titolo' | 'scadenza' | 'contributo'
type SortDir = 'asc' | 'desc'

type SchedaModal = SchedaModalData
const EMPTY_BANDI: Bando[] = []

const MESI_SHORT = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic']

function formatDateIT(d: string | null): string | null {
  if (!d) return null
  const parts = d.split('T')[0].split('-')
  if (parts.length === 3) {
    const day = parseInt(parts[2], 10)
    const month = parseInt(parts[1], 10) - 1
    const year = parseInt(parts[0], 10)
    if (!isNaN(day) && month >= 0 && month < 12 && !isNaN(year))
      return `${day} ${MESI_SHORT[month]} ${year}`
  }
  return null
}

function giorniColorClass(giorni: number): string {
  if (giorni < 30) return 'scadenza-giorni-red'
  if (giorni <= 90) return 'scadenza-giorni-orange'
  return 'scadenza-giorni-green'
}

function formatEuro(val: number | null) {
  if (val === null || val === undefined) return '—'
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(val)
}

// ── Icons ──────────────────────────────────────────────────
function IconSearch() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
}
function IconDownload() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
}
function IconChevronUp() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'inline', width: 12, height: 12, marginLeft: 3 }}><polyline points="18 15 12 9 6 15"/></svg>
}
function IconChevronDown() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'inline', width: 12, height: 12, marginLeft: 3 }}><polyline points="6 9 12 15 18 9"/></svg>
}
function IconTrash() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
}

// ── Table row ──────────────────────────────────────────────
function BandoRow({ b, dimmed, schedaLoading, onScheda, confirmDeleteId, onDeleteRequest, onDeleteConfirm, onDeleteCancel, deleting }: {
  b: Bando
  dimmed: boolean
  schedaLoading: number | null
  onScheda: (b: Bando) => void
  confirmDeleteId: number | null
  onDeleteRequest: (id: number) => void
  onDeleteConfirm: (id: number) => void
  onDeleteCancel: () => void
  deleting: number | null
}) {
  const isConfirming = confirmDeleteId === b.id
  const scadenzaStr = formatDateIT(b.data_scadenza)
  const inRevisione = b.review_status === 'da_revisionare'
  return (
    <tr style={dimmed ? { opacity: 0.52, color: 'var(--color-text-muted)' } : undefined}>
      <td className="bandi-title-cell">
        <div className="bandi-title-stack">
          <button
            className="td-title-link"
            style={dimmed ? { color: 'var(--color-text-muted)' } : undefined}
            onClick={() => onScheda(b)}
            disabled={schedaLoading === b.id}
            title={b.titolo ?? `Bando #${b.id}`}
          >
            {b.titolo ?? `Bando #${b.id}`}
          </button>
        </div>
      </td>
      <td className="td-muted bandi-ente-cell">{b.ente ?? '—'}</td>
      <td className="bandi-scadenza-cell">
        {scadenzaStr && (
          <div>
            <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)' }}>{scadenzaStr}</span>
            {b.giorni_alla_scadenza !== null && (
              <div className={`scadenza-giorni ${giorniColorClass(b.giorni_alla_scadenza)}`}>
                {b.giorni_alla_scadenza < 0 ? 'scaduto' : `${b.giorni_alla_scadenza} gg`}
              </div>
            )}
          </div>
        )}
      </td>
      <td className="bandi-contributo-cell">{b.contributo_max !== null ? <span className="font-medium">{formatEuro(b.contributo_max)}</span> : <span className="td-muted">—</span>}</td>
      <td className="bandi-actions-cell">
        {isConfirming ? (
          <div className="btn-group" style={{ alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>Sei sicuro?</span>
            <button
              className="btn btn-sm btn-danger-solid"
              onClick={() => onDeleteConfirm(b.id)}
              disabled={deleting === b.id}
            >
              {deleting === b.id ? <div className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} /> : 'Sì, elimina'}
            </button>
            <button className="btn btn-sm" onClick={onDeleteCancel}>Annulla</button>
          </div>
        ) : (
          <div className="btn-group bandi-actions-default">
            {inRevisione ? (
              <a className="btn btn-sm btn-primary" href={`/dashboard/bandi/${b.id}`}>Revisiona</a>
            ) : (
              <button
                className="btn btn-sm btn-primary"
                onClick={() => onScheda(b)}
                disabled={schedaLoading === b.id}
              >
                {schedaLoading === b.id
                  ? <div className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} />
                  : 'Scheda'}
              </button>
            )}
            {b.has_pdf ? (
              <a
                href={apiHref(`/api/bandi/${b.id}/pdf`)}
                download
                className="btn btn-sm"
                title="Scarica PDF originale"
                aria-label={`Scarica PDF originale di ${b.titolo ?? `Bando #${b.id}`}`}
              >
                <IconDownload /> PDF
              </a>
            ) : (
              <button className="btn btn-sm" disabled title="PDF originale non disponibile: ricarica il documento">
                PDF
              </button>
            )}
            <button
              className="btn btn-sm"
              style={{ color: 'var(--color-danger)', borderColor: 'var(--color-danger)' }}
              onClick={() => onDeleteRequest(b.id)}
              title="Elimina bando"
              aria-label={`Elimina ${b.titolo ?? `Bando #${b.id}`}`}
            >
              <IconTrash />
            </button>
          </div>
        )}
      </td>
    </tr>
  )
}

// ── Table shell ────────────────────────────────────────────
function BandoTable({ rows, dimmed, emptyMsg, schedaLoading, onScheda, handleSort, SortIcon, confirmDeleteId, onDeleteRequest, onDeleteConfirm, onDeleteCancel, deleting }: {
  rows: Bando[]
  dimmed: boolean
  emptyMsg: string
  schedaLoading: number | null
  onScheda: (b: Bando) => void
  handleSort: (k: SortKey) => void
  SortIcon: React.FC<{ col: SortKey }>
  confirmDeleteId: number | null
  onDeleteRequest: (id: number) => void
  onDeleteConfirm: (id: number) => void
  onDeleteCancel: () => void
  deleting: number | null
}) {
  return (
    <div className="table-wrapper bandi-table-wrapper">
      <table className="data-table bandi-table">
        <colgroup>
          <col className="bandi-col-title" />
          <col className="bandi-col-ente" />
          <col className="bandi-col-scadenza" />
          <col className="bandi-col-contributo" />
          <col className="bandi-col-actions" />
        </colgroup>
        <thead>
          <tr>
            <th className="sortable" onClick={() => handleSort('titolo')}>Titolo <SortIcon col="titolo" /></th>
            <th>Ente</th>
            <th className="sortable" onClick={() => handleSort('scadenza')}>Scadenza <SortIcon col="scadenza" /></th>
            <th className="sortable" onClick={() => handleSort('contributo')}>Contributo max <SortIcon col="contributo" /></th>
            <th className="bandi-actions-heading">Azioni</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0
            ? <tr><td colSpan={5} style={{ textAlign: 'center', padding: '32px', color: 'var(--color-text-muted)' }}>{emptyMsg}</td></tr>
            : rows.map(b => (
              <BandoRow
                key={b.id} b={b} dimmed={dimmed} schedaLoading={schedaLoading} onScheda={onScheda}
                confirmDeleteId={confirmDeleteId} onDeleteRequest={onDeleteRequest}
                onDeleteConfirm={onDeleteConfirm} onDeleteCancel={onDeleteCancel} deleting={deleting}
              />
            ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────
export default function Bandi() {
  const { data, isLoading: loading, error: queryError } = useBandi<{ bandi: Bando[] }>()
  const { data: dashboardData, isLoading: dashboardLoading, error: dashboardError } = useDashboard<DashboardData>()
  const bandi = data?.bandi ?? EMPTY_BANDI
  const error = queryError || dashboardError ? 'Errore nel caricamento dei bandi.' : null
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [quickFilter, setQuickFilter] = useState<QuickFilter>('tutti')
  const [regioneFilter, setRegioneFilter] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('scadenza')
  const [sortDir, setSortDir] = useState<SortDir>('asc')
  const [openScheda, setOpenScheda] = useState<SchedaModal | null>(null)
  const [schedaLoading, setSchedaLoading] = useState<number | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
  const [deleting, setDeleting] = useState<number | null>(null)

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), 300)
    return () => clearTimeout(t)
  }, [query])

  const deleteMutation = useApiMutation((id: number) =>
    fetch(`/api/bandi/${id}`, withApiKey({ method: 'DELETE' })).then(res => {
      if (!res.ok) throw new Error()
    }))

  const handleSort = useCallback((key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('asc') }
  }, [sortKey])

  const handleScheda = async (bando: Bando) => {
    setSchedaLoading(bando.id)
    try {
      const res = await fetch(`/api/bandi/${bando.id}/scheda`, withApiKey())
      const d = await res.json()
      setOpenScheda({
        id: bando.id,
        titolo: bando.titolo ?? `Bando #${bando.id}`,
        scheda: d.scheda ?? '',
        has_pdf: bando.has_pdf,
        review_status: d.review_status ?? bando.review_status,
        null_percentage: d.null_percentage ?? bando.null_percentage,
        review_reasons: d.review_reasons ?? bando.review_reasons,
      })
    } catch {
      toast.error('Impossibile caricare la scheda del bando.')
    } finally {
      setSchedaLoading(null)
    }
  }

  const categoryByBandoId = useMemo(() => {
    const categories = new Map<number, DashboardCategory>()
    for (const card of dashboardData?.cards ?? []) categories.set(card.id, dashboardCategory(card))
    return categories
  }, [dashboardData])

  const filterCounts = useMemo(() => ({
    ammissibili: bandi.filter(b => categoryByBandoId.get(b.id) === 'ammissibili').length,
    da_revisionare: bandi.filter(b => b.review_status === 'da_revisionare').length,
    non_ammissibili: bandi.filter(b => categoryByBandoId.get(b.id) === 'non_ammissibili').length,
    scaduti: bandi.filter(b => categoryByBandoId.get(b.id) === 'scaduti').length,
  }), [bandi, categoryByBandoId])

  const regioni = useMemo(() => {
    const set = new Set<string>()
    for (const b of bandi) {
      try {
        const arr = JSON.parse(b.regioni ?? '[]')
        if (Array.isArray(arr)) arr.forEach((r: string) => { if (r) set.add(r) })
      } catch { /* skip malformed */ }
    }
    return Array.from(set).sort()
  }, [bandi])

  const filteredBandi = useMemo(() => {
    const filterRegione = (b: Bando): boolean => {
      if (!regioneFilter) return true
      try {
        const arr: string[] = JSON.parse(b.regioni ?? '[]')
        if (!arr.length) return true
        const lower = arr.map((r: string) => r.toLowerCase())
        if (lower.some(r => r === 'tutta italia' || r === 'tutte')) return true
        return lower.includes(regioneFilter.toLowerCase())
      } catch { return true }
    }
    const searchFn = (b: Bando) => {
      if (debouncedQuery) {
        const q = debouncedQuery.toLowerCase()
        if (!(b.titolo ?? '').toLowerCase().includes(q) && !(b.ente ?? '').toLowerCase().includes(q)) return false
      }
      return filterRegione(b)
    }
    const sortFn = (a: Bando, b: Bando) => {
      let cmp = 0
      if (sortKey === 'titolo') {
        cmp = (a.titolo ?? '').localeCompare(b.titolo ?? '', 'it')
      } else if (sortKey === 'scadenza') {
        const aVal = a.giorni_alla_scadenza
        const bVal = b.giorni_alla_scadenza
        if (aVal === null && bVal === null) cmp = 0
        else if (aVal === null) cmp = 1
        else if (bVal === null) cmp = -1
        else cmp = aVal - bVal
      } else if (sortKey === 'contributo') {
        cmp = (b.contributo_max ?? 0) - (a.contributo_max ?? 0)
      }
      return sortDir === 'asc' ? cmp : -cmp
    }
    const matchesQuickFilter = (b: Bando): boolean => {
      if (quickFilter === 'tutti') return true
      if (quickFilter === 'da_revisionare') return b.review_status === 'da_revisionare'
      return categoryByBandoId.get(b.id) === quickFilter
    }

    return bandi.filter(searchFn).filter(matchesQuickFilter).sort(sortFn)
  }, [bandi, categoryByBandoId, debouncedQuery, quickFilter, regioneFilter, sortKey, sortDir])

  const handleDeleteRequest = useCallback((id: number) => setConfirmDeleteId(id), [])
  const handleDeleteCancel = useCallback(() => setConfirmDeleteId(null), [])
  const handleDeleteConfirm = useCallback(async (id: number) => {
    setDeleting(id)
    try {
      await deleteMutation.mutateAsync(id)
      setConfirmDeleteId(null)
      toast.success('Bando eliminato.')
    } catch {
      toast.error('Errore durante l\'eliminazione del bando.')
    } finally {
      setDeleting(null)
    }
  }, [deleteMutation])

  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sortKey !== col) return null
    return sortDir === 'asc' ? <IconChevronUp /> : <IconChevronDown />
  }

  const tableProps = {
    schedaLoading, onScheda: handleScheda, handleSort, SortIcon,
    confirmDeleteId, onDeleteRequest: handleDeleteRequest,
    onDeleteConfirm: handleDeleteConfirm, onDeleteCancel: handleDeleteCancel, deleting,
  }

  const emptyFilterLabel: Record<QuickFilter, string> = {
    tutti: 'Nessun bando',
    ammissibili: 'Nessun bando ammissibile',
    da_revisionare: 'Nessun bando da revisionare',
    non_ammissibili: 'Nessun bando non ammissibile',
    scaduti: 'Nessun bando scaduto',
  }

  if (loading || dashboardLoading) {
    return <div className="loading-center"><div className="spinner" /> Caricamento bandi…</div>
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <h1 className="page-title">Bandi</h1>
          <p className="page-subtitle">{bandi.length} bandi in archivio</p>
        </div>
        <div className="topbar-actions">
          <div className="search-bar">
            <IconSearch />
            <input
              type="text"
              placeholder="Cerca per titolo o ente…"
              aria-label="Cerca bandi per titolo o ente"
              value={query}
              onChange={e => setQuery(e.target.value)}
            />
          </div>
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      {bandi.length === 0 && !error ? (
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
          </div>
          <h3>Nessun bando caricato</h3>
          <p>Vai su "Carica Bando" per estrarre i dati da un PDF.</p>
        </div>
      ) : (
        <>
          <div className="filter-bar" style={{ marginBottom: 'var(--space-4)' }}>
            <div className="quick-filter">
              <button
                className={`quick-filter-btn${quickFilter === 'tutti' ? ' active' : ''}`}
                onClick={() => setQuickFilter('tutti')}
              >
                <span>Tutti</span>
                <span className="quick-filter-count">{bandi.length}</span>
              </button>
              <button
                className={`quick-filter-btn${quickFilter === 'ammissibili' ? ' active' : ''}`}
                onClick={() => setQuickFilter('ammissibili')}
              >
                <span>Ammissibili</span>
                <span className="quick-filter-count">{filterCounts.ammissibili}</span>
              </button>
              <button
                className={`quick-filter-btn${quickFilter === 'da_revisionare' ? ' active' : ''}`}
                onClick={() => setQuickFilter('da_revisionare')}
              >
                <span>Da revisionare</span>
                <span className="quick-filter-count">{filterCounts.da_revisionare}</span>
              </button>
              <button
                className={`quick-filter-btn${quickFilter === 'non_ammissibili' ? ' active' : ''}`}
                onClick={() => setQuickFilter('non_ammissibili')}
              >
                <span>Non ammissibili</span>
                <span className="quick-filter-count">{filterCounts.non_ammissibili}</span>
              </button>
              <button
                className={`quick-filter-btn${quickFilter === 'scaduti' ? ' active' : ''}`}
                onClick={() => setQuickFilter('scaduti')}
              >
                <span>Scaduti</span>
                <span className="quick-filter-count">{filterCounts.scaduti}</span>
              </button>
            </div>
            {regioni.length > 0 && (
              <select
                value={regioneFilter}
                onChange={e => setRegioneFilter(e.target.value)}
                className="filter-select"
              >
                <option value="">Tutte le regioni</option>
                {regioni.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            )}
          </div>

          <BandoTable
            rows={filteredBandi}
            dimmed={quickFilter === 'scaduti'}
            emptyMsg={query ? `${emptyFilterLabel[quickFilter]} per "${query}"` : emptyFilterLabel[quickFilter]}
            {...tableProps}
          />
        </>
      )}

      {openScheda && (
        <ModalScheda data={openScheda} onClose={() => setOpenScheda(null)} />
      )}
    </div>
  )
}
