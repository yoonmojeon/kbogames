import { useState, useEffect } from 'react'
import axios from 'axios'
import PredictCard from '../components/PredictCard'

const KBO_TEAMS = ['KIA', 'LG', 'SSG', 'KT', 'NC', '두산', '롯데', '삼성', '한화', '키움']

export default function PredictPage() {
  const [todayGames, setTodayGames] = useState([])
  const [loading, setLoading] = useState(true)
  const [customPrediction, setCustomPrediction] = useState(null)
  const [customLoading, setCustomLoading] = useState(false)
  const [form, setForm] = useState({ home: 'LG', away: 'KIA', home_pitcher: '', away_pitcher: '' })
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('today')
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().slice(0, 10))
  const [scheduleSource, setScheduleSource] = useState('')

  const loadGamesByDate = (date, refresh = false) => {
    setLoading(true)
    axios.get(`/api/games/date?game_date=${date}${refresh ? '&refresh=true' : ''}`)
      .then(r => {
        setTodayGames(r.data.games || [])
        setScheduleSource(r.data.games?.[0]?.source || '')
      })
      .catch(() => {
        setTodayGames([])
        setScheduleSource('')
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadGamesByDate(selectedDate)
  }, [])

  const handleCustomPredict = async () => {
    if (form.home === form.away) {
      setError('홈팀과 원정팀이 같을 수 없습니다')
      return
    }
    setError(null)
    setCustomLoading(true)
    try {
      const r = await axios.post('/api/predict', {
        home_team: form.home,
        away_team: form.away,
        home_pitcher: form.home_pitcher || null,
        away_pitcher: form.away_pitcher || null,
      })
      setCustomPrediction(r.data)
      setTab('custom')
    } catch (e) {
      setError(e.response?.data?.detail || '예측 실패')
    } finally {
      setCustomLoading(false)
    }
  }

  const selectedDateLabel = new Date(`${selectedDate}T00:00:00`).toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long'
  })

  return (
    <div>
      {/* 헤더 */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 4 }}>
          ⚾ 승부예측
        </h1>
        <div style={{ color: '#505070', fontSize: 14 }}>{selectedDateLabel}</div>
      </div>

      {/* 탭 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {[
          { id: 'today', label: `날짜별 경기 (${todayGames.length})` },
          { id: 'custom', label: '직접 예측하기' },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className="btn"
            style={{
              background: tab === t.id ? 'rgba(99,102,241,0.2)' : 'transparent',
              color: tab === t.id ? '#818cf8' : '#9090b0',
              border: `1px solid ${tab === t.id ? 'rgba(99,102,241,0.4)' : 'rgba(255,255,255,0.08)'}`,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 오늘의 경기 */}
      {tab === 'today' && (
        <div>
          <div className="card" style={{
            padding: 16, marginBottom: 16,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
          }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>조회 날짜</div>
              <div style={{ fontSize: 12, color: '#505070' }}>
                저장 데이터에 없으면 KBO 공식 일정에서 실시간 조회합니다.
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="date"
                value={selectedDate}
                onChange={e => {
                  setSelectedDate(e.target.value)
                  loadGamesByDate(e.target.value)
                }}
                style={{
                  padding: '9px 12px', borderRadius: 8,
                  background: '#1e1e35', border: '1px solid rgba(255,255,255,0.12)',
                  color: '#f0f0ff', fontFamily: 'inherit', fontSize: 13,
                }}
              />
              <button
                className="btn btn-ghost"
                onClick={() => loadGamesByDate(selectedDate, true)}
                disabled={loading}
              >
                실시간 조회
              </button>
            </div>
          </div>

          {loading ? (
            <div style={{ display: 'grid', gap: 16 }}>
              {[1, 2, 3].map(i => (
                <div key={i} className="skeleton" style={{ height: 220, borderRadius: 16 }} />
              ))}
            </div>
          ) : todayGames.length === 0 ? (
            <div className="card" style={{
              padding: 60, textAlign: 'center',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
            }}>
              <div style={{ fontSize: 48 }}>⚾</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#9090b0' }}>
                선택한 날짜의 경기가 없습니다
              </div>
              <div style={{ fontSize: 14, color: '#505070' }}>
                다른 날짜를 선택하거나 직접 예측하기 탭에서 원하는 팀 매치업을 예측해보세요
              </div>
              <button
                onClick={() => setTab('custom')}
                className="btn btn-primary"
                style={{ marginTop: 8 }}
              >
                직접 예측하기
              </button>
            </div>
          ) : (
            <div style={{ display: 'grid', gap: 16 }}>
              {scheduleSource && (
                <div style={{
                  fontSize: 12, color: '#505070',
                  padding: '0 4px 4px',
                }}>
                  데이터 출처: {scheduleSource === 'kbo_live' ? 'KBO 공식 실시간 일정' : '로컬 수집 데이터'}
                </div>
              )}
              {todayGames.map((g, i) => (
                <PredictCard key={i} prediction={g} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* 직접 예측 */}
      {tab === 'custom' && (
        <div style={{ display: 'grid', gap: 16 }}>
          {/* 입력 폼 */}
          <div className="card" style={{ padding: 24 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20 }}>
              매치업 설정
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 16, alignItems: 'center', marginBottom: 16 }}>
              {/* 원정팀 */}
              <div>
                <label style={{ fontSize: 12, color: '#9090b0', marginBottom: 8, display: 'block' }}>원정팀</label>
                <select
                  value={form.away}
                  onChange={e => setForm({ ...form, away: e.target.value })}
                  style={{
                    width: '100%', padding: '10px 12px', borderRadius: 10,
                    background: '#1e1e35', border: '1px solid rgba(255,255,255,0.1)',
                    color: '#f0f0ff', fontSize: 15, fontWeight: 600,
                    fontFamily: 'inherit', cursor: 'pointer',
                  }}
                >
                  {KBO_TEAMS.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                <input
                  type="text"
                  placeholder="원정 선발투수 (선택)"
                  value={form.away_pitcher}
                  onChange={e => setForm({ ...form, away_pitcher: e.target.value })}
                  style={{
                    width: '100%', padding: '8px 12px', borderRadius: 8,
                    background: '#161628', border: '1px solid rgba(255,255,255,0.08)',
                    color: '#f0f0ff', fontSize: 13, fontFamily: 'inherit',
                    marginTop: 8,
                  }}
                />
              </div>

              {/* VS */}
              <div style={{ textAlign: 'center' }}>
                <div style={{
                  width: 44, height: 44, borderRadius: '50%',
                  background: 'rgba(99,102,241,0.15)',
                  border: '1px solid rgba(99,102,241,0.3)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontWeight: 800, fontSize: 13, color: '#818cf8', margin: '0 auto',
                }}>VS</div>
                <div style={{ fontSize: 10, color: '#505070', marginTop: 4 }}>홈 →</div>
              </div>

              {/* 홈팀 */}
              <div>
                <label style={{ fontSize: 12, color: '#9090b0', marginBottom: 8, display: 'block' }}>홈팀</label>
                <select
                  value={form.home}
                  onChange={e => setForm({ ...form, home: e.target.value })}
                  style={{
                    width: '100%', padding: '10px 12px', borderRadius: 10,
                    background: '#1e1e35', border: '1px solid rgba(255,255,255,0.1)',
                    color: '#f0f0ff', fontSize: 15, fontWeight: 600,
                    fontFamily: 'inherit', cursor: 'pointer',
                  }}
                >
                  {KBO_TEAMS.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                <input
                  type="text"
                  placeholder="홈 선발투수 (선택)"
                  value={form.home_pitcher}
                  onChange={e => setForm({ ...form, home_pitcher: e.target.value })}
                  style={{
                    width: '100%', padding: '8px 12px', borderRadius: 8,
                    background: '#161628', border: '1px solid rgba(255,255,255,0.08)',
                    color: '#f0f0ff', fontSize: 13, fontFamily: 'inherit',
                    marginTop: 8,
                  }}
                />
              </div>
            </div>

            {error && (
              <div style={{
                padding: '10px 14px', borderRadius: 8, marginBottom: 12,
                background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                color: '#ef4444', fontSize: 13,
              }}>
                ⚠️ {error}
              </div>
            )}

            <button
              onClick={handleCustomPredict}
              disabled={customLoading}
              className="btn btn-primary"
              style={{ width: '100%', justifyContent: 'center', padding: '12px', fontSize: 15, fontWeight: 700 }}
            >
              {customLoading ? (
                <><span className="animate-spin" style={{ display: 'inline-block' }}>⟳</span> AI 분석 중...</>
              ) : '⚾ 승부 예측하기'}
            </button>
          </div>

          {/* 예측 결과 */}
          {customPrediction && (
            <PredictCard prediction={customPrediction} showDetail />
          )}
        </div>
      )}
    </div>
  )
}
