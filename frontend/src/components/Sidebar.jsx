import {
    Activity,
    AlertTriangle,
    Cpu,
    LayoutDashboard,
    LogOut,
    Mail,
    ScrollText,
    TrendingDown,
    Users,
    Zap
} from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Overview' },
  { to: '/outreach', icon: Zap, label: 'Cold Outreach' },
  { to: '/outreach/history', icon: ScrollText, label: 'Outreach History' },
  { to: '/risks', icon: AlertTriangle, label: 'Deal Risks' },
  { to: '/churn', icon: TrendingDown, label: 'Churn Intel' },
  { to: '/pipeline', icon: Activity, label: 'Pipeline' },
  { to: '/clients', icon: Users, label: 'Clients' },
  { to: '/emails', icon: Mail, label: 'Emails' },
  { to: '/logs', icon: ScrollText, label: 'Audit Logs' },
]

export default function Sidebar() {
  const { logout, user } = useAuth()

  return (
    <aside className="fixed left-0 top-0 h-screen w-56 bg-surface border-r border-border flex flex-col z-50">
      <div className="px-5 py-5 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-accent/10 border border-accent/30 flex items-center justify-center">
            <Cpu className="w-4 h-4 text-accent" />
          </div>
          <div>
            <div className="font-display font-700 text-sm text-text leading-none">RevOps AI</div>
            <div className="text-xs text-muted mt-0.5 font-mono">v1.0.0 · live</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 group ${
                isActive
                  ? 'bg-accent/10 text-accent border border-accent/20'
                  : 'text-text-dim hover:text-text hover:bg-panel'
              }`
            }
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            <span className="font-body">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-4 border-t border-border">
        {user && (
          <div className="text-xs text-muted font-mono mb-2 truncate">
            Signed in as <span className="text-text">{user.username}</span>
          </div>
        )}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-success animate-pulse-slow" />
            <span className="text-xs text-muted font-mono">All agents online</span>
          </div>
          <button
            onClick={logout}
            className="text-xs text-muted hover:text-text flex items-center gap-1"
            title="Log out"
          >
            <LogOut className="w-3.5 h-3.5" />
            Logout
          </button>
        </div>
      </div>
    </aside>
  )
}

