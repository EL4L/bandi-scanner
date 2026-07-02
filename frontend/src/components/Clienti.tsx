import { useEffect, useState } from 'react'
import { toast } from '../toast'

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

interface ClienteForm {
  ragione_sociale: string
  p_iva: string
  codice_ateco: string
  regione: string
  fatturato: string
  dimensione_impresa: string
  descrizione_attivita: string
  data_costituzione: string
  numero_dipendenti: string
  forma_giuridica: string
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
  }
  scadenza: string | null
  giorni_alla_scadenza: number | null
}

const EMPTY_FORM: ClienteForm = {
  ragione_sociale: '',
  p_iva: '',
  codice_ateco: '',
  regione: '',
  fatturato: '',
  dimensione_impresa: '',
  descrizione_attivita: '',
  data_costituzione: '',
  numero_dipendenti: '',
  forma_giuridica: '',
}

function formatEuro(val: number) {
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(val)
}

function matchCountBadgeClass(count: number): string {
  if (count > 5) return 'badge-success'
  if (count > 0) return 'badge-warning'
  return 'badge-neutral'
}

function pillClass(score: number, max: number): string {
  if (score === max) return 'breakdown-pill-full'
  if (score >= max / 2) return 'breakdown-pill-partial'
  return 'breakdown-pill-zero'
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
  const [form, setForm] = useState<ClienteForm>(EMPTY_FORM)
  const [formErrors, setFormErrors] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)
  const [deleting, setDeleting] = useState(false)

  const [detailCliente, setDetailCliente] = useState<Cliente | null>(null)
  const [detailBandi, setDetailBandi] = useState<BandoMatch[]>([])
  const [detailLoading, setDetailLoading] = useState(false)

  const fetchClienti = async () => {
    try {
      const res = await fetch('/api/clienti')
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

  useEffect(() => {
    if (!modalOpen) return
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') closeModal() }
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
  }, [modalOpen])

  useEffect(() => {
    if (!detailCliente) return
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') closeDetail() }
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
  }, [detailCliente])

  const openAdd = () => {
    setEditId(null)
    setForm(EMPTY_FORM)
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
      const res = await fetch(`/api/clienti/${c.id}/bandi`)
      const d = await res.json()
      setDetailBandi(d.bandi ?? [])
    } catch {
      toast.error('Impossibile caricare i bandi del cliente.')
    } finally {
      setDetailLoading(false)
    }
  }

  const closeDetail = () => { setDetailCliente(null); setDetailBandi([]) }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setFormErrors([])

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
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
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
      await fetch(`/api/clienti/${id}`, { method: 'DELETE' })
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
                      <p className="td-muted" style={{ marginTop: 2, maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {c.descrizione_attivita}
                      </p>
                    )}
                  </td>
                  <td className="td-muted" style={{ fontFamily: 'ui-monospace, monospace', fontSize: '0.82rem' }}>
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
                    <span className={`badge ${matchCountBadgeClass(c.match_count)}`}>
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
                        <button className="btn btn-sm" onClick={() => openEdit(c)} title="Modifica">
                          <IconEdit />
                        </button>
                        <button className="btn btn-sm btn-ghost" onClick={() => setDeleteConfirm(c.id)} title="Elimina">
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
          <div className="modal modal-xl" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <p className="modal-title">{detailCliente.ragione_sociale}</p>
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
                {detailCliente.descrizione_attivita && (
                  <span className="td-muted text-sm" style={{ gridColumn: '1 / -1' }}>
                    {detailCliente.descrizione_attivita}
                  </span>
                )}
              </div>

              <hr className="divider" />

              <p className="result-section-title" style={{ marginBottom: 10 }}>
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
                  {detailBandi.map(b => (
                    <div key={b.bando_id} className="cliente-bando-row">
                      <div className="cliente-bando-info">
                        <p className="td-title">{b.titolo ?? `Bando #${b.bando_id}`}</p>
                        {b.ente && <p className="td-muted" style={{ fontSize: '0.78rem', marginTop: 2 }}>{b.ente}</p>}
                        <div className="breakdown-pills" style={{ marginTop: 7 }}>
                          <span className={`breakdown-pill ${pillClass(b.breakdown.regione, 30)}`}>Regione {b.breakdown.regione}/30</span>
                          <span className={`breakdown-pill ${pillClass(b.breakdown.ateco, 40)}`}>ATECO {b.breakdown.ateco}/40</span>
                          <span className={`breakdown-pill ${pillClass(b.breakdown.dimensione, 20)}`}>Dimensione {b.breakdown.dimensione}/20</span>
                          <span className={`breakdown-pill ${pillClass(b.breakdown.fatturato, 10)}`}>Fatturato {b.breakdown.fatturato}/10</span>
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
                          <div style={{ textAlign: 'center', marginTop: 6 }}>
                            <p style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', lineHeight: 1.3 }}>{b.scadenza}</p>
                            {b.giorni_alla_scadenza !== null && (
                              <p className={`scadenza-giorni ${giorniColorClass(b.giorni_alla_scadenza)}`} style={{ marginTop: 2 }}>
                                {b.giorni_alla_scadenza < 0 ? 'scaduto' : `${b.giorni_alla_scadenza} gg`}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Edit / create form modal (unchanged) ── */}
      {modalOpen && (
        <div className="modal-backdrop" onClick={closeModal}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <p className="modal-title">{editId ? 'Modifica cliente' : 'Nuovo cliente'}</p>
                <p className="modal-subtitle">Compila i dati del profilo aziendale</p>
              </div>
              <button className="modal-close" onClick={closeModal} aria-label="Chiudi">
                <IconClose />
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                {formErrors.length > 0 && (
                  <div className="alert alert-danger" style={{ marginBottom: 16 }}>
                    <ul style={{ margin: 0, paddingLeft: 18 }}>
                      {formErrors.map((e, i) => <li key={i}>{e}</li>)}
                    </ul>
                  </div>
                )}

                <div className="form-grid">
                  <div className="field form-full">
                    <label htmlFor="ragione_sociale">Ragione Sociale *</label>
                    <input
                      id="ragione_sociale"
                      type="text"
                      value={form.ragione_sociale}
                      onChange={e => setField('ragione_sociale', e.target.value)}
                      placeholder="Es. Rossi Srl"
                      required
                    />
                  </div>

                  <div className="field">
                    <label htmlFor="p_iva">Partita IVA *</label>
                    <input
                      id="p_iva"
                      type="text"
                      value={form.p_iva}
                      onChange={e => setField('p_iva', e.target.value)}
                      placeholder="11 cifre senza spazi"
                      maxLength={11}
                      required
                    />
                    <p className="help">Esattamente 11 cifre numeriche</p>
                  </div>

                  <div className="field">
                    <label htmlFor="codice_ateco">Codice ATECO *</label>
                    <input
                      id="codice_ateco"
                      type="text"
                      value={form.codice_ateco}
                      onChange={e => setField('codice_ateco', e.target.value)}
                      placeholder="Es. 62.01 o 62.01.09"
                      required
                    />
                    <p className="help">Formato: XX.XX o XX.XX.XX</p>
                  </div>

                  <div className="field">
                    <label htmlFor="regione">Regione *</label>
                    <select
                      id="regione"
                      value={form.regione}
                      onChange={e => setField('regione', e.target.value)}
                      required
                    >
                      <option value="">— Seleziona —</option>
                      {regioni.map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </div>

                  <div className="field">
                    <label htmlFor="dimensione_impresa">Dimensione impresa *</label>
                    <select
                      id="dimensione_impresa"
                      value={form.dimensione_impresa}
                      onChange={e => setField('dimensione_impresa', e.target.value)}
                      required
                    >
                      <option value="">— Seleziona —</option>
                      {dimensioni.map(d => <option key={d} value={d}>{d}</option>)}
                    </select>
                  </div>

                  <div className="field">
                    <label htmlFor="fatturato">Fatturato annuo (€) *</label>
                    <input
                      id="fatturato"
                      type="number"
                      min="0"
                      step="1000"
                      value={form.fatturato}
                      onChange={e => setField('fatturato', e.target.value)}
                      placeholder="Es. 500000"
                      required
                    />
                  </div>

                  <div className="field">
                    <label htmlFor="data_costituzione">Data di costituzione</label>
                    <input
                      id="data_costituzione"
                      type="date"
                      value={form.data_costituzione}
                      onChange={e => setField('data_costituzione', e.target.value)}
                    />
                    <p className="help">Per calcolo anzianità impresa (opzionale)</p>
                  </div>

                  <div className="field">
                    <label htmlFor="numero_dipendenti">Numero dipendenti</label>
                    <input
                      id="numero_dipendenti"
                      type="number"
                      min="0"
                      value={form.numero_dipendenti}
                      onChange={e => setField('numero_dipendenti', e.target.value)}
                      placeholder="Es. 25"
                    />
                  </div>

                  <div className="field">
                    <label htmlFor="forma_giuridica">Forma giuridica</label>
                    <input
                      id="forma_giuridica"
                      type="text"
                      value={form.forma_giuridica}
                      onChange={e => setField('forma_giuridica', e.target.value)}
                      placeholder="Es. s.r.l., s.p.a., ditta individuale"
                    />
                  </div>

                  <div className="field form-full">
                    <label htmlFor="descrizione_attivita">Descrizione attività</label>
                    <textarea
                      id="descrizione_attivita"
                      value={form.descrizione_attivita}
                      onChange={e => setField('descrizione_attivita', e.target.value)}
                      placeholder="Breve descrizione dell'attività svolta (opzionale, migliora il matching)"
                    />
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn" onClick={closeModal}>Annulla</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving
                    ? <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Salvataggio…</>
                    : editId ? 'Salva modifiche' : 'Aggiungi cliente'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
