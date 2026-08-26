/**
 * Fill-in-the-blank body: the sentence with its blank highlighted in place — and
 * filled in once revealed — followed by the four candidate fills.
 */

import { Check } from 'lucide-react'

import { BLANK_TOKEN, OPTION_LETTERS } from '../../utils/constants'
import { splitOnBlank } from '../../utils/format'

export default function FillBlankCard({ item, revealed }) {
  const [before, after] = splitOnBlank(item.sentence)

  return (
    <>
      <p className="card__prompt blank-sentence">
        {before}
        <mark>{revealed ? item.correct_answer : BLANK_TOKEN}</mark>
        {after}
      </p>
      <div className="options">
        {item.options.map((option, index) => {
          const correct = revealed && index === item.correct_index
          return (
            <div className={`option${correct ? ' option--correct' : ''}`} key={option}>
              <span className="option__letter">{OPTION_LETTERS[index]}</span>
              <span className="option__text">{option}</span>
              {correct && (
                <span className="option__mark">
                  <Check size={15} aria-hidden="true" />
                </span>
              )}
            </div>
          )
        })}
      </div>
    </>
  )
}
