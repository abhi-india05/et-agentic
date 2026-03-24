import { CheckCircle2, XCircle, Clock, AlertCircle } from 'lucide-react'

const AGENT_ORDER = [
  'orchestrator',
  'prospecting_agent',
  'digital_twin_agent',
  'outreach_agent',
  'deal_intelligence_agent',
  'crm_auditor_agent',
  'churn_agent',
  'action_agent',
  'explainability_agent',
  'failure_recovery',
]

const AGENT_LABELS = {
  orchestrator: 'Orchestrator',
  prospecting_agent: 'Prospecting',
  digital_twin_agent: 'Digital Twin',
  outreach_agent: 'Outreach',
  deal_intelligence_agent: 'Deal Intel',
  crm_auditor_agent: 'CRM Audit',
  churn_agent: 'Churn Predict',
  action_agent: 'Action Exec',
  explainability_agent: 'Explainability',
  failure_recovery: 'Recovery',
}

function AgentNode({ name, status, confidence, isLast }) {
  const label = AGENT_LABELS[name] || name

  const stateStyle = {
    success: { icon: CheckCircle2, color: 'text-success', bg: 'bg-success/10 border-success/30' },
    failure: { icon: XCircle, color: 'text-danger', bg: 'bg-danger/10 border-danger/30' },
    pending: { icon: Clock, color: 'text-accent agent-pulse', bg: 'bg-accent/10 border-accent/30' },
    escalated: { icon: AlertCircle, color: 'text-warn', bg: 'bg-warn/10 border-warn/30' },
  }[status] || { icon: Clock, color: 'text-muted', bg: 'bg-muted/5 border-border' }

  const Icon = stateStyle.icon

  return (
    <div className="flex items-center gap-1">
      <div className={`flex flex-col items-center gap-1 px-3 py-2 rounded-lg border ${stateStyle.bg} min-w-[90px]`}>
        <Icon className={`w-3.5 h-3.5 ${stateStyle.color}`} />
        <span className="text-xs font-mono text-text-dim text-center leading-tight">{label}</span>
        {confidence != null && (
          <span className="text-xs font-mono text-muted">{Math.round(confidence * 100)}%</span>
        )}
      </div>
      {!isLast && (
        <div className="w-4 h-px bg-border flex-shrink-0" />
      )}
    </div>
  )
}

export default function AgentFlow({ completedAgents = [], failedAgents = [], agentOutputs = {}, taskType = '' }) {
  const relevantAgents = {
    cold_outreach: ['orchestrator', 'prospecting_agent', 'digital_twin_agent', 'outreach_agent', 'action_agent', 'crm_auditor_agent', 'explainability_agent'],
    risk_detection: ['orchestrator', 'deal_intelligence_agent', 'crm_auditor_agent', 'action_agent', 'explainability_agent'],
    churn_prediction: ['orchestrator', 'churn_agent', 'action_agent', 'explainability_agent'],
  }[taskType] || AGENT_ORDER.slice(0, 5)

  return (
    <div className="card">
      <div className="text-xs text-muted font-mono uppercase tracking-wider mb-3">Agent Execution Flow</div>
      <div className="flex flex-wrap items-center gap-1 overflow-x-auto pb-1">
        {relevantAgents.map((name, i) => {
          const status = failedAgents.includes(name)
            ? 'failure'
            : completedAgents.includes(name)
            ? 'success'
            : 'pending'

          const output = agentOutputs[name]
          const confidence = output?.confidence

          return (
            <AgentNode
              key={name}
              name={name}
              status={status}
              confidence={confidence}
              isLast={i === relevantAgents.length - 1}
            />
          )
        })}
      </div>
    </div>
  )
}
