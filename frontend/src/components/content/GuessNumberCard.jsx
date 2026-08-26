/**
 * Guess-the-number body: the question, then either the tolerance hint or the
 * target with its accepted range.
 *
 * Before the reveal only the tolerance is shown — the accepted range brackets the
 * target, so printing it early would give the answer away.
 */

export default function GuessNumberCard({ item, revealed }) {
  const tolerance = item.range_label?.match(/±\s*([^)]+)/)?.[1] ?? item.tolerance

  return (
    <>
      <p className="card__prompt">{item.question}</p>

      {revealed ? (
        <div className="target">
          <span className="target__value">{item.correct_answer}</span>
          <span className="target__range">accepted {item.range_label}</span>
        </div>
      ) : (
        <div className="target">
          <span className="target__value" aria-hidden="true">
            ?
          </span>
          <span className="target__unit">
            any guess within ±{tolerance}
            {item.unit ? ` ${item.unit}` : ''} counts as correct
          </span>
        </div>
      )}
    </>
  )
}
