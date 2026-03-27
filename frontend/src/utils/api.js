const BASE = '/api'

const AUTH_TOKEN_KEY = 'revops_access_token'

export function getAuthToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY) || ''
}

export function setAuthToken(token) {
  if (!token) {
    localStorage.removeItem(AUTH_TOKEN_KEY)
    return
  }
  localStorage.setItem(AUTH_TOKEN_KEY, token)
}

async function request(path, options = {}) {
  const token = getAuthToken()
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
    ...options,
  })
  if (res.status === 401) {
    setAuthToken('')
    window.dispatchEvent(new CustomEvent('auth:expired'))
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Network error' }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  login: (body) => request('/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  health: () => request('/health'),
  pipeline: () => request('/pipeline'),
  logs: (sessionId) => request(`/logs${sessionId ? `?session_id=${sessionId}` : ''}`),
  emails: () => request('/emails'),
  sessions: () => request('/sessions'),
  memoryStats: () => request('/memory/stats'),

  runOutreach: (body) =>
    request('/run-outreach', { method: 'POST', body: JSON.stringify(body) }),

  detectRisk: (body) =>
    request('/detect-risk', { method: 'POST', body: JSON.stringify(body) }),

  predictChurn: (body) =>
    request('/predict-churn', { method: 'POST', body: JSON.stringify(body) }),

  sendSequences: (body) =>
    request('/send-sequences', { method: 'POST', body: JSON.stringify(body) }),
}
