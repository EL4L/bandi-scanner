import { useEffect, useState, useCallback, useMemo } from 'react'

interface Bando {
  id: number
  titolo: string | null
  ente: string | null
  data_scadenza: string | null
  contributo_max: number | null
  urgenza: string | null
  giorni_alla_scadenza: number | null
}

type QuickFilter = 'tutti' | 'attivi' | 'scaduti'
type SortKey = 'urgenza' | 'scadenza' | 'titolo' | 'contributo'
type SortDir = 'asc' | 'desc'

interface SchedaModal { id: number; titolo: string; scheda: string }

function isExpired(b: Bando): boolean {
  return b.giorni_alla_scadenza !== null && b.giorni_alla_scadenza < 0
}

function urgencyLabel(u: string) {
  if (u === 'alta') return 'Urgente'
  if (u === 'media') return 'In scadenza'
  if (u === 'bassa') return 'Regolare'
  return u
}
function urgencyClass(u: string) {
  if (u === 'alta') return 'badge-alta'
  if (u === 'media') return 'badge-media'
  if (u === 'bassa') return 'badge-bassa'
  return 'badge-neutral'
}
function urgencyOrder(u: string | null) {
  if (u === 'alta') return 0
  if (u === 'media') return 1
  if (u === 'bassa') return 2
  return 3
}

function formatDate(d: string | null) {
  if (!d) return '—'
  const parts = d.split('T')[0].split('-')
  if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`
  return d
}

function formatEuro(val: number | null) {
  if (val === null || val === undefined) return '—'
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(val)
}

function renderMarkdown(text: string) {
  const lines = text.split('\n')
  const elements: React.ReactNode[] = []
  let listItems: string[] = []
  let listKey = 0
  const inlineParse = (s: string): React.ReactNode => {
    const parts = s.split(/(\*\*[^*]+\*\*)/)
    return parts.map((p, i) =>
      p.startsWith('**') && p.endsWith('**') ? <strong key={i}>{p.slice(2, -2)}</strong> : p
    )
  }
  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(<ul key={`ul-${listKey++}`}>{listItems.map((item, i) => <li key={i}>{inlineParse(item)}</li>)}</ul>)
      listItems = []
    }
  }
  lines.forEach((line, i) => {
    if (line.startsWith('# '))       { flushList(); elements.push(<h1 key={i}>{line.slice(2)}</h1>) }
    else if (line.startsWith('## ')) { flushList(); elements.push(<h2 key={i}>{line.slice(3)}</h2>) }
    else if (line.startsWith('### ')){ flushList(); elements.push(<h3 key={i}>{line.slice(4)}</h3>) }
    else if (line.startsWith('- ') || line.startsWith('* ')) { listItems.push(line.slice(2)) }
    else if (line.trim() === '')     { flushList() }
    else                             { flushList(); elements.push(<p key={i}>{inlineParse(line)}</p>) }
  })
  flushList()
  return <>{elements}</>
}

// ── Icons ──────────────────────────────────────────────────
function IconSearch() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
}
function IconDownload() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
}
function IconClose() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
}
function IconChevronUp() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'inline', width: 12, height: 12, marginLeft: 3 }}><polyline points="18 15 12 9 6 15"/></svg>
}
function IconChevronDown() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'inline', width: 12, height: 12, marginLeft: 3 }}><polyline points="6 9 12 15 18 9"/></svg>
}
function IconChevronDownSm() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
}

// ── Table row ──────────────────────────────────────────────
function BandoRow({ b, dimmed, schedaLoading, onScheda }: {
  b: Bando
  dimmed: boolean
  schedaLoading: number | null
  onScheda: (b: Bando) => void
}) {
  return (
    <tr style={dimmed ? { opacity: 0.52, color: 'var(--color-text-muted)' } : undefined}>
      <td className="td-muted" style={{ fontSize: '0.75rem' }}>{b.id}</td>
      <td>
        <span className="td-title" style={dimmed ? { color: 'var(--color-text-muted)' } : undefined}>
          {b.titolo ?? `Bando #${b.id}`}
        </span>
      </td>
      <td className="td-muted">{b.ente ?? '—'}</td>
      <td>
        {b.urgenza
          ? <span className={`badge ${urgencyClass(b.urgenza)}`}>{urgencyLabel(b.urgenza)}</span>
          : <span className="td-muted">—</span>}
      </td>
      <td>
        {b.data_scadenza ? (
          <>
            <span>{formatDate(b.data_scadenza)}</span>
            {b.giorni_alla_scadenza !== null && (
              <span className="td-muted" style={{ marginLeft: 6 }}>
                ({b.giorni_alla_scadenza < 0 ? 'scaduto' : `${b.giorni_alla_scadenza} gg`})
              </span>
            )}
          </>
        ) : <span className="td-muted">—</span>}
      </td>
      <td>{b.contributo_max !== null ? formatEuro(b.contributo_max) : <span className="td-muted">—</span>}</td>
      <td>
        <div className="btn-group">
          <button
            className="btn btn-sm btn-primary"
            onClick={() => onScheda(b)}
            disabled={schedaLoading === b.id}
          >
            {schedaLoading === b.id
              ? <div className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} />
              : 'Scheda'}
          </button>
          <a href={`/api/bandi/${b.id}/scheda.md`} download className="btn btn-sm" title="Scarica .md">
            <IconDownload />
          </a>
        </div>
      </td>
    </tr>
  )
}

// ── Table shell ────────────────────────────────────────────
function BandoTable({ rows, dimmed, emptyMsg, schedaLoading, onScheda, handleSort, SortIcon }: {
  rows: Bando[]
  dimmed: boolean
  emptyMsg: string
  schedaLoading: number | null
  onScheda: (b: Bando) => void
  handleSort: (k: SortKey) => void
  SortIcon: React.FC<{ col: SortKey }>
}) {
  return (
    <div className="table-wrapper">
      <table className="data-table">
        <thead>
          <tr>
            <th style={{ width: 40 }}>#</th>
            <th className="sortable" onClick={() => handleSort('titolo')}>Titolo <SortIcon col="titolo" /></th>
            <th>Ente</th>
            <th className="sortable" onClick={() => handleSort('urgenza')}>Urgenza <SortIcon col="urgenza" /></th>
            <th className="sortable" onClick={() => handleSort('scadenza')}>Scadenza <SortIcon col="scadenza" /></th>
            <th className="sortable" onClick={() => handleSort('contributo')}>Contributo max <SortIcon col="contributo" /></th>
            <th>Azioni</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0
            ? <tr><td colSpan={7} style={{ textAlign: 'center', padding: '32px', color: 'var(--color-text-muted)' }}>{emptyMsg}</td></tr>
            : rows.map(b => (
              <BandoRow key={b.id} b={b} dimmed={dimmed} schedaLoading={schedaLoading} onScheda={onScheda} />
            ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────
export default function Bandi() {
  const [bandi, setBandi] = useState<Bando[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [quickFilter, setQuickFilter] = useState<QuickFilter>('tutti')
  const [showScaduti, setShowScaduti] = useState(false)
  const [sortKey, setSortKey] = useState<SortKey>('urgenza')
  const [sortDir, setSortDir] = useState<SortDir>('asc')
  const [openScheda, setOpenScheda] = useState<SchedaModal | null>(null)
  const [schedaLoading, setSchedaLoading] = useState<number | null>(null)

  useEffect(() => {
    setLoading(true)
    fetch('/api/bandi')
      .then(r => r.json())
      .then(d => { setBandi(d.bandi ?? []); setLoading(false) })
      .catch(() => { setError('Errore nel caricamento dei bandi.'); setLoading(false) })
  }, [])

  useEffect(() => {
    if (!openScheda) return
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpenScheda(null) }
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
  }, [openScheda])

  const handleSort = useCallback((key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('asc') }
  }, [sortKey])

  const handleScheda = async (bando: Bando) => {
    setSchedaLoading(bando.id)
    try {
      const res = await fetch(`/api/bandi/${bando.id}/scheda`)
      const d = await res.json()
      setOpenScheda({ id: bando.id, titolo: bando.titolo ?? `Bando #${bando.id}`, scheda: d.scheda ?? '' })
    } finally {
      setSchedaLoading(null)
    }
  }

  // Counts for quick filter labels (before search)
  const totalAttivi = useMemo(() => bandi.filter(b => !isExpired(b)).length, [bandi])
  const totalScaduti = useMemo(() => bandi.filter(isExpired).length, [bandi])

  // Search → split → sort
  const { sortedAttivi, sortedScaduti } = useMemo(() => {
    const searchFn = (b: Bando) => {
      if (!query) return true
      const q = query.toLowerCase()
      return (b.titolo ?? '').toLowerCase().includes(q) || (b.ente ?? '').toLowerCase().includes(q)
    }
    const sortFn = (a: Bando, b: Bando) => {
      let cmp = 0
      if (sortKey === 'urgenza') cmp = urgencyOrder(a.urgenza) - urgencyOrder(b.urgenza)
      else if (sortKey === 'scadenza') cmp = (a.giorni_alla_scadenza ?? 9999) - (b.giorni_alla_scadenza ?? 9999)
      else if (sortKey === 'titolo') cmp = (a.titolo ?? '').localeCompare(b.titolo ?? '')
      else if (sortKey === 'contributo') cmp = (b.contributo_max ?? 0) - (a.contributo_max ?? 0)
      return sortDir === 'asc' ? cmp : -cmp
    }
    const filtered = bandi.filter(searchFn)
    return {
      sortedAttivi: filtered.filter(b => !isExpired(b)).sort(sortFn),
      sortedScaduti: filtered.filter(isExpired).sort(sortFn),
    }
  }, [bandi, query, sortKey, sortDir])

  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sortKey !== col) return null
    return sortDir === 'asc' ? <IconChevronUp /> : <IconChevronDown />
  }

  const tableProps = { schedaLoading, onScheda: handleScheda, handleSort, SortIcon }

  if (loading) {
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
          {/* Quick filter bar */}
          <div className="quick-filter" style={{ marginBottom: 16 }}>
            <button
              className={`quick-filter-btn${quickFilter === 'tutti' ? ' active' : ''}`}
              onClick={() => setQuickFilter('tutti')}
            >
              Tutti ({bandi.length})
            </button>
            <button
              className={`quick-filter-btn${quickFilter === 'attivi' ? ' active' : ''}`}
              onClick={() => setQuickFilter('attivi')}
            >
              Attivi ({totalAttivi})
            </button>
            <button
              className={`quick-filter-btn${quickFilter === 'scaduti' ? ' active' : ''}`}
              onClick={() => setQuickFilter('scaduti')}
            >
              Scaduti ({totalScaduti})
            </button>
          </div>

          {/* View: tutti */}
          {quickFilter === 'tutti' && (
            <>
              <BandoTable
                rows={sortedAttivi}
                dimmed={false}
                emptyMsg={query ? `Nessun bando attivo per "${query}"` : 'Nessun bando attivo'}
                {...tableProps}
              />
              {totalScaduti > 0 && (
                <>
                  <button
                    className={`scaduti-toggle${showScaduti ? ' open' : ''}`}
                    onClick={() => setShowScaduti(v => !v)}
                  >
                    <IconChevronDownSm />
                    {showScaduti ? 'Nascondi bandi scaduti' : 'Mostra bandi scaduti'}
                    <span className="scaduti-count">{sortedScaduti.length}</span>
                  </button>
                  {showScaduti && (
                    <div style={{ marginTop: 8 }}>
                      <BandoTable
                        rows={sortedScaduti}
                        dimmed={true}
                        emptyMsg={query ? `Nessun bando scaduto per "${query}"` : 'Nessun bando scaduto'}
                        {...tableProps}
                      />
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {/* View: attivi */}
          {quickFilter === 'attivi' && (
            <BandoTable
              rows={sortedAttivi}
              dimmed={false}
              emptyMsg={query ? `Nessun bando attivo per "${query}"` : 'Nessun bando attivo'}
              {...tableProps}
            />
          )}

          {/* View: scaduti */}
          {quickFilter === 'scaduti' && (
            <BandoTable
              rows={sortedScaduti}
              dimmed={true}
              emptyMsg={query ? `Nessun bando scaduto per "${query}"` : 'Nessun bando scaduto'}
              {...tableProps}
            />
          )}
        </>
      )}

      {openScheda && (
        <div className="modal-backdrop" onClick={() => setOpenScheda(null)}>
          <div className="modal modal-lg" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <p className="modal-title">{openScheda.titolo}</p>
                <p className="modal-subtitle">Scheda di sintesi</p>
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
                <a href={`/api/bandi/${openScheda.id}/scheda.md`} download className="btn btn-sm">
                  <IconDownload /> Scarica
                </a>
                <button className="modal-close" onClick={() => setOpenScheda(null)} aria-label="Chiudi">
                  <IconClose />
                </button>
              </div>
            </div>
            <div className="modal-body">
              <div className="scheda-content">
                {openScheda.scheda ? renderMarkdown(openScheda.scheda) : (
                  <p className="text-muted">Scheda non disponibile per questo bando.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
