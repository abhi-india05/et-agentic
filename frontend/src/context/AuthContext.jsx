import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { api, setAuthToken } from '../services/api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)        // { user_id, username, role, is_admin }
  const [isAuthed, setIsAuthed] = useState(false)
  const [authChecked, setAuthChecked] = useState(false)

  // --- Auto-login on mount via /auth/me (cookie-based) ---
  useEffect(() => {
    let cancelled = false
    api.me()
      .then((u) => {
        if (!cancelled) {
          setUser(u)
          setIsAuthed(true)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setUser(null)
          setIsAuthed(false)
        }
      })
      .finally(() => {
        if (!cancelled) setAuthChecked(true)
      })
    return () => { cancelled = true }
  }, [])

  // --- Listen for global 401 expired event ---
  useEffect(() => {
    const onExpired = () => {
      setUser(null)
      setIsAuthed(false)
    }
    window.addEventListener('auth:expired', onExpired)
    return () => window.removeEventListener('auth:expired', onExpired)
  }, [])

  // --- Login ---
  const login = useCallback(async (credentials) => {
    const res = await api.login(credentials)
    setAuthToken(res.access_token)
    // Fetch user info after successful login
    const me = await api.me()
    setUser(me)
    setIsAuthed(true)
    return res
  }, [])

  // --- Register ---
  const register = useCallback(async (credentials) => {
    const res = await api.register(credentials)
    setAuthToken(res.access_token)
    const me = await api.me()
    setUser(me)
    setIsAuthed(true)
    return res
  }, [])

  // --- Logout ---
  const logout = useCallback(async () => {
    try {
      await api.logout()
    } catch {
      // ignore logout errors
    } finally {
      setAuthToken('')
      setUser(null)
      setIsAuthed(false)
    }
  }, [])

  const value = {
    user,
    isAuthed,
    authChecked,
    login,
    register,
    logout,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
