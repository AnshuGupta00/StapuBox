/**
 * The audit panel: how the batch scored, what retrieval contributed, and what the
 * QA layer rejected.
 *
 * The rejection counts matter as much as the items — a short batch with
 * `ungrounded_rejections: 2` is the agent refusing to guess, which is the
 * behaviour the spec asks for, so it is shown rather than hidden.
 */

import { Database, Globe, Info, Search, TrendingUp, Trophy } from 'lucide-react'

import { useContent } from '../../context/ContentContext'
import { typeMeta } from '../../utils/constants'

function Stat({ label, value }) {
  return (
    <div className="stat">
      <div className="stat__value">{value}</div>
      <div className="stat__label">{label}</div>
    </div>
  )
}

function Mix({ title, mix, accentFor }) {
  const entries = Object.entries(mix || {})
  if (!entries.length) return null
  const max = Math.max(...entries.map(([, n]) => n))

  return (
    <div className="field">
      <div className="field__label">{title}</div>
      <div className="mix">
        {entries.map(([key, count]) => (
          <div className="mix__row" key={key}>
            <span>{accentFor ? typeMeta(key).label : key}</span>
            <span className="mix__bar">
              <span
                className="mix__fill"
                style={{
                  width: `${(count / max) * 100}%`,
                  '--type-accent': accentFor ? typeMeta(key).accent : 'var(--accent)',
                }}
              />
            </span>
            <span className="mix__count">{count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function EngagementInsights() {
  const { insights, retrieval, diagnostics, items } = useContent()

  if (!items.length || !insights) return null

  const best = items.find((item) => item.id === insights.best_item_id)
  const rejected =
    (diagnostics?.schema_rejections || 0) +
    (diagnostics?.duplicate_rejections || 0) +
    (diagnostics?.ungrounded_rejections || 0)

  return (
    <section className="panel">
      <div className="panel__head">
        <TrendingUp size={15} aria-hidden="true" />
        <h2>Engagement insights</h2>
      </div>

      <div className="panel__body">
        <div className="stat-grid">
          <Stat label="Avg. score" value={insights.average_score} />
          <Stat label="Grounded" value={`${insights.grounded}/${insights.count}`} />
          <Stat label="Opinion" value={insights.opinion} />
          <Stat label="Truncation" value={insights.truncation_warnings} />
        </div>

        {best && (
          <div className="note">
            <Trophy size={15} style={{ color: 'var(--amber)', flex: 'none' }} aria-hidden="true" />
            <span>
              Lead with the {typeMeta(best.content_type).label.toLowerCase()} —{' '}
              <strong>{best.engagement_score}/100</strong>, the strongest in this batch.
            </span>
          </div>
        )}

        <Mix title="Format mix" mix={insights.type_mix} accentFor />
        <Mix title="Instagram surface" mix={insights.surface_mix} />

        {retrieval && (
          <details className="details">
            <summary>Retrieval &amp; QA report</summary>
            <div className="details__body">
              <div className="stat-grid">
                <Stat
                  label="Web results"
                  value={retrieval.web_search_used ? retrieval.web_results : '—'}
                />
                <Stat label="KB hits" value={retrieval.vector_db_hits} />
                <Stat label="LLM calls" value={diagnostics?.llm_calls ?? 0} />
                <Stat label="Rejected" value={rejected} />
              </div>

              <div className="notes">
                <div className="note">
                  {retrieval.web_search_used ? (
                    <Globe size={14} style={{ flex: 'none' }} aria-hidden="true" />
                  ) : (
                    <Database size={14} style={{ flex: 'none' }} aria-hidden="true" />
                  )}
                  <span>
                    {retrieval.web_search_used
                      ? `Live web search contributed ${retrieval.web_results} result(s).`
                      : 'No live web search on this request.'}
                  </span>
                </div>

                {(retrieval.messages || []).map((message, i) => (
                  <div className="note" key={i}>
                    <span className="note__dot" aria-hidden="true">
                      •
                    </span>
                    <span>{message}</span>
                  </div>
                ))}

                {(diagnostics?.warnings || []).map((warning, i) => (
                  <div className="note" key={`w-${i}`} style={{ color: 'var(--amber)' }}>
                    <Info size={14} style={{ flex: 'none' }} aria-hidden="true" />
                    <span>{warning}</span>
                  </div>
                ))}

                {!!rejected && (
                  <div className="note">
                    <Info size={14} style={{ flex: 'none' }} aria-hidden="true" />
                    <span>
                      Rejected before delivery: {diagnostics.schema_rejections} schema,{' '}
                      {diagnostics.duplicate_rejections} duplicate,{' '}
                      {diagnostics.ungrounded_rejections} ungrounded.
                    </span>
                  </div>
                )}
              </div>

              {retrieval.notes && (
                <div className="field">
                  <div className="field__label">
                    <span>
                      <Search size={12} style={{ verticalAlign: -1, marginRight: 5 }} />
                      Evidence digest
                    </span>
                    <span className="field__hint">what every item in this batch cited</span>
                  </div>
                  <pre className="digest">{retrieval.notes}</pre>
                </div>
              )}
            </div>
          </details>
        )}
      </div>
    </section>
  )
}
