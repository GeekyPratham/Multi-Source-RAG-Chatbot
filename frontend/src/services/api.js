// src/services/api.js — all backend API calls
import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || ''   // empty = use Vite proxy

export const api = axios.create({ baseURL: BASE, timeout: 120_000 })

// Auto-attach access token if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('insightagent_access_token')
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Auto-refresh access token on 401, then retry the original request once
let _refreshing = null
api.interceptors.response.use(
  r => r,
  async err => {
    const original = err.config
    if (err.response?.status === 401 && !original._retry) {
      original._retry = true
      const rt = localStorage.getItem('insightagent_refresh_token')
      const uid = localStorage.getItem('insightagent_user_id')
      if (rt && uid) {
        // Deduplicate concurrent refresh calls
        if (!_refreshing) {
          _refreshing = axios.post(`${BASE}/api/auth/refresh/v2`, {
            refresh_token: rt,
            user_id: uid,
          }).then(res => {
            const { access_token, refresh_token } = res.data
            localStorage.setItem('insightagent_access_token', access_token)
            localStorage.setItem('insightagent_refresh_token', refresh_token)
            return access_token
          }).finally(() => { _refreshing = null })
        }
        try {
          const newToken = await _refreshing
          original.headers.Authorization = `Bearer ${newToken}`
          return api(original)
        } catch {
          // Refresh failed — clear session and redirect to login
          localStorage.removeItem('insightagent_access_token')
          localStorage.removeItem('insightagent_refresh_token')
          localStorage.removeItem('insightagent_user_id')
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(err)
  }
)

// ── Auth ──────────────────────────────────────────────────────────────────────
export const validateApiKey = (api_key) =>
  api.post('/api/auth/validate', { api_key }).then(r => r.data)

// ── Recommender ───────────────────────────────────────────────────────────────
export const getRecommendations = (query) =>
  api.post('/api/recommend', { query }).then(r => r.data)

// ── Chat ──────────────────────────────────────────────────────────────────────
export const sendChat = (payload) =>
  api.post('/api/chat', payload).then(r => r.data)

// ── Sources ───────────────────────────────────────────────────────────────────
export const addUrl = (url, session_id) =>
  api.post('/api/sources/url', { url, session_id }).then(r => r.data)

export const uploadPdf = (file, session_id) => {
  const form = new FormData()
  form.append('file', file)
  form.append('session_id', session_id)
  return api.post('/api/sources/pdf', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}

export const listSources = (session_id) =>
  api.get('/api/sources/list', { params: { session_id } }).then(r => r.data)

export const removeUrl = (url, session_id) =>
  api.delete('/api/sources/url', { params: { url, session_id } }).then(r => r.data)

export const removePdf = (filename, session_id) =>
  api.delete('/api/sources/pdf', { params: { filename, session_id } }).then(r => r.data)

export default api