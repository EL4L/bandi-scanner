import { useModalA11y } from '../useModalA11y'

export interface ClienteForm {
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

export const EMPTY_CLIENTE_FORM: ClienteForm = {
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

function IconClose() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

interface Props {
  isEdit: boolean
  form: ClienteForm
  formErrors: string[]
  saving: boolean
  regioni: string[]
  dimensioni: string[]
  onFieldChange: (key: keyof ClienteForm, val: string) => void
  onSubmit: (e: React.FormEvent) => void
  onClose: () => void
}

export function ClienteFormModal({
  isEdit, form, formErrors, saving, regioni, dimensioni, onFieldChange, onSubmit, onClose,
}: Props) {
  const modalRef = useModalA11y(onClose)

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-form-title"
        ref={modalRef}
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <p className="modal-title" id="modal-form-title">{isEdit ? 'Modifica cliente' : 'Nuovo cliente'}</p>
            <p className="modal-subtitle">Compila i dati del profilo aziendale</p>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Chiudi">
            <IconClose />
          </button>
        </div>

        <form onSubmit={onSubmit}>
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
                  onChange={e => onFieldChange('ragione_sociale', e.target.value)}
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
                  onChange={e => onFieldChange('p_iva', e.target.value.replace(/\D/g, ''))}
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
                  onChange={e => onFieldChange('codice_ateco', e.target.value)}
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
                  onChange={e => onFieldChange('regione', e.target.value)}
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
                  onChange={e => onFieldChange('dimensione_impresa', e.target.value)}
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
                  onChange={e => onFieldChange('fatturato', e.target.value)}
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
                  onChange={e => onFieldChange('data_costituzione', e.target.value)}
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
                  onChange={e => onFieldChange('numero_dipendenti', e.target.value)}
                  placeholder="Es. 25"
                />
              </div>

              <div className="field">
                <label htmlFor="forma_giuridica">Forma giuridica</label>
                <select
                  id="forma_giuridica"
                  value={form.forma_giuridica}
                  onChange={e => onFieldChange('forma_giuridica', e.target.value)}
                >
                  <option value="">— Non specificata —</option>
                  <option value="srl">S.r.l.</option>
                  <option value="spa">S.p.A.</option>
                  <option value="snc">S.n.c.</option>
                  <option value="sas">S.a.s.</option>
                  <option value="ditta individuale">Ditta individuale</option>
                  <option value="cooperativa">Cooperativa</option>
                  <option value="associazione">Associazione</option>
                </select>
              </div>

              <div className="field form-full">
                <label htmlFor="descrizione_attivita">Descrizione attività</label>
                <textarea
                  id="descrizione_attivita"
                  value={form.descrizione_attivita}
                  onChange={e => onFieldChange('descrizione_attivita', e.target.value)}
                  placeholder="Breve descrizione dell'attività svolta (opzionale, migliora il matching)"
                />
              </div>
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn" onClick={onClose}>Annulla</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving
                ? <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Salvataggio…</>
                : isEdit ? 'Salva modifiche' : 'Aggiungi cliente'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
