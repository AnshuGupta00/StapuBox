/**
 * The request builder: sport, difficulty, formats, batch size, optional topic and
 * the web-search switch.
 *
 * Batch size defaults to 5 (the spec asks for 4-5 per request) and the optional
 * topic is what turns live web search on even for an opinion-only batch.
 */

import { Sparkles } from 'lucide-react'

import { useContent } from '../../context/ContentContext'
import { MAX_COUNT, MIN_COUNT } from '../../utils/constants'
import Button from '../common/Button'
import ContentTypeSelector from './ContentTypeSelector'
import DifficultySelector from './DifficultySelector'
import SportSelector from './SportSelector'

export default function ContentForm() {
  const {
    request,
    update,
    toggleContentType,
    selectAllTypes,
    meta,
    loading,
    generate,
    mockMode,
  } = useContent()

  const submit = (event) => {
    event.preventDefault()
    generate()
  }

  return (
    <form className="panel" onSubmit={submit}>
      <div className="panel__head">
        <Sparkles size={15} aria-hidden="true" />
        <h2>Generate a batch</h2>
      </div>

      <div className="panel__body">
        <SportSelector
          sports={meta.sports}
          value={request.sport}
          onChange={(sport) => update({ sport })}
          disabled={loading}
        />

        <DifficultySelector
          difficulties={meta.difficulties}
          value={request.difficulty}
          onChange={(difficulty) => update({ difficulty })}
          disabled={loading}
        />

        <ContentTypeSelector
          contentTypes={meta.content_types}
          selected={request.content_types}
          onToggle={toggleContentType}
          onSelectAll={selectAllTypes}
          disabled={loading}
        />

        <div className="field">
          <label className="field__label" htmlFor="count">
            Batch size
            <span className="field__hint">{request.count} items</span>
          </label>
          <input
            id="count"
            className="range"
            type="range"
            min={MIN_COUNT}
            max={MAX_COUNT}
            value={request.count}
            disabled={loading}
            onChange={(e) => update({ count: Number(e.target.value) })}
          />
        </div>

        <div className="field">
          <label className="field__label" htmlFor="topic">
            Topic
            <span className="field__hint">optional — forces web search</span>
          </label>
          <input
            id="topic"
            className="input"
            type="text"
            maxLength={200}
            placeholder="e.g. Ashes 2025, Grand Slam finals"
            value={request.topic}
            disabled={loading}
            onChange={(e) => update({ topic: e.target.value })}
          />
        </div>

        <label className="switch">
          <input
            type="checkbox"
            checked={request.use_web_search}
            disabled={loading}
            onChange={(e) => update({ use_web_search: e.target.checked })}
          />
          <span className="switch__text">
            <span className="switch__label">Ground on live web search</span>
            <span className="switch__hint">
              {mockMode === true
                ? 'Mock mode: offline sample facts are used instead.'
                : 'Adds live results to the ChromaDB knowledge base sweep.'}
            </span>
          </span>
        </label>

        <Button type="submit" variant="primary" icon={Sparkles} busy={loading} block>
          {loading ? 'Generating…' : 'Generate content'}
        </Button>
      </div>
    </form>
  )
}
