import { useState } from 'react'
import { TrendingDown, DollarSign, AlertCircle, Shield } from 'lucide-react'
import { SectionHeader, LoadingState, ErrorState, RiskBadge, ConfidenceBar, StatCard } from '../components/UI.jsx'
import AgentFlow from '../components/AgentFlow.jsx'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from 'recharts'
import { api } from '../utils/api.js'
import { fmt } from '../utils/fmt.js'

function ChurnCard({ risk, rank }) {
  const pct = Math.round((risk.churn_probability || 0) * 100)
  const urgencyColor = { critical: 'border-danger/40 bg-danger/5', high: 'border-warn/40 bg-warn/5', medium: 'border-accent/20', low: 'border-success/20' }[risk.urgency] || 'border-border'

  const radarData = [
    { subject: 'Health', value: 100 - (risk.health_score || 50) },
    { subject: 'Engage', value: Math.max(0, 100 - (risk.health_score || 50)) },
    { subject: 'Tickets', value: Math.min(100, (risk.risk_factors?.length || 0) * 15) },
    { subject: 'Trend', value: pct },
    { subject: 'Renewal', value: pct * 0.8 },
  ]

  return (
    <div className={`card border ${urgencyColor} space-y-4`}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-surface border border-border flex items-center justify-center font-display font-700 text-sm text-muted">
            #{rank}
          </div>
          <div>
            <div className="font-display font-700 text-text text-lg">{risk.company}</div>
            <div className="text-xs text-muted">{risk.industry} · {risk.contact_name}</div>
          </div>
        </div>
        <div className="text-right">
          <div
            className="text-3xl font-display font-800"
            style={{ color: pct > 70 ? '#FF3B5C' : pct > 50 ? '#FFB800' : '#00E5FF' }}
          >
            {pct}%
          </div>
          <div className="text-xs text-muted">churn risk</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="bg-void rounded-lg p-2.5">
          <div className="text-muted mb-1">ARR at Risk</div>
          <div className="font-display font-700 text-danger text-base">{fmt.currency(risk.arr)}</div>
        </div>
        <div className="bg-void rounded-lg p-2.5">
          <div className="text-muted mb-1">Health Score</div>
          <div className="font-display font-700 text-text text-base">{risk.health_score}/100</div>
        </div>
      </div>

      {risk.risk_factors?.length > 0 && (
        <div>
          <div className="text-xs text-muted mb-2">Risk Factors</div>
          <div className="space-y-1">
            {risk.risk_factors.map((f, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-text-dim">
                <AlertCircle className="w-3 h-3 text-danger flex-shrink-0 mt-0.5" />
                <span>{f}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="border-t border-border pt-3">
        <div className="flex items-center gap-2 mb-2">
          <Shield className="w-3.5 h-3.5 text-success" />
          <div className="text-xs text-muted font-mono uppercase tracking-wider">Retention Strategy</div>
        </div>
        <div className="text-sm text-text leading-relaxed bg-success/5 border border-success/20 rounded-lg p-3">
          {risk.retention_strategy}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <RiskBadge level={risk.urgency} />
        <span className="text-xs font-mono text-muted">{risk.stage}</span>
      </div>
    </div>
  )
}

export default function ChurnPage() {
  const [topN, setTopN] = useState(3)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function handleRun() {
    setLoading(true)
    setResult(null)
    setError(null)
    try {
      const res = await api.predictChurn({ top_n: topN })
      setResult(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const agentOutputs = result?.data?.agent_outputs || {}
  const completedAgents = result?.data?.completed_agents || []
  const failedAgents = result?.data?.failed_agents || []
  const churnData = agentOutputs?.churn_agent?.data || {}
  const actionData = agentOutputs?.action_agent?.data || {}
  const risks = churnData.top_churn_risks || []
  const explanation = result?.data?.explanation || {}

  return (
    <div className="space-y-6 animate-fade-up">
      <SectionHeader
        title="Churn Intelligence"
        subtitle="Predict customer churn risk from 20-account dataset with custom retention strategies"
      />

      <div className="card">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="text-xs text-muted font-mono block mb-1.5">Top N Risks to Surface</label>
            <select
              value={topN}
              onChange={e => setTopN(parseInt(e.target.value))}
              className="bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none"
            >
              {[3, 5, 7, 10].map(n => <option key={n} value={n}>Top {n}</option>)}
            </select>
          </div>
          <button onClick={handleRun} disabled={loading} className="btn-primary flex items-center gap-2 disabled:opacity-50">
            <TrendingDown className="w-4 h-4" />
            {loading ? 'Analyzing accounts…' : 'Run Churn Prediction'}
          </button>
        </div>
      </div>

      {loading && <LoadingState message="Scoring 20 accounts · generating retention strategies…" />}
      {error && <ErrorState message={error} />}

      {result && !loading && (
        <div className="space-y-6">
          <AgentFlow
            completedAgents={completedAgents}
            failedAgents={failedAgents}
            agentOutputs={agentOutputs}
            taskType="churn_prediction"
          />

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Analyzed" value={churnData.total_analyzed || 0} color="accent" icon={TrendingDown} />
            <StatCard label="Critical Risks" value={churnData.critical_count || 0} color="danger" icon={AlertCircle} />
            <StatCard label="ARR at Risk" value={fmt.currency(churnData.total_arr_at_risk)} color="warn" icon={DollarSign} />
            <StatCard label="Retention Emails" value={actionData.emails_sent || 0} color="success" icon={Shield} />
          </div>

          {explanation.executive_summary && (
            <div className="card bg-plasma/5 border-plasma/20">
              <div className="text-xs text-muted font-mono uppercase tracking-wider mb-2">AI Analysis</div>
              <p className="text-sm text-text leading-relaxed">{explanation.executive_summary}</p>
            </div>
          )}

          {risks.length > 0 && (
            <div className="space-y-4">
              <SectionHeader
                title={`Top ${risks.length} Churn Risks`}
                subtitle={`${fmt.currency(churnData.total_arr_at_risk)} total ARR at risk`}
              />
              <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                {risks.map((risk, i) => <ChurnCard key={i} risk={risk} rank={i + 1} />)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
