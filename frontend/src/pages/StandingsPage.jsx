import { useState, useEffect } from 'react'
import axios from 'axios'

const TEAM_COLORS = {
  KIA: '#EA0029', LG: '#C30452', SSG: '#CE0E2D', KT: '#888',
  NC: '#1D467E', '두산': '#3344bb', '롯데': '#002B5B',
  '삼성': '#1428A0', '한화': '#FF6600', '키움': '#820024',
}

export default function StandingsPage() {
  const [standings, setStandings] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedTeam, setSelectedTeam] = useState(null)
  const [teamStats, setTeamStats] = useState(null)
  const [updatedAt, setUpdatedAt] = useState(null)

  useEffect(() => {
    loadStandings()
  }, [])

  const loadStandings = (refresh = false) => {
    setLoading(true)
    axios.get(`/api/standings${refresh ? '?refresh=true' : ''}`)
      .then(r => setStandings(r.data))
      .catch(() => {})
      .finally(() => {
        setUpdatedAt(new Date())
        setLoading(false)
      })
  }

  const handleTeamClick = async (team) => {
    setSelectedTeam(team)
    try {
      const r = await axios.get(`/api/team/${team}/stats`)
      setTeamStats(r.data)
    } catch (e) {}
  }

  const getMedalColor = (rank) => {
    if (rank === 1) return '#fbbf24'
    if (rank === 2) return '#94a3b8'
    if (rank === 3) return '#b45309'
    return null
  }

  return (
    <div>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 4 }}>🏆 팀 순위</h1>
          <div style={{ color: '#505070', fontSize: 14 }}>
            2026 KBO 리그 정규시즌 순위 · KBO 공식 실시간 반영
            {updatedAt && <span> · 갱신 {updatedAt.toLocaleTimeString('ko-KR')}</span>}
          </div>
        </div>
        <button
          className="btn btn-primary"
          disabled={loading}
          onClick={() => loadStandings(true)}
          style={{ fontSize: 13 }}
        >
          {loading ? '갱신 중...' : '실시간 순위 갱신'}
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: selectedTeam ? '1fr 340px' : '1fr', gap: 20 }}>
        {/* 순위표 */}
        <div className="card" style={{ overflow: 'hidden' }}>
          {/* 테이블 헤더 */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '48px 1fr 60px 60px 60px 60px 80px 80px',
            gap: 0, padding: '12px 20px',
            background: 'rgba(99,102,241,0.08)',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            fontSize: 11, fontWeight: 700, color: '#505070',
            textTransform: 'uppercase', letterSpacing: '0.06em',
          }}>
            <span>순위</span>
            <span>팀</span>
            <span style={{ textAlign: 'center' }}>경기</span>
            <span style={{ textAlign: 'center' }}>승</span>
            <span style={{ textAlign: 'center' }}>패</span>
            <span style={{ textAlign: 'center' }}>무</span>
            <span style={{ textAlign: 'center' }}>승률</span>
            <span style={{ textAlign: 'center' }}>게임차</span>
          </div>

          {loading ? (
            [...Array(10)].map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 52, margin: '4px 12px', borderRadius: 8 }} />
            ))
          ) : standings.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: '#505070' }}>
              데이터 없음. 데이터 수집 후 다시 시도하세요.
            </div>
          ) : (
            standings.map((s, i) => {
              const isPlayoff = i < 5
              const isSelected = selectedTeam === s.team
              const medal = getMedalColor(i + 1)
              const color = TEAM_COLORS[s.team]

              return (
                <div
                  key={s.team}
                  onClick={() => handleTeamClick(s.team)}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '48px 1fr 60px 60px 60px 60px 80px 80px',
                    gap: 0, padding: '14px 20px',
                    borderBottom: '1px solid rgba(255,255,255,0.04)',
                    cursor: 'pointer',
                    background: isSelected
                      ? `${color}15`
                      : isPlayoff
                        ? 'rgba(99,102,241,0.04)'
                        : 'transparent',
                    transition: 'all 0.2s',
                    borderLeft: isSelected ? `3px solid ${color}` : '3px solid transparent',
                  }}
                  onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = 'rgba(255,255,255,0.04)' }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = isSelected ? `${color}15`
                      : isPlayoff ? 'rgba(99,102,241,0.04)' : 'transparent'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <span style={{
                      fontSize: 14, fontWeight: 800,
                      color: medal || (isPlayoff ? '#6366f1' : '#505070'),
                    }}>
                      {medal ? (i === 0 ? '🥇' : i === 1 ? '🥈' : '🥉') : i + 1}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{
                      width: 4, height: 28, borderRadius: 2,
                      background: color || '#444',
                    }} />
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 14 }}>{s.team}</div>
                      {isPlayoff && (
                        <div style={{ fontSize: 10, color: '#6366f1' }}>포스트시즌</div>
                      )}
                    </div>
                  </div>

                  {[s.games, s.wins, s.losses, s.draws || 0].map((v, j) => (
                    <div key={j} style={{
                      textAlign: 'center', fontSize: 13,
                      color: j === 1 ? '#22c55e' : j === 2 ? '#ef4444' : '#9090b0',
                      fontWeight: j < 3 ? 600 : 400,
                    }}>
                      {v || 0}
                    </div>
                  ))}

                  <div style={{
                    textAlign: 'center', fontSize: 15, fontWeight: 800,
                    color: isSelected ? color : '#f0f0ff',
                  }}>
                    {s.win_rate ? s.win_rate.toFixed(3) : '.000'}
                  </div>

                  <div style={{ textAlign: 'center', fontSize: 13, color: '#505070' }}>
                    {s.gb || '-'}
                  </div>
                </div>
              )
            })
          )}

          {/* 포스트시즌 구분선 표시 */}
          {!loading && standings.length > 5 && (
            <div style={{
              padding: '6px 20px', fontSize: 11, color: '#6366f1',
              background: 'rgba(99,102,241,0.05)',
              borderTop: '1px dashed rgba(99,102,241,0.3)',
            }}>
              ↑ 포스트시즌 진출권 (5위 이상)
            </div>
          )}
        </div>

        {/* 팀 상세 패널 */}
        {selectedTeam && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div className="card" style={{ padding: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
                <h3 style={{ fontWeight: 800, fontSize: 18 }}>
                  <span style={{ marginRight: 8,
                    color: TEAM_COLORS[selectedTeam] }}>■</span>
                  {selectedTeam}
                </h3>
                <button
                  onClick={() => setSelectedTeam(null)}
                  style={{ background: 'none', border: 'none', color: '#505070', cursor: 'pointer', fontSize: 18 }}
                >×</button>
              </div>

              {teamStats ? (
                <>
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 11, color: '#505070', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>2026 시즌 성적</div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
                      {[
                        { label: '승', value: teamStats.season_stats?.wins, color: '#22c55e' },
                        { label: '패', value: teamStats.season_stats?.losses, color: '#ef4444' },
                        { label: '승률', value: teamStats.season_stats?.win_rate?.toFixed(3), color: '#818cf8' },
                      ].map(item => (
                        <div key={item.label} style={{
                          padding: '10px 12px', borderRadius: 10,
                          background: 'rgba(255,255,255,0.04)',
                          border: '1px solid rgba(255,255,255,0.06)',
                          textAlign: 'center',
                        }}>
                          <div style={{ fontSize: 20, fontWeight: 800, color: item.color }}>
                            {item.value ?? '-'}
                          </div>
                          <div style={{ fontSize: 11, color: '#505070' }}>{item.label}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: 11, color: '#505070', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>최근 20경기</div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                      {[
                        { label: '승률', value: teamStats.recent_stats?.win_rate?.toFixed(3) },
                        { label: '평균 득점', value: teamStats.recent_stats?.avg_runs_scored },
                        { label: '평균 실점', value: teamStats.recent_stats?.avg_runs_allowed },
                        { label: '득실차', value: teamStats.recent_stats ? (teamStats.recent_stats.avg_runs_scored - teamStats.recent_stats.avg_runs_allowed).toFixed(2) : '-' },
                      ].map(item => (
                        <div key={item.label} style={{
                          padding: '8px 12px', borderRadius: 8,
                          background: 'rgba(255,255,255,0.03)',
                          border: '1px solid rgba(255,255,255,0.05)',
                          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        }}>
                          <span style={{ fontSize: 12, color: '#9090b0' }}>{item.label}</span>
                          <span style={{ fontSize: 14, fontWeight: 700 }}>{item.value ?? '-'}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* 최근 폼 */}
                  {teamStats.recent_stats?.recent_form && (
                    <div style={{ marginTop: 14 }}>
                      <div style={{ fontSize: 11, color: '#505070', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        최근 폼 (최신 →)
                      </div>
                      <div style={{ display: 'flex', gap: 6 }}>
                        {teamStats.recent_stats.recent_form.map((w, i) => (
                          <div key={i} style={{
                            flex: 1, height: 32, borderRadius: 6,
                            background: w ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)',
                            border: `1px solid ${w ? 'rgba(34,197,94,0.4)' : 'rgba(239,68,68,0.4)'}`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 11, fontWeight: 700,
                            color: w ? '#22c55e' : '#ef4444',
                          }}>
                            {w ? 'W' : 'L'}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div style={{ color: '#505070', textAlign: 'center', padding: 20 }}>로딩 중...</div>
              )}
            </div>

            <button
              className="btn btn-ghost"
              style={{ justifyContent: 'center', width: '100%' }}
              onClick={() => {
                window.location.href = `/api/h2h/${selectedTeam}/KIA`
              }}
            >
              라인업 보기
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
