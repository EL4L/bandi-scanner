import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Dashboard from './components/Dashboard'
import DashboardBandoDetail from './components/DashboardBandoDetail'
import Bandi from './components/Bandi'
import Clienti from './components/Clienti'
import CaricaBando from './components/CaricaBando'
import ToastHost from './components/ToastHost'
import './dashboard.css'

function IconGrid() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  )
}

function IconFileText() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  )
}

function IconUsers() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  )
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

function Sidebar() {
  const location = useLocation()
  const navClass = ({ isActive }: { isActive: boolean }) =>
    'sidebar-nav-item' + (isActive ? ' active' : '')

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-logo" aria-label="BandoMatch AI">
          <img
            src="/bandomatch-ai-logo.jpeg"
            alt="BandoMatch AI"
            className="sidebar-logo-image"
          />
        </div>
      </div>

      <nav className="sidebar-nav">
        <NavLink to="/" end className={({ isActive }) =>
          'sidebar-nav-item' + (isActive || location.pathname.startsWith('/dashboard/') ? ' active' : '')}>
          <IconGrid /> Dashboard
        </NavLink>
        <NavLink to="/bandi" className={navClass}>
          <IconFileText /> Bandi
        </NavLink>
        <NavLink to="/clienti" className={navClass}>
          <IconUsers /> Clienti
        </NavLink>
        <NavLink to="/carica" className={navClass}>
          <IconUpload /> Carica Bando
        </NavLink>
      </nav>

      <div className="sidebar-footer">
        <p className="sidebar-version">BandoMatch AI · v1.0</p>
      </div>
    </aside>
  )
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, retry: 1 } },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="layout">
          <Sidebar />
          <main className="main-content">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/dashboard/bandi/:bandoId" element={<DashboardBandoDetail />} />
              <Route path="/bandi" element={<Bandi />} />
              <Route path="/clienti" element={<Clienti />} />
              <Route path="/carica" element={<CaricaBando />} />
            </Routes>
          </main>
          <ToastHost />
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
