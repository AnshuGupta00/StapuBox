/**
 * One button, three visual weights, plus a built-in busy state so callers never
 * have to hand-roll a spinner next to a label.
 */

import { Loader2 } from 'lucide-react'

export default function Button({
  children,
  variant = 'subtle',
  size = 'md',
  busy = false,
  disabled = false,
  block = false,
  icon: Icon = null,
  className = '',
  ...rest
}) {
  const classes = [
    'btn',
    `btn--${variant}`,
    size === 'sm' ? 'btn--sm' : '',
    block ? 'btn--block' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <button className={classes} disabled={disabled || busy} {...rest}>
      {busy ? (
        <Loader2 size={15} className="spin" aria-hidden="true" />
      ) : (
        Icon && <Icon size={15} aria-hidden="true" />
      )}
      {children}
    </button>
  )
}
