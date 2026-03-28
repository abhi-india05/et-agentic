/**
 * Centralized API layer — single source for all backend calls.
 *
 * Features:
 *  - In-memory access token + httpOnly cookie dual-auth
 *  - Global 401 handling via CustomEvent('auth:expired')
 *  - Pagination header extraction (X-Page, X-Page-Size, X-Total-Count)
 *  - Consistent error parsing
 */

const BASE = '/api'

let inMemoryToken = ''

export function getAuthToken() {
  return inMemoryToken || ''
}

export function setAuthToken(token) {
  inMemoryToken = token || ''
}

/**
 * Core request helper.
 * @param {string} path - API path (e.g. '/auth/login')
 * @param {RequestInit} options - fetch options
 * @returns {Promise<any>} parsed JSON, null for 204
 */
async function request(path, options = {}) {
  const token = getAuthToken()
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  }

  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    ...options,
    headers,
  })

  if (res.status === 401) {
    setAuthToken('')
    window.dispatchEvent(new CustomEvent('auth:expired'))
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Network error' }))
    const msg = typeof err.detail === 'string'
      ? err.detail
      : err.message || `HTTP ${res.status}`
    throw new Error(msg)
  }

  if (res.status === 204) return null
  return res.json()
}

/**
 * Extended request that also returns pagination headers from the response.
 * Used specifically by list endpoints.
 * @returns {Promise<{ data: any[], pagination: { page, pageSize, total } }>}
 */
async function requestWithPagination(path, options = {}) {
  const token = getAuthToken()
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  }

  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    ...options,
    headers,
  })

  if (res.status === 401) {
    setAuthToken('')
    window.dispatchEvent(new CustomEvent('auth:expired'))
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Network error' }))
    const msg = typeof err.detail === 'string'
      ? err.detail
      : err.message || `HTTP ${res.status}`
    throw new Error(msg)
  }

  const data = await res.json()
  const pagination = {
    page: parseInt(res.headers.get('X-Page') || '1', 10),
    pageSize: parseInt(res.headers.get('X-Page-Size') || '20', 10),
    total: parseInt(res.headers.get('X-Total-Count') || '0', 10),
  }

  return { data, pagination }
}

// ---------------------------------------------------------------------------
// Public API object
// ---------------------------------------------------------------------------

export const api = {
  // --- Auth ---
  login: (body) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify(body) }),

  register: (body) =>
    request('/auth/register', { method: 'POST', body: JSON.stringify(body) }),

  logout: () =>
    request('/auth/logout', { method: 'POST' }),

  me: () =>
    request('/auth/me'),

  refresh: (body) =>
    request('/auth/refresh', { method: 'POST', body: body ? JSON.stringify(body) : '{}' }),

  // --- Health ---
  health: () => request('/health'),

  // --- Pipeline & Workflows ---
  pipeline: () => request('/pipeline'),
  logs: (sessionId) =>
    request(`/logs${sessionId ? `?session_id=${sessionId}` : ''}`),
  emails: () => request('/emails'),
  sessions: () => request('/sessions'),
  memoryStats: () => request('/memory/stats'),

  // --- Products (full CRUD + pagination + filters) ---
  products: ({ page = 1, pageSize = 20, name, createdFrom, createdTo, includeDeleted = false } = {}) => {
    const params = new URLSearchParams()
    params.set('page', String(page))
    params.set('page_size', String(pageSize))
    if (name) params.set('name', name)
    if (createdFrom) params.set('created_from', createdFrom)
    if (createdTo) params.set('created_to', createdTo)
    if (includeDeleted) params.set('include_deleted', 'true')
    return requestWithPagination(`/products?${params.toString()}`)
  },

  createProduct: (body) =>
    request('/products', { method: 'POST', body: JSON.stringify(body) }),

  product: (id) =>
    request(`/products/${id}`),

  updateProduct: (id, body) =>
    request(`/products/${id}`, { method: 'PUT', body: JSON.stringify(body) }),

  deleteProduct: (id) =>
    request(`/products/${id}`, { method: 'DELETE' }),

  // --- Agent Workflows ---
  runOutreach: (body) =>
    request('/run-outreach', { method: 'POST', body: JSON.stringify(body) }),

  detectRisk: (body) =>
    request('/detect-risk', { method: 'POST', body: JSON.stringify(body) }),

  predictChurn: (body) =>
    request('/predict-churn', { method: 'POST', body: JSON.stringify(body) }),

  sendSequences: (body) =>
    request('/send-sequences', { method: 'POST', body: JSON.stringify(body) }),
}
