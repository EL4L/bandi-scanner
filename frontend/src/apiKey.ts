// Chiave statica di accesso alle API, iniettata a build-time da Vite
// (VITE_APP_API_KEY). Protegge da abuso casuale di chi trova l'URL pubblico,
// non da un attaccante che ispeziona il bundle JS servito al browser: la
// chiave è per forza presente nel codice client per poter chiamare le API.
// Limite noto e accettato per un tool ad uso interno — vedi
// AUDIT_BANDI_SCANNER.md (D-3) per il contesto completo.
export const API_KEY = import.meta.env.VITE_APP_API_KEY ?? ''

/** Aggiunge l'header X-API-Key alle opzioni di una fetch(). */
export function withApiKey(init: RequestInit = {}): RequestInit {
  return {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      'X-API-Key': API_KEY,
    },
  }
}

/** Aggiunge la chiave come query string, per i link <a href download> che il
 * browser naviga senza poter allegare header custom. */
export function apiHref(path: string): string {
  const sep = path.includes('?') ? '&' : '?'
  return `${path}${sep}api_key=${encodeURIComponent(API_KEY)}`
}
