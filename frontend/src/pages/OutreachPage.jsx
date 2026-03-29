import { ChevronDown, ChevronUp, ExternalLink, History, Mail, Play, RotateCcw, User, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { useParams } from 'react-router-dom'
import AgentFlow from '../components/AgentFlow.jsx'
import { AgentTag, ErrorState, LoadingState, SectionHeader } from '../components/UI.jsx'
import { api } from '../services/api.js'
import { fmt } from '../utils/fmt.js'

const INDUSTRIES = ['SaaS', 'Healthcare', 'Finance', 'Logistics', 'Retail', 'Manufacturing', 'CleanTech', 'AI/ML', 'Cybersecurity', 'EdTech']
const SIZES = ['1-50', '51-200', '201-500', '501-2000', '2000+']
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function getLeadKey(sequence, index = 0) {
  return sequence?.lead_id || sequence?.sequence_id || sequence?.lead_email || `lead-${index}`
}

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

function SelectedLeadSourceCard({ lead }) {
  const [expanded, setExpanded] = useState(false)
  const linkedinUrl = lead.linkedin_url || lead.linkedin || ''
  const role = lead.role || lead.title || 'Unknown role'
  const aboutText = lead.about || lead.raw_data?.summary || ''
  const hasLongAbout = aboutText.length > 220

  return (
    <div className="card space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-display font-700 text-text">{lead.name || 'Unknown name'}</div>
          <div className="text-xs text-muted mt-1">{role}</div>
          <div className="text-xs text-muted">{lead.company || 'Unknown company'}</div>
        </div>
        {lead.id && (
          <div className="text-[10px] text-muted font-mono break-all max-w-[180px] text-right">ID: {lead.id}</div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
        <div className="space-y-1">
          <div className="text-muted font-mono uppercase tracking-wider">LinkedIn</div>
          {linkedinUrl ? (
            <a
              href={linkedinUrl}
              target="_blank"
              rel="noreferrer"
              className="text-accent hover:underline break-all inline-flex items-center gap-1"
            >
              {linkedinUrl}
              <ExternalLink className="w-3 h-3" />
            </a>
          ) : (
            <div className="text-text-dim">No LinkedIn URL available</div>
          )}
        </div>

        <div className="space-y-1">
          <div className="text-muted font-mono uppercase tracking-wider">Email</div>
          <div className="text-text-dim break-all">{lead.email || 'No email available'}</div>
        </div>
      </div>

      <div className="space-y-1">
        <div className="text-muted font-mono uppercase tracking-wider text-xs">Headline</div>
        <div className="text-xs text-text-dim leading-relaxed">{lead.headline || 'No headline available'}</div>
      </div>

      <div className="space-y-1">
        <div className="text-muted font-mono uppercase tracking-wider text-xs">About</div>
        <div className={`text-xs text-text-dim leading-relaxed whitespace-pre-wrap ${expanded ? '' : 'max-h-20 overflow-hidden'}`}>
          {aboutText || 'No about section available'}
        </div>
        {hasLongAbout && (
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-accent hover:underline font-mono"
          >
            {expanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </div>
    </div>
  )
}

function LeadCard({ lead, sequence, twin }) {
  const linkedinUrl = lead.linkedin_url || lead.linkedin
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
        <span className="font-mono text-text-dim">{lead.email || 'No email available'}</span>
        {linkedinUrl && (
          <a href={linkedinUrl} target="_blank" rel="noreferrer" className="text-accent hover:underline flex items-center gap-1 ml-1">
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
          <div className="text-xs text-muted mb-1.5">Twin Enrichment</div>
          <div className="flex flex-wrap gap-1.5">
            {twin.buying_style && (
              <span className="text-xs bg-info/10 border border-info/30 text-info px-2 py-0.5 rounded font-mono">Style: {twin.buying_style}</span>
            )}
            {twin.recommended_tone && (
              <span className="text-xs bg-accent/10 border border-accent/30 text-accent px-2 py-0.5 rounded font-mono">Tone: {twin.recommended_tone}</span>
            )}
            {twin.risk_perception && (
              <span className="text-xs bg-danger/10 border border-danger/30 text-danger px-2 py-0.5 rounded font-mono">Risk: {twin.risk_perception}</span>
            )}
          </div>
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

function DigitalTwinCard({ twin, lead }) {
  const leadName = lead?.name || twin?.buyer_name || 'Unknown lead'
  const leadRole = lead?.title || twin?.buyer_title || 'Unknown role'
  const personaSummary = twin?.persona_summary || twin?.opening_hook || 'No persona summary available'
  const inferredPriorities = Array.isArray(twin?.inferred_priorities)
    ? twin.inferred_priorities
    : (Array.isArray(twin?.primary_motivations) ? twin.primary_motivations : [])
  const extractedSignals = Array.isArray(twin?.signals_extracted)
    ? twin.signals_extracted
    : (Array.isArray(twin?.decision_criteria) ? twin.decision_criteria : [])
  const hasConfidence = typeof twin?.confidence_score === 'number'

  return (
    <div className="card space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-display font-700 text-text">{leadName}</div>
          <div className="text-xs text-muted mt-1">{leadRole}</div>
        </div>
        {hasConfidence && (
          <div className="text-xs text-muted font-mono">Confidence: {fmt.pct(twin.confidence_score)}</div>
        )}
      </div>

      <div className="space-y-1">
        <div className="text-xs text-muted uppercase tracking-wider font-mono">Persona Summary</div>
        <div className="text-xs text-text-dim leading-relaxed">{personaSummary}</div>
      </div>

      <div className="space-y-1">
        <div className="text-xs text-muted uppercase tracking-wider font-mono">Inferred Priorities</div>
        {inferredPriorities.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {inferredPriorities.map((priority, idx) => (
              <span key={idx} className="text-xs bg-accent/10 border border-accent/30 text-accent px-2 py-0.5 rounded font-mono">{priority}</span>
            ))}
          </div>
        ) : (
          <div className="text-xs text-text-dim">No inferred priorities available</div>
        )}
      </div>

      <div className="space-y-1">
        <div className="text-xs text-muted uppercase tracking-wider font-mono">Signals Extracted</div>
        {extractedSignals.length > 0 ? (
          <ul className="space-y-1">
            {extractedSignals.map((signal, idx) => (
              <li key={idx} className="text-xs text-text-dim leading-relaxed">• {signal}</li>
            ))}
          </ul>
        ) : (
          <div className="text-xs text-text-dim">No extracted signals available</div>
        )}
      </div>

      {twin?.top_objections?.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-muted">Top Objection</div>
          <div className="text-xs text-danger font-mono">{twin.top_objections[0]?.objection}</div>
          <div className="text-xs text-success font-mono">↳ {twin.top_objections[0]?.counter_strategy}</div>
        </div>
      )}

      {twin?.opening_hook && (
        <div className="text-xs text-muted italic">"{twin.opening_hook}"</div>
      )}
    </div>
  )
}

function LogsTab({ sessionId }) {
  const defaultForm = {
    company: '',
    industry: 'SaaS',
    size: '51-200',
    website: '',
    product_name: '',
    product_description: '',
    notes: '',
    auto_send: false,
  }
  const [form, setForm] = useState(defaultForm)
  const [loading, setLoading] = useState(false)
  const [hydratingSession, setHydratingSession] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [draftSequences, setDraftSequences] = useState([])
  const [sender, setSender] = useState({ from_name: 'RevOps AI', from_email: 'sales@revops-ai.com' })
  const [sendingDrafts, setSendingDrafts] = useState(false)
  const [sendSummary, setSendSummary] = useState(null)
  const [editedEmails, setEditedEmails] = useState({})
  const [emailErrors, setEmailErrors] = useState({})

  function logAgentTerminalStatus(finalOutput, source) {
    const outputs = finalOutput?.agent_outputs || {}
    const prospectingStatus = outputs?.prospecting_agent?.status || 'unknown'
    const digitalTwinStatus = outputs?.digital_twin_agent?.status || 'unknown'
    const prospectingTag = prospectingStatus === 'success' ? 'SUCCESS' : 'FAILURE'
    const digitalTwinTag = digitalTwinStatus === 'success' ? 'SUCCESS' : 'FAILURE'
    console.log(`[FRONTEND][${source}][prospecting_agent][${prospectingTag}] status=${prospectingStatus}`)
    console.log(`[FRONTEND][${source}][digital_twin_agent][${digitalTwinTag}] status=${digitalTwinStatus}`)
  }

  useEffect(() => {
    if (!sessionId) {
      setHydratingSession(false)
      setError(null)
      setResult(null)
      setForm(defaultForm)
      return
    }

    let cancelled = false

    async function loadSession() {
      setHydratingSession(true)
      setError(null)
      try {
        const session = await api.outreachSession(sessionId)
        if (cancelled) return

        const input = session.input_data || {}
        const productContext = typeof input.product_context === 'object' && input.product_context !== null
          ? input.product_context
          : {}

        setForm({
          company: input.company || '',
          industry: input.industry || 'SaaS',
          size: input.size || '51-200',
          website: input.website || '',
          product_name: input.product_name || productContext.name || '',
          product_description: input.product_description || productContext.description || '',
          notes: input.notes || '',
          auto_send: Boolean(input.auto_send),
        })

        const fallbackFinalOutput = {
          session_id: session.session_id,
          status: session.status,
          plan: session.plan || {},
          agent_outputs: session.agent_outputs || {},
          completed_agents: [],
          failed_agents: [],
          explanation: {},
        }
        const hydratedFinalOutput = session.final_output && typeof session.final_output === 'object'
          ? session.final_output
          : fallbackFinalOutput

        setResult({
          session_id: session.session_id,
          task_type: hydratedFinalOutput.task_type || 'outreach',
          status: session.status || hydratedFinalOutput.status || 'completed',
          data: hydratedFinalOutput,
        })
        logAgentTerminalStatus(hydratedFinalOutput, 'resume-load')
      } catch (e) {
        if (cancelled) return
        setError(e.message)
        console.error(`[FRONTEND][resume-load][FAILURE] ${e.message}`)
      } finally {
        if (!cancelled) {
          setHydratingSession(false)
        }
      }
    }

    loadSession()
    return () => {
      cancelled = true
    }
  }, [sessionId])

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
      setEditedEmails({})
      setEmailErrors({})
      return
    }

    const nextDrafts = sequences.map((seq, idx) => ({
      lead_id: seq.lead_id || getLeadKey(seq, idx),
      lead_name: seq.lead_name || '',
      lead_email: seq.lead_email || '',
      sequence_id: seq.sequence_id,
      emails: (seq.emails || []).map((e) => ({
        subject: e.subject || '',
        body: e.body || '',
      })),
    }))
    setDraftSequences(nextDrafts)

    const nextEditedEmails = {}
    nextDrafts.forEach((seq, idx) => {
      const leadKey = getLeadKey(seq, idx)
      nextEditedEmails[leadKey] = seq.lead_email || ''
    })
    setEditedEmails(nextEditedEmails)
    setEmailErrors({})
  }, [sequences])

  async function runWorkflow({ clearExisting } = { clearExisting: true }) {
    if (!form.company.trim()) return
    setLoading(true)
    if (clearExisting) {
      setResult(null)
    }
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
      logAgentTerminalStatus(res?.data || {}, 'run-outreach')
      toast.success(sessionId ? 'Workflow continued successfully' : 'Outreach campaign launched successfully')
    } catch (e) {
      setError(e.message)
      console.error(`[FRONTEND][run-outreach][FAILURE] ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    await runWorkflow({ clearExisting: true })
  }

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

  function updateRecipientEmail(leadKey, value) {
    setEditedEmails((prev) => ({
      ...prev,
      [leadKey]: value,
    }))
    setEmailErrors((prev) => {
      if (!prev[leadKey]) return prev
      const next = { ...prev }
      if (EMAIL_RE.test(String(value || '').trim())) {
        delete next[leadKey]
      }
      return next
    })
  }

  async function handleSendReviewed() {
    if (!draftSequences.length) return
    setSendingDrafts(true)
    setError(null)
    try {
      const nextEmailErrors = {}
      draftSequences.forEach((seq, seqIdx) => {
        const leadKey = getLeadKey(seq, seqIdx)
        const recipientEmail = String(editedEmails[leadKey] ?? seq.lead_email ?? '').trim()
        if (!EMAIL_RE.test(recipientEmail)) {
          nextEmailErrors[leadKey] = recipientEmail ? 'Invalid email format' : 'Enter recipient email'
        }
      })

      if (Object.keys(nextEmailErrors).length > 0) {
        setEmailErrors(nextEmailErrors)
        setError('Please fix invalid recipient emails before sending.')
        toast.error('Please fix invalid recipient emails before sending.')
        return
      }

      const payload = {
        sequences: draftSequences.map((seq, seqIdx) => {
          const leadKey = getLeadKey(seq, seqIdx)
          const recipientEmail = String(editedEmails[leadKey] ?? seq.lead_email ?? '').trim()
          return {
            lead_id: seq.lead_id || leadKey,
            lead_name: seq.lead_name,
            lead_email: recipientEmail,
            email: recipientEmail,
            sequence_id: seq.sequence_id,
            emails: seq.emails.map((e) => ({
              subject: e.subject,
              body: e.body,
              from_name: sender.from_name,
              from_email: sender.from_email,
            })),
          }
        }),
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

      {sessionId && (
        <div className="card border-accent/25 bg-accent/5 space-y-3">
          <div className="flex items-center gap-2 text-sm font-display font-700 text-text">
            <History className="w-4 h-4 text-accent" />
            Resumed Session
          </div>
          <div className="text-xs text-muted font-mono break-all">{sessionId}</div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => runWorkflow({ clearExisting: false })}
              disabled={loading || hydratingSession}
              className="btn-primary flex items-center gap-2 disabled:opacity-50"
            >
              <Play className="w-4 h-4" />
              Continue Workflow
            </button>
            <button
              type="button"
              onClick={() => runWorkflow({ clearExisting: true })}
              disabled={loading || hydratingSession}
              className="btn-ghost flex items-center gap-2 disabled:opacity-50"
            >
              <RotateCcw className="w-4 h-4" />
              Regenerate
            </button>
          </div>
        </div>
      )}

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
          <button type="submit" disabled={loading || hydratingSession} className="btn-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
            <Zap className="w-4 h-4" />
            {loading ? 'Running agents…' : sessionId ? 'Run Workflow From Loaded Session' : 'Launch Outreach Campaign'}
          </button>
        </form>
      </div>

      {hydratingSession && <LoadingState message="Loading saved outreach workflow..." />}
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

          {leads.length > 0 && (
            <div className="space-y-4">
              <SectionHeader title="Selected Leads" subtitle="Raw LinkedIn leads returned by the prospecting stage" />
              <div className="max-h-[34rem] overflow-y-auto pr-1 custom-scrollbar space-y-3">
                {leads.map((lead, i) => (
                  <SelectedLeadSourceCard
                    key={lead.id || lead.lead_id || i}
                    lead={lead}
                  />
                ))}
              </div>
            </div>
          )}

          {twins.length > 0 && (
            <div className="space-y-4">
              <SectionHeader title="Digital Twin Insights" subtitle="Persona and behavioral insights from the digital twin agent" />
              {twins.map((twin, i) => (
                <DigitalTwinCard
                  key={leads[i]?.id || twin?.buyer_name || i}
                  twin={twin}
                  lead={leads[i]}
                />
              ))}
            </div>
          )}

          {leads.length > 0 && (
            <div className="space-y-4">
              <SectionHeader title="Qualified Leads" subtitle={`${leads.length} leads · ICP fit: ${fmt.pct(prospectData.icp_fit_score)}`} />
              {leads.map((lead, i) => (
                <LeadCard
                  key={lead.id || i}
                  lead={lead}
                  sequence={sequences[i]}
                  twin={twins[i]}
                />
              ))}
            </div>
          )}

          {!form.auto_send && draftSequences.length > 0 && (
            <div className="space-y-4">
              <SectionHeader title="Review Before Sending" subtitle="Human-in-the-loop final review and recipient control" />
              <div className="card space-y-4 border-accent/25 bg-accent/5">
                <div>
                  <div className="text-sm font-display font-700 text-text">Review Before Send (Human-in-the-loop)</div>
                  <div className="text-xs text-muted mt-1">Edit sender, recipient email, and message content before delivery.</div>
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
                  {draftSequences.map((seq, seqIdx) => {
                    const leadKey = getLeadKey(seq, seqIdx)
                    return (
                      <div key={seq.sequence_id || seqIdx} className="border border-border rounded-lg p-3 space-y-3 bg-panel">
                        <div className="text-xs text-muted font-mono">
                          {seq.lead_name || 'Lead'} · {seq.lead_email || 'no-email'}
                        </div>
                        <div>
                          <label className="text-xs text-muted font-mono block mb-1.5">Recipient Email</label>
                          <input
                            type="email"
                            value={editedEmails[leadKey] ?? seq.lead_email ?? ''}
                            onChange={e => updateRecipientEmail(leadKey, e.target.value)}
                            placeholder="Enter recipient email"
                            className={`w-full bg-void border rounded-lg px-3 py-2 text-sm text-text focus:border-accent focus:outline-none ${emailErrors[leadKey] ? 'border-danger' : 'border-border'}`}
                          />
                          {emailErrors[leadKey] && (
                            <div className="text-xs text-danger font-mono mt-1">{emailErrors[leadKey]}</div>
                          )}
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
                    )
                  })}
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
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function EntriesTab() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [companyFilter, setCompanyFilter] = useState('')
  
  useEffect(() => {
    fetchEntries()
  }, [statusFilter, companyFilter])

  async function fetchEntries() {
    setLoading(true)
    try {
      const response = await api.outreachEntries({ status: statusFilter, company: companyFilter })
      setEntries(response.data?.entries || response.entries || [])
    } catch (e) {
      toast.error('Failed to load outreach entries')
    } finally {
      setLoading(false)
    }
  }

  async function updateStatus(id, newStatus) {
    try {
      await api.updateOutreachStatus(id, newStatus)
      setEntries(entries.map(e => e.id === id ? { ...e, status: newStatus } : e))
      toast.success('Status updated')
    } catch (e) {
      toast.error('Failed to update status')
    }
  }

  const statuses = ['draft', 'sent', 'opened', 'replied', 'meeting_scheduled', 'closed_won', 'closed_lost']
  const statusColors = {
    draft: 'bg-muted/20 text-muted border-muted/30',
    sent: 'bg-info/20 text-info border-info/30',
    opened: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
    replied: 'bg-success/20 text-success border-success/30',
    meeting_scheduled: 'bg-plasma/20 text-plasma border-plasma/30',
    closed_won: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    closed_lost: 'bg-danger/20 text-danger border-danger/30'
  }

  return (
    <div className="space-y-6">
      <SectionHeader title="Outreach Pipeline" subtitle="Manage and track your active outreach entries" />
      <div className="card space-y-4">
        <div className="flex gap-4">
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="bg-void border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent focus:outline-none">
            <option value="">All Statuses</option>
            {statuses.map(s => <option key={s} value={s}>{s.replace('_', ' ').toUpperCase()}</option>)}
          </select>
          <input type="text" placeholder="Filter by company..." value={companyFilter} onChange={e => setCompanyFilter(e.target.value)} className="bg-void border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent focus:outline-none flex-1" />
        </div>
        
        {loading ? <LoadingState message="Loading entries..." /> : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
             {entries.length === 0 ? (
               <div className="col-span-full text-center text-muted font-mono text-sm py-10 border border-dashed border-border rounded-xl">No entries found.</div>
             ) : entries.map(entry => (
               <div key={entry.id} className="border border-border rounded-xl p-4 bg-panel flex flex-col gap-3 relative hover:border-accent/40 transition-colors">
                 <div className="flex items-center justify-between">
                   <div className="font-display font-600 text-text truncate pr-2" title={entry.company_name}>{entry.company_name}</div>
                   <div className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase font-600 border whitespace-nowrap ${statusColors[entry.status] || 'bg-muted/20 text-muted'}`}>
                     {entry.status.replace('_', ' ')}
                   </div>
                 </div>
                 
                 <div className="text-xs text-muted flex items-center gap-2">
                   <Mail className="w-3.5 h-3.5" /> <span className="uppercase tracking-wider font-mono">{entry.outreach_type}</span>
                 </div>
                 
                 {entry.message && (
                    <p className="text-xs text-text-dim leading-relaxed line-clamp-3 bg-void p-2 rounded border border-border custom-scrollbar overflow-y-auto max-h-24">
                        {entry.message}
                    </p>
                 )}
                 
                 <div className="mt-auto pt-3 border-t border-border flex items-center justify-between">
                   <div className="text-[10px] text-muted font-mono">{new Date(entry.created_at).toLocaleDateString()}</div>
                   <select 
                      value={entry.status} 
                      onChange={e => updateStatus(entry.id, e.target.value)}
                      className="bg-transparent text-xs font-600 text-accent text-right focus:outline-none cursor-pointer p-0 m-0 hover:text-cyan-300 transition-colors w-1/2 text-ellipsis overflow-hidden"
                   >
                     {statuses.map(s => <option key={s} value={s} className="bg-panel text-text text-sm">{s.replace('_', ' ').toUpperCase()}</option>)}
                   </select>
                 </div>
               </div>
             ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function OutreachPage() {
  const { session_id } = useParams()
  const [tab, setTab] = useState('logs')

  useEffect(() => {
    setTab('logs')
  }, [session_id])
  
  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex gap-2 border-b border-border/50 pb-px">
        <button 
          onClick={() => setTab('logs')} 
          className={`px-4 py-2 text-sm font-mono uppercase tracking-wider transition-colors ${tab === 'logs' ? 'text-accent border-b-2 border-accent' : 'text-muted hover:text-text'}`}
        >
          Logs
        </button>
        <button 
          onClick={() => setTab('entries')} 
          className={`px-4 py-2 text-sm font-mono uppercase tracking-wider transition-colors ${tab === 'entries' ? 'text-accent border-b-2 border-accent' : 'text-muted hover:text-text'}`}
        >
          Entries
        </button>
      </div>
      
      {tab === 'logs' ? <LogsTab sessionId={session_id} /> : <EntriesTab />}
    </div>
  )
}
