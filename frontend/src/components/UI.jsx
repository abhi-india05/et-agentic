import { Loader2 } from 'lucide-react'

export function Spinner({ size = 'md' }) {
  const s = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-8 h-8' }[size]
  return <Loader2 className={`${s} animate-spin text-accent`} />
}

export function LoadingState({ message = 'Processing…' }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <div className="relative">
        <div className="w-12 h-12 rounded-full border-2 border-border" />
        <div className="absolute inset-0 w-12 h-12 rounded-full border-2 border-accent border-t-transparent animate-spin" />
      </div>
      <div className="text-center">
        <div className="text-sm text-text font-mono">{message}</div>
        <div className="text-xs text-muted mt-1">Agents are working autonomously</div>
      </div>
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 gap-3">
      <div className="w-10 h-10 rounded-full bg-danger/10 border border-danger/30 flex items-center justify-center">
        <span className="text-danger text-lg">!</span>
      </div>
      <div className="text-sm text-danger">{message}</div>
      {onRetry && (
        <button onClick={onRetry} className="btn-ghost text-xs mt-1">
          Retry
        </button>
      )}
    </div>
  )
}

export function StatCard({ label, value, sub, color = 'accent', icon: Icon }) {
  const colors = {
    accent: 'text-accent',
    danger: 'text-danger',
    warn: 'text-warn',
    success: 'text-success',
    plasma: 'text-plasma',
  }
  return (
    <div className="stat-card">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted font-mono uppercase tracking-wider">{label}</span>
        {Icon && <Icon className={`w-4 h-4 ${colors[color] || 'text-muted'}`} />}
      </div>
      <div className={`text-2xl font-display font-700 ${colors[color] || 'text-text'}`}>{value}</div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  )
}

export function RiskBadge({ level }) {
  const map = {
    critical: 'badge-critical',
    high: 'badge-high',
    medium: 'badge-medium',
    low: 'badge-low',
    success: 'badge-success',
    failure: 'badge-failure',
  }
  return <span className={map[level?.toLowerCase()] || 'badge bg-muted/20 text-muted'}>{level}</span>
}

export function ConfidenceBar({ value }) {
  const pct = Math.round((value || 0) * 100)
  const color = pct >= 80 ? 'bg-success' : pct >= 60 ? 'bg-accent' : pct >= 40 ? 'bg-warn' : 'bg-danger'
  return (
    <div className="flex items-center gap-2">
      <div className="progress-bar flex-1">
        <div className={`progress-fill ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-muted w-8 text-right">{pct}%</span>
    </div>
  )
}

export function AgentTag({ name, status }) {
  const statusColor = {
    success: 'border-success/30 text-success bg-success/5',
    failure: 'border-danger/30 text-danger bg-danger/5',
    pending: 'border-accent/30 text-accent bg-accent/5 agent-pulse',
  }[status] || 'border-border text-muted'

  const label = name.replace(/_agent$/, '').replace(/_/g, ' ')
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono border ${statusColor}`}>
      {label}
    </span>
  )
}

export function SectionHeader({ title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between mb-5">
      <div>
        <h2 className="text-lg font-display font-700 text-text">{title}</h2>
        {subtitle && <p className="text-sm text-muted mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function EmptyState({ icon: Icon, title, description }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 gap-3 text-center">
      {Icon && <Icon className="w-8 h-8 text-muted/50" />}
      <div className="text-sm font-display text-text-dim">{title}</div>
      {description && <div className="text-xs text-muted max-w-xs">{description}</div>}
    </div>
  )
}

export function Divider() {
  return <div className="glow-line my-4" />
}

export function JsonViewer({ data }) {
  return (
    <pre className="text-xs font-mono text-text-dim bg-void rounded-lg p-4 overflow-auto max-h-64 border border-border">
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

/* ─── Modal ───────────────────────────────────────────────────────────── */

export function Modal({ open, onClose, title, children, footer }) {
  if (!open) return null

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="card w-full max-w-md mx-4 animate-fade-up relative"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-display font-700 text-text">{title}</h3>
          <button
            onClick={onClose}
            className="text-muted hover:text-text text-lg leading-none transition"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="text-sm text-text-dim">{children}</div>

        {footer && (
          <div className="flex items-center justify-end gap-3 mt-5 pt-4 border-t border-border">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

/* ─── PaginationControls ──────────────────────────────────────────────── */

export function PaginationControls({ page, pageSize, total, onPageChange }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className="flex items-center justify-between pt-4 border-t border-border/40 mt-4">
      <span className="text-xs text-muted font-mono">
        {total} total · page {page} of {totalPages}
      </span>
      <div className="flex items-center gap-2">
        <button
          className="btn-ghost text-xs disabled:opacity-30 disabled:cursor-not-allowed"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          ← Prev
        </button>
        <button
          className="btn-ghost text-xs disabled:opacity-30 disabled:cursor-not-allowed"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          Next →
        </button>
      </div>
    </div>
  )
}

/* ─── FormInput ───────────────────────────────────────────────────────── */

export function FormInput({ label, value, onChange, type = 'text', placeholder, maxLength, required, disabled, icon: Icon }) {
  return (
    <label className="block">
      {label && <span className="text-xs text-muted font-mono block mb-1.5">{label}</span>}
      <div className="relative">
        {Icon && <Icon className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted" />}
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          maxLength={maxLength}
          required={required}
          disabled={disabled}
          className={`w-full bg-void border border-border rounded-lg ${Icon ? 'pl-9' : 'px-3'} pr-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none disabled:opacity-50 transition`}
        />
      </div>
    </label>
  )
}

/* ─── TextArea ────────────────────────────────────────────────────────── */

export function TextArea({ label, value, onChange, placeholder, maxLength, rows = 3, disabled }) {
  return (
    <label className="block">
      {label && <span className="text-xs text-muted font-mono block mb-1.5">{label}</span>}
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
        rows={rows}
        disabled={disabled}
        className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none min-h-[44px] disabled:opacity-50 transition"
      />
    </label>
  )
}

/* ─── Button ──────────────────────────────────────────────────────────── */

export function Button({ children, variant = 'primary', onClick, type = 'button', disabled, className = '' }) {
  const variants = {
    primary: 'btn-primary',
    ghost: 'btn-ghost',
    danger: 'btn-danger',
  }
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${variants[variant] || variants.primary} disabled:opacity-50 ${className}`}
    >
      {children}
    </button>
  )
}
