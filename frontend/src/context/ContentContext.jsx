/**
 * Shares one instance of `useContentGeneration` with the whole dashboard, so the
 * form, the card list and the insights panel all read the same batch without
 * prop-drilling through four layers.
 */

import { createContext, useContext } from 'react'

import { useContentGeneration } from '../hooks/useContentGeneration'

const ContentContext = createContext(null)

export function ContentProvider({ children }) {
  const value = useContentGeneration()
  return <ContentContext.Provider value={value}>{children}</ContentContext.Provider>
}

export function useContent() {
  const value = useContext(ContentContext)
  if (!value) {
    throw new Error('useContent must be used inside <ContentProvider>')
  }
  return value
}

export default ContentContext
