import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { apiHref } from '../apiKey'
import { useDashboardBandoDetail } from '../lib/queries'
import { BreakdownBar, IconArrowLeft, IconDownload, IconExternal, scoreCircleClass } from '../lib/clienti-shared'
import type { Ammissibilita, ScoreBreakdown } from '../lib/dashboard-shared'

interface AnalisiCliente {
  id: number
  ragione_sociale: string
  codice_ateco: string | null
  regione: string | null
  dimensione_impresa: string | null
  fatturato: number | null
  score: number
  breakdown: ScoreBreakdown
  breakdown_error?: string | null
  ammissibilita: Ammissibilita
  spiegazione_score?: string | null
}

interface BandoDetailResponse {
  bando: {
    id: number
    titolo: string
    ente: string | null
    scadenza: string | null
    giorni_alla_scadenza: number | null
    urgenza: string | null
    fonte_url: string | null
    has_pdf: boolean
    scheda: string
    dati: Record<string, unknown>
  }
  clienti: AnalisiCliente[]
}

function isPresent(value: unknown): boolean {
  if (value == null || value === '') return false
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'object') return Object.values(value as Record<string, unknown>).some(isPresent)
  return true
}

function formatMoney(value: unknown): string | null {
  if (typeof value !== 'number') return null
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(value)
}

function humanize(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase())
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : []
}

function InfoValue({ label, value }: { label: string; value: React.ReactNode }) {
  if (value == null || value === '') return null
  return <div className="analysis-info-value"><span>{label}</span><strong>{value}</strong></div>
}

function InfoList({ items, empty = 'Dato non rilevato' }: { items: string[]; empty?: string }) {
  if (items.length === 0) return <p className="analysis-empty-value">{empty}</p>
  return <ul className="analysis-info-list">{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>
}

function InfoCard({ title, subtitle, children, className = '' }: {
  title: string
  subtitle: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <section className={`analysis-info-card ${className}`}>
      <div className="analysis-info-card-heading"><h2>{title}</h2><p>{subtitle}</p></div>
      <div className="analysis-info-card-body">{children}</div>
    </section>
  )
}

function percentageLines(value: unknown): string[] {
  if (typeof value === 'number') return [`${value}%`]
  if (!value || typeof value !== 'object') return []
  return Object.entries(value as Record<string, unknown>)
    .filter(([, amount]) => typeof amount === 'number')
    .map(([key, amount]) => `${humanize(key)}: ${amount}%`)
}

function dimensionLines(value: unknown): string[] {
  if (!value || typeof value !== 'object') return []
  return Object.entries(value as Record<string, unknown>)
    .filter(([, enabled]) => enabled === true)
    .map(([key]) => humanize(key))
}

function exclusionLines(value: unknown): string[] {
  if (typeof value === 'string' && value.trim()) return [value]
  if (!value || typeof value !== 'object') return []
  const result: string[] = []
  Object.values(value as Record<string, unknown>).forEach(item => {
    if (typeof item === 'string' && item.trim()) result.push(item)
    if (Array.isArray(item)) item.forEach(entry => { if (typeof entry === 'string' && entry.trim()) result.push(entry) })
  })
  return [...new Set(result)]
}

function agevolazioneLines(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.flatMap(item => {
    if (!item || typeof item !== 'object') return []
    const entry = item as Record<string, unknown>
    const parts = [
      typeof entry.tipo === 'string' ? humanize(entry.tipo) : null,
      formatMoney(entry.importo_max) ? `fino a ${formatMoney(entry.importo_max)}` : null,
      typeof entry.percentuale === 'number' ? `${entry.percentuale}%` : null,
      typeof entry.descrizione === 'string' ? entry.descrizione : null,
    ].filter(Boolean)
    return parts.length > 0 ? [parts.join(' · ')] : []
  })
}

function statusLabel(cliente: AnalisiCliente): { label: string; className: string } {
  if (cliente.ammissibilita?.errore) return { label: 'Verifica non riuscita', className: 'warning' }
  if (cliente.ammissibilita?.ammissibile === false) return { label: 'Non ammissibile', className: 'danger' }
  if (cliente.breakdown.status === 'da_verificare' || cliente.ammissibilita?.ammissibile === null) {
    return { label: 'Da verificare', className: 'warning' }
  }
  return { label: 'Ammissibile sui dati disponibili', className: 'success' }
}

export default function DashboardBandoDetail() {
  const navigate = useNavigate()
  const params = useParams()
  const bandoId = params.bandoId && /^\d+$/.test(params.bandoId) ? Number(params.bandoId) : null
  const { data, isLoading, error } = useDashboardBandoDetail<BandoDetailResponse>(bandoId)
  const [selectedClienteId, setSelectedClienteId] = useState<number | null>(null)

  useEffect(() => {
    if (data?.clienti.length && selectedClienteId === null) setSelectedClienteId(data.clienti[0].id)
  }, [data, selectedClienteId])

  const selectedCliente = useMemo(
    () => data?.clienti.find(cliente => cliente.id === selectedClienteId) ?? null,
    [data, selectedClienteId],
  )

  if (isLoading) return <div className="loading-center"><div className="spinner" /> Caricamento analisi…</div>
  if (error || !data) return <div><button className="cliente-back" onClick={() => navigate('/')}><IconArrowLeft /> Torna alla dashboard</button><div className="alert alert-danger">Impossibile caricare il dettaglio del bando.</div></div>

  const { bando } = data
  const d = bando.dati
  const status = selectedCliente ? statusLabel(selectedCliente) : null
  const regioni = stringList(d.regioni_ammesse)
  const ateco = stringList(d.codici_ateco_ammessi)
  const attivita = stringList(d.attivita_ammesse)
  const forme = stringList(d.forme_giuridiche_ammesse)
  const spese = stringList(d.spese_ammissibili)
  const tipiAgevolazione = stringList(d.tipo_agevolazione).map(humanize)
  const percentuali = percentageLines(d.percentuale_fondo_perduto)
  const dimensioni = dimensionLines(d.dimensione_impresa)
  const esclusioni = exclusionLines(d.note_esclusioni)
  const strumenti = agevolazioneLines(d.agevolazioni)
  const fonti = Array.isArray(d.fonti) ? d.fonti.filter(item => item && typeof item === 'object') as Array<Record<string, unknown>> : []
  const anzianita = d.anzianita_impresa && typeof d.anzianita_impresa === 'object' ? d.anzianita_impresa as Record<string, unknown> : {}

  const requisitiExtra = [
    typeof d.fatturato_max === 'number' ? `Fatturato massimo: ${formatMoney(d.fatturato_max)}` : null,
    typeof d.numero_dipendenti_min === 'number' ? `Dipendenti minimi: ${d.numero_dipendenti_min}` : null,
    typeof d.numero_dipendenti_max === 'number' ? `Dipendenti massimi: ${d.numero_dipendenti_max}` : null,
    typeof anzianita.mesi_minimi_dalla_costituzione === 'number' ? `Anzianità minima: ${anzianita.mesi_minimi_dalla_costituzione} mesi` : null,
    typeof anzianita.mesi_massimi_dalla_costituzione === 'number' ? `Anzianità massima: ${anzianita.mesi_massimi_dalla_costituzione} mesi` : null,
  ].filter((item): item is string => Boolean(item))

  return (
    <div className="analysis-page">
      <button className="cliente-back" onClick={() => navigate('/')}><IconArrowLeft /> Torna alla dashboard</button>

      <header className="analysis-header">
        <div>
          <p className="analysis-eyebrow">Analisi bando–cliente</p>
          <h1>{bando.titolo}</h1>
          <p>{bando.ente || 'Ente non rilevato'}{bando.scadenza ? ` · Scadenza ${bando.scadenza}` : ''}</p>
        </div>
        <div className="analysis-header-actions">
          <a href={apiHref(`/api/bandi/${bando.id}/scheda.md`)} download className="btn"><IconDownload /> Scarica scheda</a>
          {bando.has_pdf && <a href={apiHref(`/api/bandi/${bando.id}/pdf`)} download className="btn"><IconDownload /> PDF originale</a>}
          {bando.fonte_url && <a href={bando.fonte_url} target="_blank" rel="noopener noreferrer" className="btn"><IconExternal /> Fonte</a>}
        </div>
      </header>

      <section className="analysis-client-picker">
        <div><label htmlFor="analysis-cliente">Cliente da analizzare</label><p>Seleziona un profilo per aggiornare score, requisiti ed esclusioni.</p></div>
        {data.clienti.length > 0 ? (
          <select id="analysis-cliente" value={selectedClienteId ?? ''} onChange={event => setSelectedClienteId(Number(event.target.value))}>
            {data.clienti.map(cliente => <option key={cliente.id} value={cliente.id}>{cliente.ragione_sociale} · ATECO {cliente.codice_ateco || 'N/D'}</option>)}
          </select>
        ) : <span className="analysis-empty-value">Nessun cliente presente in anagrafica.</span>}
      </section>

      {selectedCliente && status && (
        <section className="analysis-score-grid">
          <div className="analysis-score-card">
            <p className="analysis-panel-label">Compatibilità</p>
            <div className={`score-circle analysis-score-circle ${scoreCircleClass(selectedCliente.score)}`} style={{ '--score': selectedCliente.score } as React.CSSProperties}><span>{selectedCliente.score}%</span></div>
            <span className={`analysis-verdict analysis-verdict--${status.className}`}>{status.label}</span>
            <p className="analysis-score-note">Lo score misura la compatibilità dei dati disponibili, non la probabilità di ottenere il finanziamento.</p>
            {selectedCliente.ammissibilita?.motivi_esclusione?.length > 0 && <InfoList items={selectedCliente.ammissibilita.motivi_esclusione} />}
          </div>

          <div className="analysis-breakdown-card">
            <div><p className="analysis-panel-label">Composizione dello score</p><h2>{selectedCliente.ragione_sociale}</h2></div>
            <div className="breakdown-bars analysis-breakdown-bars">
              <BreakdownBar label="Regione" score={selectedCliente.breakdown.regione} max={30} />
              <BreakdownBar label="ATECO" score={selectedCliente.breakdown.ateco} max={40} />
              <BreakdownBar label="Dimensione" score={selectedCliente.breakdown.dimensione} max={20} />
              <BreakdownBar label="Fatturato" score={selectedCliente.breakdown.fatturato} max={10} />
            </div>
            {selectedCliente.spiegazione_score && <p className="analysis-breakdown-note">{selectedCliente.spiegazione_score}</p>}
          </div>
        </section>
      )}

      <div className="analysis-section-heading"><p className="analysis-eyebrow">Informazioni del bando</p><h2>Dati estratti e organizzati per la verifica</h2></div>

      <div className="analysis-info-grid">
        <InfoCard title="In sintesi" subtitle="Identità e caratteristiche principali">
          <InfoValue label="Ente" value={bando.ente || null} />
          <InfoValue label="Data di pubblicazione" value={typeof d.data_pubblicazione === 'string' ? d.data_pubblicazione : null} />
          <InfoValue label="Modalità" value={typeof d.modalita_presentazione === 'string' ? humanize(d.modalita_presentazione) : null} />
          <InfoValue label="Territorio" value={regioni.length > 0 ? regioni.join(', ') : 'Tutto il territorio nazionale'} />
          {attivita.length > 0 && <><h3>Interventi finanziabili</h3><InfoList items={attivita} /></>}
        </InfoCard>

        <InfoCard title="Agevolazione" subtitle="Importi, percentuali e strumenti">
          <InfoValue label="Contributo massimo" value={formatMoney(d.contributo_max)} />
          <InfoValue label="Spesa minima" value={formatMoney(d.spesa_minima_ammissibile)} />
          <InfoValue label="Spesa massima" value={formatMoney(d.spesa_massima_ammissibile)} />
          {tipiAgevolazione.length > 0 && <InfoValue label="Tipologia" value={tipiAgevolazione.join(', ')} />}
          {percentuali.length > 0 && <><h3>Percentuale a fondo perduto</h3><InfoList items={percentuali} /></>}
          {strumenti.length > 0 && <><h3>Strumenti previsti</h3><InfoList items={strumenti} /></>}
        </InfoCard>

        <InfoCard title="Requisiti di accesso" subtitle="Profilo delle imprese destinatarie">
          <InfoValue label="Regioni ammesse" value={regioni.length > 0 ? regioni.join(', ') : 'Tutte le regioni'} />
          <InfoValue label="Dimensioni" value={dimensioni.length > 0 ? dimensioni.join(', ') : null} />
          <InfoValue label="Forme giuridiche" value={forme.length > 0 ? forme.join(', ') : null} />
          <InfoValue label="ATECO" value={d.ateco_aperto_a_tutti === true ? 'Aperto a tutti i settori' : ateco.join(', ') || null} />
          <InfoList items={requisitiExtra} empty="Nessun altro requisito strutturato rilevato" />
        </InfoCard>

        <InfoCard title="Spese ammissibili" subtitle="Categorie di costo finanziabili">
          <InfoList items={spese} empty="Nessuna categoria di spesa rilevata" />
        </InfoCard>

        <InfoCard title="Scadenza e domanda" subtitle="Tempi e modalità di presentazione">
          <InfoValue label="Scadenza" value={bando.scadenza} />
          <InfoValue label="Giorni rimanenti" value={bando.giorni_alla_scadenza !== null ? (bando.giorni_alla_scadenza >= 0 ? `${bando.giorni_alla_scadenza} giorni` : 'Bando scaduto') : null} />
          <InfoValue label="Modalità di presentazione" value={typeof d.modalita_presentazione === 'string' ? humanize(d.modalita_presentazione) : null} />
          <InfoValue label="Cumulabilità" value={typeof d.cumulabilita === 'string' ? d.cumulabilita : null} />
        </InfoCard>

        <InfoCard title="Esclusioni e controlli" subtitle="Limiti da verificare prima della domanda">
          <InfoList items={esclusioni} empty="Nessuna esclusione strutturata rilevata" />
        </InfoCard>

        <InfoCard title="Fonte ed evidenze" subtitle="Riferimenti per tornare al documento originale" className="analysis-info-card--full">
          <div className="analysis-source-actions">
            {bando.fonte_url && <a href={bando.fonte_url} target="_blank" rel="noopener noreferrer" className="btn btn-sm"><IconExternal /> Fonte ufficiale</a>}
            {bando.has_pdf && <a href={apiHref(`/api/bandi/${bando.id}/pdf`)} download className="btn btn-sm"><IconDownload /> PDF originale</a>}
          </div>
          {fonti.length > 0 ? (
            <div className="analysis-evidence-list">
              {fonti.map((fonte, index) => (
                <div key={index} className="analysis-evidence">
                  <span>{typeof fonte.campo === 'string' ? humanize(fonte.campo) : 'Evidenza'}{typeof fonte.pagina === 'number' ? ` · pagina ${fonte.pagina}` : ''}</span>
                  <p>{typeof fonte.testo === 'string' ? fonte.testo : 'Testo non disponibile'}</p>
                  {typeof fonte.certezza === 'string' && <small>Certezza {fonte.certezza}</small>}
                </div>
              ))}
            </div>
          ) : <p className="analysis-empty-value">Nessuna evidenza puntuale disponibile: verifica il documento originale.</p>}
        </InfoCard>
      </div>

      {!isPresent(d) && <div className="alert alert-warning">I dati strutturati del bando non sono disponibili.</div>}
    </div>
  )
}
