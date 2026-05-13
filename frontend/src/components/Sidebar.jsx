import { useState, useEffect } from 'react'
import axios from 'axios'

const TEAM_COLORS = {
  KIA: '#EA0029', LG: '#C30452', SSG: '#CE0E2D', KT: '#aaaaaa',
  NC: '#1D467E', '두산': '#4444aa', '롯데': '#002B5B',
  '삼성': '#1428A0', '한화': '#FF6600', '키움': '#820024',
}

export default function Sidebar({ currentPage, setPage }) {
  const [standings, setStandings] = useState([])

  useEffect(() => {
    axios.get('/api/standings').then(r => setStandings(r.data)).catch(() => {})
  }, [])

  return (
    <aside style={{ width: 220, flexShrink: 0 }}>
      {/* 미니 순위 */}
      <div className="card" style={{ padding: 16 }}>
        <div style={{
          fontSize: 11, fontWeight: 700, color: '#505070',
          textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12
        }}>
          현재 순위
        </div>

        {standings.length === 0 ? (
          [...Array(10)].map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 28, marginBottom: 4 }} />
          ))
        ) : (
          standings.slice(0, 10).map((s, i) => (
            <div
              key={s.team}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '5px 6px', borderRadius: 8,
                cursor: 'pointer',
                transition: 'background 0.2s',
                background: i < 5 ? 'rgba(99,102,241,0.04)' : 'transparent',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
              onMouseLeave={e => e.currentTarget.style.background = i < 5 ? 'rgba(99,102,241,0.04)' : 'transparent'}
              onClick={() => setPage('standings')}
            >
              <span style={{
                width: 18, textAlign: 'center', fontSize: 11, fontWeight: 700,
                color: i === 0 ? '#fbbf24' : i < 5 ? '#6366f1' : '#505070',
              }}>
                {s.rank || i + 1}
              </span>
              <div style={{
                width: 4, height: 20, borderRadius: 2,
                background: TEAM_COLORS[s.team] || '#444',
                flexShrink: 0,
              }} />
              <span style={{ flex: 1, fontSize: 13, fontWeight: 500 }}>{s.team}</span>
              <span style={{ fontSize: 12, color: '#505070' }}>
                {s.win_rate ? s.win_rate.toFixed(3) : '-'}
              </span>
            </div>
          ))
        )}

        <button
          onClick={() => setPage('standings')}
          className="btn btn-ghost"
          style={{ width: '100%', justifyContent: 'center', marginTop: 10, fontSize: 12 }}
        >
          전체 순위 보기
        </button>
      </div>

      {/* 데이터 기준일 */}
      <div style={{
        marginTop: 12, padding: '10px 14px',
        background: 'rgba(99,102,241,0.08)',
        border: '1px solid rgba(99,102,241,0.2)',
        borderRadius: 10, fontSize: 11, color: '#6366f1',
      }}>
        <div style={{ fontWeight: 600, marginBottom: 2 }}>데이터 기준일</div>
        <div style={{ color: '#818cf8' }}>2026년 5월 12일</div>
        <div style={{ marginTop: 6, color: '#505070' }}>AI 앙상블 예측</div>
        <div style={{ color: '#505070' }}>XGBoost + LightGBM + NN</div>
      </div>
    </aside>
  )
}
