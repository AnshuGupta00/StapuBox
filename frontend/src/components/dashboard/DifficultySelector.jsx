/**
 * Difficulty picker.
 *
 * The hint spells out what difficulty actually changes: it widens the knowledge
 * base sweep and asks for more obscure facts, and it is ignored for polls, which
 * have no correct answer to be hard about.
 */

const HINTS = {
  Easy: 'Widely known facts — highest completion rate.',
  Medium: 'The engagement sweet spot: answerable, still worth a guess.',
  Hard: 'Obscure records; widens the knowledge base sweep.',
}

export default function DifficultySelector({
  difficulties,
  value,
  onChange,
  disabled = false,
}) {
  return (
    <div className="field">
      <div className="field__label">
        Difficulty
        <span className="field__hint">{HINTS[value] || ''}</span>
      </div>
      <div className="segmented" role="group" aria-label="Difficulty">
        {difficulties.map((level) => (
          <button
            key={level}
            type="button"
            className="segmented__option"
            aria-pressed={value === level}
            disabled={disabled}
            onClick={() => onChange(level)}
          >
            {level}
          </button>
        ))}
      </div>
    </div>
  )
}
