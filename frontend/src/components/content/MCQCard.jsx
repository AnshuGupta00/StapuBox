/**
 * MCQ body: the question plus four options with the correct one marked once the
 * answer is revealed.
 */

import { Check } from 'lucide-react'

import { OPTION_LETTERS } from '../../utils/constants'

export default function MCQCard({ item, revealed }) {
  return (
    <>
      <p className="card__prompt">{item.question}</p>
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
