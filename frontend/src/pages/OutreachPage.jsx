import { ChevronDown, ChevronUp, ExternalLink, Mail, User, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import AgentFlow from '../components/AgentFlow.jsx'
import { AgentTag, ErrorState, LoadingState, SectionHeader } from '../components/UI.jsx'
import { api } from '../services/api.js'
import { fmt } from '../utils/fmt.js'

const INDUSTRIES = ['SaaS', 'Healthcare', 'Finance', 'Logistics', 'Retail', 'Manufacturing', 'CleanTech', 'AI/ML', 'Cybersecurity', 'EdTech']
const SIZES = ['1-50', '51-200', '201-500', '501-2000', '2000+']

function EmailCard({ email, step }) {
  const [expanded, setExpanded] = useState(step === 1)
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-panel hover:bg-surface transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="w-6 h-6 rounded-full bg-accent/15 text-accent text-xs flex items-center justify-center font-mono font-600">{step}</span>
          <div className="text-left">
            <div className="text-xs text-muted font-mono">Day {email.send_day}</div>
            <div className="text-sm text-text font-display font-500 mt-0.5">{email.subject}</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-muted hidden sm:block">{email.angle}</span>
          {expanded ? <ChevronUp className="w-4 h-4 text-muted" /> : <ChevronDown className="w-4 h-4 text-muted" />}
        </div>
      </button>
      {expanded && (
        <div className="px-4 py-4 bg-void border-t border-border space-y-3">
          <pre className="text-xs text-text-dim font-mono whitespace-pre-wrap leading-relaxed">{email.body}</pre>
          <div className="flex items-center gap-2 pt-2 border-t border-border">
            <span className="text-xs text-muted">CTA:</span>
            <span className="text-xs text-accent font-mono">{email.cta}</span>
          </div>
        </div>
      )}
    </div>
  )
}

function LeadCard({ lead, twin, sequence }) {
  const [showTwin, setShowTwin] = useState(false)
  return (
    <div className="card space-y-4">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-plasma/10 border border-plasma/30 flex items-center justify-center">
            <User className="w-5 h-5 text-plasma" />
          </div>
          <div>
            <div className="font-display font-600 text-text">{lead.name}</div>
            <div className="text-xs text-muted">{lead.title}</div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-muted mb-1">Lead Score</div>
          <div className="text-lg font-display font-700 text-accent">{fmt.pct(lead.score)}</div>
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs">
        <Mail className="w-3.5 h-3.5 text-muted" />
        <span className="font-mono text-text-dim">{lead.email}</span>
        {lead.linkedin && (
          <a href={lead.linkedin} target="_blank" rel="noreferrer" className="text-accent hover:underline flex items-center gap-1 ml-1">
            LinkedIn <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>

      {lead.pain_points?.length > 0 && (
        <div>
          <div className="text-xs text-muted mb-1.5">Pain Points</div>
          <div className="flex flex-wrap gap-1.5">
            {lead.pain_points.map((p, i) => (
              <span key={i} className="text-xs bg-warn/10 border border-warn/20 text-warn px-2 py-0.5 rounded font-mono">{p}</span>
            ))}
          </div>
        </div>
      )}

      {twin && (
        <div>
          <button onClick={() => setShowTwin(!showTwin)} className="text-xs text-accent font-mono hover:underline flex items-center gap-1">
            {showTwin ? '▾' : '▸'} Digital Twin Insights
          </button>
          {showTwin && (
            <div className="mt-2 p-3 bg-void rounded-lg border border-border space-y-2">
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div><span className="text-muted">Style:</span> <span className="text-text font-mono">{twin.buying_style}</span></div>
                <div><span className="text-muted">Risk:</span> <span className="text-text font-mono">{twin.risk_perception}</span></div>
                <div><span className="text-muted">Timeline:</span> <span className="text-text font-mono">{twin.estimated_decision_timeline}</span></div>
                <div><span className="text-muted">Tone:</span> <span className="text-text font-mono">{twin.recommended_tone}</span></div>
              </div>
              {twin.top_objections?.length > 0 && (
                <div>
                  <div className="text-xs text-muted mb-1">Top Objection</div>
                  <div className="text-xs text-danger font-mono">{twin.top_objections[0]?.objection}</div>
                  <div className="text-xs text-success font-mono mt-0.5">↳ {twin.top_objections[0]?.counter_strategy}</div>
                </div>
              )}
              <div className="text-xs text-muted italic">"{twin.opening_hook}"</div>
            </div>
          )}
        </div>
      )}

      {sequence && (
        <div>
          <div className="text-xs text-muted font-mono uppercase tracking-wider mb-3">Email Sequence</div>
          <div className="space-y-2">
            {sequence.emails?.map((email, i) => (
              <EmailCard key={i} email={email} step={i + 1} />
            ))}
          </div>
          {sequence.predicted_reply_rate && (
            <div className="flex gap-4 mt-3 pt-3 border-t border-border text-xs">
              <div><span className="text-muted">Predicted open rate:</span> <span className="text-accent font-mono">{fmt.pct(sequence.predicted_open_rate)}</span></div>
              <div><span className="text-muted">Reply rate:</span> <span className="text-accent font-mono">{fmt.pct(sequence.predicted_reply_rate)}</span></div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function OutreachPage() {
  const [form, setForm] = useState({
    company: '',
    industry: 'SaaS',
    size: '51-200',
    website: '',
    product_name: '',
    product_description: '',
    notes: '',
    auto_send: false,
  })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [draftSequences, setDraftSequences] = useState([])
  const [sender, setSender] = useState({ from_name: 'RevOps AI', from_email: 'sales@revops-ai.com' })
  const [sendingDrafts, setSendingDrafts] = useState(false)
  const [sendSummary, setSendSummary] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.company.trim()) return
    setLoading(true)
    setResult(null)
    setError(null)
    setSendSummary(null)
    try {
      const payload = { ...form }
      if (payload.website && !payload.website.startsWith('http')) {
        payload.website = 'https://' + payload.website
      }
      Object.keys(payload).forEach(k => {
        if (payload[k] === '') payload[k] = null
      })
      const res = await api.runOutreach(payload)
      setResult(res)
      toast.success('Outreach campaign launched successfully')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const agentOutputs = result?.data?.agent_outputs || {}
  const completedAgents = result?.data?.completed_agents || []
  const failedAgents = result?.data?.failed_agents || []
  const prospectData = agentOutputs?.prospecting_agent?.data || {}
  const twinData = agentOutputs?.digital_twin_agent?.data || {}
  const outreachData = agentOutputs?.outreach_agent?.data || {}
  const actionData = agentOutputs?.action_agent?.data || {}
  const explanation = result?.data?.explanation || {}

  const leads = prospectData.leads || []
  const twins = twinData.twin_profiles || []
  const sequences = outreachData.sequences || []

  useEffect(() => {
    if (!sequences.length) {
      setDraftSequences([])
      return
    }
    setDraftSequences(
      sequences.map((seq) => ({
        lead_name: seq.lead_name || '',
        lead_email: seq.lead_email || '',
        sequence_id: seq.sequence_id,
        emails: (seq.emails || []).map((e) => ({
          subject: e.subject || '',
          body: e.body || '',
        })),
      }))
    )
  }, [sequences])

  function updateDraftEmail(seqIdx, emailIdx, field, value) {
    setDraftSequences((prev) =>
      prev.map((seq, i) => {
        if (i !== seqIdx) return seq
        return {
          ...seq,
          emails: seq.emails.map((email, j) => {
            if (j !== emailIdx) return email
            return { ...email, [field]: value }
          }),
        }
      })
    )
  }

  async function handleSendReviewed() {
    if (!draftSequences.length) return
    setSendingDrafts(true)
    setError(null)
    try {
      const payload = {
        sequences: draftSequences.map((seq) => ({
          lead_name: seq.lead_name,
          lead_email: seq.lead_email,
          sequence_id: seq.sequence_id,
          emails: seq.emails.map((e) => ({
            subject: e.subject,
            body: e.body,
            from_name: sender.from_name,
            from_email: sender.from_email,
          })),
        })),
      }
      const res = await api.sendSequences(payload)
      setSendSummary(res.summary || null)
      toast.success('Sequences sent successfully')
    } catch (e) {
      setError(e.message)
    } finally {
      setSendingDrafts(false)
    }
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <SectionHeader
        title="Cold Outreach"
        subtitle="AI-powered prospecting and personalized email sequence generation"
      />

      <div className="card">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-muted font-mono block mb-1.5">Company Name *</label>
              <input
                type="text"
                value={form.company}
                onChange={e => setForm({ ...form, company: e.target.value })}
                placeholder="Acme Corp"
                className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder:text-muted focus:border-accent focus:outline-none transition-colors"
                required
              />
            </div>
            <div>
              <label className="text-xs text-muted font-mono block mb-1.5">Industry</label>
              <select
                value={form.industry}
                onChange={e => setForm({ ...form, industry: e.target.value })}
                className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none transition-colors"
              >
                {INDUSTRIES.map(i => <option key={i} value={i}>{i}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-muted font-mono block mb-1.5">Company Size</label>
              <select
                value={form.size}
                onChange={e => setForm({ ...form, size: e.target.value })}
                className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none transition-colors"
              >
                {SIZES.map(s => <option key={s} value={s}>{s} employees</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-muted font-mono block mb-1.5">Website (optional)</label>
              <input
                type="text"
                value={form.website}
                onChange={e => setForm({ ...form, website: e.target.value })}
                placeholder="https://acme.com"
                className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder:text-muted focus:border-accent focus:outline-none transition-colors"
              />
            </div>
            <div>
              <label className="text-xs text-muted font-mono block mb-1.5">Product Name (optional)</label>
              <input
                type="text"
                value={form.product_name}
                onChange={e => setForm({ ...form, product_name: e.target.value })}
                placeholder="RevOps AI Copilot"
                className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder:text-muted focus:border-accent focus:outline-none transition-colors"
              />
            </div>
          </div>
          <div>
            <label className="text-xs text-muted font-mono block mb-1.5">Product Description (optional)</label>
            <textarea
              value={form.product_description}
              onChange={e => setForm({ ...form, product_description: e.target.value })}
              placeholder="Describe what you want to market, value proposition, and ideal outcomes..."
              rows={2}
              className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder:text-muted focus:border-accent focus:outline-none transition-colors resize-none"
            />
          </div>
          <div>
            <label className="text-xs text-muted font-mono block mb-1.5">Notes (optional)</label>
            <textarea
              value={form.notes}
              onChange={e => setForm({ ...form, notes: e.target.value })}
              placeholder="Any specific context about this prospect..."
              rows={2}
              className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder:text-muted focus:border-accent focus:outline-none transition-colors resize-none"
            />
          </div>
          <label className="flex items-center gap-2 text-xs text-muted font-mono">
            <input
              type="checkbox"
              checked={!!form.auto_send}
              onChange={e => setForm({ ...form, auto_send: e.target.checked })}
              className="accent-cyan-400"
            />
            Auto-send immediately after generation (disable for human review)
          </label>
          <button type="submit" disabled={loading} className="btn-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
            <Zap className="w-4 h-4" />
            {loading ? 'Running agents…' : 'Launch Outreach Campaign'}
          </button>
        </form>
      </div>

      {loading && <LoadingState message="Orchestrating prospecting → digital twin → outreach agents…" />}
      {error && <ErrorState message={error} />}

      {result && !loading && (
        <div className="space-y-6">
          <AgentFlow
            completedAgents={completedAgents}
            failedAgents={failedAgents}
            agentOutputs={agentOutputs}
            taskType="cold_outreach"
          />

          {explanation.executive_summary && (
            <div className="card bg-accent/5 border-accent/20">
              <div className="text-xs text-muted font-mono uppercase tracking-wider mb-2">AI Summary</div>
              <p className="text-sm text-text leading-relaxed">{explanation.executive_summary}</p>
              <div className="flex flex-wrap gap-2 mt-3">
                {completedAgents.map(a => <AgentTag key={a} name={a} status="success" />)}
                {failedAgents.map(a => <AgentTag key={a} name={a} status="failure" />)}
              </div>
            </div>
          )}

          {actionData.emails_sent > 0 && (
            <div className="card border-success/20 bg-success/5">
              <div className="text-sm text-success font-display font-600">
                ✓ {actionData.emails_sent} emails queued · {actionData.crm_updates || 0} CRM updates
              </div>
            </div>
          )}

          {!form.auto_send && draftSequences.length > 0 && (
            <div className="card space-y-4 border-accent/25 bg-accent/5">
              <div>
                <div className="text-sm font-display font-700 text-text">Review Before Send (Human-in-the-loop)</div>
                <div className="text-xs text-muted mt-1">Edit sender and message content before delivery.</div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-muted font-mono block mb-1.5">Sender Name</label>
                  <input
                    type="text"
                    value={sender.from_name}
                    onChange={e => setSender({ ...sender, from_name: e.target.value })}
                    className="w-full bg-void border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted font-mono block mb-1.5">Sender Email</label>
                  <input
                    type="email"
                    value={sender.from_email}
                    onChange={e => setSender({ ...sender, from_email: e.target.value })}
                    className="w-full bg-void border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
                  />
                </div>
              </div>

              <div className="space-y-4">
                {draftSequences.map((seq, seqIdx) => (
                  <div key={seq.sequence_id || seqIdx} className="border border-border rounded-lg p-3 space-y-3 bg-panel">
                    <div className="text-xs text-muted font-mono">
                      {seq.lead_name || 'Lead'} · {seq.lead_email || 'no-email'}
                    </div>
                    {seq.emails.map((email, emailIdx) => (
                      <div key={emailIdx} className="space-y-2 border-t border-border pt-2">
                        <div className="text-xs text-muted font-mono">Email #{emailIdx + 1}</div>
                        <input
                          type="text"
                          value={email.subject}
                          onChange={e => updateDraftEmail(seqIdx, emailIdx, 'subject', e.target.value)}
                          className="w-full bg-void border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
                        />
                        <textarea
                          value={email.body}
                          onChange={e => updateDraftEmail(seqIdx, emailIdx, 'body', e.target.value)}
                          rows={5}
                          className="w-full bg-void border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent focus:outline-none resize-y font-mono"
                        />
                      </div>
                    ))}
                  </div>
                ))}
              </div>

              <button
                onClick={handleSendReviewed}
                disabled={sendingDrafts}
                className="btn-primary flex items-center gap-2 disabled:opacity-50"
              >
                <Mail className="w-4 h-4" />
                {sendingDrafts ? 'Sending reviewed drafts…' : 'Send Reviewed Emails'}
              </button>

              {sendSummary && (
                <div className="text-xs text-success font-mono">
                  Sent: {sendSummary.sent || 0} · Failed: {sendSummary.failed || 0} · Sequences: {sendSummary.total_sequences || 0}
                </div>
              )}
            </div>
          )}

          {leads.length > 0 && (
            <div className="space-y-4">
              <SectionHeader title={`${leads.length} Qualified Leads`} subtitle={`ICP fit: ${fmt.pct(prospectData.icp_fit_score)}`} />
              {leads.map((lead, i) => (
                <LeadCard
                  key={i}
                  lead={lead}
                  twin={twins[i]}
                  sequence={sequences[i]}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
