import { useState, useEffect } from 'react'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import PredictPage from './pages/PredictPage'
import StandingsPage from './pages/StandingsPage'
import LineupsPage from './pages/LineupsPage'
import AnalysisPage from './pages/AnalysisPage'

const PAGES = {
  predict: PredictPage,
  standings: StandingsPage,
  lineups: LineupsPage,
  analysis: AnalysisPage,
}

export default function App() {
  const [page, setPage] = useState('predict')
  const [serverOnline, setServerOnline] = useState(null)

  useEffect(() => {
    fetch('/api/health')
      .then(r => r.json())
      .then(d => setServerOnline(d.status === 'ok'))
      .catch(() => setServerOnline(false))
  }, [])

  const PageComponent = PAGES[page] || PredictPage

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Header serverOnline={serverOnline} currentPage={page} setPage={setPage} />
      <div style={{ display: 'flex', flex: 1, padding: '24px 20px', gap: '20px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
        <Sidebar currentPage={page} setPage={setPage} />
        <main style={{ flex: 1, minWidth: 0 }}>
          <PageComponent />
        </main>
      </div>
    </div>
  )
}
