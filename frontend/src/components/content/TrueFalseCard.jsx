/**
 * True / False body: the statement plus a two-up verdict strip that only lights
 * up the winning side once the answer is revealed.
 */

export default function TrueFalseCard({ item, revealed }) {
  return (
    <>
      <p className="card__prompt">{item.statement}</p>
      <div className="tf-answer" role="group" aria-label="Verdict">
        {[true, false].map((value) => {
          const active = revealed && item.answer === value
          return (
            <div
              className={`tf-answer__side${active ? ' tf-answer__side--active' : ''}`}
              key={String(value)}
            >
              {value ? 'True' : 'False'}
            </div>
          )
        })}
      </div>
    </>
  )
}
