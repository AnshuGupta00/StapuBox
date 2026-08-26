/**
 * This-or-That body: two opposing sides and nothing else.
 *
 * There is deliberately no reveal affordance and no correct-answer styling here —
 * the type is opinion-based by design, and the card must not imply a verdict.
 */

export default function PollCard({ item }) {
  const [left, right] = item.options

  return (
    <>
      <p className="card__prompt">{item.prompt}</p>
      <div className="duel">
        <div className="duel__side">{left}</div>
        <div className="duel__vs" aria-hidden="true">
          VS
        </div>
        <div className="duel__side">{right}</div>
      </div>
      {item.explanation && (
        <p className="cites__why" style={{ fontStyle: 'normal' }}>
          {item.explanation}
        </p>
      )}
    </>
  )
}
