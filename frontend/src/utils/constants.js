/**
 * Static option lists, per-type presentation metadata and small formatters.
 *
 * The lists here are only fallbacks: the dashboard prefers `/api/meta` so that
 * adding a sport or a content type on the backend needs no frontend change.
 * Everything visual (accent colour, icon, wording) lives here.
 */

import { Hash, ListChecks, Split, ToggleLeft, Type } from 'lucide-react'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://stapubox.onrender.com'
export const FALLBACK_SPORTS = [
  'Cricket',
  'Football',
  'Tennis',
  'Badminton',
  'Basketball',
  'Hockey',
  'Athletics',
  'Formula 1',
  'Kabaddi',
  'Chess',
]

export const FALLBACK_DIFFICULTIES = ['Easy', 'Medium', 'Hard']

/** Mirrors GET /api/meta -> content_types, used until that call resolves. */
export const FALLBACK_CONTENT_TYPES = [
  {
    value: 'MCQ',
    label: 'Multiple Choice',
    contract: '4 options, exactly 1 correct',
    fact_checked: true,
    sticker: 'Quiz sticker',
    surface: 'Story',
  },
  {
    value: 'TrueFalse',
    label: 'True / False',
    contract: 'declarative statement, boolean verdict',
    fact_checked: true,
    sticker: 'Poll sticker',
    surface: 'Story',
  },
  {
    value: 'Poll',
    label: 'This or That',
    contract: '2 options, no correct answer (opinion-based)',
    fact_checked: false,
    sticker: 'Poll sticker',
    surface: 'Story',
  },
  {
    value: 'FillBlank',
    label: 'Fill in the Blank',
    contract: 'one blank, 4 candidate fills',
    fact_checked: true,
    sticker: 'Quiz sticker',
    surface: 'Reel Caption',
  },
  {
    value: 'GuessNumber',
    label: 'Guess the Number',
    contract: 'numeric target with an accepted ± range',
    fact_checked: true,
    sticker: 'Questions sticker',
    surface: 'Feed',
  },
]

/** Presentation only: colour + icon + short label per content type. */
export const TYPE_META = {
  MCQ: { label: 'MCQ', accent: 'var(--t-mcq)', Icon: ListChecks },
  TrueFalse: { label: 'True / False', accent: 'var(--t-truefalse)', Icon: ToggleLeft },
  Poll: { label: 'This or That', accent: 'var(--t-poll)', Icon: Split },
  FillBlank: { label: 'Fill in the Blank', accent: 'var(--t-fillblank)', Icon: Type },
  GuessNumber: { label: 'Guess the Number', accent: 'var(--t-guessnumber)', Icon: Hash },
}

export const typeMeta = (value) =>
  TYPE_META[value] || { label: value, accent: 'var(--accent)', Icon: ListChecks }

export const SPORT_EMOJI = {
  Cricket: '🏏',
  Football: '⚽',
  Tennis: '🎾',
  Badminton: '🏸',
  Basketball: '🏀',
  Hockey: '🏑',
  Athletics: '🏃',
  'Formula 1': '🏎️',
  Kabaddi: '🤼',
  Chess: '♟️',
}

/** Which retrieval backend a citation handle came from. */
export const SOURCE_KIND = {
  web_search: { label: 'Web search', className: 'cite__ref--web' },
  vector_db: { label: 'Knowledge base', className: 'cite__ref--kb' },
  opinion: { label: 'Opinion — not fact-checked', className: '' },
}

export const MIN_COUNT = 1
export const MAX_COUNT = 10

/** The spec's default ask: a batch of 4-5 mixed items. */
export const DEFAULT_REQUEST = {
  sport: 'Cricket',
  difficulty: 'Medium',
  content_types: [],
  count: 5,
  topic: '',
  use_web_search: true,
}

export const scoreTier = (score) => {
  if (score >= 70) return 'high'
  if (score >= 50) return 'medium'
  return 'low'
}

export const OPTION_LETTERS = ['A', 'B', 'C', 'D']

/** The blank marker the backend emits inside fill-in-the-blank sentences. */
export const BLANK_TOKEN = '____'
