import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Lock, LogIn, User } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'

export default function LoginPage() {
  const navigate = useNavigate()
  const { login, register: authRegister } = useAuth()
  const [form, setForm] = useState({ username: '', password: '' })
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.username || !form.password) {
      setError('Enter username and password.')
      return
    }
    setLoading(true)
    setError('')
    try {
      if (mode === 'register') {
        await authRegister(form)
      } else {
        await login(form)
      }
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-void bg-grid flex items-center justify-center px-4">
      <div className="w-full max-w-md card space-y-5">
        <div>
          <h1 className="text-xl font-display font-700 text-text">
            {mode === 'register' ? 'Create your account' : 'Sign in to RevOps AI'}
          </h1>
          <p className="text-xs text-muted mt-1">
            {mode === 'register'
              ? 'Register to access agent workflows and protected APIs.'
              : 'Authenticate to access agent workflows and protected APIs.'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <label className="block">
            <span className="text-xs text-muted font-mono block mb-1.5">Username</span>
            <div className="relative">
              <User className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input
                type="text"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                className="w-full bg-void border border-border rounded-lg pl-9 pr-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none"
              />
            </div>
          </label>

          <label className="block">
            <span className="text-xs text-muted font-mono block mb-1.5">Password</span>
            <div className="relative">
              <Lock className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="w-full bg-void border border-border rounded-lg pl-9 pr-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none"
              />
            </div>
          </label>

          {error ? <div className="text-xs text-danger font-mono">{error}</div> : null}

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50"
          >
            <LogIn className="w-4 h-4" />
            {loading
              ? (mode === 'register' ? 'Creating account…' : 'Signing in…')
              : (mode === 'register' ? 'Create account' : 'Sign in')}
          </button>

          <button
            type="button"
            disabled={loading}
            onClick={() => { setMode(mode === 'register' ? 'login' : 'register'); setError('') }}
            className="w-full text-xs text-muted font-mono hover:text-text transition"
          >
            {mode === 'register'
              ? 'Have an account? Sign in'
              : 'New here? Create an account'}
          </button>
        </form>
      </div>
    </div>
  )
}
