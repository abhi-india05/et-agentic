import { CheckCircle2, Mail, Plus, Search, Send, Sparkles, Users, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { ErrorState, LoadingState, SectionHeader } from '../components/UI.jsx'
import { api } from '../services/api.js'
import { fmt } from '../utils/fmt.js'

const EMPTY_CUSTOMER_FORM = {
  company_name: '',
  company_domain: '',
  contact_name: '',
  contact_email: '',
  notes: '',
}

function buildDefaultFollowup(customer) {
  const contact = customer?.contact_name || customer?.company_name || 'there'
  const company = customer?.company_name || 'your team'
  return {
    subject: `Quick follow-up for ${company}`,
    body: `Hi ${contact},\n\nWanted to quickly follow up on our last conversation and share next steps relevant to your priorities.\n\nWould you be open to a short follow-up this week?`,
  }
}

export default function ClientsPage() {
  const [customers, setCustomers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [query, setQuery] = useState('')
  const [selectedCustomerId, setSelectedCustomerId] = useState('')

  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newCustomer, setNewCustomer] = useState(EMPTY_CUSTOMER_FORM)
  const [creatingCustomer, setCreatingCustomer] = useState(false)

  const [followupSubject, setFollowupSubject] = useState('')
  const [followupBody, setFollowupBody] = useState('')
  const [sendingFollowup, setSendingFollowup] = useState(false)
  const [followupSentByCustomerId, setFollowupSentByCustomerId] = useState({})
  const [markingReplied, setMarkingReplied] = useState(false)

  const [showRefineModal, setShowRefineModal] = useState(false)
  const [refinePrompt, setRefinePrompt] = useState('')
  const [refining, setRefining] = useState(false)
  const [refineError, setRefineError] = useState(null)
  const [refineExplanation, setRefineExplanation] = useState('')

  async function loadCustomers() {
    setLoading(true)
    setError(null)
    try {
      const res = await api.customers({ page: 1, pageSize: 200, query })
      const items = res.customers || []
      setCustomers(items)
      if (!selectedCustomerId && items.length > 0) {
        setSelectedCustomerId(items[0].id)
      }
      if (selectedCustomerId && items.every(item => item.id !== selectedCustomerId)) {
        setSelectedCustomerId(items[0]?.id || '')
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadCustomers()
    }, 250)
    return () => window.clearTimeout(timer)
  }, [query])

  const selectedCustomer = useMemo(
    () => customers.find(item => item.id === selectedCustomerId) || null,
    [customers, selectedCustomerId]
  )

  useEffect(() => {
    if (!selectedCustomer) {
      setFollowupSubject('')
      setFollowupBody('')
      setRefineExplanation('')
      return
    }
    const draft = buildDefaultFollowup(selectedCustomer)
    setFollowupSubject(draft.subject)
    setFollowupBody(draft.body)
    setRefineExplanation('')
  }, [selectedCustomerId])

  async function handleCreateCustomer(e) {
    e.preventDefault()
    if (!newCustomer.company_name.trim()) {
      toast.error('Company name is required')
      return
    }

    setCreatingCustomer(true)
    try {
      const payload = {
        company_name: newCustomer.company_name,
        company_domain: newCustomer.company_domain || null,
        contact_name: newCustomer.contact_name || null,
        contact_email: newCustomer.contact_email || null,
        notes: newCustomer.notes || null,
      }
      const res = await api.createCustomer(payload)
      const created = res.customer
      toast.success(res.created ? 'Customer added successfully' : 'Customer already existed for this source')
      setShowCreateForm(false)
      setNewCustomer(EMPTY_CUSTOMER_FORM)
      await loadCustomers()
      if (created?.id) {
        setSelectedCustomerId(created.id)
      }
    } catch (e) {
      toast.error(e.message)
    } finally {
      setCreatingCustomer(false)
    }
  }

  async function handleSendFollowup() {
    if (!selectedCustomer) return
    if (!selectedCustomer.contact_email) {
      toast.error('This customer has no contact email. Add one before sending follow-up.')
      return
    }
    if (!followupSubject.trim() || !followupBody.trim()) {
      toast.error('Subject and follow-up body are required')
      return
    }

    setSendingFollowup(true)
    try {
      const res = await api.sendLeadEmail({
        lead_id: selectedCustomer.id,
        lead_name: selectedCustomer.contact_name || selectedCustomer.company_name,
        sequence_id: `cust_followup_${Date.now()}`,
        email: selectedCustomer.contact_email,
        subject: followupSubject.trim(),
        content: followupBody,
      })
      const sent = res?.summary?.sent || 0
      const failed = res?.summary?.failed || 0
      if (sent > 0 && selectedCustomer?.id) {
        setFollowupSentByCustomerId(prev => ({ ...prev, [selectedCustomer.id]: true }))
      }
      if (sent > 0 && failed === 0) {
        toast.success('Follow-up email sent successfully')
      } else {
        toast.error(`Follow-up send result: sent ${sent}, failed ${failed}`)
      }
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSendingFollowup(false)
    }
  }

  async function handleMarkAsReplied() {
    if (!selectedCustomer) return
    if (!followupSentByCustomerId[selectedCustomer.id]) {
      toast.error('Send a follow-up email first.')
      return
    }

    setMarkingReplied(true)
    try {
      const res = await api.markCustomerReplied(selectedCustomer.id)
      const updated = res?.customer
      if (!updated?.id) {
        throw new Error('Failed to refresh replied timestamp')
      }

      setCustomers(prev => prev.map(item => (item.id === updated.id ? { ...item, ...updated } : item)))
      toast.success(`Marked as replied at ${fmt.datetime(updated.marked_as_customer_at || updated.created_at)}`)
    } catch (e) {
      toast.error(e.message || 'Failed to mark as replied')
    } finally {
      setMarkingReplied(false)
    }
  }

  function openRefineModal() {
    if (!selectedCustomer) return
    setShowRefineModal(true)
    setRefinePrompt('')
    setRefineError(null)
  }

  function closeRefineModal() {
    if (refining) return
    setShowRefineModal(false)
    setRefinePrompt('')
    setRefineError(null)
  }

  async function handleRefineFollowup(e) {
    e.preventDefault()
    if (!selectedCustomer) return
    if (!refinePrompt.trim()) {
      setRefineError('Please provide a refinement prompt.')
      return
    }
    if (!followupBody.trim()) {
      setRefineError('Draft a follow-up email body first.')
      return
    }

    setRefining(true)
    setRefineError(null)
    try {
      const res = await api.refineOutreachEmail({
        lead_id: selectedCustomer.id,
        original_email: followupBody,
        prompt: refinePrompt.trim(),
        lead_context: {
          session_id: `customer_followup_${selectedCustomer.id}`,
          customer: selectedCustomer,
          followup_subject: followupSubject,
        },
        insights: {
          type: 'customer_followup',
          customer_notes: selectedCustomer.notes || '',
        },
      })

      setFollowupBody(res.refined_email || followupBody)
      setRefineExplanation(res.explanation || 'Refined with AI')
      toast.success('Follow-up draft refined with AI')
      closeRefineModal()
    } catch (e) {
      setRefineError(e.message)
    } finally {
      setRefining(false)
    }
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <SectionHeader
        title="Clients"
        subtitle="Manage converted customers, view details, and draft AI-refined follow-up emails"
        action={
          <button
            type="button"
            onClick={() => setShowCreateForm(value => !value)}
            className="btn-ghost text-xs flex items-center gap-2"
          >
            <Plus className="w-3.5 h-3.5" />
            {showCreateForm ? 'Close Form' : 'Add Customer'}
          </button>
        }
      />

      {showCreateForm && (
        <form onSubmit={handleCreateCustomer} className="card space-y-3 border-accent/25 bg-accent/5">
          <div className="text-sm font-display font-700 text-text">Add Customer Manually</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              value={newCustomer.company_name}
              onChange={(e) => setNewCustomer(prev => ({ ...prev, company_name: e.target.value }))}
              placeholder="Company name *"
              className="w-full bg-void border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
              required
            />
            <input
              value={newCustomer.company_domain}
              onChange={(e) => setNewCustomer(prev => ({ ...prev, company_domain: e.target.value }))}
              placeholder="Company website/domain"
              className="w-full bg-void border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
            />
            <input
              value={newCustomer.contact_name}
              onChange={(e) => setNewCustomer(prev => ({ ...prev, contact_name: e.target.value }))}
              placeholder="Contact name"
              className="w-full bg-void border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
            />
            <input
              type="email"
              value={newCustomer.contact_email}
              onChange={(e) => setNewCustomer(prev => ({ ...prev, contact_email: e.target.value }))}
              placeholder="Contact email"
              className="w-full bg-void border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
            />
          </div>
          <textarea
            rows={3}
            value={newCustomer.notes}
            onChange={(e) => setNewCustomer(prev => ({ ...prev, notes: e.target.value }))}
            placeholder="Notes"
            className="w-full bg-void border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent focus:outline-none resize-y"
          />
          <div className="flex justify-end">
            <button type="submit" className="btn-primary disabled:opacity-50" disabled={creatingCustomer}>
              {creatingCustomer ? 'Saving...' : 'Save Customer'}
            </button>
          </div>
        </form>
      )}

      <div className="card space-y-3">
        <div className="relative">
          <Search className="w-4 h-4 text-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by company, contact, or email"
            className="w-full bg-void border border-border rounded-lg pl-9 pr-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
          />
        </div>

        {loading && <LoadingState message="Loading clients..." />}
        {error && !loading && <ErrorState message={error} onRetry={loadCustomers} />}

        {!loading && !error && customers.length === 0 && (
          <div className="text-sm text-muted text-center py-8 border border-dashed border-border rounded-lg">
            No customers yet. Convert replied leads from Outreach or add one manually.
          </div>
        )}

        {!loading && !error && customers.length > 0 && (
          <div className="space-y-2 max-h-[20rem] overflow-y-auto custom-scrollbar pr-1">
            {customers.map((customer) => (
              <button
                key={customer.id}
                type="button"
                onClick={() => setSelectedCustomerId(customer.id)}
                className={`w-full text-left border rounded-lg p-3 transition-colors ${
                  selectedCustomerId === customer.id
                    ? 'border-accent bg-accent/5'
                    : 'border-border bg-panel hover:border-accent/40'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-display font-700 text-text truncate">{customer.company_name}</div>
                    <div className="text-xs text-muted mt-1 truncate">{customer.contact_name || 'No contact name'}</div>
                    <div className="text-xs text-muted truncate">{customer.contact_email || 'No contact email'}</div>
                  </div>
                  <div className="text-[11px] text-muted font-mono">{fmt.reltime(customer.marked_as_customer_at || customer.created_at)}</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {selectedCustomer && (
        <div className="card space-y-4">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-accent" />
            <div className="text-sm font-display font-700 text-text">Customer Details</div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
            <div className="bg-void border border-border rounded-lg p-3">
              <div className="text-xs text-muted font-mono uppercase">Company</div>
              <div className="text-text mt-1">{selectedCustomer.company_name}</div>
            </div>
            <div className="bg-void border border-border rounded-lg p-3">
              <div className="text-xs text-muted font-mono uppercase">Website/Domain</div>
              <div className="text-text mt-1">{selectedCustomer.company_domain || 'Not provided'}</div>
            </div>
            <div className="bg-void border border-border rounded-lg p-3">
              <div className="text-xs text-muted font-mono uppercase">Contact Name</div>
              <div className="text-text mt-1">{selectedCustomer.contact_name || 'Not provided'}</div>
            </div>
            <div className="bg-void border border-border rounded-lg p-3">
              <div className="text-xs text-muted font-mono uppercase">Contact Email</div>
              <div className="text-text mt-1">{selectedCustomer.contact_email || 'Not provided'}</div>
            </div>
            <div className="bg-void border border-border rounded-lg p-3">
              <div className="text-xs text-muted font-mono uppercase">Marked as Customer</div>
              <div className="text-text mt-1">{fmt.datetime(selectedCustomer.marked_as_customer_at || selectedCustomer.created_at)}</div>
            </div>
          </div>

          <div className="bg-void border border-border rounded-lg p-3">
            <div className="text-xs text-muted font-mono uppercase">Notes</div>
            <div className="text-sm text-text-dim mt-1 whitespace-pre-wrap">{selectedCustomer.notes || 'No notes yet.'}</div>
          </div>

          <div className="border-t border-border pt-4 space-y-3">
            <div className="text-sm font-display font-700 text-text flex items-center gap-2">
              <Mail className="w-4 h-4 text-accent" />
              Draft Follow-up Email
            </div>

            <input
              value={followupSubject}
              onChange={(e) => setFollowupSubject(e.target.value)}
              placeholder="Follow-up subject"
              className="w-full bg-void border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
            />
            <textarea
              rows={8}
              value={followupBody}
              onChange={(e) => setFollowupBody(e.target.value)}
              placeholder="Write your follow-up email"
              className="w-full bg-void border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent focus:outline-none resize-y font-mono"
            />

            {refineExplanation && (
              <div className="text-xs text-muted bg-void border border-border rounded-md px-2 py-1.5">
                AI note: {refineExplanation}
              </div>
            )}

            <div className="flex flex-wrap gap-2 justify-end">
              {followupSentByCustomerId[selectedCustomer.id] && (
                <button
                  type="button"
                  onClick={handleMarkAsReplied}
                  disabled={markingReplied}
                  className="btn-ghost flex items-center gap-2 text-xs disabled:opacity-50"
                  title="Mark customer as replied and refresh analytics timestamp"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  {markingReplied ? 'Marking...' : 'Mark as Replied'}
                </button>
              )}
              <button type="button" onClick={openRefineModal} className="btn-ghost flex items-center gap-2 text-xs">
                <Sparkles className="w-3.5 h-3.5" />
                Refine with AI
              </button>
              <button
                type="button"
                onClick={handleSendFollowup}
                disabled={sendingFollowup || !selectedCustomer.contact_email}
                className="btn-primary flex items-center gap-2 text-xs disabled:opacity-50"
              >
                <Send className="w-3.5 h-3.5" />
                {sendingFollowup ? 'Sending...' : 'Send Follow-up'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showRefineModal && selectedCustomer && (
        <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="card w-full max-w-2xl space-y-4 border-accent/25">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-display font-700 text-text">Refine Follow-up with AI</div>
                <div className="text-xs text-muted mt-1">Example: Make this warmer and more concise.</div>
              </div>
              <button
                type="button"
                onClick={closeRefineModal}
                className="btn-ghost p-2"
                disabled={refining}
                aria-label="Close refine modal"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleRefineFollowup} className="space-y-3">
              <label className="text-xs text-muted font-mono block">Refinement prompt</label>
              <textarea
                value={refinePrompt}
                onChange={(e) => setRefinePrompt(e.target.value)}
                rows={5}
                className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder:text-muted focus:border-accent focus:outline-none resize-y"
                placeholder="Make this sharper and outcome-focused"
              />
              {refineError && <div className="text-xs text-danger font-mono">{refineError}</div>}

              <div className="flex items-center justify-end gap-2">
                <button type="button" onClick={closeRefineModal} className="btn-ghost" disabled={refining}>Cancel</button>
                <button
                  type="submit"
                  disabled={refining || !refinePrompt.trim()}
                  className="btn-primary flex items-center gap-2 disabled:opacity-50"
                >
                  <Sparkles className="w-4 h-4" />
                  {refining ? 'Refining...' : 'Apply Refinement'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
