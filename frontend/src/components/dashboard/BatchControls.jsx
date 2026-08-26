/**
 * Actions on the batch that is already on screen: regenerate the whole thing,
 * copy every item as paste-ready text, or clear the board.
 *
 * "Regenerate batch" re-runs the same request — the novelty ledger on the backend
 * guarantees the second batch is different content, not a reshuffle.
 */

import { Copy, RefreshCw, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { useContent } from '../../context/ContentContext'
import { batchToText, copyText } from '../../utils/format'
import Button from '../common/Button'

export default function BatchControls() {
  const { items, loading, generate, clear, batchId } = useContent()
  const [copied, setCopied] = useState(false)

  if (!items.length) return null

  const copyAll = async () => {
    const ok = await copyText(batchToText(items))
    setCopied(ok)
    setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div className="section-head">
      <h2>Generated content</h2>
      <span className="section-head__meta">
        {items.length} item{items.length === 1 ? '' : 's'}
        {batchId ? ` · batch ${batchId}` : ''}
      </span>
      <span className="topbar__spacer" />
      <div className="btn-row">
        <Button size="sm" variant="ghost" icon={Copy} onClick={copyAll}>
          {copied ? 'Copied' : 'Copy all'}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          icon={RefreshCw}
          busy={loading}
          onClick={generate}
        >
          Regenerate batch
        </Button>
        <Button size="sm" variant="danger" icon={Trash2} onClick={clear} disabled={loading}>
          Clear
        </Button>
      </div>
    </div>
  )
}
