import { Building2, ChevronRight, History, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState, SectionHeader } from '../components/UI.jsx'
import { api } from '../services/api.js'
import { fmt } from '../utils/fmt.js'

const STATUS_CLASS = {
  completed: 'bg-success/10 text-success border-success/30',
  completed_with_errors: 'bg-warn/10 text-warn border-warn/30',
  running: 'bg-accent/10 text-accent border-accent/30',
  failed: 'bg-danger/10 text-danger border-danger/30',
  pending: 'bg-muted/20 text-muted border-muted/30',
}

function StatusBadge({ status }) {
  const normalized = String(status || 'pending').toLowerCase()
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono uppercase border ${STATUS_CLASS[normalized] || STATUS_CLASS.pending}`}>
      {normalized.replace(/_/g, ' ')}
    </span>
  )
}

export default function OutreachHistoryPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadHistory()
  }, [])

  async function loadHistory() {
    setLoading(true)
    setError(null)
    try {
      const response = await api.outreachSessions()
      setItems(response.items || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex items-center justify-between gap-3">
        <SectionHeader
          title="Outreach History"
          subtitle="Review previous outreach runs and resume any workflow"
        />
        <button onClick={loadHistory} className="btn-ghost flex items-center gap-2 text-xs">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {loading && <LoadingState message="Loading outreach sessions..." />}
      {error && <ErrorState message={error} onRetry={loadHistory} />}

      {!loading && !error && (
        <div className="card p-0 overflow-hidden">
          {items.length === 0 ? (
            <EmptyState
              icon={History}
              title="No outreach sessions yet"
              description="Run a cold outreach workflow to see history here."
            />
          ) : (
            <div className="divide-y divide-border/60">
              {items.map((item) => (
                <button
                  key={item.session_id}
                  onClick={() => navigate(`/outreach/${item.session_id}`)}
                  className="w-full text-left px-4 py-3 hover:bg-surface/50 transition-colors"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center gap-2">
                        <Building2 className="w-4 h-4 text-accent flex-shrink-0" />
                        <span className="text-sm font-display font-600 text-text truncate">{item.company || 'Unknown company'}</span>
                        <StatusBadge status={item.status} />
                      </div>
                      <div className="text-xs text-muted font-mono">
                        {item.industry || 'Unknown industry'}
                        {item.product_name ? ` · ${item.product_name}` : ''}
                      </div>
                      <div className="text-xs text-muted">Created {fmt.datetime(item.created_at)}</div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-muted flex-shrink-0 mt-1" />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
