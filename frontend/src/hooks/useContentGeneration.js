/**
 * All dashboard state in one hook: the request form, the generated batch, and
 * the two async actions the spec asks for (generate a batch, regenerate a single
 * item).
 *
 * Two details worth knowing:
 *
 * - **Regenerate sends an `avoid` list** built from every prompt currently on
 *   screen, so the agent is pushed onto a different fact instead of rephrasing
 *   the one being replaced.
 * - **Per-item busy state** is tracked by item id, so regenerating one card
 *   never greys out the rest of the batch.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  fetchHealth,
  fetchMeta,
  generateContent,
  regenerateContent,
} from '../services/api'
import {
  DEFAULT_REQUEST,
  FALLBACK_CONTENT_TYPES,
  FALLBACK_DIFFICULTIES,
  FALLBACK_SPORTS,
} from '../utils/constants'
import { deriveInsights } from '../utils/format'

/** The text of an item, whichever field its type keeps its prompt in. */
export function promptOf(item) {
  return item.question || item.statement || item.sentence || item.prompt || ''
}

export function useContentGeneration() {
  const [request, setRequest] = useState(DEFAULT_REQUEST)

  const [items, setItems] = useState([])
  const [insights, setInsights] = useState(null)
  const [retrieval, setRetrieval] = useState(null)
  const [diagnostics, setDiagnostics] = useState(null)
  const [batchId, setBatchId] = useState(null)

  const [loading, setLoading] = useState(false)
  const [busyIds, setBusyIds] = useState([])
  const [error, setError] = useState(null)

  const [meta, setMeta] = useState({
    sports: FALLBACK_SPORTS,
    difficulties: FALLBACK_DIFFICULTIES,
    content_types: FALLBACK_CONTENT_TYPES,
  })
  const [health, setHealth] = useState(null)

  // Option lists and the dependency report come from the backend, so the UI
  // cannot drift from the generator registry or hide a missing knowledge base.
  useEffect(() => {
    let live = true
    fetchMeta()
      .then((data) => live && data?.content_types?.length && setMeta(data))
      .catch(() => {
        /* fall back to the bundled lists — surfaced by the first request anyway */
      })
    fetchHealth()
      .then((data) => live && setHealth(data))
      .catch(() => live && setHealth(null))
    return () => {
      live = false
    }
  }, [])

  const refreshHealth = useCallback(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
  }, [])

  const update = useCallback((patch) => {
    setRequest((current) => ({ ...current, ...patch }))
  }, [])

  const toggleContentType = useCallback((value) => {
    setRequest((current) => {
      const selected = current.content_types.includes(value)
        ? current.content_types.filter((v) => v !== value)
        : [...current.content_types, value]
      return { ...current, content_types: selected }
    })
  }, [])

  /** Clearing the selection is meaningful: the backend reads it as "mix all five". */
  const selectAllTypes = useCallback(() => {
    setRequest((current) => ({ ...current, content_types: [] }))
  }, [])

  const generate = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await generateContent(request)
      setItems(data.items || [])
      setInsights(data.insights || null)
      setRetrieval(data.retrieval || null)
      setDiagnostics(data.diagnostics || null)
      setBatchId(data.batch_id || null)
      refreshHealth()
      return data
    } catch (err) {
      setError(err.message)
      return null
    } finally {
      setLoading(false)
    }
  }, [request, refreshHealth])

  const regenerateItem = useCallback(
    async (target) => {
      setBusyIds((current) => [...current, target.id])
      setError(null)
      try {
        const data = await regenerateContent({
          sport: target.sport,
          difficulty: target.difficulty,
          content_type: target.content_type,
          topic: request.topic,
          use_web_search: request.use_web_search,
          // Everything on screen, so the replacement is a different fact.
          avoid: items.map(promptOf).filter(Boolean),
        })
        if (!data?.item) return null
        setItems((current) => {
          const next = current.map((item) => (item.id === target.id ? data.item : item))
          setInsights(deriveInsights(next))
          return next
        })
        setDiagnostics(data.diagnostics || null)
        return data.item
      } catch (err) {
        setError(err.message)
        return null
      } finally {
        setBusyIds((current) => current.filter((id) => id !== target.id))
      }
    },
    [items, request.topic, request.use_web_search]
  )

  const clear = useCallback(() => {
    setItems([])
    setInsights(null)
    setRetrieval(null)
    setDiagnostics(null)
    setBatchId(null)
    setError(null)
  }, [])

  const dismissError = useCallback(() => setError(null), [])

  const mockMode = health?.mock_mode ?? diagnostics?.mock_mode ?? null

  return useMemo(
    () => ({
      request,
      update,
      toggleContentType,
      selectAllTypes,

      items,
      insights,
      retrieval,
      diagnostics,
      batchId,

      loading,
      busyIds,
      error,
      dismissError,

      meta,
      health,
      mockMode,

      generate,
      regenerateItem,
      clear,
    }),
    [
      request,
      update,
      toggleContentType,
      selectAllTypes,
      items,
      insights,
      retrieval,
      diagnostics,
      batchId,
      loading,
      busyIds,
      error,
      dismissError,
      meta,
      health,
      mockMode,
      generate,
      regenerateItem,
      clear,
    ]
  )
}
