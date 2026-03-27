const BASE = '/api'

let inMemoryToken = ''

export function getAuthToken() {
  return inMemoryToken || ''
}

export function setAuthToken(token) {
  inMemoryToken = token || ''
}

async function request(path, options = {}) {
  const token = getAuthToken()
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
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
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  login: (body) => request('/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  register: (body) => request('/auth/register', { method: 'POST', body: JSON.stringify(body) }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  me: () => request('/auth/me'),
  health: () => request('/health'),
  pipeline: () => request('/pipeline'),
  logs: (sessionId) => request(`/logs${sessionId ? `?session_id=${sessionId}` : ''}`),
  emails: () => request('/emails'),
  sessions: () => request('/sessions'),
  memoryStats: () => request('/memory/stats'),
  products: (limit = 50) => request(`/products?limit=${limit}`),
  createProduct: (body) => request('/products', { method: 'POST', body: JSON.stringify(body) }),
  product: (id) => request(`/products/${id}`),
  updateProduct: (id, body) => request(`/products/${id}`, { method: 'PUT', body: JSON.stringify(body) }),

  runOutreach: (body) =>
    request('/run-outreach', { method: 'POST', body: JSON.stringify(body) }),

  detectRisk: (body) =>
    request('/detect-risk', { method: 'POST', body: JSON.stringify(body) }),

  predictChurn: (body) =>
    request('/predict-churn', { method: 'POST', body: JSON.stringify(body) }),

  sendSequences: (body) =>
    request('/send-sequences', { method: 'POST', body: JSON.stringify(body) }),
}
