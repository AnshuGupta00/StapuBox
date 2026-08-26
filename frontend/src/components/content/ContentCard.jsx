/**
 * The shell around every generated item: badges, the type-specific body, the
 * evidence trail, the Instagram payload, and the per-item actions.
 *
 * The body is chosen by `content_type` from a small registry, which keeps this
 * component ignorant of any single type's answer shape — adding a sixth format
 * means adding one card here, not rewriting the shell.
 */

import { Copy, Eye, EyeOff, RefreshCw, Smartphone } from 'lucide-react'
import { useState } from 'react'

import { useContent } from '../../context/ContentContext'
import { scoreTier, typeMeta } from '../../utils/constants'
import { copyText, itemToText } from '../../utils/format'
import Button from '../common/Button'
import SourceCitation from '../common/SourceCitation'
import FillBlankCard from './FillBlankCard'
import GuessNumberCard from './GuessNumberCard'
import MCQCard from './MCQCard'
import PollCard from './PollCard'
import TrueFalseCard from './TrueFalseCard'

const BODIES = {
  MCQ: MCQCard,
  TrueFalse: TrueFalseCard,
  Poll: PollCard,
  FillBlank: FillBlankCard,
  GuessNumber: GuessNumberCard,
}

export default function ContentCard({ item }) {
  const { regenerateItem, busyIds } = useContent()
  const [revealed, setRevealed] = useState(false)
  const [copied, setCopied] = useState(false)

  const Body = BODIES[item.content_type]
  if (!Body) return null

  const meta = typeMeta(item.content_type)
  const { Icon } = meta
  const busy = busyIds.includes(item.id)
  const opinion = item.content_type === 'Poll' || !item.grounding?.fact_checked
  const ig = item.instagram
  const grounded = item.grounding?.is_grounded

  const copy = async () => {
    const ok = await copyText(itemToText(item))
    setCopied(ok)
    setTimeout(() => setCopied(false), 1600)
  }

  return (
    <article
      className={`card${busy ? ' card--busy' : ''}`}
      style={{ '--type-accent': meta.accent }}
      aria-busy={busy}
    >
      <header className="card__head">
        <span className="badge badge--type">
          <Icon size={13} aria-hidden="true" />
          {meta.label}
        </span>
        <span className="badge">{item.sport}</span>
        {opinion ? (
          <span className="badge badge--opinion">Opinion</span>
        ) : (
          <span className="badge">{item.difficulty}</span>
        )}
        <span className="card__head-spacer" />
        {!opinion && (
          <span className={`badge ${grounded ? 'badge--ok' : 'badge--danger'}`}>
            {grounded
              ? `${item.grounding.resolved_sources.length} source${
                  item.grounding.resolved_sources.length === 1 ? '' : 's'
                }`
              : 'ungrounded'}
          </span>
        )}
      </header>

      <div className="card__body">
        <Body item={item} revealed={revealed} />

        {revealed && !opinion && (
          <div className="reveal">
            <div className="reveal__row">
              <span className="reveal__key">Answer</span>
              <span className="reveal__value" style={{ color: 'var(--green)', fontWeight: 600 }}>
                {item.correct_answer}
              </span>
            </div>
            {item.explanation && (
              <div className="reveal__row">
                <span className="reveal__key">Why</span>
                <span className="reveal__value">{item.explanation}</span>
              </div>
            )}
          </div>
        )}

        <SourceCitation grounding={item.grounding} opinionBased={opinion} />

        {ig && (
          <div className="ig">
            <div className="ig__head">
              <Smartphone size={13} aria-hidden="true" />
              {ig.sticker} · {ig.surface}
              {!ig.within_limits && (
                <span className="badge badge--warn" style={{ marginLeft: 'auto' }}>
                  over limit
                </span>
              )}
            </div>
            <div className="ig__body">
              {ig.caption && <div className="ig__caption">{ig.caption}</div>}
              {!!ig.hashtags?.length && (
                <div className="ig__tags">
                  {ig.hashtags.map((tag) => (
                    <span className="ig__tag" key={tag}>
                      {tag}
                    </span>
                  ))}
                </div>
              )}
              {(ig.limit_warnings || []).map((warning) => (
                <div className="ig__warn" key={warning}>
                  {warning}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <footer className="card__foot">
        <span className={`score score--${scoreTier(item.engagement_score)}`}>
          <span className="score__dot" aria-hidden="true" />
          {item.engagement_score}/100
        </span>
        <span className="card__foot-spacer" />

        {!opinion && (
          <Button
            size="sm"
            variant="ghost"
            icon={revealed ? EyeOff : Eye}
            onClick={() => setRevealed((current) => !current)}
          >
            {revealed ? 'Hide answer' : 'Show answer'}
          </Button>
        )}
        <Button size="sm" variant="ghost" icon={Copy} onClick={copy}>
          {copied ? 'Copied' : 'Copy'}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          icon={RefreshCw}
          busy={busy}
          onClick={() => regenerateItem(item)}
          aria-label={`Regenerate this ${meta.label}`}
        >
          Regenerate
        </Button>
      </footer>
    </article>
  )
}
