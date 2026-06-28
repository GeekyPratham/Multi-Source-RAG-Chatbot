import { useState } from 'react'
import { Send, Loader2 } from 'lucide-react'

export default function ChatInput({ onSend, loading, disabled }) {
  const [text, setText] = useState('')

  function handleSend() {
    const msg = text.trim()
    if (!msg || loading || disabled) return
    onSend(msg)
    setText('')
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="border-t border-surface-700 bg-surface-900 px-4 py-3">
      <div className="flex items-end gap-2 max-w-4xl mx-auto">
        <textarea
          className="input-base resize-none text-sm min-h-[44px] max-h-[120px] leading-relaxed py-2.5"
          placeholder="Ask anything… (Shift+Enter for new line)"
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKey}
          rows={1}
          disabled={disabled}
          style={{ height: Math.min(120, Math.max(44, text.split('\n').length * 22 + 22)) }}
        />
        <button
          onClick={handleSend}
          disabled={!text.trim() || loading || disabled}
          className="btn-primary px-3 py-2.5 shrink-0 flex items-center gap-1.5"
        >
          {loading
            ? <Loader2 className="w-4 h-4 animate-spin" />
            : <Send className="w-4 h-4" />
          }
        </button>
      </div>
      <p className="text-center text-xs text-gray-600 mt-1.5">
        Model picks tools automatically · Web · Arxiv · Wikipedia · Loaded PDFs & URLs
      </p>
    </div>
  )
}
