import { useState, useEffect } from 'react'

const NAV_ITEMS = [
  { id: 'predict', label: '오늘의 예측', icon: '⚾' },
  { id: 'standings', label: '팀 순위', icon: '🏆' },
  { id: 'lineups', label: '1군 라인업', icon: '👥' },
  { id: 'analysis', label: '팀 분석', icon: '📊' },
]

export default function Header({ serverOnline, currentPage, setPage }) {
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  return (
    <header style={{
      background: 'rgba(10,10,18,0.95)',
      borderBottom: '1px solid rgba(255,255,255,0.08)',
      backdropFilter: 'blur(20px)',
      position: 'sticky', top: 0, zIndex: 100,
    }}>
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '0 20px' }}>
        {/* Top bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 64 }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 40, height: 40, borderRadius: 10,
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 20, boxShadow: '0 0 20px rgba(99,102,241,0.4)',
            }}>⚾</div>
            <div>
              <div style={{ fontWeight: 800, fontSize: 18, letterSpacing: '-0.5px' }}>
                KBO <span style={{ color: '#6366f1' }}>AI</span> 예측
              </div>
              <div style={{ fontSize: 11, color: '#505070' }}>Korea Baseball Organization</div>
            </div>
          </div>

          {/* Nav */}
          <nav style={{ display: 'flex', gap: 4 }}>
            {NAV_ITEMS.map(item => (
              <button
                key={item.id}
                onClick={() => setPage(item.id)}
                className="btn"
                style={{
                  background: currentPage === item.id
                    ? 'rgba(99,102,241,0.2)'
                    : 'transparent',
                  color: currentPage === item.id ? '#818cf8' : '#9090b0',
                  border: currentPage === item.id
                    ? '1px solid rgba(99,102,241,0.4)'
                    : '1px solid transparent',
                  padding: '7px 14px',
                  fontSize: 13,
                }}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
          </nav>

          {/* Status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ fontSize: 13, color: '#505070' }}>
              {time.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
              <div style={{
                width: 8, height: 8, borderRadius: '50%',
                background: serverOnline === null ? '#f59e0b'
                  : serverOnline ? '#22c55e' : '#ef4444',
                boxShadow: serverOnline ? '0 0 8px #22c55e' : 'none',
                animation: serverOnline === null ? 'pulse 1s infinite' : 'none',
              }} />
              <span style={{ color: '#505070' }}>
                {serverOnline === null ? '연결 중' : serverOnline ? '서버 연결됨' : '오프라인'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
