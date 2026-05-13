import { useState, useEffect } from 'react'
import axios from 'axios'

const KBO_TEAMS = ['KIA', 'LG', 'SSG', 'KT', 'NC', '두산', '롯데', '삼성', '한화', '키움']

const TEAM_COLORS = {
  KIA: '#EA0029', LG: '#C30452', SSG: '#CE0E2D', KT: '#888',
  NC: '#1D467E', '두산': '#3344bb', '롯데': '#002B5B',
  '삼성': '#1428A0', '한화': '#FF6600', '키움': '#820024',
}

const TEAM_NAMES = {
  KIA: '기아 타이거즈', LG: 'LG 트윈스', SSG: 'SSG 랜더스', KT: 'KT 위즈',
  NC: 'NC 다이노스', '두산': '두산 베어스', '롯데': '롯데 자이언츠',
  '삼성': '삼성 라이온즈', '한화': '한화 이글스', '키움': '키움 히어로즈',
}

const POSITION_ORDER = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH', 'SP', 'RP', 'MR', 'CL', '내야', '외야', '투수', '포수']
const POSITION_LABELS = {
  C: '포수', '1B': '1루수', '2B': '2루수', '3B': '3루수', SS: '유격수',
  LF: '좌익수', CF: '중견수', RF: '우익수', DH: '지명타자',
  SP: '선발', RP: '계투', MR: '중간계투', CL: '마무리',
}

const POS_COLORS = {
  투수: '#6366f1', 포수: '#f59e0b', 내야수: '#22c55e', 외야수: '#ef4444',
  SP: '#6366f1', RP: '#818cf8', MR: '#a78bfa', CL: '#c084fc',
  C: '#f59e0b',
  '1B': '#22c55e', '2B': '#22c55e', '3B': '#22c55e', SS: '#22c55e',
  LF: '#ef4444', CF: '#ef4444', RF: '#ef4444', DH: '#f59e0b',
}

function PlayerCard({ player }) {
  const posColor = POS_COLORS[player.position] || '#505070'
  const posLabel = POSITION_LABELS[player.position] || player.position

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '8px 12px', borderRadius: 8,
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.05)',
      transition: 'all 0.2s',
      cursor: 'default',
    }}
    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.06)'}
    onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
    >
      <div style={{
        width: 28, height: 28, borderRadius: 6, flexShrink: 0,
        background: `${posColor}20`, border: `1px solid ${posColor}40`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10, fontWeight: 800, color: posColor,
      }}>
        {player.position?.slice(0, 2) || '?'}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {player.name}
        </div>
        <div style={{ fontSize: 11, color: '#505070' }}>
          {posLabel}
          {player.number ? ` #${player.number}` : ''}
          {player.throws_bats ? ` · ${player.throws_bats}` : ''}
        </div>
      </div>
    </div>
  )
}

function TeamLineupPanel({ team, lineup, color }) {
  const [filter, setFilter] = useState('all')

  const grouped = {
    투수: lineup.filter(p => ['SP', 'RP', 'MR', 'CL', '투수'].includes(p.position)),
    타자: lineup.filter(p => !['SP', 'RP', 'MR', 'CL', '투수'].includes(p.position)),
  }

  const filtered = filter === 'all' ? lineup
    : filter === 'pitcher' ? grouped.투수
    : grouped.타자

  return (
    <div className="card" style={{ overflow: 'hidden', height: 'fit-content' }}>
      {/* 팀 헤더 */}
      <div style={{
        padding: '16px 20px',
        background: `linear-gradient(135deg, ${color}30, ${color}10)`,
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}>
        <div style={{ fontWeight: 800, fontSize: 16, color }}>
          {team}
        </div>
        <div style={{ fontSize: 12, color: '#9090b0', marginTop: 2 }}>
          {TEAM_NAMES[team] || team} · 1군 엔트리 {lineup.length}명
        </div>
      </div>

      {/* 필터 */}
      <div style={{ padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.04)', display: 'flex', gap: 6 }}>
        {[
          { id: 'all', label: `전체 (${lineup.length})` },
          { id: 'pitcher', label: `투수 (${grouped.투수.length})` },
          { id: 'batter', label: `타자 (${grouped.타자.length})` },
        ].map(f => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            style={{
              padding: '4px 10px', borderRadius: 6, border: 'none', cursor: 'pointer',
              fontSize: 11, fontWeight: 600, fontFamily: 'inherit',
              background: filter === f.id ? `${color}30` : 'rgba(255,255,255,0.05)',
              color: filter === f.id ? color : '#505070',
              transition: 'all 0.2s',
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* 선수 목록 */}
      <div style={{ padding: 12, display: 'grid', gap: 4, maxHeight: 400, overflowY: 'auto' }}>
        {filtered.length === 0 ? (
          <div style={{ padding: 20, textAlign: 'center', color: '#505070', fontSize: 13 }}>
            데이터 없음
          </div>
        ) : (
          filtered.map((p, i) => <PlayerCard key={i} player={p} />)
        )}
      </div>
    </div>
  )
}

export default function LineupsPage() {
  const [selectedTeam, setSelectedTeam] = useState(null)
  const [lineups, setLineups] = useState({})
  const [loading, setLoading] = useState({})
  const [view, setView] = useState('grid')
  const [refreshing, setRefreshing] = useState(false)

  const loadLineup = async (team, refresh = false) => {
    if (lineups[team] && !refresh) return

    setLoading(prev => ({ ...prev, [team]: true }))
    try {
      const r = await axios.get(`/api/team/${team}/lineup${refresh ? '?refresh=true' : ''}`)
      setLineups(prev => ({ ...prev, [team]: r.data.players || [] }))
    } catch (e) {
      setLineups(prev => ({ ...prev, [team]: [] }))
    } finally {
      setLoading(prev => ({ ...prev, [team]: false }))
    }
  }

  const handleTeamSelect = (team) => {
    setSelectedTeam(team === selectedTeam ? null : team)
    loadLineup(team)
  }

  const loadAll = () => {
    KBO_TEAMS.forEach(t => loadLineup(t))
  }

  const refreshAll = async () => {
    setRefreshing(true)
    try {
      const r = await axios.post('/api/lineups/refresh')
      setLineups(r.data.entry || {})
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 4 }}>👥 1군 라인업</h1>
          <div style={{ color: '#505070', fontSize: 14 }}>KBO 각 팀의 현재 1군 등록 선수 명단</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={loadAll}
            className="btn btn-primary"
            style={{ fontSize: 13 }}
          >
            전체 로드
          </button>
          <button
            onClick={refreshAll}
            disabled={refreshing}
            className="btn btn-ghost"
            style={{ fontSize: 13 }}
          >
            {refreshing ? '실시간 갱신 중...' : '실시간 갱신'}
          </button>
          {[
            { id: 'grid', icon: '⊞' },
            { id: 'single', icon: '☰' },
          ].map(v => (
            <button
              key={v.id}
              onClick={() => setView(v.id)}
              className="btn"
              style={{
                background: view === v.id ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.05)',
                color: view === v.id ? '#818cf8' : '#505070',
                border: `1px solid ${view === v.id ? 'rgba(99,102,241,0.4)' : 'rgba(255,255,255,0.08)'}`,
              }}
            >
              {v.icon}
            </button>
          ))}
        </div>
      </div>

      {/* 팀 선택 버튼 */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 20 }}>
        {KBO_TEAMS.map(team => {
          const color = TEAM_COLORS[team]
          const isSelected = selectedTeam === team
          return (
            <button
              key={team}
              onClick={() => handleTeamSelect(team)}
              style={{
                padding: '8px 16px', borderRadius: 10,
                border: `1px solid ${isSelected ? color : 'rgba(255,255,255,0.1)'}`,
                background: isSelected ? `${color}20` : 'rgba(255,255,255,0.04)',
                color: isSelected ? color : '#9090b0',
                cursor: 'pointer', fontFamily: 'inherit',
                fontSize: 13, fontWeight: isSelected ? 700 : 400,
                transition: 'all 0.2s',
              }}
            >
              {team}
              {lineups[team] && (
                <span style={{ marginLeft: 6, opacity: 0.6, fontSize: 11 }}>
                  {lineups[team].length}명
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* 그리드 뷰 */}
      {view === 'grid' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
          {(selectedTeam ? [selectedTeam] : KBO_TEAMS).map(team => {
            const color = TEAM_COLORS[team]
            const isLoading = loading[team]
            const lineup = lineups[team]

            if (!lineup && !isLoading) {
              return (
                <div
                  key={team}
                  className="card"
                  onClick={() => handleTeamSelect(team)}
                  style={{
                    padding: 32, textAlign: 'center', cursor: 'pointer',
                    borderColor: `${color}30`,
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = '#1e1e35'}
                  onMouseLeave={e => e.currentTarget.style.background = '#161628'}
                >
                  <div style={{
                    width: 52, height: 52, borderRadius: 12,
                    background: `${color}15`, border: `1px solid ${color}30`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    margin: '0 auto 12px',
                    fontSize: 24,
                  }}>
                    ⚾
                  </div>
                  <div style={{ fontWeight: 700, fontSize: 16, color, marginBottom: 4 }}>{team}</div>
                  <div style={{ fontSize: 12, color: '#505070', marginBottom: 12 }}>{TEAM_NAMES[team]}</div>
                  <div style={{ fontSize: 12, color: '#6366f1' }}>클릭하여 라인업 로드</div>
                </div>
              )
            }

            if (isLoading) {
              return (
                <div key={team} className="card" style={{ padding: 20 }}>
                  <div className="skeleton" style={{ height: 60, borderRadius: 8, marginBottom: 12 }} />
                  {[...Array(8)].map((_, i) => (
                    <div key={i} className="skeleton" style={{ height: 36, borderRadius: 8, marginBottom: 6 }} />
                  ))}
                </div>
              )
            }

            return (
              <TeamLineupPanel key={team} team={team} lineup={lineup || []} color={color} />
            )
          })}
        </div>
      )}

      {/* 싱글 뷰 (선택한 팀 전체 상세) */}
      {view === 'single' && selectedTeam && lineups[selectedTeam] && (
        <TeamLineupPanel
          team={selectedTeam}
          lineup={lineups[selectedTeam]}
          color={TEAM_COLORS[selectedTeam]}
        />
      )}

      {view === 'single' && !selectedTeam && (
        <div className="card" style={{ padding: 60, textAlign: 'center', color: '#505070' }}>
          위에서 팀을 선택하세요
        </div>
      )}
    </div>
  )
}
