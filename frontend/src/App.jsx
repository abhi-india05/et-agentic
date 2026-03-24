import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar.jsx'
import Overview from './pages/Overview.jsx'
import OutreachPage from './pages/OutreachPage.jsx'
import RisksPage from './pages/RisksPage.jsx'
import ChurnPage from './pages/ChurnPage.jsx'
import PipelinePage from './pages/PipelinePage.jsx'
import EmailsPage from './pages/EmailsPage.jsx'
import LogsPage from './pages/LogsPage.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-void bg-grid">
        <Sidebar />
        <main className="ml-56 min-h-screen">
          <div className="max-w-6xl mx-auto px-6 py-8">
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/outreach" element={<OutreachPage />} />
              <Route path="/risks" element={<RisksPage />} />
              <Route path="/churn" element={<ChurnPage />} />
              <Route path="/pipeline" element={<PipelinePage />} />
              <Route path="/emails" element={<EmailsPage />} />
              <Route path="/logs" element={<LogsPage />} />
            </Routes>
          </div>
        </main>
      </div>
    </BrowserRouter>
  )
}
