import { useState } from 'react'
import { toast } from '../toast'
import { withApiKey } from '../apiKey'
import { useClienti, useApiMutation } from '../lib/queries'
import { ClienteFormModal, EMPTY_CLIENTE_FORM, validaDimensione, type ClienteForm } from './ClienteFormModal'
import { ClienteDetailPage } from './ClienteDetailPage'
import { ModalScheda, type SchedaModalData } from './ModalScheda'
import {
  type Cliente, type BandoMatch,
  formatEuro, matchCountBadgeClass,
  IconPlus, IconEdit, IconTrash, IconClose, IconSearch, IconChevronRight,
} from '../lib/clienti-shared'

export default function Clienti() {
  const { data, isLoading: loading, error: queryError } = useClienti<{
    clienti: Cliente[]; regioni: string[]; dimensioni: string[]
  }>()
  const clienti = data?.clienti ?? []
  const regioni = data?.regioni ?? []
  const dimensioni = data?.dimensioni ?? []
  const error = queryError ? 'Impossibile caricare i clienti.' : null

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

  const [anagraficaForm, setAnagraficaForm] = useState<ClienteForm>(EMPTY_CLIENTE_FORM)
  const [anagraficaErrors, setAnagraficaErrors] = useState<string[]>([])
  const [anagraficaSaving, setAnagraficaSaving] = useState(false)

  const [search, setSearch] = useState('')

  const [openScheda, setOpenScheda] = useState<SchedaModalData | null>(null)
  const [schedaLoading, setSchedaLoading] = useState<number | null>(null)

  const formFromCliente = (c: Cliente): ClienteForm => ({
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

  const openAdd = () => {
    setEditId(null)
    setForm(EMPTY_CLIENTE_FORM)
    setFormErrors([])
    setModalOpen(true)
  }

  const openEdit = (c: Cliente) => {
    setEditId(c.id)
    setForm(formFromCliente(c))
    setFormErrors([])
    setModalOpen(true)
  }

  const closeModal = () => { setModalOpen(false); setFormErrors([]) }

  const openDetail = async (c: Cliente) => {
    setDetailCliente(c)
    setDetailBandi([])
    setDetailLoading(true)
    setAnagraficaForm(formFromCliente(c))
    setAnagraficaErrors([])
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

  const setAnagraficaField = (key: keyof ClienteForm, val: string) =>
    setAnagraficaForm(prev => ({ ...prev, [key]: val }))

  const handleAnagraficaSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setAnagraficaErrors([])
    if (!detailCliente) return

    const clientErrors: string[] = []
    if (!/^\d{11}$/.test(anagraficaForm.p_iva.trim())) {
      clientErrors.push('Partita IVA non valida: deve contenere esattamente 11 cifre numeriche.')
    }
    if (!/^\d{2}\.\d{2}(\.\d{2})?$/.test(anagraficaForm.codice_ateco.trim())) {
      clientErrors.push('Codice ATECO non valido: usa il formato XX.XX o XX.XX.XX (es. 62.01).')
    }
    const dipendenti = anagraficaForm.numero_dipendenti.trim() ? parseInt(anagraficaForm.numero_dipendenti, 10) : null
    const fatturatoNum = anagraficaForm.fatturato.trim() ? parseFloat(anagraficaForm.fatturato) : null
    clientErrors.push(...validaDimensione(anagraficaForm.dimensione_impresa, dipendenti, fatturatoNum))
    if (clientErrors.length > 0) {
      setAnagraficaErrors(clientErrors)
      return
    }

    setAnagraficaSaving(true)
    const payload = {
      ragione_sociale: anagraficaForm.ragione_sociale.trim(),
      p_iva: anagraficaForm.p_iva.trim(),
      codice_ateco: anagraficaForm.codice_ateco.trim(),
      regione: anagraficaForm.regione,
      fatturato: parseFloat(anagraficaForm.fatturato) || 0,
      dimensione_impresa: anagraficaForm.dimensione_impresa,
      descrizione_attivita: anagraficaForm.descrizione_attivita.trim(),
      data_costituzione: anagraficaForm.data_costituzione.trim() || null,
      numero_dipendenti: anagraficaForm.numero_dipendenti.trim() ? parseInt(anagraficaForm.numero_dipendenti) : null,
      forma_giuridica: anagraficaForm.forma_giuridica.trim() || null,
    }
    try {
      const updated = await saveMutation.mutateAsync({ url: `/api/clienti/${detailCliente.id}`, method: 'PUT', body: payload })
      setDetailCliente(prev => prev ? { ...prev, ...payload, id: prev.id, match_count: prev.match_count } : prev)
      toast.success('Anagrafica aggiornata.')
      void updated
    } catch (err) {
      const errors = (err as { errors?: string[] })?.errors
      setAnagraficaErrors(errors ?? ['Errore di rete. Riprova.'])
    } finally {
      setAnagraficaSaving(false)
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
  }

  const handleDelete = async (id: number) => {
    setDeleting(true)
    try {
      await deleteMutation.mutateAsync(id)
      setDeleteConfirm(null)
      toast.success('Cliente eliminato.')
    } catch {
      toast.error('Eliminazione non riuscita. Riprova.')
    } finally {
      setDeleting(false)
    }
  }

  const setField = (key: keyof ClienteForm, val: string) =>
    setForm(prev => ({ ...prev, [key]: val }))

  const q = search.trim().toLowerCase()
  const clientiFiltrati = q
    ? clienti.filter(c =>
        c.ragione_sociale.toLowerCase().includes(q) ||
        c.p_iva.toLowerCase().includes(q))
    : clienti

  if (loading) {
    return <div className="loading-center"><div className="spinner" /> Caricamento clienti…</div>
  }

  if (detailCliente) {
    return (
      <>
        <ClienteDetailPage
          cliente={detailCliente}
          bandi={detailBandi}
          loading={detailLoading}
          onBack={closeDetail}
          onScheda={handleScheda}
          schedaLoading={schedaLoading}
          regioni={regioni}
          dimensioni={dimensioni}
          anagraficaForm={anagraficaForm}
          anagraficaErrors={anagraficaErrors}
          anagraficaSaving={anagraficaSaving}
          onAnagraficaFieldChange={setAnagraficaField}
          onAnagraficaSubmit={handleAnagraficaSubmit}
        />
        {openScheda && <ModalScheda data={openScheda} onClose={() => setOpenScheda(null)} />}
      </>
    )
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <h1 className="page-title">Clienti</h1>
          <p className="page-subtitle">
            {q
              ? `${clientiFiltrati.length} di ${clienti.length} clienti`
              : `${clienti.length} ${clienti.length === 1 ? 'cliente' : 'clienti'} in anagrafica`}
          </p>
        </div>
        <button className="btn btn-primary" onClick={openAdd}>
          <IconPlus /> Aggiungi cliente
        </button>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      {clienti.length > 0 && (
        <div className="clienti-search">
          <span className="clienti-search-icon"><IconSearch /></span>
          <input
            type="text"
            placeholder="Cerca cliente per nome o P.IVA…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            aria-label="Cerca cliente"
          />
          {search && (
            <button className="clienti-search-clear" onClick={() => setSearch('')} aria-label="Cancella ricerca">
              <IconClose />
            </button>
          )}
        </div>
      )}

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
      ) : clientiFiltrati.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </div>
          <h3>Nessun risultato</h3>
          <p>Nessun cliente corrisponde a "{search}". Prova con un altro nome o P.IVA.</p>
          <button className="btn btn-ghost" onClick={() => setSearch('')}>Azzera ricerca</button>
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="data-table clienti-table">
            <thead>
              <tr>
                <th>Ragione Sociale</th>
                <th>Codice ATECO</th>
                <th>Regione</th>
                <th>Fatturato</th>
                <th>Dimensione</th>
                <th>Bandi compatibili</th>
                <th>Azioni</th>
                <th aria-hidden="true"></th>
              </tr>
            </thead>
            <tbody>
              {clientiFiltrati.map(c => (
                <tr key={c.id} className="cliente-row" onClick={() => openDetail(c)}>
                  <td>
                    <span className="cliente-name">{c.ragione_sociale}</span>
                    <p className="cliente-piva">{c.p_iva}</p>
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
                  <td onClick={e => e.stopPropagation()}>
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
                  <td className="cliente-row-go" aria-hidden="true"><IconChevronRight /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Add/edit modal ── */}
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
