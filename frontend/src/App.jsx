import { ContentProvider } from './context/ContentContext'
import Dashboard from './pages/Dashboard'

export default function App() {
  return (
    <ContentProvider>
      <Dashboard />
    </ContentProvider>
  )
}
