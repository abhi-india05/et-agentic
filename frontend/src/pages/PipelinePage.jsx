import { useState, useEffect } from 'react'
import { Activity, RefreshCw, TrendingUp } from 'lucide-react'
import { SectionHeader, LoadingState, ErrorState, RiskBadge, StatCard } from '../components/UI.jsx'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { api } from '../services/api.js'
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

const STAGE_ORDER = ['Prospecting', 'Discovery', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost', 'Re-engagement']

function AccountRow({ acc }) {
  const health = acc.health_score || 0
  const healthColor = health >= 70 ? 'text-success' : health >= 40 ? 'text-warn' : 'text-danger'
  const daysAgo = fmt.reltime(acc.last_activity)

  return (
    <tr className="border-b border-border/40 hover:bg-surface/50 transition-colors">
      <td className="py-3 px-4">
        <div className="font-display font-500 text-text text-sm">{acc.company}</div>
        <div className="text-xs text-muted font-mono">{acc.contact_name}</div>
      </td>
      <td className="py-3 px-4">
        <span
          className="text-xs font-mono px-2 py-0.5 rounded border"
          style={{
            color: STAGE_COLORS[acc.stage] || '#4B5E7A',
            borderColor: (STAGE_COLORS[acc.stage] || '#4B5E7A') + '40',
            background: (STAGE_COLORS[acc.stage] || '#4B5E7A') + '15',
          }}
        >
          {acc.stage}
        </span>
      </td>
      <td className="py-3 px-4 text-right">
        <div className="text-sm font-mono text-text">{fmt.currency(acc.deal_value)}</div>
      </td>
      <td className="py-3 px-4 text-center">
        <span className={`text-sm font-display font-700 ${healthColor}`}>{health}</span>
      </td>
      <td className="py-3 px-4 text-right text-xs text-muted font-mono">{daysAgo}</td>
      <td className="py-3 px-4 text-right text-xs font-mono text-text-dim">{acc.industry}</td>
    </tr>
  )
}

export default function PipelinePage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('All')
  const [sortBy, setSortBy] = useState('deal_value')

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const res = await api.pipeline()
      setData(res)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <LoadingState message="Loading pipeline…" />
  if (error) return <ErrorState message={error} onRetry={loadData} />

  const stages = data?.stats?.stages || {}
  const accounts = data?.accounts || []
  const totalPipeline = data?.stats?.total_pipeline_value || 0

  const pieData = Object.entries(stages)
    .map(([stage, info]) => ({ name: stage, value: info.total_value, count: info.count }))
    .filter(d => d.value > 0)

  const filteredAccounts = accounts
    .filter(a => filter === 'All' || a.stage === filter)
    .sort((a, b) => {
      if (sortBy === 'deal_value') return b.deal_value - a.deal_value
      if (sortBy === 'health') return b.health_score - a.health_score
      if (sortBy === 'activity') return new Date(b.last_activity) - new Date(a.last_activity)
      return 0
    })

  const activeStages = Object.keys(stages).filter(s => s !== 'Closed Lost')
  const avgHealth = accounts.length > 0
    ? Math.round(accounts.reduce((s, a) => s + (a.health_score || 0), 0) / accounts.length)
    : 0

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex items-center justify-between">
        <SectionHeader
          title="Pipeline Overview"
          subtitle={`${accounts.length} accounts · ${fmt.currency(totalPipeline)} total value`}
        />
        <button onClick={loadData} className="btn-ghost flex items-center gap-2 text-xs">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Pipeline" value={fmt.currency(totalPipeline)} color="accent" icon={TrendingUp} />
        <StatCard label="Active Deals" value={accounts.filter(a => !['Closed Won', 'Closed Lost'].includes(a.stage)).length} color="plasma" icon={Activity} />
        <StatCard label="Avg Health" value={`${avgHealth}/100`} color={avgHealth >= 70 ? 'success' : avgHealth >= 40 ? 'warn' : 'danger'} />
        <StatCard label="Closed Won" value={fmt.currency(stages['Closed Won']?.total_value || 0)} color="success" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card lg:col-span-1">
          <div className="text-xs text-muted font-mono uppercase tracking-wider mb-4">Value by Stage</div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={90}
                paddingAngle={3}
                dataKey="value"
              >
                {pieData.map((d, i) => (
                  <Cell key={i} fill={STAGE_COLORS[d.name] || '#4B5E7A'} fillOpacity={0.85} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #1E2D45', borderRadius: 8, fontSize: 12 }}
                formatter={(val) => [fmt.currency(val), 'Value']}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1.5 mt-2">
            {pieData.slice(0, 5).map(d => (
              <div key={d.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ background: STAGE_COLORS[d.name] || '#4B5E7A' }} />
                  <span className="text-text-dim">{d.name}</span>
                </div>
                <span className="font-mono text-muted">{d.count} · {fmt.currency(d.value)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card lg:col-span-2 overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <div className="text-xs text-muted font-mono uppercase tracking-wider">All Accounts</div>
            <div className="flex items-center gap-2">
              <select
                value={filter}
                onChange={e => setFilter(e.target.value)}
                className="bg-void border border-border rounded-lg px-2 py-1.5 text-xs text-text focus:outline-none focus:border-accent"
              >
                <option value="All">All stages</option>
                {STAGE_ORDER.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value)}
                className="bg-void border border-border rounded-lg px-2 py-1.5 text-xs text-text focus:outline-none focus:border-accent"
              >
                <option value="deal_value">Sort: Value</option>
                <option value="health">Sort: Health</option>
                <option value="activity">Sort: Activity</option>
              </select>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-muted font-mono uppercase tracking-wider">
                  <th className="py-2 px-4 text-left">Company</th>
                  <th className="py-2 px-4 text-left">Stage</th>
                  <th className="py-2 px-4 text-right">Value</th>
                  <th className="py-2 px-4 text-center">Health</th>
                  <th className="py-2 px-4 text-right">Activity</th>
                  <th className="py-2 px-4 text-right">Industry</th>
                </tr>
              </thead>
              <tbody>
                {filteredAccounts.map((acc, i) => <AccountRow key={i} acc={acc} />)}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
