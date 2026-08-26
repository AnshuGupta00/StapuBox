/**
 * Copy-to-clipboard plumbing and the plain-text shapes a creator pastes into
 * Instagram. Kept out of the components so the "paste into Story vs paste into
 * caption" wording lives in one place.
 */

import { BLANK_TOKEN } from './constants'

/** Copies text, falling back to a hidden textarea where the async API is blocked. */
export async function copyText(text) {
  if (!text) return false
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // Fall through to the legacy path (http://, or a denied permission).
  }
  try {
    const area = document.createElement('textarea')
    area.value = text
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(area)
    return ok
  } catch {
    return false
  }
}

/** The sticker payload: prompt, options, then the caption and hashtags. */
export function itemToText(item) {
  const ig = item.instagram || {}
  const lines = [`${ig.sticker || 'Sticker'} · ${ig.surface || 'Story'}`, '', ig.prompt_text || '']

  if (ig.option_texts?.length) {
    lines.push('')
    ig.option_texts.forEach((option, index) => {
      const correct = isCorrectOption(item, option, index) ? '  ✓' : ''
      lines.push(`${index + 1}. ${option}${correct}`)
    })
  }

  if (item.content_type === 'GuessNumber') {
    lines.push('', `Answer: ${item.correct_answer} (accepted ${item.range_label})`)
  }

  if (item.explanation) lines.push('', `Why: ${item.explanation}`)
  if (ig.caption) lines.push('', '--- caption ---', ig.caption)
  if (ig.hashtags?.length) lines.push('', ig.hashtags.join(' '))

  return lines.join('\n')
}

/** One block of text for a whole batch, in the order shown on screen. */
export function batchToText(items) {
  return items
    .map((item, index) => `### ${index + 1}. ${item.content_type} — ${item.sport}\n${itemToText(item)}`)
    .join('\n\n')
}

function isCorrectOption(item, option, index) {
  if (item.content_type === 'Poll') return false
  if (item.content_type === 'TrueFalse') return option === item.correct_answer
  return index === item.correct_index
}

/** Splits a fill-in-the-blank sentence around its blank for highlighted render. */
export function splitOnBlank(sentence = '') {
  const at = sentence.indexOf(BLANK_TOKEN)
  if (at === -1) return [sentence, '']
  return [sentence.slice(0, at), sentence.slice(at + BLANK_TOKEN.length)]
}

export function titleCase(value = '') {
  return value.replace(/(^|\s)\S/g, (c) => c.toUpperCase())
}

/**
 * Recomputes the batch insights the backend sends with `/api/generate`.
 *
 * `/api/regenerate` returns one item, not a batch, so after an in-place swap the
 * server's numbers are stale by one item; this keeps the panel honest without a
 * second round trip. Field names match `BatchInsights` on the backend.
 */
export function deriveInsights(items) {
  if (!items.length) {
    return {
      count: 0,
      average_score: 0,
      best_item_id: null,
      type_mix: {},
      surface_mix: {},
      grounded: 0,
      opinion: 0,
      truncation_warnings: 0,
    }
  }

  const typeMix = {}
  const surfaceMix = {}
  items.forEach((item) => {
    typeMix[item.content_type] = (typeMix[item.content_type] || 0) + 1
    const surface = item.instagram?.surface
    if (surface) surfaceMix[surface] = (surfaceMix[surface] || 0) + 1
  })

  const best = items.reduce((a, b) => (b.engagement_score > a.engagement_score ? b : a))
  const total = items.reduce((sum, item) => sum + item.engagement_score, 0)

  return {
    count: items.length,
    average_score: Math.round(total / items.length),
    best_item_id: best.id,
    type_mix: typeMix,
    surface_mix: surfaceMix,
    grounded: items.filter((i) => i.grounding?.is_grounded).length,
    opinion: items.filter((i) => !i.grounding?.fact_checked).length,
    truncation_warnings: items.filter((i) => i.instagram && !i.instagram.within_limits).length,
  }
}
