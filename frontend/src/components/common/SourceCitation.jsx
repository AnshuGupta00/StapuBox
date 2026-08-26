/**
 * Shows which retrieved evidence supports an item's answer.
 *
 * The backend resolves the handles the model cited (`W1`, `K3`, …) against what
 * was actually retrieved, so anything listed here is real evidence — an invented
 * handle never reaches the client. Polls carry no sources by design and render
 * the opinion notice instead.
 */

import { Database, Globe, Split } from 'lucide-react'

import { SOURCE_KIND } from '../../utils/constants'

const ICONS = { web_search: Globe, vector_db: Database, opinion: Split }

export default function SourceCitation({ grounding, opinionBased = false }) {
  if (!grounding) return null

  const sources = grounding.resolved_sources || []

  if (opinionBased || !grounding.fact_checked) {
    return (
      <div className="cites">
        <div className="cites__head">
          <Split size={13} aria-hidden="true" />
          Opinion-based — not fact-checked
        </div>
        <p className="cites__why">
          {grounding.reasoning ||
            'This-or-That polls have no correct answer, so no factual source is claimed.'}
        </p>
      </div>
    )
  }

  return (
    <div className="cites">
      <div className="cites__head">
        <Globe size={13} aria-hidden="true" />
        Grounded in {sources.length} source{sources.length === 1 ? '' : 's'}
        <span className="badge badge--plain" style={{ marginLeft: 'auto' }}>
          {grounding.confidence} confidence
        </span>
      </div>

      {sources.map((source) => {
        const kind = SOURCE_KIND[source.kind] || { label: source.kind, className: '' }
        const Icon = ICONS[source.kind] || Globe
        return (
          <div className="cite" key={`${source.ref}-${source.title}`}>
            <span className={`cite__ref ${kind.className}`}>{source.ref}</span>
            <div className="cite__body">
              <div className="cite__title">
                <Icon
                  size={12}
                  aria-hidden="true"
                  style={{ marginRight: 5, verticalAlign: -1 }}
                />
                {kind.label}
                {source.title ? ` — ${source.title}` : ''}
              </div>
              {source.snippet && <div className="cite__snippet">{source.snippet}</div>}
              {source.url && (
                <a
                  className="cite__link"
                  href={source.url}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  {source.url}
                </a>
              )}
            </div>
          </div>
        )
      })}

      {!sources.length && (
        <p className="cites__why">
          No source resolved — this item would have been rejected before reaching you.
        </p>
      )}

      {grounding.reasoning && <p className="cites__why">{grounding.reasoning}</p>}
    </div>
  )
}
