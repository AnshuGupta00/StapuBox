/** Sport picker. Options come from `/api/meta`, emoji from the local map. */

import { SPORT_EMOJI } from '../../utils/constants'

export default function SportSelector({ sports, value, onChange, disabled = false }) {
  return (
    <div className="field">
      <label className="field__label" htmlFor="sport-cricket">
        Sport
      </label>
      <div className="sport-grid" role="group" aria-label="Sport">
        {sports.map((sport) => (
          <button
            key={sport}
            id={`sport-${sport.toLowerCase().replace(/\s+/g, '-')}`}
            type="button"
            className="sport-chip"
            aria-pressed={value === sport}
            disabled={disabled}
            onClick={() => onChange(sport)}
          >
            <span className="sport-chip__emoji" aria-hidden="true">
              {SPORT_EMOJI[sport] || '🏆'}
            </span>
            {sport}
          </button>
        ))}
      </div>
    </div>
  )
}
