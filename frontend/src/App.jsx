import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useEffect, useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import Overview from './pages/Overview.jsx'
import OutreachPage from './pages/OutreachPage.jsx'
import RisksPage from './pages/RisksPage.jsx'
import ChurnPage from './pages/ChurnPage.jsx'
import PipelinePage from './pages/PipelinePage.jsx'
import EmailsPage from './pages/EmailsPage.jsx'
import LogsPage from './pages/LogsPage.jsx'
import ProductsPage from './pages/ProductsPage.jsx'
import ProductDetailPage from './pages/ProductDetailPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import { api, setAuthToken } from './utils/api.js'

export default function App() {
  const [isAuthed, setIsAuthed] = useState(false)
  const [authChecked, setAuthChecked] = useState(false)

  useEffect(() => {
    const onExpired = () => setIsAuthed(false)
    window.addEventListener('auth:expired', onExpired)
    return () => window.removeEventListener('auth:expired', onExpired)
  }, [])

  useEffect(() => {
    let cancelled = false
    api.me()
      .then(() => {
        if (!cancelled) setIsAuthed(true)
      })
      .catch(() => {
        if (!cancelled) setIsAuthed(false)
      })
      .finally(() => {
        if (!cancelled) setAuthChecked(true)
      })
    return () => { cancelled = true }
  }, [])

  if (!authChecked) {
    return null
  }

  if (!isAuthed) {
    return <LoginPage onLogin={() => setIsAuthed(true)} />
  }

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-void bg-grid">
        <Sidebar onLogout={() => {
          api.logout().catch(() => {})
            .finally(() => {
              setAuthToken('')
              setIsAuthed(false)
            })
        }} />
        <main className="ml-56 min-h-screen">
          <div className="max-w-6xl mx-auto px-6 py-8">
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/outreach" element={<OutreachPage />} />
              <Route path="/risks" element={<RisksPage />} />
              <Route path="/churn" element={<ChurnPage />} />
              <Route path="/pipeline" element={<PipelinePage />} />
              <Route path="/products" element={<ProductsPage />} />
              <Route path="/products/:productId" element={<ProductDetailPage />} />
              <Route path="/emails" element={<EmailsPage />} />
              <Route path="/logs" element={<LogsPage />} />
            </Routes>
          </div>
        </main>
      </div>
    </BrowserRouter>
  )
}
