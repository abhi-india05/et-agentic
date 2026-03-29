/**
 * Centralized API layer — single source for all backend calls.
 *
 * Features:
 *  - In-memory access token + httpOnly cookie dual-auth
 *  - Global 401 handling via CustomEvent('auth:expired')
 *  - Pagination header extraction (X-Page, X-Page-Size, X-Total-Count)
 *  - Consistent error parsing
 */

import toast from 'react-hot-toast'

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
      : err.error?.message || err.message || `HTTP ${res.status}`
    toast.error(msg)
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
      : err.error?.message || err.message || `HTTP ${res.status}`
    toast.error(msg)
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
  deleteLog: (logId) =>
    request(`/logs/${encodeURIComponent(logId)}`, { method: 'DELETE' }),
  clearLogs: ({ sessionId } = {}) =>
    request(`/logs${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''}`, { method: 'DELETE' }),
  emails: () => request('/emails'),
  sessions: () => request('/sessions'),
  memoryStats: () => request('/memory/stats'),

  // --- Agent Workflows ---
  runOutreach: (body) =>
    request('/run-outreach', { method: 'POST', body: JSON.stringify(body) }),

  detectRisk: (body) =>
    request('/detect-risk', { method: 'POST', body: JSON.stringify(body) }),

  predictChurn: (body) =>
    request('/predict-churn', { method: 'POST', body: JSON.stringify(body) }),

  sendSequences: (body) =>
    request('/send-sequences', { method: 'POST', body: JSON.stringify(body) }),

  sendLeadEmail: (body) =>
    request('/send-sequences', { method: 'POST', body: JSON.stringify(body) }),

  refineOutreachEmail: (body) =>
    request('/outreach/refine-email', { method: 'POST', body: JSON.stringify(body) }),

  customers: ({ page = 1, pageSize = 50, query } = {}) => {
    const params = new URLSearchParams()
    params.set('page', String(page))
    params.set('page_size', String(pageSize))
    if (query) params.set('query', query)
    return request(`/outreach/customers?${params.toString()}`)
  },

  customerDetail: (customerId) =>
    request(`/outreach/customers/${encodeURIComponent(customerId)}`),

  createCustomer: (body) =>
    request('/outreach/customers', { method: 'POST', body: JSON.stringify(body) }),

  markCustomerReplied: (customerId) =>
    request(`/outreach/customers/${encodeURIComponent(customerId)}/mark-replied`, { method: 'PATCH' }),

  addCustomerFromEntry: (entryId, body) =>
    request(`/outreach/customers/from-entry/${encodeURIComponent(entryId)}`, {
      method: 'POST',
      body: JSON.stringify(body || {}),
    }),

  // --- Outreach Sessions (history / resume) ---
  outreachSessions: ({ page = 1, pageSize = 50 } = {}) => {
    const params = new URLSearchParams()
    params.set('page', String(page))
    params.set('page_size', String(pageSize))
    return request(`/outreach/sessions?${params.toString()}`)
  },

  outreachSession: (sessionId) =>
    request(`/outreach/sessions/${encodeURIComponent(sessionId)}`),

  // --- Outreach Entries ---
  outreachEntries: ({ page = 1, pageSize = 50, status, company, } = {}) => {
    const params = new URLSearchParams()
    params.set('page', String(page))
    params.set('page_size', String(pageSize))
    if (status) params.set('status', status)
    if (company) params.set('company', company)
    // Note: outreach endpoints are mapped under /outreach
    return requestWithPagination(`/outreach/entries?${params.toString()}`)
  },

  updateOutreachStatus: (id, status) =>
    request(`/outreach/entries/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
}
