import { useEffect, useRef, useState } from 'react'
import { toast } from '../toast'
import { apiHref, withApiKey } from '../apiKey'
import { renderMarkdown } from '../lib/renderMarkdown'
import { useInvalidateAll } from '../lib/queries'

interface ExtractionResult {
  filename: string
  size_kb: number
  status?: 'duplicato'
  messaggio?: string
  empty_pdf?: boolean
  save_error?: string
  extraction_error?: string
  bando_id?: number
  scadenza_estratta?: string
  null_percentage?: number
  warnings?: string[]
  errors?: string[]
  scheda?: string
  bando_info?: Record<string, unknown>
  data?: Record<string, unknown>
}

type StepStatus = 'done' | 'active' | 'pending'

function uploadStepStatuses(uploading: boolean, result: ExtractionResult | null): StepStatus[] {
  if (uploading) return ['done', 'active', 'pending']
  if (!result) return ['pending', 'pending', 'pending']
  const extractionOk = !result.empty_pdf && !result.extraction_error
  const matchingDone = extractionOk && !!result.bando_id && !result.errors?.length && result.status !== 'duplicato'
  return ['done', extractionOk ? 'done' : 'pending', matchingDone ? 'done' : 'pending']
}

function IconUpload() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  )
}

function IconCheck() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function IconLink() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  )
}

function IconX() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

function IconFile() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  )
}

function IconWarning() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, width: 18, height: 18 }}>
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  )
}

function IconDownload() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, width: 14, height: 14 }}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  )
}

function IconSparkles() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3l1.6 5.4L19 10l-5.4 1.6L12 17l-1.6-5.4L5 10l5.4-1.6L12 3z" />
      <path d="M19 3v3M20.5 4.5h-3" />
    </svg>
  )
}

function IconTarget() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1" />
    </svg>
  )
}

function IconInfo() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  )
}

function UploadProgress({ statuses }: { statuses: StepStatus[] }) {
  const labels = ['PDF caricato', 'Estrazione AI', 'Matching automatico']
  return (
    <div className="progress-steps">
      {labels.map((label, i) => (
        <div key={label} style={{ display: 'flex', alignItems: 'center', flex: i < labels.length - 1 ? 1 : undefined }}>
          <div className={`progress-step${statuses[i] === 'done' ? ' done' : ''}${statuses[i] === 'active' ? ' active' : ''}`}>
            <div className="progress-step-dot">
              {statuses[i] === 'done' ? <IconCheck /> : i + 1}
            </div>
            <span className="progress-step-label">{label}</span>
          </div>
          {i < labels.length - 1 && <div className="progress-step-line" />}
        </div>
      ))}
    </div>
  )
}

export default function CaricaBando() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [mode, setMode] = useState<'pdf' | 'url'>('pdf')
  const [bandoUrl, setBandoUrl] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<ExtractionResult | null>(null)
  const [networkError, setNetworkError] = useState<string | null>(null)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const invalidateAll = useInvalidateAll()

  useEffect(() => {
    if (!uploading) {
      setElapsedSeconds(0)
      return
    }
    const interval = setInterval(() => setElapsedSeconds(s => s + 1), 1000)
    return () => clearInterval(interval)
  }, [uploading])

  const extractionWaitMessage = (): string => {
    if (elapsedSeconds < 15) return 'Estrazione in corso — può richiedere fino a un minuto.'
    if (elapsedSeconds < 45) return "L'analisi AI sta impiegando più del previsto, attendi ancora qualche secondo…"
    return 'Il documento è più lungo o complesso del solito: la richiesta è ancora in corso, attendi.'
  }

  const handleFile = (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setNetworkError('Formato non supportato. Carica un file PDF.')
      toast.error('Formato non supportato. Carica un file PDF.')
      return
    }
    if (file.size > 10_000_000) {
      const sizeMB = (file.size / 1_000_000).toFixed(1)
      setNetworkError(`File troppo grande (${sizeMB} MB). Limite massimo: 10 MB.`)
      toast.error(`File troppo grande (${sizeMB} MB). Limite massimo: 10 MB.`)
      return
    }
    setSelectedFile(file)
    setResult(null)
    setNetworkError(null)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  const handleUpload = async () => {
    if (!selectedFile) return
    setUploading(true)
    setNetworkError(null)
    setResult(null)

    const fd = new FormData()
    fd.append('file', selectedFile)

    try {
      const res = await fetch('/api/estrazione', withApiKey({ method: 'POST', body: fd }))
      const data: ExtractionResult = await res.json()
      setResult(data)
      if (data.status === 'duplicato') {
        toast.info('Bando già presente in archivio.')
      } else if (data.bando_id && !data.errors?.length) {
        toast.success('Bando salvato con successo.')
        invalidateAll()
      } else if (data.empty_pdf) {
        toast.error('PDF vuoto o non leggibile.')
      } else if (data.errors?.length) {
        toast.error('Estrazione completata con errori di validazione.')
      }
    } catch {
      setNetworkError('Errore di rete durante il caricamento. Verifica la connessione.')
      toast.error('Errore di rete durante il caricamento.')
    } finally {
      setUploading(false)
    }
  }

  const handleUploadUrl = async () => {
    if (!bandoUrl.trim()) return
    try {
      new URL(bandoUrl.trim())
    } catch {
      setNetworkError('URL non valido. Deve iniziare con https://')
      toast.error('URL non valido.')
      return
    }

    setUploading(true)
    setNetworkError(null)
    setResult(null)

    try {
      const res = await fetch('/api/estrazione-url', withApiKey({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: bandoUrl.trim() }),
      }))
      const data: ExtractionResult = await res.json()
      if (!res.ok) {
        setNetworkError(data.errors?.[0] ?? 'Impossibile elaborare il link.')
        toast.error(data.errors?.[0] ?? 'Impossibile elaborare il link.')
        return
      }
      setResult(data)
      if (data.status === 'duplicato') {
        toast.info('Bando già presente in archivio.')
      } else if (data.bando_id && !data.errors?.length) {
        toast.success('Bando salvato con successo.')
        invalidateAll()
      } else if (data.empty_pdf) {
        toast.error('Pagina vuota o non leggibile.')
      } else if (data.errors?.length) {
        toast.error('Estrazione completata con errori di validazione.')
      }
    } catch {
      setNetworkError('Errore di rete durante il caricamento. Verifica la connessione.')
      toast.error('Errore di rete durante il caricamento.')
    } finally {
      setUploading(false)
    }
  }

  const handleReset = () => {
    setSelectedFile(null)
    setBandoUrl('')
    setMode('pdf')
    setResult(null)
    setNetworkError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const isDuplicate = result?.status === 'duplicato'
  const success = result && result.bando_id && !result.errors?.length && !isDuplicate

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Carica Bando</h1>
        <p className="page-subtitle">Estrai i dati da un PDF e aggiungilo all'archivio</p>
      </div>

      {!result && (
        <div className="ai-disclaimer">
          <IconInfo />
          <span>
            Il testo del bando (un documento pubblico) viene inviato a un modello AI esterno per l'estrazione.
            I dati dei tuoi clienti non vengono mai condivisi con provider esterni: restano nel sistema e il
            confronto con i bandi è calcolato localmente.
          </span>
        </div>
      )}

      {!result && (
        <div className="carica-layout">
          <div className="carica-main">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              style={{ display: 'none' }}
              onChange={handleInputChange}
            />

            <div className="carica-mode-tabs" role="tablist" aria-label="Sorgente del bando">
              <button
                type="button"
                role="tab"
                aria-selected={mode === 'pdf'}
                className={`carica-mode-tab${mode === 'pdf' ? ' active' : ''}`}
                onClick={() => { setMode('pdf'); setNetworkError(null) }}
              >
                <IconUpload /> Carica PDF
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === 'url'}
                className={`carica-mode-tab${mode === 'url' ? ' active' : ''}`}
                onClick={() => { setMode('url'); setNetworkError(null) }}
              >
                <IconLink /> Da URL
              </button>
            </div>

            <div className="card">
              {mode === 'pdf' ? (
                <div
                  className={`upload-zone${dragOver ? ' drag-over' : ''}`}
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={handleDrop}
                  role="button"
                  tabIndex={0}
                  aria-label="Seleziona un file PDF da caricare, o trascinalo qui"
                  onKeyDown={e => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      fileInputRef.current?.click()
                    }
                  }}
                >
                  <div className="upload-zone-icon">
                    <IconUpload />
                  </div>
                  {selectedFile ? (
                    <>
                      <p className="upload-zone-title">{selectedFile.name}</p>
                      <p className="upload-zone-sub">
                        {(selectedFile.size / 1024).toFixed(0)} KB · Clicca per cambiare file
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="upload-zone-title">Trascina il PDF qui, o clicca per selezionare</p>
                      <p className="upload-zone-sub">Solo file PDF · Max 10 MB</p>
                    </>
                  )}
                </div>
              ) : (
                <div className="upload-zone-url">
                  <label htmlFor="bando-url-input" className="upload-zone-title" style={{ display: 'block', marginBottom: 'var(--space-2)' }}>
                    Incolla il link alla pagina del bando o al PDF online
                  </label>
                  <input
                    id="bando-url-input"
                    type="url"
                    inputMode="url"
                    placeholder="https://www.regione.esempio.it/bando-innovazione"
                    className="upload-url-input"
                    value={bandoUrl}
                    onChange={e => setBandoUrl(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter' && bandoUrl.trim()) handleUploadUrl() }}
                  />
                  <p className="upload-zone-sub" style={{ marginTop: 'var(--space-2)' }}>
                    Solo link https:// · pagina web o PDF direttamente online
                  </p>
                </div>
              )}

              <div className="upload-steps">
                <div className="upload-step">
                  <span className="upload-step-num">1</span>
                  <p className="upload-step-text">
                    {mode === 'pdf'
                      ? <><strong>Seleziona il PDF</strong> del bando da analizzare</>
                      : <><strong>Incolla il link</strong> alla pagina o al PDF del bando</>}
                  </p>
                </div>
                <div className="upload-step">
                  <span className="upload-step-num">2</span>
                  <p className="upload-step-text">L'<strong>AI estrae i dati</strong> chiave: scadenze, ATECO, contributi, requisiti</p>
                </div>
                <div className="upload-step">
                  <span className="upload-step-num">3</span>
                  <p className="upload-step-text">Il sistema calcola il <strong>matching automatico</strong> con i tuoi clienti</p>
                </div>
              </div>

              {networkError && (
                <div className="alert alert-danger" style={{ marginTop: 'var(--space-4)' }}>{networkError}</div>
              )}

              {((mode === 'pdf' && selectedFile) || (mode === 'url' && bandoUrl.trim())) && (
                <div style={{ display: 'flex', gap: 'var(--space-3)', marginTop: 'var(--space-4)', justifyContent: 'flex-end' }}>
                  <button className="btn" onClick={handleReset}>Annulla</button>
                  <button
                    className="btn btn-primary"
                    onClick={mode === 'pdf' ? handleUpload : handleUploadUrl}
                    disabled={uploading}
                  >
                    {uploading
                      ? <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Analisi in corso…</>
                      : <><IconUpload /> Estrai e salva</>}
                  </button>
                </div>
              )}

              {uploading && (
                <div style={{ marginTop: 'var(--space-5)' }}>
                  <UploadProgress statuses={uploadStepStatuses(uploading, result)} />
                  <p className="text-sm text-muted" style={{ textAlign: 'center' }}>
                    {extractionWaitMessage()}
                  </p>
                </div>
              )}
            </div>

            <div className="ai-disclaimer">
              <IconInfo />
              <span>
                I dati vengono estratti automaticamente tramite intelligenza artificiale e possono contenere imprecisioni.
                Verifica sempre scadenze, importi e requisiti sulla fonte ufficiale prima di utilizzarli con i clienti.
              </span>
            </div>
          </div>

          <div className="carica-side">
            <p className="carica-side-title">Come funziona</p>

            <div className="feature-card">
              <div className="feature-card-icon"><IconSparkles /></div>
              <p className="feature-card-title">Estrazione AI</p>
              <p className="feature-card-text">
                Il PDF viene letto e interpretato riga per riga: titolo, scadenze, codici ATECO ammessi,
                contributo massimo e requisiti vengono strutturati in pochi secondi.
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-card-icon"><IconTarget /></div>
              <p className="feature-card-title">Matching automatico</p>
              <p className="feature-card-text">
                Ogni bando viene confrontato con l'intera anagrafica clienti: regione, ATECO, dimensione
                e fatturato generano uno score di compatibilità 0-100.
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-card-icon"><IconFile /></div>
              <p className="feature-card-title">Scheda sintetica</p>
              <p className="feature-card-text">
                Ottieni una scheda pronta da condividere con il cliente, con i punti chiave del bando
                e i criteri di ammissibilità già verificati.
              </p>
            </div>
          </div>
        </div>
      )}

      {result && (
        <div style={{ maxWidth: 760 }}>
          <UploadProgress statuses={uploadStepStatuses(uploading, result)} />

          {/* Status banner */}
          {isDuplicate && result.bando_id && (
            <div className="alert alert-warning" style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)', marginBottom: 'var(--space-5)' }}>
              <IconWarning />
              <div style={{ flex: 1 }}>
                <strong>Bando già presente in archivio</strong>
                <p style={{ margin: '4px 0 10px', fontSize: 'var(--text-sm)' }}>
                  Un bando con lo stesso titolo ed ente è già stato salvato (ID #{result.bando_id}).
                  Non è stato creato un duplicato.
                </p>
                <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                  <a
                    href={apiHref(`/api/bandi/${result.bando_id}/scheda.md`)}
                    download
                    className="btn btn-sm"
                  >
                    <IconDownload /> Scarica scheda esistente
                  </a>
                  <a href="/bandi" className="btn btn-sm">
                    Vai ai Bandi
                  </a>
                </div>
              </div>
            </div>
          )}
          {result.empty_pdf && (
            <div className="alert alert-danger" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-5)' }}>
              <IconX />
              Il PDF è vuoto o non contiene testo leggibile. Prova con un PDF non scansionato.
            </div>
          )}
          {result.extraction_error && (
            <div className="alert alert-danger" style={{ marginBottom: 'var(--space-5)' }}>
              <strong>Errore di estrazione:</strong> {result.extraction_error}
            </div>
          )}
          {result.save_error && (
            <div className="alert alert-warning" style={{ marginBottom: 'var(--space-5)' }}>
              <strong>Errore di salvataggio:</strong> {result.save_error}
            </div>
          )}
          {result.errors && result.errors.length > 0 && (
            <div className="alert alert-danger" style={{ marginBottom: 'var(--space-5)' }}>
              <strong>Errori di validazione:</strong>
              <ul style={{ margin: '6px 0 0', paddingLeft: 'var(--space-4)' }}>
                {result.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </div>
          )}
          {success && (
            <div className="alert alert-success" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-5)' }}>
              <IconCheck />
              Bando salvato con successo (ID #{result.bando_id}).
              {result.scadenza_estratta && <> Scadenza: <strong>{result.scadenza_estratta}</strong>.</>}
            </div>
          )}

          {/* File info */}
          <div className="card" style={{ marginBottom: 'var(--space-4)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
              <div style={{
                width: 40, height: 40, background: 'var(--color-accent-soft)',
                borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
              }}>
                <IconFile />
              </div>
              <div>
                <p className="font-bold" style={{ fontSize: 'var(--text-base)' }}>{result.filename}</p>
                <p className="text-muted text-sm">{result.size_kb.toFixed(0)} KB</p>
              </div>
              {result.null_percentage !== undefined && (
                <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
                  <p className="text-xs text-muted">Campi compilati</p>
                  <p className="font-bold" style={{ fontSize: 'var(--text-lg)', color: result.null_percentage > 40 ? 'var(--color-warning)' : 'var(--color-success)' }}>
                    {100 - Math.round(result.null_percentage)}%
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Warnings */}
          {result.warnings && result.warnings.length > 0 && (
            <div className="card" style={{ marginBottom: 'var(--space-4)' }}>
              <p className="result-section-title">Avvertenze</p>
              <ul style={{ margin: 0, paddingLeft: 'var(--space-5)' }}>
                {result.warnings.map((w, i) => (
                  <li key={i} className="text-sm" style={{ color: 'var(--color-warning)', marginBottom: 3 }}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Scheda */}
          {result.scheda && (
            <div className="card" style={{ marginBottom: 'var(--space-4)' }}>
              <p className="result-section-title">Scheda estratta</p>
              <div className="scheda-content">
                {renderMarkdown(result.scheda)}
              </div>
            </div>
          )}


          <div style={{ display: 'flex', gap: 'var(--space-3)', marginTop: 'var(--space-2)' }}>
            <button className="btn btn-primary" onClick={handleReset}>
              <IconUpload /> Carica un altro bando
            </button>
            {success && (
              <>
                <a href="/bandi" className="btn btn-primary">Vai ai Bandi →</a>
                <a href="/" className="btn">Vai alla Dashboard</a>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
