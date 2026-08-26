/** A dismissible failure message, and the softer banner used for warnings. */

import { Info, X } from 'lucide-react'

export default function ErrorMessage({ title = 'Request failed', message, onDismiss }) {
  if (!message) return null
  return (
    <div className="alert" role="alert">
      <div>
        <div className="alert__title">{title}</div>
        <div>{message}</div>
      </div>
      {onDismiss && (
        <button className="alert__close" onClick={onDismiss} aria-label="Dismiss">
          <X size={16} />
        </button>
      )}
    </div>
  )
}

export function Banner({ children }) {
  if (!children) return null
  return (
    <div className="banner">
      <Info size={16} style={{ flex: 'none', marginTop: 1 }} aria-hidden="true" />
      <div>{children}</div>
    </div>
  )
}
