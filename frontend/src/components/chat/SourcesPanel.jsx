import { useState, useEffect } from 'react'
import { Globe, FileText, Plus, X, Loader2, Upload } from 'lucide-react'
import { useSession } from '../../hooks/useSession'
import { addUrl, uploadPdf, listSources, removeUrl, removePdf } from '../../services/api'
import toast from 'react-hot-toast'

export default function SourcesPanel() {
  const { sessionId } = useSession()
  const [urls, setUrls] = useState([])
  const [pdfs, setPdfs] = useState([])
  const [urlInput, setUrlInput] = useState('')
  const [loadingUrl, setLoadingUrl] = useState(false)
  const [loadingPdf, setLoadingPdf] = useState(false)

  // Load existing sources on mount
  useEffect(() => {
    listSources(sessionId).then(data => {
      setUrls(data.urls || [])
      setPdfs(data.pdfs || [])
    }).catch(() => {})
  }, [sessionId])

  async function handleAddUrl() {
    const url = urlInput.trim()
    if (!url) return
    setLoadingUrl(true)
    try {
      const res = await addUrl(url, sessionId)
      if (res.success) {
        setUrls(prev => [...prev, { url, title: res.title || url, tool_name: res.tool_name }])
        setUrlInput('')
        toast.success('URL loaded!')
      } else {
        toast.error(res.message)
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load URL')
    } finally {
      setLoadingUrl(false)
    }
  }

  async function handleUploadPdf(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setLoadingPdf(true)
    try {
      const res = await uploadPdf(file, sessionId)
      if (res.success) {
        setPdfs(prev => [...prev, { filename: file.name, tool_name: res.tool_name }])
        toast.success(`PDF "${file.name}" loaded!`)
      } else {
        toast.error(res.message)
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to upload PDF')
    } finally {
      setLoadingPdf(false)
      e.target.value = ''
    }
  }

  async function handleRemoveUrl(url) {
    await removeUrl(url, sessionId).catch(() => {})
    setUrls(prev => prev.filter(u => u.url !== url))
    toast.success('URL removed')
  }

  async function handleRemovePdf(filename) {
    await removePdf(filename, sessionId).catch(() => {})
    setPdfs(prev => prev.filter(p => p.filename !== filename))
    toast.success('PDF removed')
  }

  return (
    <div className="p-3 space-y-4">
      {/* URLs */}
      <div>
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1">
          <Globe className="w-3 h-3" /> URLs
        </p>
        <div className="flex gap-1 mb-2">
          <input
            className="input-base text-xs py-1.5 px-2"
            placeholder="https://..."
            value={urlInput}
            onChange={e => setUrlInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleAddUrl()}
          />
          <button
            onClick={handleAddUrl}
            disabled={!urlInput.trim() || loadingUrl}
            className="btn-primary px-2 py-1.5 shrink-0"
            title="Add URL"
          >
            {loadingUrl ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
          </button>
        </div>
        {urls.map(u => (
          <div key={u.url} className="flex items-center justify-between gap-1 py-1 px-2 rounded bg-surface-700 mb-1 group">
            <div className="min-w-0">
              <p className="text-xs text-gray-300 truncate">{u.title || u.url}</p>
              <p className="text-xs text-gray-500 font-mono">{u.tool_name}</p>
            </div>
            <button onClick={() => handleRemoveUrl(u.url)} className="text-gray-600 hover:text-red-400 shrink-0">
              <X className="w-3 h-3" />
            </button>
          </div>
        ))}
        {urls.length === 0 && <p className="text-xs text-gray-600 text-center py-2">No URLs loaded</p>}
      </div>

      {/* PDFs */}
      <div>
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1">
          <FileText className="w-3 h-3" /> PDFs
        </p>
        <label className="flex items-center justify-center gap-2 w-full py-2 px-3 rounded-lg border border-dashed border-surface-600 hover:border-brand-500 cursor-pointer text-xs text-gray-400 hover:text-brand-400 transition-colors mb-2">
          {loadingPdf ? <Loader2 className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />}
          {loadingPdf ? 'Processing…' : 'Upload PDF'}
          <input type="file" accept=".pdf" className="hidden" onChange={handleUploadPdf} disabled={loadingPdf} />
        </label>
        {pdfs.map(p => (
          <div key={p.filename} className="flex items-center justify-between gap-1 py-1 px-2 rounded bg-surface-700 mb-1">
            <div className="min-w-0">
              <p className="text-xs text-gray-300 truncate">{p.filename}</p>
              <p className="text-xs text-gray-500 font-mono">{p.tool_name}</p>
            </div>
            <button onClick={() => handleRemovePdf(p.filename)} className="text-gray-600 hover:text-red-400 shrink-0">
              <X className="w-3 h-3" />
            </button>
          </div>
        ))}
        {pdfs.length === 0 && <p className="text-xs text-gray-600 text-center py-2">No PDFs loaded</p>}
      </div>
    </div>
  )
}