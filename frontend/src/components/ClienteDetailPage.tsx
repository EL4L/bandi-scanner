import { useState } from 'react'
import { apiHref } from '../apiKey'
import type { ClienteForm } from './ClienteFormModal'
import {
  type Cliente, type BandoMatch,
  formatEuro, formatFormaGiuridica, formatDataCostituzione,
  stripColorByGiorni, scoreCircleClass,
  BreakdownBar, IconAlert, IconBan, IconArrowLeft, IconDownload, IconExternal,
} from '../lib/clienti-shared'

interface Props {
  cliente: Cliente
  bandi: BandoMatch[]
  loading: boolean
  onBack: () => void
  onScheda: (b: BandoMatch) => void
  schedaLoading: number | null
  regioni: string[]
  dimensioni: string[]
  anagraficaForm: ClienteForm
  anagraficaErrors: string[]
  anagraficaSaving: boolean
  onAnagraficaFieldChange: (key: keyof ClienteForm, val: string) => void
  onAnagraficaSubmit: (e: React.FormEvent) => void
}

type Tab = 'bandi' | 'anagrafica'

function formatFatturatoInput(value: string): string {
  const digits = value.replace(/\D/g, '').replace(/^0+(?=\d)/, '')
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
}

export function ClienteDetailPage({
  cliente, bandi, loading, onBack, onScheda, schedaLoading,
  regioni, dimensioni,
  anagraficaForm, anagraficaErrors, anagraficaSaving,
  onAnagraficaFieldChange, onAnagraficaSubmit,
}: Props) {
  const [tab, setTab] = useState<Tab>('bandi')

  return (
    <div>
      <button className="cliente-back" onClick={onBack}>
        <IconArrowLeft /> Torna ai clienti
      </button>

      <div className="cliente-hero">
        <div className="cliente-hero-inner">
          <div className="cliente-hero-eyebrow"><span className="pulse-dot" /> Scheda azienda</div>
          <h1 className="cliente-hero-title">{cliente.ragione_sociale}</h1>
          <div className="cliente-hero-meta">
            <span className="chip chip-ateco">ATECO {cliente.codice_ateco}</span>
            <span className="chip">Dimensione <strong>{cliente.dimensione_impresa}</strong></span>
            <span className="chip">Regione <strong>{cliente.regione}</strong></span>
            {cliente.fatturato ? (
              <span className="chip">Fatturato <strong>{formatEuro(cliente.fatturato)}</strong></span>
            ) : null}
            {formatFormaGiuridica(cliente.forma_giuridica) && (
              <span className="chip">Forma <strong>{formatFormaGiuridica(cliente.forma_giuridica)}</strong></span>
            )}
            {formatDataCostituzione(cliente.data_costituzione) && (
              <span className="chip">Costituita <strong>{formatDataCostituzione(cliente.data_costituzione)}</strong></span>
            )}
          </div>
        </div>
      </div>

      <div className="cliente-tabs">
        <button className={`cliente-tab${tab === 'bandi' ? ' active' : ''}`} onClick={() => setTab('bandi')}>
          Bandi analizzati<span className="cliente-tab-count">{bandi.length}</span>
        </button>
        <button className={`cliente-tab${tab === 'anagrafica' ? ' active' : ''}`} onClick={() => setTab('anagrafica')}>
          Anagrafica
        </button>
      </div>

      {tab === 'bandi' ? (
        <div>
          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '24px 0' }}>
              <div className="spinner" />
            </div>
          ) : bandi.length === 0 ? (
            <p className="text-muted text-sm">Nessun bando compatibile trovato per questo cliente.</p>
          ) : (
            <>
              <div className="cliente-scan-line">
                <span className="pulse-dot" /> Il radar ha analizzato <strong>{bandi.length}</strong> {bandi.length === 1 ? 'bando' : 'bandi'} per questa azienda
              </div>
              {bandi.map(b => {
                const escluso = b.ammissibilita?.ammissibile === false
                const erroreVerifica = b.ammissibilita?.errore === true
                const daVerificare = !escluso && !erroreVerifica && b.breakdown.status === 'da_verificare'
                return (
                  <div
                    key={b.bando_id}
                    className={`bcard${escluso ? ' bcard-muted' : ''}`}
                    style={{ '--edge': stripColorByGiorni(b.giorni_alla_scadenza) } as React.CSSProperties}
                  >
                    <div className="bcard-top">
                      <div>
                        <p className="bcard-title">{b.titolo ?? `Bando #${b.bando_id}`}</p>
                        {b.ente && <p className="bcard-ente">{b.ente}</p>}
                        {b.scadenza && !escluso && !daVerificare && !erroreVerifica && (
                          <p className="bcard-scad">
                            Scade <strong>{b.scadenza}</strong>
                            {b.giorni_alla_scadenza !== null && b.giorni_alla_scadenza >= 0 && (
                              <> · <strong>{b.giorni_alla_scadenza} gg</strong></>
                            )}
                          </p>
                        )}
                        {erroreVerifica && (
                          <span className="badge badge-warning" style={{ marginTop: 'var(--space-2)' }}
                            title="Il controllo di ammissibilità non è riuscito per un errore tecnico: verifica manualmente i requisiti">
                            <IconAlert /> Verifica non riuscita
                          </span>
                        )}
                        {daVerificare && (
                          <span className="badge badge-warning" style={{ marginTop: 'var(--space-2)' }}
                            title="Il bando non contiene dati sufficienti per valutare la compatibilità">
                            <IconAlert /> Da verificare
                          </span>
                        )}
                        {escluso && (
                          <div className="eligibility-excluded" style={{ marginTop: 'var(--space-2)' }}>
                            <span className="badge badge-escluso"><IconBan /> Non ammissibile</span>
                            <ul className="eligibility-reasons">
                              {(b.ammissibilita?.motivi_esclusione?.length
                                ? b.ammissibilita.motivi_esclusione
                                : ['Non è stato possibile determinare il requisito non rispettato: verifica manualmente.']
                              ).map((motivo, i) => <li key={i}>{motivo}</li>)}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>

                    {!escluso && (
                      <div className="cliente-score-summary">
                        <div
                          className={`score-circle score-circle--radar ${scoreCircleClass(b.score)}`}
                          style={{ '--score': b.score } as React.CSSProperties}
                          aria-label={`Score totale ${b.score}%`}
                        >
                          <span>{b.score}%</span>
                        </div>
                        <div className="breakdown-bars cliente-score-breakdown">
                          <BreakdownBar label="Regione" score={b.breakdown.regione} max={30} />
                          <BreakdownBar label="ATECO" score={b.breakdown.ateco} max={40} />
                          <BreakdownBar label="Dimensione" score={b.breakdown.dimensione} max={20} />
                          <BreakdownBar label="Fatturato" score={b.breakdown.fatturato} max={10} />
                        </div>
                      </div>
                    )}

                    <div className="bcard-actions">
                      <button className="btn btn-sm btn-primary" onClick={() => onScheda(b)} disabled={schedaLoading === b.bando_id}>
                        {schedaLoading === b.bando_id ? <div className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} /> : 'Scheda'}
                      </button>
                      <a href={apiHref(`/api/bandi/${b.bando_id}/scheda.md`)} download className="btn btn-sm"
                        aria-label={`Scarica scheda di ${b.titolo ?? `Bando #${b.bando_id}`}`}>
                        <IconDownload /> Scheda .md
                      </a>
                      {b.has_pdf ? (
                        <a href={apiHref(`/api/bandi/${b.bando_id}/pdf`)} download className="btn btn-sm"
                          aria-label={`Scarica PDF originale di ${b.titolo ?? `Bando #${b.bando_id}`}`}>
                          <IconDownload /> PDF
                        </a>
                      ) : (
                        <button className="btn btn-sm" disabled title="PDF originale non disponibile: ricarica il documento">
                          PDF non disponibile
                        </button>
                      )}
                      {b.fonte_url && (
                        <a href={b.fonte_url} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-ghost"
                          aria-label={`Apri fonte ufficiale di ${b.titolo ?? `Bando #${b.bando_id}`}`}>
                          <IconExternal /> Fonte
                        </a>
                      )}
                    </div>
                  </div>
                )
              })}
            </>
          )}
        </div>
      ) : (
        <form onSubmit={onAnagraficaSubmit}>
          {anagraficaErrors.length > 0 && (
            <div className="alert alert-danger" style={{ marginBottom: 'var(--space-4)' }}>
              <ul style={{ margin: 0, paddingLeft: 'var(--space-4)' }}>
                {anagraficaErrors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </div>
          )}
          <div className="cliente-form-grid">
            <div className="cliente-form-section">
              <h3>Dati anagrafici</h3>
              <p className="cliente-form-sec-sub">Identità e forma dell'azienda</p>
              <div className="field">
                <label htmlFor="an-ragione-sociale">Ragione sociale *</label>
                <input id="an-ragione-sociale" type="text" required
                  value={anagraficaForm.ragione_sociale}
                  onChange={e => onAnagraficaFieldChange('ragione_sociale', e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="an-piva">Partita IVA *</label>
                <input id="an-piva" type="text" maxLength={11} required
                  value={anagraficaForm.p_iva}
                  onChange={e => onAnagraficaFieldChange('p_iva', e.target.value.replace(/\D/g, ''))} />
                <p className="help">Esattamente 11 cifre numeriche</p>
              </div>
              <div className="field">
                <label htmlFor="an-forma">Forma giuridica *</label>
                <select id="an-forma" required value={anagraficaForm.forma_giuridica}
                  onChange={e => onAnagraficaFieldChange('forma_giuridica', e.target.value)}>
                  <option value="">— Seleziona —</option>
                  <option value="srl">S.r.l.</option>
                  <option value="spa">S.p.A.</option>
                  <option value="snc">S.n.c.</option>
                  <option value="sas">S.a.s.</option>
                  <option value="ditta individuale">Ditta individuale</option>
                  <option value="cooperativa">Cooperativa</option>
                  <option value="associazione">Associazione</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="an-data-costituzione">Data di costituzione</label>
                <input id="an-data-costituzione" type="date"
                  value={anagraficaForm.data_costituzione}
                  onChange={e => onAnagraficaFieldChange('data_costituzione', e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="an-regione">Regione *</label>
                <select id="an-regione" required value={anagraficaForm.regione}
                  onChange={e => onAnagraficaFieldChange('regione', e.target.value)}>
                  <option value="">— Seleziona —</option>
                  {regioni.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
            </div>

            <div className="cliente-form-section">
              <h3>Attività e dimensione</h3>
              <p className="cliente-form-sec-sub">Parametri che il radar usa per il match</p>
              <div className="field">
                <label htmlFor="an-ateco">Codice ATECO *</label>
                <input id="an-ateco" type="text" required
                  value={anagraficaForm.codice_ateco}
                  onChange={e => onAnagraficaFieldChange('codice_ateco', e.target.value)} />
                <p className="help">Formato: XX.XX o XX.XX.XX</p>
              </div>
              <div className="field">
                <label htmlFor="an-descrizione">Descrizione attività</label>
                <textarea id="an-descrizione"
                  value={anagraficaForm.descrizione_attivita}
                  onChange={e => onAnagraficaFieldChange('descrizione_attivita', e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="an-fatturato">Fatturato annuo (€) *</label>
                <input id="an-fatturato" type="text" inputMode="numeric" pattern="[0-9.]*" required
                  placeholder="Es. 1.000.000"
                  value={formatFatturatoInput(anagraficaForm.fatturato)}
                  onChange={e => onAnagraficaFieldChange('fatturato', e.target.value.replace(/\D/g, ''))} />
                <p className="help">Separazione automatica: 1.000, 100.000, 1.000.000</p>
              </div>
              <div className="field">
                <label htmlFor="an-dipendenti">Numero dipendenti</label>
                <input id="an-dipendenti" type="number" min="0"
                  value={anagraficaForm.numero_dipendenti}
                  onChange={e => onAnagraficaFieldChange('numero_dipendenti', e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="an-dimensione">Categoria dimensionale *</label>
                <select id="an-dimensione" required value={anagraficaForm.dimensione_impresa}
                  onChange={e => onAnagraficaFieldChange('dimensione_impresa', e.target.value)}>
                  <option value="">— Seleziona —</option>
                  {dimensioni.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
            </div>
          </div>

          <div className="cliente-form-footer">
            <button type="submit" className="btn btn-primary" disabled={anagraficaSaving}>
              {anagraficaSaving
                ? <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Salvataggio…</>
                : 'Salva modifiche'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
