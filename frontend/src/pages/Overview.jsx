import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, AlertTriangle, TrendingDown, Zap, DollarSign, Mail, CheckCircle, Clock } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { StatCard, LoadingState, ErrorState, SectionHeader } from '../components/UI.jsx'
import { api } from '../utils/api.js'
import { fmt } from '../utils/fmt.js'

const STAGE_COLORS = {
  'Discovery': '#00E5FF',
  'Proposal': '#7C3AED',
  'Negotiation': '#FFB800',
  'Closed Won': '#00E676',
  'Closed Lost': '#FF3B5C',
  'Prospecting': '#4B5E7A',
  'Re-engagement': '#FF6B35',
}

export default function Overview() {
  const navigate = useNavigate()
  const [pipeline, setPipeline] = useState(null)
  const [health, setHealth] = useState(null)
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 15000)
    return () => clearInterval(interval)
  }, [])

  async function loadData() {
    try {
      const [p, h, l] = await Promise.all([api.pipeline(), api.health(), api.logs()])
      setPipeline(p)
      setHealth(h)
      setLogs(l.logs?.slice(0, 6) || [])
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <LoadingState message="Loading dashboard…" />
  if (error) return <ErrorState message={error} onRetry={loadData} />

  const stages = pipeline?.stats?.stages || {}
  const chartData = Object.entries(stages).map(([stage, info]) => ({
    stage: stage.replace(' ', '\n'),
    count: info.count,
    value: info.total_value,
    color: STAGE_COLORS[stage] || '#4B5E7A',
  }))

  const totalPipeline = pipeline?.stats?.total_pipeline_value || 0
  const totalAccounts = pipeline?.stats?.total_accounts || 0
  const emailStats = health?.email_stats || {}
  const memStats = health?.vector_store || {}

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-800 text-text">
            Revenue <span className="text-gradient-accent">Intelligence</span>
          </h1>
          <p className="text-sm text-muted mt-1">Autonomous multi-agent sales operations · live</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
          <span className="text-xs font-mono text-muted">System operational</span>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Pipeline Value"
          value={fmt.currency(totalPipeline)}
          sub={`${totalAccounts} total accounts`}
          color="accent"
          icon={DollarSign}
        />
        <StatCard
          label="Emails Sent"
          value={fmt.num(emailStats.sent || 0)}
          sub={`${fmt.pct(emailStats.success_rate || 0)} success rate`}
          color="plasma"
          icon={Mail}
        />
        <StatCard
          label="Agent Memory"
          value={fmt.num(memStats.total_documents || 0)}
          sub="interactions stored"
          color="success"
          icon={CheckCircle}
        />
        <StatCard
          label="Active Agents"
          value="10"
          sub="all systems nominal"
          color="warn"
          icon={Activity}
        />
      </div>

      {/* Pipeline Chart + Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card lg:col-span-2">
          <SectionHeader title="Pipeline Distribution" subtitle="Deals by stage" />
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="stage" tick={{ fontSize: 11, fill: '#4B5E7A', fontFamily: 'JetBrains Mono' }} />
              <YAxis tick={{ fontSize: 11, fill: '#4B5E7A' }} />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #1E2D45', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: '#C8D8F0' }}
                formatter={(val, name) => [name === 'count' ? val : fmt.currency(val), name]}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {chartData.map((d, i) => <Cell key={i} fill={d.color} fillOpacity={0.85} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card flex flex-col gap-3">
          <div className="text-xs text-muted font-mono uppercase tracking-wider">Quick Actions</div>
          <button onClick={() => navigate('/outreach')} className="btn-primary w-full flex items-center justify-center gap-2">
            <Zap className="w-4 h-4" /> Run Cold Outreach
          </button>
          <button onClick={() => navigate('/risks')} className="btn-ghost w-full flex items-center justify-center gap-2">
            <AlertTriangle className="w-4 h-4" /> Detect Deal Risks
          </button>
          <button onClick={() => navigate('/churn')} className="btn-ghost w-full flex items-center justify-center gap-2">
            <TrendingDown className="w-4 h-4" /> Predict Churn
          </button>
          <div className="mt-auto pt-3 border-t border-border space-y-2">
            {Object.entries(stages).slice(0, 4).map(([stage, info]) => (
              <div key={stage} className="flex items-center justify-between text-xs">
                <span className="text-muted font-mono">{stage}</span>
                <span className="text-text font-mono">{info.count} · {fmt.currency(info.total_value)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Logs */}
      <div className="card">
        <SectionHeader
          title="Recent Agent Activity"
          subtitle="Latest audit log entries"
          action={
            <button onClick={() => navigate('/logs')} className="btn-ghost text-xs">
              View all →
            </button>
          }
        />
        {logs.length === 0 ? (
          <p className="text-sm text-muted text-center py-6">No activity yet. Run an agent workflow to see logs.</p>
        ) : (
          <div className="space-y-2">
            {logs.map((log, i) => (
              <div key={i} className="flex items-center gap-3 py-2 border-b border-border/50 last:border-0">
                <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${log.status === 'success' ? 'bg-success' : 'bg-danger'}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-accent">{log.agent_name}</span>
                    <span className="text-xs text-muted">·</span>
                    <span className="text-xs text-text-dim truncate">{log.action}</span>
                  </div>
                  <div className="text-xs text-muted truncate mt-0.5">{fmt.truncate(log.output_summary, 80)}</div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="text-xs font-mono text-muted">{fmt.reltime(log.timestamp)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
