import { useState, useCallback } from 'react'

const KEY = 'insightagent_groq_key'

export function useApiKey() {
  const [apiKey, setApiKeyState] = useState(() => localStorage.getItem(KEY) || '')

  const setApiKey = useCallback((key) => {
    localStorage.setItem(KEY, key)
    setApiKeyState(key)
  }, [])

  const clearApiKey = useCallback(() => {
    localStorage.removeItem(KEY)
    setApiKeyState('')
  }, [])

  return { apiKey, setApiKey, clearApiKey }
}
