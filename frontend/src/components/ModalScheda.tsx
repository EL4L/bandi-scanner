import { apiHref } from '../apiKey'
import { useModalA11y } from '../useModalA11y'
import { renderMarkdown } from '../lib/renderMarkdown'

export interface SchedaModalData {
  id: number
  titolo: string | null
  scheda: string
  fonte_url?: string | null
}

function IconDownload() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
}
function IconExternal() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
}
function IconClose() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16 }}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
}

interface Props {
  data: SchedaModalData
  onClose: () => void
}

export function ModalScheda({ data, onClose }: Props) {
  const modalRef = useModalA11y(onClose)

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal modal-lg"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-scheda-title"
        ref={modalRef}
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <p className="modal-title" id="modal-scheda-title">{data.titolo || `Bando #${data.id}`}</p>
            <p className="modal-subtitle">Scheda di sintesi</p>
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
            <a href={apiHref(`/api/bandi/${data.id}/scheda.md`)} download className="btn btn-sm">
              <IconDownload /> Scarica
            </a>
            {data.fonte_url && (
              <a href={data.fonte_url} target="_blank" rel="noopener noreferrer" className="btn btn-sm">
                <IconExternal /> Fonte
              </a>
            )}
            <button className="modal-close" onClick={onClose} aria-label="Chiudi">
              <IconClose />
            </button>
          </div>
        </div>
        <div className="modal-body">
          <div className="scheda-content">
            {data.scheda
              ? renderMarkdown(data.scheda)
              : <p className="text-muted">Scheda non disponibile per questo bando.</p>
            }
          </div>
        </div>
      </div>
    </div>
  )
}
