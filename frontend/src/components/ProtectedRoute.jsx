import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

/**
 * Route wrapper that redirects unauthenticated users to /login.
 * Use inside <Routes>:
 *   <Route path="/products" element={<ProtectedRoute><ProductsPage /></ProtectedRoute>} />
 */
export default function ProtectedRoute({ children }) {
  const { isAuthed, authChecked } = useAuth()

  if (!authChecked) return null // still checking session

  if (!isAuthed) return <Navigate to="/login" replace />

  return children
}
