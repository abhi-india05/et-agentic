import { useState } from 'react'
import { AlertTriangle, TrendingDown, Clock, Zap } from 'lucide-react'
import toast from 'react-hot-toast'
import { SectionHeader, LoadingState, ErrorState, RiskBadge, ConfidenceBar, StatCard } from '../components/UI.jsx'
import AgentFlow from '../components/AgentFlow.jsx'
import { api } from '../services/api.js'
import { fmt } from '../utils/fmt.js'

function RiskCard({ risk }) {
  const [expanded, setExpanded] = useState(false)
  const levelColor = { critical: 'border-danger/40 bg-danger/5', high: 'border-warn/40 bg-warn/5', medium: 'border-accent/20', low: 'border-success/20' }[risk.risk_level] || 'border-border'

  return (
    <div className={`card border ${levelColor} space-y-3`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <RiskBadge level={risk.risk_level} />
            {risk.escalate_to_manager && (
              <span className="badge bg-danger/15 text-danger border border-danger/30 animate-pulse-slow">⚠ Escalated</span>
            )}
          </div>
          <div className="font-display font-700 text-text text-lg">{risk.company}</div>
          <div className="text-xs text-muted font-mono mt-0.5">Deal velocity: {risk.deal_velocity || 'stalled'}</div>
        </div>
        <div className="text-right flex-shrink-0">
          <div className="text-2xl font-display font-800 text-danger">{Math.round((risk.risk_score || 0) * 100)}</div>
          <div className="text-xs text-muted">risk score</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="bg-void rounded-lg p-2.5">
          <div className="text-muted mb-0.5">Days Inactive</div>
          <div className="font-display font-700 text-warn text-lg">{risk.days_inactive}</div>
        </div>
        <div className="bg-void rounded-lg p-2.5">
          <div className="text-muted mb-0.5">Close Probability</div>
          <div className="font-display font-700 text-text text-lg">{fmt.pct(risk.predicted_close_probability)}</div>
        </div>
      </div>

      {risk.risk_signals?.length > 0 && (
        <div>
          <div className="text-xs text-muted mb-1.5">Risk Signals</div>
          <div className="space-y-1">
            {risk.risk_signals.slice(0, 3).map((s, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-text-dim">
                <span className="text-danger mt-0.5 flex-shrink-0">▸</span>
                <span>{s}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="border-t border-border pt-3">
        <div className="text-xs text-muted mb-1">Recovery Strategy</div>
        <div className="text-sm text-text leading-relaxed">{risk.recovery_strategy}</div>
      </div>

      <button onClick={() => setExpanded(!expanded)} className="text-xs text-accent font-mono hover:underline">
        {expanded ? '▾ Hide actions' : '▸ Show recommended actions'}
      </button>

      {expanded && risk.recommended_actions?.length > 0 && (
        <div className="space-y-1.5 pl-2 border-l-2 border-accent/30">
          {risk.recommended_actions.map((a, i) => (
            <div key={i} className="text-xs text-text-dim flex items-start gap-2">
              <span className="text-accent font-mono flex-shrink-0">{i + 1}.</span>
              <span>{a}</span>
            </div>
          ))}
        </div>
      )}

      {risk.competitor_threat && (
        <div className="flex items-center gap-2 text-xs text-warn bg-warn/10 border border-warn/20 rounded-lg px-3 py-2">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          Competitor threat detected{risk.competitor_name ? `: ${risk.competitor_name}` : ''}
        </div>
      )}
    </div>
  )
}

export default function RisksPage() {
  const [form, setForm] = useState({ inactivity_threshold_days: 10, check_all: true })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function handleRun() {
    setLoading(true)
    setResult(null)
    setError(null)
    try {
      const res = await api.detectRisk(form)
      setResult(res)
      toast.success('Risk detection completed')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const agentOutputs = result?.data?.agent_outputs || {}
  const completedAgents = result?.data?.completed_agents || []
  const failedAgents = result?.data?.failed_agents || []
  const dealData = agentOutputs?.deal_intelligence_agent?.data || {}
  const crmData = agentOutputs?.crm_auditor_agent?.data || {}
  const actionData = agentOutputs?.action_agent?.data || {}
  const risks = dealData.risks || []

  return (
    <div className="space-y-6 animate-fade-up">
      <SectionHeader
        title="Deal Risk Detection"
        subtitle="Autonomous detection of at-risk deals with AI-generated recovery strategies"
      />

      <div className="card">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="text-xs text-muted font-mono block mb-1.5">Inactivity Threshold (days)</label>
            <input
              type="number"
              min={1}
              max={90}
              value={form.inactivity_threshold_days}
              onChange={e => setForm({ ...form, inactivity_threshold_days: parseInt(e.target.value) })}
              className="w-32 bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none"
            />
          </div>
          <button onClick={handleRun} disabled={loading} className="btn-primary flex items-center gap-2 disabled:opacity-50">
            <AlertTriangle className="w-4 h-4" />
            {loading ? 'Scanning deals…' : 'Run Risk Detection'}
          </button>
        </div>
      </div>

      {loading && <LoadingState message="Deal Intelligence → CRM Auditor → Action agents running…" />}
      {error && <ErrorState message={error} />}

      {result && !loading && (
        <div className="space-y-6">
          <AgentFlow
            completedAgents={completedAgents}
            failedAgents={failedAgents}
            agentOutputs={agentOutputs}
            taskType="risk_detection"
          />

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="At-Risk Deals" value={dealData.total_at_risk || 0} color="warn" icon={AlertTriangle} />
            <StatCard label="Critical" value={dealData.critical_count || 0} color="danger" icon={TrendingDown} />
            <StatCard label="Missed Follow-ups" value={crmData.missed_followups?.length || 0} color="warn" icon={Clock} />
            <StatCard label="Emails Sent" value={actionData.emails_sent || 0} color="success" icon={Zap} />
          </div>

          {crmData.revenue_at_risk > 0 && (
            <div className="card border-danger/30 bg-danger/5">
              <div className="text-sm text-danger font-display font-600">
                {fmt.currency(crmData.revenue_at_risk)} revenue at risk across {crmData.stuck_deals?.length || 0} stuck deals
              </div>
            </div>
          )}

          {risks.length > 0 ? (
            <div className="space-y-4">
              <SectionHeader title={`${risks.length} At-Risk Deals`} subtitle="Sorted by risk score, highest first" />
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {risks.map((risk, i) => <RiskCard key={i} risk={risk} />)}
              </div>
            </div>
          ) : (
            <div className="card text-center py-8">
              <div className="text-success text-2xl mb-2">✓</div>
              <div className="text-sm text-text">No at-risk deals found for the given threshold</div>
              <div className="text-xs text-muted mt-1">Try lowering the inactivity threshold</div>
            </div>
          )}

          {crmData.missed_followups?.length > 0 && (
            <div className="card">
              <SectionHeader title="Missed Follow-ups" subtitle={`${crmData.missed_followups.length} contacts need attention`} />
              <div className="space-y-2">
                {crmData.missed_followups.slice(0, 5).map((mf, i) => (
                  <div key={i} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0 text-sm">
                    <div>
                      <span className="text-text font-display font-500">{mf.company}</span>
                      <span className="text-muted mx-2">·</span>
                      <span className="text-muted text-xs font-mono">{mf.contact_name}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-warn font-mono text-xs">{mf.days_since_contact}d silent</span>
                      <span className={`badge ${mf.urgency === 'high' ? 'badge-high' : 'badge-medium'}`}>{mf.urgency}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
