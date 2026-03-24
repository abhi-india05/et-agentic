import { useState, useEffect } from 'react'
import { Mail, CheckCircle, XCircle, RefreshCw } from 'lucide-react'
import { SectionHeader, LoadingState, ErrorState, StatCard } from '../components/UI.jsx'
import { api } from '../utils/api.js'
import { fmt } from '../utils/fmt.js'

export default function EmailsPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(null)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const res = await api.emails()
      setData(res)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <LoadingState message="Loading email records…" />
  if (error) return <ErrorState message={error} onRetry={load} />

  const emails = data?.emails || []
  const stats = data?.stats || {}

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex items-center justify-between">
        <SectionHeader title="Email Activity" subtitle={`${emails.length} emails tracked`} />
        <button onClick={load} className="btn-ghost flex items-center gap-2 text-xs">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Sent" value={fmt.num(stats.sent || 0)} icon={Mail} color="accent" />
        <StatCard label="Success Rate" value={fmt.pct(stats.success_rate || 0)} icon={CheckCircle} color="success" />
        <StatCard label="Failed" value={fmt.num(stats.failed || 0)} icon={XCircle} color="danger" />
        <StatCard label="Total Tracked" value={fmt.num(stats.total || 0)} color="plasma" />
      </div>

      {emails.length === 0 ? (
        <div className="card text-center py-12">
          <Mail className="w-10 h-10 text-muted/40 mx-auto mb-3" />
          <div className="text-sm text-text-dim">No emails sent yet</div>
          <div className="text-xs text-muted mt-1">Run a Cold Outreach workflow to generate emails</div>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-muted font-mono uppercase tracking-wider">
                  <th className="py-2 px-4 text-left">To</th>
                  <th className="py-2 px-4 text-left">Subject</th>
                  <th className="py-2 px-4 text-center">Step</th>
                  <th className="py-2 px-4 text-center">Status</th>
                  <th className="py-2 px-4 text-right">Sent</th>
                </tr>
              </thead>
              <tbody>
                {emails.map((email, i) => (
                  <>
                    <tr
                      key={i}
                      className="border-b border-border/40 hover:bg-surface/50 transition-colors cursor-pointer"
                      onClick={() => setExpanded(expanded === i ? null : i)}
                    >
                      <td className="py-3 px-4">
                        <div className="text-text font-display font-500 text-sm">{email.to_name}</div>
                        <div className="text-xs text-muted font-mono">{email.to_email}</div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="text-sm text-text-dim max-w-xs truncate">{email.subject}</div>
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className="text-xs font-mono text-muted">#{email.sequence_step}</span>
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className={`badge ${email.status?.includes('sent') ? 'badge-success' : 'badge-failure'}`}>
                          {email.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right text-xs text-muted font-mono">
                        {fmt.reltime(email.sent_at)}
                      </td>
                    </tr>
                    {expanded === i && (
                      <tr key={`exp-${i}`} className="border-b border-border">
                        <td colSpan={5} className="px-4 pb-4 pt-1">
                          <pre className="text-xs font-mono text-text-dim bg-void rounded-lg p-4 whitespace-pre-wrap leading-relaxed border border-border">
                            {email.body_text}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
