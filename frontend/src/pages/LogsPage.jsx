import { useState, useEffect, useCallback } from 'react'
import { ScrollText, RefreshCw, Search, Filter } from 'lucide-react'
import { SectionHeader, LoadingState, ErrorState, ConfidenceBar } from '../components/UI.jsx'
import { api } from '../services/api.js'
import { fmt } from '../utils/fmt.js'

const STATUS_DOT = {
  success: 'bg-success',
  failure: 'bg-danger',
  pending: 'bg-accent agent-pulse',
  retrying: 'bg-warn agent-pulse',
  escalated: 'bg-danger animate-pulse',
}

function LogRow({ log, expanded, onToggle }) {
  const dot = STATUS_DOT[log.status] || 'bg-muted'

  return (
    <div className="border-b border-border/30 last:border-0">
      <button
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface/40 transition-colors text-left"
        onClick={onToggle}
      >
        <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dot}`} />
        <div className="w-28 flex-shrink-0">
          <span className="text-xs font-mono text-accent truncate block">{log.agent_name}</span>
        </div>
        <div className="w-32 flex-shrink-0 text-xs font-mono text-text-dim truncate">{log.action}</div>
        <div className="flex-1 text-xs text-muted truncate hidden md:block">{fmt.truncate(log.output_summary, 70)}</div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="w-14 hidden lg:block">
            <ConfidenceBar value={log.confidence} />
          </div>
          <span className="text-xs font-mono text-muted w-20 text-right">{fmt.reltime(log.timestamp)}</span>
          <span className="text-xs text-muted">{expanded ? '▴' : '▾'}</span>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-1 space-y-3 bg-void/50">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div>
              <div className="text-muted font-mono mb-1">SESSION</div>
              <div className="font-mono text-text-dim">{log.session_id}</div>
            </div>
            <div>
              <div className="text-muted font-mono mb-1">TIMESTAMP</div>
              <div className="font-mono text-text-dim">{fmt.datetime(log.timestamp)}</div>
            </div>
            <div>
              <div className="text-muted font-mono mb-1">INPUT</div>
              <div className="text-text-dim">{log.input_summary}</div>
            </div>
            <div>
              <div className="text-muted font-mono mb-1">OUTPUT</div>
              <div className="text-text-dim">{log.output_summary}</div>
            </div>
          </div>
          {log.reasoning && (
            <div>
              <div className="text-muted font-mono text-xs mb-1">AI REASONING</div>
              <div className="text-xs text-text-dim bg-surface rounded-lg p-3 border border-border leading-relaxed italic">
                {log.reasoning}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function LogsPage() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [filterAgent, setFilterAgent] = useState('all')
  const [filterStatus, setFilterStatus] = useState('all')
  const [expanded, setExpanded] = useState(null)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const res = await api.logs()
      setLogs(res.logs || [])
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const agents = ['all', ...new Set(logs.map(l => l.agent_name))]
  const statuses = ['all', 'success', 'failure', 'pending', 'escalated']

  const filtered = logs.filter(l => {
    if (filterAgent !== 'all' && l.agent_name !== filterAgent) return false
    if (filterStatus !== 'all' && l.status !== filterStatus) return false
    if (search && ![l.agent_name, l.action, l.output_summary, l.session_id].some(s => s?.toLowerCase().includes(search.toLowerCase()))) return false
    return true
  })

  const successCount = logs.filter(l => l.status === 'success').length
  const failCount = logs.filter(l => l.status === 'failure').length

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex items-center justify-between">
        <SectionHeader
          title="Audit Logs"
          subtitle={`${logs.length} total entries · ${successCount} success · ${failCount} failed`}
        />
        <button onClick={load} className="btn-ghost flex items-center gap-2 text-xs">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      <div className="card">
        <div className="flex flex-wrap gap-3">
          <div className="flex items-center gap-2 flex-1 min-w-40">
            <Search className="w-4 h-4 text-muted flex-shrink-0" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search logs…"
              className="flex-1 bg-void border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-muted focus:border-accent focus:outline-none"
            />
          </div>
          <select
            value={filterAgent}
            onChange={e => setFilterAgent(e.target.value)}
            className="bg-void border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-accent"
          >
            {agents.map(a => <option key={a} value={a}>{a === 'all' ? 'All agents' : a}</option>)}
          </select>
          <select
            value={filterStatus}
            onChange={e => setFilterStatus(e.target.value)}
            className="bg-void border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-accent"
          >
            {statuses.map(s => <option key={s} value={s}>{s === 'all' ? 'All statuses' : s}</option>)}
          </select>
        </div>
      </div>

      {loading && <LoadingState message="Loading audit logs…" />}
      {error && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && (
        <div className="card p-0 overflow-hidden">
          <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border bg-surface text-xs font-mono text-muted uppercase tracking-wider">
            <div className="w-1.5" />
            <div className="w-28">Agent</div>
            <div className="w-32">Action</div>
            <div className="flex-1 hidden md:block">Output</div>
            <div className="flex-shrink-0">Confidence / Time</div>
          </div>

          {filtered.length === 0 ? (
            <div className="text-center py-12 text-sm text-muted">
              {logs.length === 0 ? 'No logs yet. Run an agent workflow to start.' : 'No logs match your filters.'}
            </div>
          ) : (
            <div className="max-h-[600px] overflow-y-auto">
              {filtered.map((log, i) => (
                <LogRow
                  key={i}
                  log={log}
                  expanded={expanded === i}
                  onToggle={() => setExpanded(expanded === i ? null : i)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
