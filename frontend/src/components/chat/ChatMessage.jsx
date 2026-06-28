import { Bot, User, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { clsx } from 'clsx'

const TOOL_ICONS = {
  DuckDuckGo_Search: '🔍',
  arxiv: '📄',
  wikipedia: '📖',
}
function toolIcon(name) {
  if (TOOL_ICONS[name]) return TOOL_ICONS[name]
  if (name.startsWith('URL_')) return '🌐'
  if (name.startsWith('PDF_')) return '📕'
  return '🔧'
}

function ToolTrace({ steps }) {
  const [open, setOpen] = useState(false)
  if (!steps?.length) return null
  return (
    <div className="mt-2 border border-surface-600 rounded-lg overflow-hidden text-xs">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center justify-between w-full px-3 py-2 bg-surface-700 hover:bg-surface-600 transition-colors text-gray-400"
      >
        <span className="flex items-center gap-1.5">
          🔗 <span className="font-medium text-gray-300">{steps.length} tool call{steps.length > 1 ? 's' : ''}</span>
          &nbsp;·&nbsp;
          {steps.map(s => `${toolIcon(s.tool)} ${s.tool}`).join(', ')}
        </span>
        {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>
      {open && (
        <div className="divide-y divide-surface-700">
          {steps.map((s, i) => (
            <div key={i} className="px-3 py-2 bg-surface-800 space-y-1">
              <div className="flex items-center gap-1.5 font-medium text-gray-300">
                <span>{toolIcon(s.tool)}</span>
                <span className="font-mono text-brand-400">{s.tool}</span>
                <span className="text-gray-600">· step {s.step}</span>
              </div>
              <div className="text-gray-500">
                <span className="text-gray-600">Input: </span>
                <span className="font-mono text-gray-400">{JSON.stringify(s.tool_input).slice(0, 120)}</span>
              </div>
              <div className="text-gray-500 leading-relaxed">
                <span className="text-gray-600">Result: </span>
                {s.observation.slice(0, 300)}{s.observation.length > 300 ? '…' : ''}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ChatMessage({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={clsx('flex gap-3 animate-slide-up', isUser && 'flex-row-reverse')}>
      {/* Avatar */}
      <div className={clsx(
        'shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold',
        isUser ? 'bg-brand-500 text-white' : 'bg-surface-700 border border-surface-600'
      )}>
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4 text-brand-400" />}
      </div>

      {/* Bubble */}
      <div className={clsx(
        'max-w-[80%] rounded-2xl px-4 py-3',
        isUser
          ? 'bg-brand-500 text-white rounded-tr-sm'
          : 'bg-surface-800 border border-surface-700 rounded-tl-sm'
      )}>
        {isUser ? (
          <p className="text-sm leading-relaxed">{msg.content}</p>
        ) : (
          <div>
            {msg.answered_from_history && (
              <p className="text-xs text-gray-500 mb-2 flex items-center gap-1">
                🧠 <span>Answered from conversation memory (no tool call needed)</span>
              </p>
            )}
            <div className="prose-chat text-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
            </div>
            {msg.tool_steps?.length > 0 && <ToolTrace steps={msg.tool_steps} />}
          </div>
        )}
      </div>
    </div>
  )
}
