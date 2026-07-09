import { useEffect, useState } from 'react'
import { toast } from '../toast'
import { apiHref, withApiKey } from '../apiKey'
import { useModalA11y } from '../useModalA11y'
import { ClienteFormModal, EMPTY_CLIENTE_FORM, type ClienteForm } from './ClienteFormModal'
import { ModalScheda, type SchedaModalData } from './ModalScheda'

interface Cliente {
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

interface Ammissibilita {
  ammissibile: boolean
  motivi_esclusione: string[]
  criteri_verificati: string[]
}

interface BandoMatch {
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
}

function formatEuro(val: number) {
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

function formatFormaGiuridica(val?: string | null): string | null {
  if (!val) return null
  return FORMA_GIURIDICA_LABELS[val] ?? val
}

function formatDataCostituzione(val?: string | null): string | null {
  if (!val) return null
  const parts = val.split('T')[0].split('-')
  if (parts.length !== 3) return val
  const [year, month, day] = parts
  return `${day}/${month}/${year}`
}

function matchCountBadgeClass(count: number): string {
  if (count > 5) return 'count-badge-high'
  if (count > 0) return 'count-badge-mid'
  return 'count-badge-low'
}

function stripColorByGiorni(giorni: number | null): string {
  if (giorni === null || giorni < 0) return 'var(--color-border-strong)'
  if (giorni < 30) return 'var(--status-low)'
  if (giorni <= 90) return 'var(--status-mid)'
  return 'var(--status-high)'
}

function pillClass(score: number, max: number): string {
  if (score === max) return 'breakdown-pill-full'
  if (score >= max / 2) return 'breakdown-pill-partial'
  return 'breakdown-pill-zero'
}

function pillIcon(score: number, max: number): string {
  if (score === max) return '✅'
  if (score >= max / 2) return '⚠️'
  return '❌'
}

function BreakdownBar({ label, score, max }: { label: string; score: number; max: number }) {
  const pct = max > 0 ? Math.round((score / max) * 100) : 0
  return (
    <div className={`breakdown-bar-row ${pillClass(score, max)}`}>
      <span className="breakdown-bar-label">
        {pillIcon(score, max)} {label}
      </span>
      <div className="breakdown-bar-track" role="img" aria-label={`${label}: ${score} su ${max} punti`}>
        <div className="breakdown-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="breakdown-bar-value">{score}/{max}</span>
    </div>
  )
}

function scoreCircleClass(score: number): string {
  if (score > 70) return 'score-green'
  if (score >= 40) return 'score-yellow'
  return 'score-red'
}

function giorniColorClass(giorni: number): string {
  if (giorni < 30) return 'scadenza-giorni-red'
  if (giorni <= 90) return 'scadenza-giorni-orange'
  return 'scadenza-giorni-green'
}

function IconPlus() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
}
function IconEdit() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  )
}
function IconTrash() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  )
}
function IconClose() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

export default function Clienti() {
  const [clienti, setClienti] = useState<Cliente[]>([])
  const [regioni, setRegioni] = useState<string[]>([])
  const [dimensioni, setDimensioni] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [modalOpen, setModalOpen] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [form, setForm] = useState<ClienteForm>(EMPTY_CLIENTE_FORM)
  const [formErrors, setFormErrors] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)
  const [deleting, setDeleting] = useState(false)

  const [detailCliente, setDetailCliente] = useState<Cliente | null>(null)
  const [detailBandi, setDetailBandi] = useState<BandoMatch[]>([])
  const [detailLoading, setDetailLoading] = useState(false)

  const [openScheda, setOpenScheda] = useState<SchedaModalData | null>(null)
  const [schedaLoading, setSchedaLoading] = useState<number | null>(null)

  const fetchClienti = async () => {
    try {
      const res = await fetch('/api/clienti', withApiKey())
      const d = await res.json()
      setClienti(d.clienti ?? [])
      setRegioni(d.regioni ?? [])
      setDimensioni(d.dimensioni ?? [])
    } catch {
      setError('Impossibile caricare i clienti.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchClienti() }, [])

  const openAdd = () => {
    setEditId(null)
    setForm(EMPTY_CLIENTE_FORM)
    setFormErrors([])
    setModalOpen(true)
  }

  const openEdit = (c: Cliente) => {
    setEditId(c.id)
    setForm({
      ragione_sociale: c.ragione_sociale,
      p_iva: c.p_iva,
      codice_ateco: c.codice_ateco,
      regione: c.regione,
      fatturato: String(c.fatturato ?? ''),
      dimensione_impresa: c.dimensione_impresa,
      descrizione_attivita: c.descrizione_attivita ?? '',
      data_costituzione: c.data_costituzione ?? '',
      numero_dipendenti: c.numero_dipendenti ? String(c.numero_dipendenti) : '',
      forma_giuridica: c.forma_giuridica ?? '',
    })
    setFormErrors([])
    setModalOpen(true)
  }

  const closeModal = () => { setModalOpen(false); setFormErrors([]) }

  const openDetail = async (c: Cliente) => {
    setDetailCliente(c)
    setDetailBandi([])
    setDetailLoading(true)
    try {
      const res = await fetch(`/api/clienti/${c.id}/bandi`, withApiKey())
      const d = await res.json()
      setDetailBandi(d.bandi ?? [])
    } catch {
      toast.error('Impossibile caricare i bandi del cliente.')
    } finally {
      setDetailLoading(false)
    }
  }

  const closeDetail = () => { setDetailCliente(null); setDetailBandi([]) }

  const detailModalRef = useModalA11y(closeDetail, !!detailCliente)

  const handleScheda = async (b: BandoMatch) => {
    setSchedaLoading(b.bando_id)
    try {
      const res = await fetch(`/api/bandi/${b.bando_id}/scheda`, withApiKey())
      const d = await res.json()
      setOpenScheda({ id: b.bando_id, titolo: b.titolo ?? `Bando #${b.bando_id}`, scheda: d.scheda ?? '', fonte_url: b.fonte_url })
    } catch {
      toast.error('Impossibile caricare la scheda del bando.')
    } finally {
      setSchedaLoading(null)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormErrors([])

    const clientErrors: string[] = []
    if (!/^\d{11}$/.test(form.p_iva.trim())) {
      clientErrors.push('Partita IVA non valida: deve contenere esattamente 11 cifre numeriche.')
    }
    if (!/^\d{2}\.\d{2}(\.\d{2})?$/.test(form.codice_ateco.trim())) {
      clientErrors.push('Codice ATECO non valido: usa il formato XX.XX o XX.XX.XX (es. 62.01).')
    }
    if (clientErrors.length > 0) {
      setFormErrors(clientErrors)
      return
    }

    setSaving(true)

    const payload = {
      ragione_sociale: form.ragione_sociale.trim(),
      p_iva: form.p_iva.trim(),
      codice_ateco: form.codice_ateco.trim(),
      regione: form.regione,
      fatturato: parseFloat(form.fatturato) || 0,
      dimensione_impresa: form.dimensione_impresa,
      descrizione_attivita: form.descrizione_attivita.trim(),
      data_costituzione: form.data_costituzione.trim() || null,
      numero_dipendenti: form.numero_dipendenti.trim() ? parseInt(form.numero_dipendenti) : null,
      forma_giuridica: form.forma_giuridica.trim() || null,
    }

    try {
      const url = editId ? `/api/clienti/${editId}` : '/api/clienti'
      const method = editId ? 'PUT' : 'POST'
      const res = await fetch(url, withApiKey({
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }))
      const d = await res.json()
      if (!res.ok) {
        setFormErrors(d.errors ?? ['Errore sconosciuto.'])
      } else {
        const wasEdit = editId !== null
        closeModal()
        await fetchClienti()
        toast.success(wasEdit ? 'Cliente aggiornato.' : 'Cliente aggiunto.')
      }
    } catch {
      setFormErrors(['Errore di rete. Riprova.'])
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    setDeleting(true)
    try {
      await fetch(`/api/clienti/${id}`, withApiKey({ method: 'DELETE' }))
      setDeleteConfirm(null)
      await fetchClienti()
      toast.success('Cliente eliminato.')
    } catch {
      toast.error('Eliminazione non riuscita. Riprova.')
    } finally {
      setDeleting(false)
    }
  }

  const setField = (key: keyof ClienteForm, val: string) =>
    setForm(prev => ({ ...prev, [key]: val }))

  if (loading) {
    return <div className="loading-center"><div className="spinner" /> Caricamento clienti…</div>
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <h1 className="page-title">Clienti</h1>
          <p className="page-subtitle">{clienti.length} {clienti.length === 1 ? 'cliente' : 'clienti'} in anagrafica</p>
        </div>
        <button className="btn btn-primary" onClick={openAdd}>
          <IconPlus /> Aggiungi cliente
        </button>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      {clienti.length === 0 && !error ? (
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
          </div>
          <h3>Nessun cliente</h3>
          <p>Aggiungi i profili dei tuoi clienti per calcolare la compatibilità con i bandi.</p>
          <button className="btn btn-primary" onClick={openAdd}><IconPlus /> Aggiungi cliente</button>
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Ragione Sociale</th>
                <th>P.IVA</th>
                <th>Codice ATECO</th>
                <th>Regione</th>
                <th>Fatturato</th>
                <th>Dimensione</th>
                <th>Bandi compatibili</th>
                <th>Azioni</th>
              </tr>
            </thead>
            <tbody>
              {clienti.map(c => (
                <tr key={c.id}>
                  <td>
                    <button className="cliente-name-btn" onClick={() => openDetail(c)}>
                      {c.ragione_sociale}
                    </button>
                    {c.descrizione_attivita && (
                      <p className="td-muted" style={{ marginTop: 'var(--space-1)', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {c.descrizione_attivita}
                      </p>
                    )}
                  </td>
                  <td className="td-muted" style={{ fontFamily: 'ui-monospace, monospace', fontSize: 'var(--text-sm)' }}>
                    {c.p_iva}
                  </td>
                  <td>
                    <span className="badge badge-blue">{c.codice_ateco}</span>
                  </td>
                  <td className="td-muted">{c.regione}</td>
                  <td>{c.fatturato ? formatEuro(c.fatturato) : '—'}</td>
                  <td>
                    <span className="badge badge-neutral">{c.dimensione_impresa}</span>
                  </td>
                  <td>
                    <span className={`count-badge ${matchCountBadgeClass(c.match_count)}`}>
                      {c.match_count}
                    </span>
                  </td>
                  <td>
                    {deleteConfirm === c.id ? (
                      <div className="btn-group">
                        <span className="text-sm text-muted">Confermi?</span>
                        <button
                          className="btn btn-sm btn-danger"
                          onClick={() => handleDelete(c.id)}
                          disabled={deleting}
                        >
                          {deleting ? <div className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} /> : 'Elimina'}
                        </button>
                        <button className="btn btn-sm btn-ghost" onClick={() => setDeleteConfirm(null)}>
                          Annulla
                        </button>
                      </div>
                    ) : (
                      <div className="btn-group">
                        <button className="btn btn-sm" onClick={() => openEdit(c)} title="Modifica" aria-label={`Modifica ${c.ragione_sociale}`}>
                          <IconEdit />
                        </button>
                        <button className="btn btn-sm btn-ghost" onClick={() => setDeleteConfirm(c.id)} title="Elimina" aria-label={`Elimina ${c.ragione_sociale}`}>
                          <IconTrash />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Detail modal ── */}
      {detailCliente && (
        <div className="modal-backdrop" onClick={closeDetail}>
          <div
            className="modal modal-xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-detail-title"
            ref={detailModalRef}
            onClick={e => e.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <p className="modal-title" id="modal-detail-title">{detailCliente.ragione_sociale}</p>
                <p className="modal-subtitle">Bandi compatibili</p>
              </div>
              <button className="modal-close" onClick={closeDetail} aria-label="Chiudi">
                <IconClose />
              </button>
            </div>
            <div className="modal-body">
              <div className="cliente-detail-info">
                <span className="badge badge-blue">{detailCliente.codice_ateco}</span>
                <span className="badge badge-neutral">{detailCliente.dimensione_impresa}</span>
                <span className="td-muted text-sm">{detailCliente.regione}</span>
                {detailCliente.fatturato ? (
                  <span className="text-sm">{formatEuro(detailCliente.fatturato)}</span>
                ) : null}
                {formatFormaGiuridica(detailCliente.forma_giuridica) && (
                  <span className="badge badge-neutral">{formatFormaGiuridica(detailCliente.forma_giuridica)}</span>
                )}
                {formatDataCostituzione(detailCliente.data_costituzione) && (
                  <span className="td-muted text-sm">Costituita il {formatDataCostituzione(detailCliente.data_costituzione)}</span>
                )}
                {detailCliente.descrizione_attivita && (
                  <span className="td-muted text-sm" style={{ gridColumn: '1 / -1' }}>
                    {detailCliente.descrizione_attivita}
                  </span>
                )}
              </div>

              <hr className="divider" />

              <p className="result-section-title" style={{ marginBottom: 'var(--space-3)' }}>
                {detailLoading ? 'Caricamento…' : `${detailBandi.length} bando${detailBandi.length !== 1 ? 'i' : ''} compatibil${detailBandi.length !== 1 ? 'i' : 'e'}`}
              </p>

              {detailLoading ? (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '24px 0' }}>
                  <div className="spinner" />
                </div>
              ) : detailBandi.length === 0 ? (
                <p className="text-muted text-sm">Nessun bando compatibile trovato per questo cliente.</p>
              ) : (
                <div className="cliente-bandi-list">
                  {detailBandi.map(b => {
                    const escluso = b.ammissibilita?.ammissibile === false
                    const daVerificare = !escluso && b.breakdown.status === 'da_verificare'
                    return (
                      <div key={b.bando_id} className={`cliente-bando-row${escluso ? ' match-excluded' : ''}`}>
                        <div className="deadline-strip" style={{ '--deadline-color': stripColorByGiorni(b.giorni_alla_scadenza) } as React.CSSProperties} />
                        <div className="cliente-bando-row-inner">
                          <div className="cliente-bando-info">
                            <p className="td-title">{b.titolo ?? `Bando #${b.bando_id}`}</p>
                            {b.ente && <p className="td-muted" style={{ fontSize: 'var(--text-xs)', marginTop: 'var(--space-1)' }}>{b.ente}</p>}
                            {daVerificare && (
                              <span
                                className="badge badge-warning"
                                style={{ marginTop: 'var(--space-2)' }}
                                title="Il bando non contiene dati sufficienti per valutare la compatibilità"
                              >
                                ⚠️ Da verificare
                              </span>
                            )}
                            {escluso && (
                              <div style={{ marginTop: 'var(--space-2)' }}>
                                <span className="badge badge-escluso">⛔ Non ammissibile</span>
                                {b.ammissibilita!.motivi_esclusione.length > 0 && (
                                  <ul className="td-muted text-sm" style={{ marginTop: 'var(--space-1)', paddingLeft: 'var(--space-4)' }}>
                                    {b.ammissibilita!.motivi_esclusione.map((motivo, i) => (
                                      <li key={i}>{motivo}</li>
                                    ))}
                                  </ul>
                                )}
                              </div>
                            )}
                            <div className="breakdown-bars" style={{ marginTop: 'var(--space-2)' }}>
                              <BreakdownBar label="Regione" score={b.breakdown.regione} max={30} />
                              <BreakdownBar label="ATECO" score={b.breakdown.ateco} max={40} />
                              <BreakdownBar label="Dimensione" score={b.breakdown.dimensione} max={20} />
                              <BreakdownBar label="Fatturato" score={b.breakdown.fatturato} max={10} />
                            </div>
                            <div className="btn-group" style={{ marginTop: 'var(--space-2)' }}>
                              <button
                                className="btn btn-sm"
                                onClick={() => handleScheda(b)}
                                disabled={schedaLoading === b.bando_id}
                              >
                                {schedaLoading === b.bando_id ? <div className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} /> : 'Scheda'}
                              </button>
                              <a
                                href={apiHref(`/api/bandi/${b.bando_id}/scheda.md`)}
                                download
                                className="btn btn-sm btn-ghost"
                                aria-label={`Scarica scheda di ${b.titolo ?? `Bando #${b.bando_id}`}`}
                              >
                                Scarica
                              </a>
                              {b.fonte_url && (
                                <a
                                  href={b.fonte_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="btn btn-sm btn-ghost"
                                  aria-label={`Apri fonte ufficiale di ${b.titolo ?? `Bando #${b.bando_id}`}`}
                                >
                                  Fonte
                                </a>
                              )}
                            </div>
                          </div>
                          <div className="cliente-bando-right">
                            <div
                              className={`score-circle ${scoreCircleClass(b.score)}`}
                              style={{ '--score': b.score } as React.CSSProperties}
                            >
                              <span>{b.score}%</span>
                            </div>
                            {b.scadenza && (
                              <div style={{ textAlign: 'center', marginTop: 'var(--space-2)' }}>
                                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', lineHeight: 1.3 }}>{b.scadenza}</p>
                                {b.giorni_alla_scadenza !== null && (
                                  <p className={`scadenza-giorni ${giorniColorClass(b.giorni_alla_scadenza)}`} style={{ marginTop: 'var(--space-1)' }}>
                                    {b.giorni_alla_scadenza < 0 ? 'scaduto' : `${b.giorni_alla_scadenza} gg`}
                                  </p>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}

              {openScheda && (
                <ModalScheda data={openScheda} onClose={() => setOpenScheda(null)} />
              )}
            </div>
          </div>
        </div>
      )}

      {modalOpen && (
        <ClienteFormModal
          isEdit={editId !== null}
          form={form}
          formErrors={formErrors}
          saving={saving}
          regioni={regioni}
          dimensioni={dimensioni}
          onFieldChange={setField}
          onSubmit={handleSubmit}
          onClose={closeModal}
        />
      )}
    </div>
  )
}
