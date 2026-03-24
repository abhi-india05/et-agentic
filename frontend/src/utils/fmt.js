export const fmt = {
  currency: (n) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n || 0),

  pct: (n) => `${((n || 0) * 100).toFixed(1)}%`,

  num: (n) => new Intl.NumberFormat('en-US').format(n || 0),

  date: (s) => {
    if (!s) return '—'
    try {
      return new Date(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    } catch { return s }
  },

  datetime: (s) => {
    if (!s) return '—'
    try {
      return new Date(s).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    } catch { return s }
  },

  reltime: (s) => {
    if (!s) return '—'
    const diff = Date.now() - new Date(s).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    return `${Math.floor(hrs / 24)}d ago`
  },

  truncate: (s, n = 80) => s && s.length > n ? s.slice(0, n) + '…' : (s || ''),

  riskColor: (level) => {
    const map = { critical: 'danger', high: 'warn', medium: 'accent', low: 'success' }
    return map[level?.toLowerCase()] || 'muted'
  },

  statusBadge: (status) => {
    const map = {
      success: 'badge-success',
      failure: 'badge-failure',
      pending: 'badge-medium',
      retrying: 'badge-high',
      escalated: 'badge-critical',
    }
    return map[status] || 'badge-medium'
  },

  confidencePct: (n) => `${Math.round((n || 0) * 100)}%`,
}
