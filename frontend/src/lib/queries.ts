// Hook React Query per le fetch di lista condivise cross-pagina (#14).
// Scope minimo: solo le 3 liste (dashboard/bandi/clienti). Le fetch puntuali
// (scheda bando on-demand, dettaglio bandi-compatibili-per-cliente) restano
// fetch dirette come prima — beneficio marginale dalla cache, non incluse
// per limitare la superficie di modifica.
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { withApiKey } from '../apiKey'

async function fetchJson<T = any>(url: string): Promise<T> {
  const res = await fetch(url, withApiKey())
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

const STALE_TIME = 60_000 // 1 minuto: i dati restano "freschi" per la navigazione istantanea

export const useDashboard = <T = any>() =>
  useQuery<T>({ queryKey: ['dashboard'], queryFn: () => fetchJson<T>('/api/dashboard'), staleTime: STALE_TIME })

export const useDashboardBandoDetail = <T = any>(bandoId: number | null) =>
  useQuery<T>({
    queryKey: ['dashboard', 'bando', bandoId],
    queryFn: () => fetchJson<T>(`/api/dashboard/bandi/${bandoId}`),
    enabled: bandoId !== null,
    staleTime: STALE_TIME,
  })

export const useBandi = <T = any>() =>
  useQuery<T>({ queryKey: ['bandi'], queryFn: () => fetchJson<T>('/api/bandi'), staleTime: STALE_TIME })

export const useClienti = <T = any>() =>
  useQuery<T>({ queryKey: ['clienti'], queryFn: () => fetchJson<T>('/api/clienti'), staleTime: STALE_TIME })

/** Invalida tutte le query cross-pagina dopo una mutazione (delete bando,
 * salva/elimina cliente, recalc, deduplica, upload bando). Scelta
 * deliberatamente globale (non granulare per singola queryKey): senza una
 * suite di test frontend, è la strategia più sicura contro dati stantii —
 * nel dubbio rifetcha tutto, mai un'invalidazione dimenticata. Da
 * raffinare in futuro solo se il volume di richieste diventa un problema
 * di performance reale. */
export function useInvalidateAll() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries()
}

/** Helper generico per le mutazioni POST/PUT/DELETE che devono invalidare
 * tutte le liste cross-pagina al successo. */
export function useApiMutation<TVariables = void>(
  mutationFn: (vars: TVariables) => Promise<any>
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries(),
  })
}
