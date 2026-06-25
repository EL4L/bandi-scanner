import { useRef, useState } from 'react'

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

function renderMarkdown(text: string) {
  const lines = text.split('\n')
  const elements: React.ReactNode[] = []
  let listItems: string[] = []
  let listKey = 0

  const inlineParse = (s: string): React.ReactNode => {
    const parts = s.split(/(\*\*[^*]+\*\*)/)
    return parts.map((p, i) =>
      p.startsWith('**') && p.endsWith('**')
        ? <strong key={i}>{p.slice(2, -2)}</strong>
        : p
    )
  }

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`ul-${listKey++}`}>
          {listItems.map((item, i) => <li key={i}>{inlineParse(item)}</li>)}
        </ul>
      )
      listItems = []
    }
  }

  lines.forEach((line, i) => {
    if (line.startsWith('# '))      { flushList(); elements.push(<h1 key={i}>{line.slice(2)}</h1>) }
    else if (line.startsWith('## ')){ flushList(); elements.push(<h2 key={i}>{line.slice(3)}</h2>) }
    else if (line.startsWith('### ')){ flushList(); elements.push(<h3 key={i}>{line.slice(4)}</h3>) }
    else if (line.startsWith('- ') || line.startsWith('* ')) { listItems.push(line.slice(2)) }
    else if (line.trim() === '') { flushList() }
    else { flushList(); elements.push(<p key={i}>{inlineParse(line)}</p>) }
  })
  flushList()
  return <>{elements}</>
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

export default function CaricaBando() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<ExtractionResult | null>(null)
  const [networkError, setNetworkError] = useState<string | null>(null)

  const handleFile = (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setNetworkError('Formato non supportato. Carica un file PDF.')
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
      const res = await fetch('/api/estrazione', { method: 'POST', body: fd })
      const data: ExtractionResult = await res.json()
      setResult(data)
    } catch {
      setNetworkError('Errore di rete durante il caricamento. Verifica la connessione.')
    } finally {
      setUploading(false)
    }
  }

  const handleReset = () => {
    setSelectedFile(null)
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
        <div className="card" style={{ maxWidth: 640 }}>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            style={{ display: 'none' }}
            onChange={handleInputChange}
          />

          <div
            className={`upload-zone${dragOver ? ' drag-over' : ''}`}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
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

          {networkError && (
            <div className="alert alert-danger" style={{ marginTop: 14 }}>{networkError}</div>
          )}

          {selectedFile && (
            <div style={{ display: 'flex', gap: 10, marginTop: 16, justifyContent: 'flex-end' }}>
              <button className="btn" onClick={handleReset}>Annulla</button>
              <button
                className="btn btn-primary"
                onClick={handleUpload}
                disabled={uploading}
              >
                {uploading
                  ? <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Analisi in corso…</>
                  : <><IconUpload /> Estrai e salva</>}
              </button>
            </div>
          )}

          {uploading && (
            <div className="alert alert-info" style={{ marginTop: 14 }}>
              Estrazione in corso — può richiedere fino a 30 secondi. Attendere.
            </div>
          )}
        </div>
      )}

      {result && (
        <div style={{ maxWidth: 760 }}>
          {/* Status banner */}
          {isDuplicate && result.bando_id && (
            <div className="alert alert-warning" style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 20 }}>
              <IconWarning />
              <div style={{ flex: 1 }}>
                <strong>Bando già presente in archivio</strong>
                <p style={{ margin: '4px 0 10px', fontSize: '0.875rem' }}>
                  Un bando con lo stesso titolo ed ente è già stato salvato (ID #{result.bando_id}).
                  Non è stato creato un duplicato.
                </p>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <a
                    href={`/api/bandi/${result.bando_id}/scheda.md`}
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
            <div className="alert alert-danger" style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
              <IconX />
              Il PDF è vuoto o non contiene testo leggibile. Prova con un PDF non scansionato.
            </div>
          )}
          {result.extraction_error && (
            <div className="alert alert-danger" style={{ marginBottom: 20 }}>
              <strong>Errore di estrazione:</strong> {result.extraction_error}
            </div>
          )}
          {result.save_error && (
            <div className="alert alert-warning" style={{ marginBottom: 20 }}>
              <strong>Errore di salvataggio:</strong> {result.save_error}
            </div>
          )}
          {result.errors && result.errors.length > 0 && (
            <div className="alert alert-danger" style={{ marginBottom: 20 }}>
              <strong>Errori di validazione:</strong>
              <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
                {result.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </div>
          )}
          {success && (
            <div className="alert alert-success" style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
              <IconCheck />
              Bando salvato con successo (ID #{result.bando_id}).
              {result.scadenza_estratta && <> Scadenza: <strong>{result.scadenza_estratta}</strong>.</>}
            </div>
          )}

          {/* File info */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                width: 40, height: 40, background: 'var(--color-accent-soft)',
                borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
              }}>
                <IconFile />
              </div>
              <div>
                <p className="font-bold" style={{ fontSize: '0.9rem' }}>{result.filename}</p>
                <p className="text-muted text-sm">{result.size_kb.toFixed(0)} KB</p>
              </div>
              {result.null_percentage !== undefined && (
                <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
                  <p className="text-xs text-muted">Campi compilati</p>
                  <p className="font-bold" style={{ fontSize: '1.1rem', color: result.null_percentage > 40 ? 'var(--color-warning)' : 'var(--color-success)' }}>
                    {100 - Math.round(result.null_percentage)}%
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Warnings */}
          {result.warnings && result.warnings.length > 0 && (
            <div className="card" style={{ marginBottom: 16 }}>
              <p className="result-section-title">Avvertenze</p>
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {result.warnings.map((w, i) => (
                  <li key={i} className="text-sm" style={{ color: 'var(--color-warning)', marginBottom: 3 }}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Scheda */}
          {result.scheda && (
            <div className="card" style={{ marginBottom: 16 }}>
              <p className="result-section-title">Scheda estratta</p>
              <div className="scheda-content">
                {renderMarkdown(result.scheda)}
              </div>
            </div>
          )}

          {/* Raw JSON */}
          {result.data && (
            <details style={{ marginBottom: 16 }}>
              <summary className="text-sm font-medium" style={{ cursor: 'pointer', color: 'var(--color-text-muted)', padding: '8px 0' }}>
                Dati JSON estratti (debug)
              </summary>
              <div className="json-view" style={{ marginTop: 8 }}>
                {JSON.stringify(result.data, null, 2)}
              </div>
            </details>
          )}

          <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
            <button className="btn btn-primary" onClick={handleReset}>
              <IconUpload /> Carica un altro bando
            </button>
            {success && (
              <a href="/" className="btn">Vai alla Dashboard</a>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
