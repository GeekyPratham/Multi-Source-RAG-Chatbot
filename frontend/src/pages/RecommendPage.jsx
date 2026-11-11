import { useState } from 'react'
import { Sparkles, Loader2, Search, Info, Settings } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { getRecommendations } from '../services/api'
import RecommendCard from '../components/recommender/RecommendCard'
import toast from 'react-hot-toast'

const EXAMPLE_QUERIES = [
  'Write and debug Python code for a REST API',
  'Summarise a 200-page legal document',
  'Generate creative marketing copy for a SaaS product',
  'Solve complex mathematics and proofs',
  'Answer questions from a large knowledge base (RAG)',
  'Translate and localise content into 5 languages',
]

const TASK_ICONS = {
  coding: '💻', reasoning: '🧠', creative: '🎨', research: '🔬',
  qa: '❓', summarization: '📝', math: '📐', general: '🌐',
}

export default function RecommendPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  async function handleSubmit(e) {
    e?.preventDefault()
    const q = query.trim()
    if (!q) return

    if (!user?.has_api_key) {
      toast((t) => (
        <div className="flex items-center gap-3">
          <span className="text-yellow-400 text-lg">⚠️</span>
          <div className="flex-1">
            <p className="text-sm font-medium text-white">No API key configured</p>
            <p className="text-xs text-gray-400">Please add your API key in Settings first.</p>
          </div>
          <button
            onClick={() => { toast.dismiss(t.id); navigate('/settings') }}
            className="px-3 py-1.5 rounded-lg bg-brand-500/20 border border-brand-500/30 text-brand-400 hover:bg-brand-500/30 text-xs font-medium transition-colors"
          >
            <Settings className="w-3 h-3 inline mr-1" />
            Settings
          </button>
        </div>
      ), { duration: 6000 })
      return
    }

    setLoading(true)
    setResult(null)
    try {
      const data = await getRecommendations(q)
      setResult(data)
    } catch (e) {
      const detail = e?.response?.data?.detail || ''
      if (detail === 'no_api_key_configured') {
        toast.error('No API key configured. Go to Settings to add one.')
      } else if (detail === 'invalid_api_key') {
        toast.error('Invalid API key. Update it in Settings.')
      } else {
        toast.error(e?.response?.data?.detail || 'Failed to get recommendations')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-surface-700 shrink-0">
        <div className="flex items-center gap-2 mb-1">
          <Sparkles className="w-5 h-5 text-brand-400" />
          <h1 className="font-bold text-white">LLM Recommender</h1>
        </div>
        <p className="text-gray-400 text-sm">Describe your task and get ranked recommendations for the best free and paid LLMs.</p>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6 max-w-5xl mx-auto w-full">

        {/* Input */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <label className="block text-sm font-medium text-gray-300">
            Describe your task or query
          </label>
          <div className="relative">
            <textarea
              className="input-base resize-none text-sm leading-relaxed py-3 pr-12"
              placeholder="e.g. I need to write and debug Python code for a FastAPI backend…"
              value={query}
              onChange={e => setQuery(e.target.value)}
              rows={3}
              onKeyDown={e => e.key === 'Enter' && e.ctrlKey && handleSubmit()}
            />
            <button
              type="submit"
              disabled={!query.trim() || loading}
              className="absolute right-2 bottom-2 btn-primary px-3 py-2 text-sm flex items-center gap-1.5"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              {loading ? 'Analysing…' : 'Recommend'}
            </button>
          </div>
        </form>

        {/* Example prompts */}
        {!result && !loading && (
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Try an example</p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLE_QUERIES.map(q => (
                <button
                  key={q}
                  onClick={() => { setQuery(q) }}
                  className="text-xs px-3 py-1.5 rounded-full bg-surface-700 hover:bg-surface-600 text-gray-300 hover:text-white border border-surface-600 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="space-y-3 animate-pulse">
            {[1,2,3].map(i => (
              <div key={i} className="card h-40 bg-surface-700 rounded-xl" />
            ))}
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-5 animate-fade-in">
            {/* Analysis banner */}
            <div className="card border-brand-500/30 bg-brand-500/5">
              <div className="flex items-start gap-3">
                <div className="text-2xl">{TASK_ICONS[result.task_type] || '🌐'}</div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold uppercase tracking-wider text-brand-400">Task type</span>
                    <span className="text-xs bg-brand-500/20 text-brand-300 px-2 py-0.5 rounded-full border border-brand-500/30 font-mono">
                      {result.task_type}
                    </span>
                  </div>
                  <p className="text-sm text-gray-300 leading-relaxed">{result.query_analysis}</p>
                </div>
              </div>
            </div>

            {/* Top pick reasoning */}
            <div className="flex items-start gap-2 text-sm bg-emerald-900/20 border border-emerald-800/40 rounded-xl px-4 py-3">
              <Info className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
              <div>
                <span className="font-semibold text-emerald-300">Top Pick: {result.top_pick} — </span>
                <span className="text-gray-300">{result.reasoning}</span>
              </div>
            </div>

            {/* Cards grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {result.recommendations.map((rec, i) => (
                <RecommendCard
                  key={i}
                  rec={rec}
                  isTopPick={rec.name === result.top_pick}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}