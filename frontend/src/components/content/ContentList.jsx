/**
 * The batch grid, with the two states that matter around it: skeletons while a
 * request is in flight, and a first-run empty state that explains what the five
 * formats are for.
 */

import { Sparkles } from 'lucide-react'

import { useContent } from '../../context/ContentContext'
import { CardSkeletons } from '../common/Loader'
import ContentCard from './ContentCard'

export default function ContentList() {
  const { items, loading, request } = useContent()

  if (loading && !items.length) return <CardSkeletons count={request.count} />

  if (!items.length) {
    return (
      <div className="panel">
        <div className="empty">
          <span className="empty__icon">
            <Sparkles size={22} aria-hidden="true" />
          </span>
          <h3>No content yet</h3>
          <p>
            Pick a sport and hit <strong>Generate content</strong>. You&apos;ll get a mixed
            batch — quiz, true/false, this-or-that, fill-in-the-blank and guess-the-number —
            each one schema-checked, grounded in retrieved evidence, and pre-shaped for an
            Instagram sticker or caption.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="card-grid">
      {items.map((item) => (
        <ContentCard item={item} key={item.id} />
      ))}
    </div>
  )
}
