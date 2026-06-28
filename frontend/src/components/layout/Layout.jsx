import { NavLink, useNavigate } from 'react-router-dom'
import { MessageSquare, Sparkles, Settings, LogOut, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { useState } from 'react'
import { useAuth } from '../../hooks/useAuth'
import SourcesPanel from '../chat/SourcesPanel'
import { clsx } from 'clsx'

export default function Layout({ children }) {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(true)

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-surface-900 overflow-hidden">
      {/* Sidebar */}
      <aside className={clsx(
        'flex flex-col border-r border-surface-700 transition-all duration-200 shrink-0',
        sidebarOpen ? 'w-64' : 'w-14'
      )}>
        {/* Logo + toggle */}
        <div className="flex items-center justify-between px-3 py-4 border-b border-surface-700">
          {sidebarOpen && (
            <div className="flex items-center gap-2">
              <span className="text-xl">🔎</span>
              <span className="font-bold text-white text-sm">InsightAgent</span>
            </div>
          )}
          <button
            onClick={() => setSidebarOpen(o => !o)}
            className="p-1.5 rounded-lg hover:bg-surface-700 text-gray-400 hover:text-white transition-colors ml-auto"
          >
            {sidebarOpen ? <PanelLeftClose className="w-4 h-4" /> : <PanelLeftOpen className="w-4 h-4" />}
          </button>
        </div>

        {/* Nav links */}
        <nav className="px-2 py-3 space-y-1">
          <NavItem to="/chat" icon={<MessageSquare className="w-4 h-4" />} label="Chat" open={sidebarOpen} />
          <NavItem to="/recommend" icon={<Sparkles className="w-4 h-4" />} label="LLM Recommender" open={sidebarOpen} />
          <NavItem to="/settings" icon={<Settings className="w-4 h-4" />} label="Settings" open={sidebarOpen} />
        </nav>

        {/* Sources panel (only in sidebar when open) */}
        {sidebarOpen && (
          <div className="flex-1 overflow-y-auto border-t border-surface-700 mt-2">
            <SourcesPanel />
          </div>
        )}

        {/* Footer */}
        <div className="px-2 py-3 border-t border-surface-700">
          <button
            onClick={handleLogout}
            className={clsx(
              'flex items-center gap-2 w-full px-2 py-2 rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-900/20 transition-colors text-sm',
              !sidebarOpen && 'justify-center'
            )}
            title="Logout"
          >
            <LogOut className="w-4 h-4 shrink-0" />
            {sidebarOpen && <span>Logout</span>}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-hidden flex flex-col">
        {children}
      </main>
    </div>
  )
}

function NavItem({ to, icon, label, open }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) => clsx(
        'flex items-center gap-2 px-2 py-2 rounded-lg text-sm font-medium transition-colors',
        isActive
          ? 'bg-brand-500/20 text-brand-400 border border-brand-500/30'
          : 'text-gray-400 hover:text-white hover:bg-surface-700',
        !open && 'justify-center'
      )}
      title={label}
    >
      <span className="shrink-0">{icon}</span>
      {open && <span>{label}</span>}
    </NavLink>
  )
}
