/**
 * Multi-select over the five formats, with each type's answer contract shown
 * inline so a creator knows what they are asking for.
 *
 * Selecting nothing is a valid, meaningful state: the backend reads an empty
 * `content_types` as "mix all five", which is the spec's default batch.
 */

import { Check } from 'lucide-react'

import { typeMeta } from '../../utils/constants'

export default function ContentTypeSelector({
  contentTypes,
  selected,
  onToggle,
  onSelectAll,
  disabled = false,
}) {
  const mixed = selected.length === 0

  return (
    <div className="field">
      <div className="field__label">
        Content types
        <button
          type="button"
          className="field__hint"
          style={{
            background: 'none',
            border: 0,
            cursor: 'pointer',
            color: mixed ? 'var(--accent)' : 'var(--text-faint)',
            padding: 0,
          }}
          onClick={onSelectAll}
          disabled={disabled}
        >
          {mixed ? 'mixing all five' : 'reset to mixed'}
        </button>
      </div>

      <div className="type-list" role="group" aria-label="Content types">
        {contentTypes.map((type) => {
          const meta = typeMeta(type.value)
          const active = mixed || selected.includes(type.value)
          const { Icon } = meta
          return (
            <button
              key={type.value}
              type="button"
              className="type-option"
              style={{ '--type-accent': meta.accent }}
              aria-pressed={active}
              disabled={disabled}
              onClick={() => onToggle(type.value)}
            >
              <span className="type-option__icon">
                <Icon size={17} aria-hidden="true" />
              </span>
              <span>
                <span className="type-option__label">{type.label || meta.label}</span>
                <br />
                <span className="type-option__contract">{type.contract}</span>
              </span>
              <span className="type-option__check">
                {active && <Check size={15} aria-hidden="true" />}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
