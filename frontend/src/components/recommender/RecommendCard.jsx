import { Zap, DollarSign, Trophy } from 'lucide-react'
import { clsx } from 'clsx'

export default function RecommendCard({ rec, isTopPick }) {
  return (
    <div className={clsx(
      'card border rounded-xl p-4 relative transition-all duration-200 hover:border-brand-500/50',
      isTopPick
        ? 'border-brand-500/60 bg-brand-500/5 shadow-lg shadow-brand-500/10'
        : 'border-surface-600'
    )}>
      {isTopPick && (
        <div className="absolute -top-2.5 left-4 flex items-center gap-1 bg-brand-500 text-white text-xs font-bold px-2 py-0.5 rounded-full">
          <Trophy className="w-3 h-3" /> Top Pick
        </div>
      )}

      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h3 className="font-semibold text-white text-sm">{rec.name}</h3>
          <p className="text-xs text-gray-500">{rec.provider}</p>
        </div>
        <div className="flex flex-wrap gap-1 justify-end">
          <span className={rec.tier === 'free' ? 'badge-free' : 'badge-paid'}>
            {rec.tier === 'free' ? '✓ Free' : '💳 Paid'}
          </span>
          <span className="badge-fast">
            <Zap className="w-2.5 h-2.5" />
            {rec.speed}
          </span>
        </div>
      </div>

      {/* Why recommended */}
      <p className="text-xs text-gray-300 leading-relaxed mb-3">{rec.why_recommended}</p>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <Stat label="Best for" value={rec.best_for} />
        <Stat label="Context" value={rec.context_window} />
        <Stat label="Cost" value={rec.cost} icon={<DollarSign className="w-2.5 h-2.5" />} />
        {rec.groq_model_id && (
          <Stat label="Groq ID" value={rec.groq_model_id} mono />
        )}
      </div>
    </div>
  )
}

function Stat({ label, value, icon, mono }) {
  return (
    <div className="bg-surface-700 rounded-lg px-2 py-1.5">
      <p className="text-gray-500 text-xs mb-0.5">{label}</p>
      <p className={clsx('text-gray-300 font-medium truncate', mono && 'font-mono text-brand-400')}>
        {icon && <span className="inline mr-0.5">{icon}</span>}
        {value}
      </p>
    </div>
  )
}
