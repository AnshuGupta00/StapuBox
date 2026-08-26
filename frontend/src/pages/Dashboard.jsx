/**
 * The dashboard: request builder on the left, generated batch on the right.
 *
 * The top bar doubles as a dependency read-out — LLM mode, web search, knowledge
 * base size and the novelty ledger — because every one of those silently changes
 * what the agent can produce, and a creator should see it before they wonder why
 * a batch came back short.
 */

import { Database, Globe, Sparkles, TrendingUp } from 'lucide-react'

import BatchControls from '../components/dashboard/BatchControls'
import ContentForm from '../components/dashboard/ContentForm'
import EngagementInsights from '../components/dashboard/EngagementInsights'
import ContentList from '../components/content/ContentList'
import ErrorMessage, { Banner } from '../components/common/ErrorMessage'
import { useContent } from '../context/ContentContext'

function HealthStrip({ health }) {
  if (!health) return null

  const { llm, web_search: web, knowledge_base: kb, freshness } = health.checks || {}

  return (
    <>
      {llm && (
        <span className={`badge ${llm.mode === 'live' ? 'badge--ok' : 'badge--warn'}`}>
          <Sparkles size={12} aria-hidden="true" />
          {llm.mode === 'live' ? `Live · ${llm.model}` : 'Mock mode'}
        </span>
      )}
      {web && (
        <span className={`badge ${web.enabled ? 'badge--ok' : ''}`}>
          <Globe size={12} aria-hidden="true" />
          Web search {web.enabled ? 'on' : 'off'}
        </span>
      )}
      {kb && (
        <span className={`badge ${kb.available && kb.documents ? '' : 'badge--warn'}`}>
          <Database size={12} aria-hidden="true" />
          {kb.available ? `${kb.documents} KB docs` : 'KB unavailable'}
        </span>
      )}
      {freshness && (
        <span className="badge">
          <TrendingUp size={12} aria-hidden="true" />
          {freshness.tracked} seen
        </span>
      )}
    </>
  )
}

export default function Dashboard() {
  const { error, dismissError, health, mockMode } = useContent()
  const kb = health?.checks?.knowledge_base

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark">
            <Sparkles size={20} aria-hidden="true" />
          </span>
          <div>
            <div className="brand__title">Sports Engagement Agent</div>
            <div className="brand__sub">
              Five Instagram-ready formats, grounded and schema-checked
            </div>
          </div>
        </div>
        <span className="topbar__spacer" />
        <HealthStrip health={health} />
      </header>

      <div className="layout">
        <aside className="sidebar">
          <ContentForm />
          <EngagementInsights />
        </aside>

        <main className="main-column">
          <ErrorMessage message={error} onDismiss={dismissError} />

          {mockMode === true && (
            <Banner>
              No <code>ANTHROPIC_API_KEY</code> is configured, so the agent is running in
              mock mode: items are composed from the offline fact bank and cited as
              knowledge-base sources. Add a key to <code>backend/.env</code> for live
              generation with web search.
            </Banner>
          )}

          {kb?.hint && <Banner>{kb.hint}</Banner>}
          {kb && !kb.available && (
            <Banner>
              ChromaDB is unavailable{kb.reason ? ` (${kb.reason})` : ''} — factual items will
              lean on web search alone.
            </Banner>
          )}

          <BatchControls />
          <ContentList />
        </main>
      </div>
    </div>
  )
}
