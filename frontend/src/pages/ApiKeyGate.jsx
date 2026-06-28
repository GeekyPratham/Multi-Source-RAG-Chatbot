import { Link } from 'react-router-dom'
import { UserPlus, LogIn } from 'lucide-react'

export default function ApiKeyGate() {
  return (
    <div className="min-h-screen bg-surface-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-brand-500/20 border border-brand-500/30 mb-4">
            <span className="text-3xl">🔎</span>
          </div>
          <h1 className="text-2xl font-bold text-white">InsightAgent AI</h1>
          <p className="text-gray-400 mt-1 text-sm">RAG Assistant + LLM Recommender</p>
        </div>

        {/* Auth buttons */}
        <div className="flex gap-3 mb-4">
          <Link
            to="/login"
            className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-brand-500/20 border border-brand-500/30 text-brand-400 hover:bg-brand-500/30 transition-colors text-sm font-medium"
          >
            <LogIn className="w-4 h-4" />
            Sign In
          </Link>
          <Link
            to="/signup"
            className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-surface-700 border border-surface-600 text-gray-300 hover:bg-surface-600 transition-colors text-sm font-medium"
          >
            <UserPlus className="w-4 h-4" />
            Sign Up
          </Link>
        </div>

        {/* Features */}
        <div className="mt-6 grid grid-cols-2 gap-3">
          {[
            { icon: '🤖', label: 'LLM Recommender', desc: 'Best model for your task' },
            { icon: '🔍', label: 'RAG Assistant', desc: 'Web, Arxiv, Wikipedia' },
            { icon: '📕', label: 'PDF Chat', desc: 'Upload & query documents' },
            { icon: '🌐', label: 'URL Knowledge', desc: 'Add any webpage' },
          ].map(f => (
            <div key={f.label} className="card border-surface-700 text-center py-3">
              <div className="text-2xl mb-1">{f.icon}</div>
              <div className="text-xs font-medium text-white">{f.label}</div>
              <div className="text-xs text-gray-500">{f.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}