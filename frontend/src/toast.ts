// Toast manager — leggero, senza dipendenze esterne.
// Un singleton a livello di modulo: i componenti chiamano `toast.success(...)`
// dentro i loro handler esistenti, ToastHost renderizza lo stack.

export type ToastType = 'success' | 'error' | 'info'

export interface ToastItem {
  id: number
  type: ToastType
  message: string
  leaving?: boolean
}

type Listener = (items: ToastItem[]) => void

let items: ToastItem[] = []
let listeners: Listener[] = []
let nextId = 1

function emit() {
  const snapshot = [...items]
  listeners.forEach(l => l(snapshot))
}

function remove(id: number) {
  const target = items.find(t => t.id === id)
  if (!target || target.leaving) return
  // Marca come "leaving" per l'animazione d'uscita, poi rimuove.
  items = items.map(t => (t.id === id ? { ...t, leaving: true } : t))
  emit()
  setTimeout(() => {
    items = items.filter(t => t.id !== id)
    emit()
  }, 180)
}

function push(type: ToastType, message: string, duration = 4000) {
  const id = nextId++
  items = [...items, { id, type, message }]
  emit()
  if (duration > 0) {
    setTimeout(() => remove(id), duration)
  }
  return id
}

export const toast = {
  success: (message: string) => push('success', message),
  error: (message: string) => push('error', message),
  info: (message: string) => push('info', message),
}

export function subscribeToasts(listener: Listener) {
  listeners.push(listener)
  listener([...items])
  return () => {
    listeners = listeners.filter(l => l !== listener)
  }
}

export function dismissToast(id: number) {
  remove(id)
}
