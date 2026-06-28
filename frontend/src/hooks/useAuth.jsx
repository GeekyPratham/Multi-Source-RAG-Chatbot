import { useState, useEffect, useCallback, createContext, useContext } from 'react'
import { api } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tokens, setTokens] = useState(() => {
    const at = localStorage.getItem('insightagent_access_token')
    const rt = localStorage.getItem('insightagent_refresh_token')
    const uid = localStorage.getItem('insightagent_user_id')
    return at && rt && uid ? { accessToken: at, refreshToken: rt, userId: uid } : null
  })

  // Restore session on mount
  useEffect(() => {
    if (tokens) {
      fetchUser(tokens.accessToken)
        .then(u => {
          if (u) {
            setUser(u)
          } else {
            // Try refresh
            attemptRefresh()
          }
        })
        .catch(() => {
          attemptRefresh()
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  async function fetchUser(at) {
    try {
      const res = await api.get('/api/auth/me', {
        headers: { Authorization: `Bearer ${at}` },
      })
      return res.data
    } catch {
      return null
    }
  }

  async function attemptRefresh() {
    if (!tokens) {
      setLoading(false)
      return
    }
    try {
      const res = await api.post('/api/auth/refresh/v2', {
        refresh_token: tokens.refreshToken,
        user_id: tokens.userId,
      })
      const { access_token, refresh_token } = res.data
      localStorage.setItem('insightagent_access_token', access_token)
      localStorage.setItem('insightagent_refresh_token', refresh_token)
      setTokens({ accessToken: access_token, refreshToken: refresh_token, userId: tokens.userId })

      const u = await fetchUser(access_token)
      if (u) setUser(u)
    } catch {
      // Refresh failed — clear everything
      logout()
    } finally {
      setLoading(false)
    }
  }

  const login = useCallback(async (accessToken, refreshToken, userData) => {
    localStorage.setItem('insightagent_access_token', accessToken)
    localStorage.setItem('insightagent_refresh_token', refreshToken)
    localStorage.setItem('insightagent_user_id', userData.id)
    setTokens({ accessToken, refreshToken, userId: userData.id })
    setUser(userData)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('insightagent_access_token')
    localStorage.removeItem('insightagent_refresh_token')
    localStorage.removeItem('insightagent_user_id')
    localStorage.removeItem('insightagent_groq_key')
    localStorage.removeItem('insightagent_groq_key')
    setTokens(null)
    setUser(null)
  }, [])

  const updateUser = useCallback((userData) => {
    setUser(prev => ({ ...prev, ...userData }))
  }, [])

  const getAccessToken = useCallback(() => {
    return tokens?.accessToken || null
  }, [tokens])

  const isAuthenticated = !!user && !!tokens

  return (
    <AuthContext.Provider value={{ user, loading, isAuthenticated, login, logout, updateUser, getAccessToken }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}