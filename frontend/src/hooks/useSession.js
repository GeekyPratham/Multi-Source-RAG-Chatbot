import { useState } from 'react'
import { v4 as uuidv4 } from 'uuid'

const SESSION_KEY = 'insightagent_session_id'

export function useSession() {
  const [sessionId] = useState(() => {
    let id = sessionStorage.getItem(SESSION_KEY)
    if (!id) {
      id = uuidv4()
      sessionStorage.setItem(SESSION_KEY, id)
    }
    return id
  })
  return { sessionId }
}
