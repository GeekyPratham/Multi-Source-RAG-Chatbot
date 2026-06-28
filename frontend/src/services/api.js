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