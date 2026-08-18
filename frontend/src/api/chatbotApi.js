// src/api/chatbotApi.js
import { supabase } from '../lib/supabase'

// Live Production Backend on Railway (with fallback support)
const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  "https://dsm5-clinical-chatbot-production.up.railway.app";

// ============================================================
// Helper: Get Supabase Session Token
// ============================================================

export async function getSupabaseToken() {
  const { data: { session }, error } = await supabase.auth.getSession()
  if (error || !session) {
    throw new Error('No active session. Please login again.')
  }
  return session.access_token
}

// ============================================================
// Helper: Get Headers with Authorization
// ============================================================

async function getAuthHeaders() {
  const token = await getSupabaseToken()
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
  }
}

// ============================================================
// POST /new-chat
// ============================================================

export async function createNewChat() {
  const headers = await getAuthHeaders()
  
  const res = await fetch(`${API_BASE_URL}/new-chat`, {
    method: 'POST',
    headers,
  })

  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('Session expired. Please login again.')
    }
    throw new Error('Failed to create a new chat session.')
  }

  return res.json()
}

// ============================================================
// POST /chat
// ============================================================

export async function sendMessage(sessionId, message) {
  const headers = await getAuthHeaders()
  
  const res = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      session_id: sessionId,
      message,
    }),
  })

  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('Session expired. Please login again.')
    }
    throw new Error('Failed to get a response from the assistant.')
  }

  return res.json()
}

// ============================================================
// POST /chat/stream
// Added for live typing-style responses without changing the old /chat flow.
// ============================================================

export async function sendMessageStream(sessionId, message, onChunk) {
  const headers = await getAuthHeaders()

  const res = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      session_id: sessionId,
      message,
    }),
  })

  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('Session expired. Please login again.')
    }
    throw new Error('Failed to get a streamed response from the assistant.')
  }

  const reader = res.body?.getReader()
  if (!reader) {
    throw new Error('Streaming is not supported by this browser response.')
  }

  const decoder = new TextDecoder()
  let fullAnswer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    const chunk = decoder.decode(value, { stream: true })
    if (chunk) {
      fullAnswer += chunk
      if (onChunk) onChunk(chunk)
    }
  }

  return fullAnswer
}

// ============================================================
// GET /chats
// ============================================================

export async function getChats() {
  const headers = await getAuthHeaders()
  
  const res = await fetch(`${API_BASE_URL}/chats`, {
    method: 'GET',
    headers,
  })

  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('Session expired. Please login again.')
    }
    throw new Error('Failed to load chat sessions.')
  }

  return res.json()
}

// ============================================================
// GET /chats/{session_id}
// ============================================================

export async function getChatById(sessionId) {
  const headers = await getAuthHeaders()
  
  const res = await fetch(`${API_BASE_URL}/chats/${sessionId}`, {
    method: 'GET',
    headers,
  })

  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('Session expired. Please login again.')
    }
    throw new Error('Failed to load chat history.')
  }

  return res.json()
}

// ============================================================
// DELETE /chats/{session_id}
// ============================================================

export async function deleteChat(sessionId) {
  const headers = await getAuthHeaders()
  
  const res = await fetch(`${API_BASE_URL}/chats/${sessionId}`, {
    method: 'DELETE',
    headers,
  })

  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('Session expired. Please login again.')
    }
    throw new Error('Failed to delete chat.')
  }

  return res.json()
}

// ============================================================
// PUT /chats/{session_id}
// ============================================================

export async function renameChat(sessionId, newTitle) {
  const headers = await getAuthHeaders()
  
  const res = await fetch(`${API_BASE_URL}/chats/${sessionId}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify({ title: newTitle }),
  })

  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('Session expired. Please login again.')
    }
    throw new Error('Failed to rename chat.')
  }

  return res.json()
}

// ============================================================
// POST /pipeline/chat — 4-Agent Pipeline
// ============================================================

export async function sendPipelineMessage(sessionId, message, sessionContext = null) {
  const headers = await getAuthHeaders()

  const res = await fetch(`${API_BASE_URL}/pipeline/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      session_id: sessionId,
      message,
      session_context: sessionContext,
    }),
  })

  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('Session expired. Please login again.')
    }
    throw new Error('Failed to run 4-Agent pipeline response.')
  }

  return res.json()
}

// ============================================================
// Grief Workbook Calendar API Calls
// ============================================================

export async function saveGriefEntry(entryDate, entryText, sessionId = null, themes = null) {
  const headers = await getAuthHeaders()

  const res = await fetch(`${API_BASE_URL}/grief/entry`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      entry_date: entryDate,
      entry_text: entryText,
      session_id: sessionId,
      themes,
    }),
  })

  if (!res.ok) {
    throw new Error('Failed to save Grief Workbook entry.')
  }

  return res.json()
}

export async function getGriefEntry(date, sessionId = null) {
  const headers = await getAuthHeaders()
  let url = `${API_BASE_URL}/grief/entry?date=${encodeURIComponent(date)}`
  if (sessionId) url += `&session_id=${encodeURIComponent(sessionId)}`

  const res = await fetch(url, {
    method: 'GET',
    headers,
  })

  if (!res.ok) {
    throw new Error('Failed to load Grief Workbook entry.')
  }

  return res.json()
}

export async function getGriefCalendarDates(sessionId = null) {
  const headers = await getAuthHeaders()
  let url = `${API_BASE_URL}/grief/calendar`
  if (sessionId) url += `?session_id=${encodeURIComponent(sessionId)}`

  const res = await fetch(url, {
    method: 'GET',
    headers,
  })

  if (!res.ok) {
    throw new Error('Failed to load marked calendar dates.')
  }

  return res.json()
}