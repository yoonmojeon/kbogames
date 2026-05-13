import { useState, useEffect } from 'react'
import axios from 'axios'
import {
  BarChart, Bar, LineChart, Line, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, Cell,
} from 'recharts'

const KBO_TEAMS = ['KIA', 'LG', 'SSG', 'KT', 'NC', '두산', '롯데', '삼성', '한화', '키움']
const TEAM_COLORS = {
  KIA: '#EA0029', LG: '#C30452', SSG: '#CE0E2D', KT: '#888',
  NC: '#1D467E', '두산': '#3344bb', '롯데': '#002B5B',
  '삼성': '#1428A0', '한화': '#FF6600', '키움': '#820024',
}

function StatBox({ label, value, unit = '', color = '#818cf8' }) {
  return (
    <div style={{
      padding: '14px 16px', borderRadius: 12,
      background: 'rgba(255,255,255,0.04)',
      border: '1px solid rgba(255,255,255,0.06)',
      textAlign: 'center',
    }}>
      <div style={{ fontSize: 22, fontWeight: 800, color }}>{value}{unit}</div>
      <div style={{ fontSize: 11, color: '#505070', marginTop: 2 }}>{label}</div>
    </div>
  )
}

function H2HSection({ teamA, teamB }) {
  const [h2h, setH2h] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!teamA || !teamB || teamA === teamB) return
    setLoading(true)
    axios.get(`/api/h2h/${teamA}/${teamB}?season=2026`)
      .then(r => setH2h(r.data))
      .catch(() => setH2h(null))
      .finally(() => setLoading(false))
  }, [teamA, teamB])

  if (!teamA || !teamB || teamA === teamB) return null

  const colorA = TEAM_COLORS[teamA]
  const colorB = TEAM_COLORS[teamB]

  return (
    <div className="card" style={{ padding: 20, marginTop: 16 }}>
      <h3 style={{ fontWeight: 700, fontSize: 15, marginBottom: 16 }}>
        ⚔️ 2026 상대 전적: {teamA} vs {teamB}
      </h3>

      {loading ? (
        <div className="skeleton" style={{ height: 100, borderRadius: 10 }} />
      ) : !h2h || h2h.total === 0 ? (
        <div style={{ color: '#505070', textAlign: 'center', padding: 20 }}>
          상대 전적 데이터 없음
        </div>
      ) : (
        <>
          {/* 전적 바 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <div style={{ textAlign: 'right', minWidth: 80 }}>
              <div style={{ fontWeight: 800, fontSize: 20, color: colorA }}>{h2h.home_wins}</div>
              <div style={{ fontSize: 12, color: '#9090b0' }}>{teamA}</div>
            </div>
            <div style={{ flex: 1, height: 12, borderRadius: 6, overflow: 'hidden', display: 'flex' }}>
              <div style={{
                height: '100%',
                width: `${h2h.total > 0 ? (h2h.home_wins / h2h.total) * 100 : 50}%`,
                background: `linear-gradient(90deg, ${colorA}, ${colorA}80)`,
                transition: 'width 0.6s',
              }} />
              <div style={{
                height: '100%',
                flex: 1,
                background: `linear-gradient(90deg, ${colorB}80, ${colorB})`,
              }} />
            </div>
            <div style={{ minWidth: 80 }}>
              <div style={{ fontWeight: 800, fontSize: 20, color: colorB }}>{h2h.away_wins}</div>
              <div style={{ fontSize: 12, color: '#9090b0' }}>{teamB}</div>
            </div>
          </div>

          {/* 최근 대결 */}
          {h2h.games && h2h.games.length > 0 && (
            <div>
              <div style={{ fontSize: 11, color: '#505070', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>최근 대결</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {h2h.games.slice(-5).reverse().map((g, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '6px 12px', borderRadius: 8,
                    background: 'rgba(255,255,255,0.03)',
                    fontSize: 13,
                  }}>
                    <span style={{ color: '#505070', width: 90 }}>{g.date}</span>
                    <span style={{ flex: 1, textAlign: 'right' }}>{g.away_team}</span>
                    <span style={{ fontWeight: 700, color: '#818cf8', padding: '0 8px' }}>
                      {g.away_score} : {g.home_score}
                    </span>
                    <span style={{ flex: 1 }}>{g.home_team}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default function AnalysisPage() {
  const [selectedTeam, setSelectedTeam] = useState('LG')
  const [compareTeam, setCompareTeam] = useState('KIA')
  const [teamStats, setTeamStats] = useState(null)
  const [recentGames, setRecentGames] = useState([])
  const [modelInfo, setModelInfo] = useState(null)
  const [modelPerformance, setModelPerformance] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!selectedTeam) return
    setLoading(true)
    Promise.all([
      axios.get(`/api/team/${selectedTeam}/stats?n_games=30`),
      axios.get(`/api/games/recent?team=${selectedTeam}&limit=30`),
    ]).then(([statsRes, gamesRes]) => {
      setTeamStats(statsRes.data)
      setRecentGames(gamesRes.data)
    }).catch(() => {}).finally(() => setLoading(false))

    axios.get('/api/model/info').then(r => setModelInfo(r.data)).catch(() => {})
    axios.get('/api/model/performance?limit=500').then(r => setModelPerformance(r.data)).catch(() => {})
  }, [selectedTeam])

  // 최근 경기 데이터를 차트용으로 변환
  const formChartData = recentGames.slice(0, 20).reverse().map((g, i) => {
    const isHome = g.home_team === selectedTeam
    const scored = isHome ? g.home_score : g.away_score
    const allowed = isHome ? g.away_score : g.home_score
    const win = (isHome && g.home_win === 1) || (!isHome && g.home_win === 0)
    return {
      game: `G${i + 1}`,
      득점: scored,
      실점: allowed,
      결과: win ? 1 : 0,
    }
  })

  const radarData = teamStats ? [
    { subject: '승률', A: (teamStats.recent_stats?.win_rate || 0) * 100 },
    { subject: '득점력', A: Math.min((teamStats.recent_stats?.avg_runs_scored || 0) / 8 * 100, 100) },
    { subject: '수비력', A: Math.max(100 - (teamStats.recent_stats?.avg_runs_allowed || 0) / 8 * 100, 0) },
    { subject: '홈 성적', A: (teamStats.season_stats?.win_rate || 0) * 100 },
    { subject: '최근 폼', A: (teamStats.recent_stats?.recent_form?.slice(-5).filter(Boolean).length || 0) / 5 * 100 },
  ] : []

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 4 }}>📊 팀 분석</h1>
        <div style={{ color: '#505070', fontSize: 14 }}>팀 성적 분석 및 상대 전적 비교</div>
      </div>

      {/* 팀 선택 */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <label style={{ fontSize: 12, color: '#9090b0', marginBottom: 6, display: 'block' }}>분석 팀</label>
          <select
            value={selectedTeam}
            onChange={e => setSelectedTeam(e.target.value)}
            style={{
              padding: '10px 14px', borderRadius: 10,
              background: '#1e1e35', border: '1px solid rgba(255,255,255,0.15)',
              color: TEAM_COLORS[selectedTeam] || '#f0f0ff',
              fontSize: 15, fontWeight: 700, fontFamily: 'inherit', cursor: 'pointer',
            }}
          >
            {KBO_TEAMS.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div style={{ paddingTop: 20, color: '#505070', fontWeight: 700 }}>VS</div>
        <div>
          <label style={{ fontSize: 12, color: '#9090b0', marginBottom: 6, display: 'block' }}>비교 팀</label>
          <select
            value={compareTeam}
            onChange={e => setCompareTeam(e.target.value)}
            style={{
              padding: '10px 14px', borderRadius: 10,
              background: '#1e1e35', border: '1px solid rgba(255,255,255,0.15)',
              color: TEAM_COLORS[compareTeam] || '#f0f0ff',
              fontSize: 15, fontWeight: 700, fontFamily: 'inherit', cursor: 'pointer',
            }}
          >
            {KBO_TEAMS.filter(t => t !== selectedTeam).map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </div>

      {loading ? (
        <div style={{ display: 'grid', gap: 16 }}>
          {[...Array(3)].map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 200, borderRadius: 16 }} />
          ))}
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 16 }}>
          {/* 스탯 요약 */}
          {teamStats && (
            <div className="card" style={{ padding: 20 }}>
              <h3 style={{ fontWeight: 700, fontSize: 15, marginBottom: 16, color: TEAM_COLORS[selectedTeam] }}>
                {selectedTeam} 팀 성적 요약
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))', gap: 10 }}>
                <StatBox label="시즌 승률" value={teamStats.season_stats?.win_rate?.toFixed(3) || '-'} color={TEAM_COLORS[selectedTeam]} />
                <StatBox label="시즌 승" value={teamStats.season_stats?.wins || 0} color="#22c55e" />
                <StatBox label="시즌 패" value={teamStats.season_stats?.losses || 0} color="#ef4444" />
                <StatBox label="최근 평균 득점" value={teamStats.recent_stats?.avg_runs_scored || '-'} color="#f59e0b" />
                <StatBox label="최근 평균 실점" value={teamStats.recent_stats?.avg_runs_allowed || '-'} color="#6366f1" />
                <StatBox label="최근 20경기 승률" value={teamStats.recent_stats?.win_rate?.toFixed(3) || '-'} />
              </div>
            </div>
          )}

          {/* 최근 득점/실점 차트 */}
          {formChartData.length > 0 && (
            <div className="card" style={{ padding: 20 }}>
              <h3 style={{ fontWeight: 700, fontSize: 15, marginBottom: 16 }}>
                최근 경기 득점/실점 추이
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={formChartData} barCategoryGap="20%">
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="game" tick={{ fill: '#505070', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#505070', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#1e1e35', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }}
                    labelStyle={{ color: '#9090b0' }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12, color: '#9090b0' }} />
                  <Bar dataKey="득점" fill={TEAM_COLORS[selectedTeam] || '#6366f1'} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="실점" fill="rgba(255,255,255,0.15)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 레이더 차트 */}
          {radarData.length > 0 && (
            <div className="card" style={{ padding: 20 }}>
              <h3 style={{ fontWeight: 700, fontSize: 15, marginBottom: 16 }}>
                팀 능력치 레이더
              </h3>
              <ResponsiveContainer width="100%" height={260}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="rgba(255,255,255,0.1)" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: '#9090b0', fontSize: 12 }} />
                  <Radar
                    name={selectedTeam}
                    dataKey="A"
                    stroke={TEAM_COLORS[selectedTeam] || '#6366f1'}
                    fill={TEAM_COLORS[selectedTeam] || '#6366f1'}
                    fillOpacity={0.25}
                    strokeWidth={2}
                  />
                  <Tooltip
                    contentStyle={{ background: '#1e1e35', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }}
                    formatter={(val) => [`${val.toFixed(1)}`, '']}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 상대 전적 */}
          <H2HSection teamA={selectedTeam} teamB={compareTeam} />

          {/* 모델 정보 */}
          {modelPerformance?.available && (
            <div className="card" style={{ padding: 20 }}>
              <h3 style={{ fontWeight: 700, fontSize: 15, marginBottom: 16 }}>예측-실제 결과 대시보드</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 10, marginBottom: 16 }}>
                <StatBox label="최근 평가 정확도" value={`${((modelPerformance.metrics?.accuracy || 0) * 100).toFixed(1)}`} unit="%" color="#22c55e" />
                <StatBox label="Brier Score" value={(modelPerformance.metrics?.brier || 0).toFixed(4)} color="#818cf8" />
                <StatBox label="LogLoss" value={(modelPerformance.metrics?.logloss || 0).toFixed(4)} color="#f59e0b" />
                <StatBox label="평가 경기 수" value={modelPerformance.metrics?.sample_size?.toLocaleString() || '-'} color="#6366f1" />
              </div>

              {modelPerformance.calibration?.length > 0 && (
                <div style={{ marginBottom: 18 }}>
                  <div style={{ fontSize: 12, color: '#505070', marginBottom: 8 }}>확률 구간별 실제 홈승률</div>
                  <ResponsiveContainer width="100%" height={190}>
                    <BarChart data={modelPerformance.calibration}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="bucket" tick={{ fill: '#505070', fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: '#505070', fontSize: 10 }} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={{ background: '#1e1e35', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }} />
                      <Legend wrapperStyle={{ fontSize: 12, color: '#9090b0' }} />
                      <Bar dataKey="avg_prob" name="평균 예측확률" fill="#818cf8" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="actual_rate" name="실제 홈승률" fill="#22c55e" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {modelPerformance.recent?.length > 0 && (
                <div>
                  <div style={{ fontSize: 12, color: '#505070', marginBottom: 8 }}>최근 예측 적중 기록</div>
                  <div style={{ display: 'grid', gap: 6 }}>
                    {modelPerformance.recent.slice(0, 8).map((g, i) => (
                      <div key={`${g.date}-${i}`} style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '7px 10px', borderRadius: 8,
                        background: g.correct ? 'rgba(34,197,94,0.07)' : 'rgba(239,68,68,0.07)',
                        fontSize: 12,
                      }}>
                        <span style={{ width: 82, color: '#505070' }}>{g.date}</span>
                        <span style={{ flex: 1 }}>{g.away_team} @ {g.home_team}</span>
                        <span style={{ color: '#9090b0' }}>예측 {g.predicted}</span>
                        <span style={{ color: g.correct ? '#22c55e' : '#ef4444', fontWeight: 700 }}>
                          {g.correct ? '적중' : `실제 ${g.actual}`}
                        </span>
                      </div>
                    ))}
                  </div>
                  <div style={{ marginTop: 10, fontSize: 11, color: '#505070' }}>{modelPerformance.note}</div>
                </div>
              )}
            </div>
          )}

          {modelInfo && modelInfo.metrics && (
            <div className="card" style={{ padding: 20 }}>
              <h3 style={{ fontWeight: 700, fontSize: 15, marginBottom: 16 }}>🤖 AI 모델 성능</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 10 }}>
                <StatBox label="예측 정확도" value={`${((modelInfo.metrics.accuracy || 0) * 100).toFixed(1)}`} unit="%" color="#22c55e" />
                <StatBox label="AUC-ROC" value={(modelInfo.metrics.auc_roc || 0).toFixed(4)} color="#818cf8" />
                <StatBox label="학습 경기" value={modelInfo.train_size?.toLocaleString() || '-'} color="#f59e0b" />
                <StatBox label="테스트 경기" value={modelInfo.test_size?.toLocaleString() || '-'} color="#6366f1" />
              </div>

              {modelInfo.feature_importance && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ fontSize: 12, color: '#505070', marginBottom: 10 }}>주요 예측 피처 (Top 8)</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {Object.entries(modelInfo.feature_importance).slice(0, 8).map(([feat, imp]) => (
                      <div key={feat} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{ width: 160, fontSize: 12, color: '#9090b0', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                          {feat.replace(/_/g, ' ')}
                        </div>
                        <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.06)' }}>
                          <div style={{
                            height: '100%', borderRadius: 3,
                            width: `${(imp / Object.values(modelInfo.feature_importance)[0]) * 100}%`,
                            background: 'linear-gradient(90deg, #6366f1, #818cf8)',
                            transition: 'width 0.6s',
                          }} />
                        </div>
                        <div style={{ fontSize: 11, color: '#505070', width: 50, textAlign: 'right' }}>
                          {imp.toFixed(3)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
