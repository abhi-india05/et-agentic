import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { AuthProvider, useAuth } from './context/AuthContext.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
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

function AppRoutes() {
  const { isAuthed, authChecked } = useAuth()

  if (!authChecked) return null

  return (
    <Routes>
      {/* Public route */}
      <Route
        path="/login"
        element={isAuthed ? <Navigate to="/" replace /> : <LoginPage />}
      />

      {/* Protected routes — all require auth */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppShell>
              <Overview />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/outreach"
        element={
          <ProtectedRoute>
            <AppShell>
              <OutreachPage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/risks"
        element={
          <ProtectedRoute>
            <AppShell>
              <RisksPage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/churn"
        element={
          <ProtectedRoute>
            <AppShell>
              <ChurnPage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/pipeline"
        element={
          <ProtectedRoute>
            <AppShell>
              <PipelinePage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/products"
        element={
          <ProtectedRoute>
            <AppShell>
              <ProductsPage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/products/:productId"
        element={
          <ProtectedRoute>
            <AppShell>
              <ProductDetailPage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/emails"
        element={
          <ProtectedRoute>
            <AppShell>
              <EmailsPage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/logs"
        element={
          <ProtectedRoute>
            <AppShell>
              <LogsPage />
            </AppShell>
          </ProtectedRoute>
        }
      />

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function AppShell({ children }) {
  return (
    <div className="min-h-screen bg-void bg-grid">
      <Sidebar />
      <main className="ml-56 min-h-screen">
        <div className="max-w-6xl mx-auto px-6 py-8">
          {children}
        </div>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <>
      <Toaster 
        position="top-right"
        toastOptions={{
          style: {
            background: '#18181b', // zinc-900
            color: '#fff',
            border: '1px solid #27272a', // zinc-800
          },
          success: {
            iconTheme: {
              primary: '#10b981', // emerald-500
              secondary: '#fff',
            },
          },
          error: {
            iconTheme: {
              primary: '#ef4444', // red-500
              secondary: '#fff',
            },
          },
        }}
      />
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </>
  )
}
