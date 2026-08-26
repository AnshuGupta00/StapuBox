/** Inline spinner with a label, and a card-shaped skeleton for pending batches. */

import { Loader2 } from 'lucide-react'

export default function Loader({ label = 'Working…' }) {
  return (
    <span className="loader" role="status">
      <Loader2 size={16} className="spin" aria-hidden="true" />
      {label}
    </span>
  )
}

export function CardSkeletons({ count = 4 }) {
  return (
    <div className="card-grid" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="skeleton" />
      ))}
    </div>
  )
}
