/**
 * Thin axios wrapper around the agent's four endpoints.
 *
 * Every call funnels through `unwrap`, which turns FastAPI's error shapes
 * (`detail` as a string, or Pydantic's list of validation errors) into one
 * readable message — a short batch is a 200 with warnings, so anything that
 * lands here is a genuine failure worth showing the user.
 */

import axios from 'axios'

import { API_BASE_URL } from '../utils/constants'

const api = axios.create({
  baseURL: API_BASE_URL,
  // Live generation runs web search plus five prompts; leave room for it.
  timeout: 180000,
  headers: { 'Content-Type': 'application/json' },
})

function messageFrom(error) {
  if (error.code === 'ECONNABORTED') {
    return 'The request timed out. Generation with live web search can take a while — try a smaller batch.'
  }

  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => `${(d.loc || []).filter((l) => l !== 'body').join('.')}: ${d.msg}`)
      .join('; ')
  }
  if (!error.response) {
    return `Cannot reach the API at ${API_BASE_URL}. Start it with \`uvicorn app.main:app --reload\` in backend/.`
  }
  return error.message || 'Unexpected error'
}

async function unwrap(promise) {
  try {
    const { data } = await promise
    return data
  } catch (error) {
    const wrapped = new Error(messageFrom(error))
    wrapped.status = error.response?.status
    throw wrapped
  }
}

/** Option lists and per-type contracts, so the UI mirrors the backend registry. */
export const fetchMeta = () => unwrap(api.get('/api/meta'))

/** Dependency report: LLM mode, vector DB document count, freshness ledger. */
export const fetchHealth = () => unwrap(api.get('/api/health'))

/** Generate a batch. Empty `content_types` means "mix all five". */
export const generateContent = (payload) => unwrap(api.post('/api/generate', payload))

/** Replace one item. `avoid` carries everything already on screen. */
export const regenerateContent = (payload) => unwrap(api.post('/api/regenerate', payload))

export default api
