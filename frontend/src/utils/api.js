const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Network error' }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
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
}
