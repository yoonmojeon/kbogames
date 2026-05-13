import { useState } from 'react'

const TEAM_COLORS = {
  KIA: '#EA0029', LG: '#C30452', SSG: '#CE0E2D', KT: '#888',
  NC: '#1D467E', '두산': '#3344bb', '롯데': '#003399',
  '삼성': '#1428A0', '한화': '#FF6600', '키움': '#820024',
}

const TEAM_EMOJI = {
  KIA: '🐯', LG: '👊', SSG: '🚀', KT: '🧙',
  NC: '🦕', '두산': '🐻', '롯데': '🦁', '삼성': '🦁',
  '한화': '🦅', '키움': '🦸',
}

const CONFIDENCE_CONFIG = {
  '높음': { color: '#22c55e', bg: 'rgba(34,197,94,0.12)', label: '🔥 높음' },
  '중간': { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', label: '⚡ 중간' },
  '낮음': { color: '#6366f1', bg: 'rgba(99,102,241,0.12)', label: '💡 낮음' },
}

function FormDots({ form }) {
  return (
    <div style={{ display: 'flex', gap: 3 }}>
      {(form || []).slice(-7).map((w, i) => (
        <div key={i} style={{
          width: 8, height: 8, borderRadius: '50%',
          background: w ? '#22c55e' : '#ef4444',
        }} />
      ))}
    </div>
  )
}

function TeamPanel({ team, winProb, recentStats, pitcher, pitcherStats, isWinner }) {
  const color = TEAM_COLORS[team] || '#6366f1'
  const emoji = TEAM_EMOJI[team] || '⚾'

  return (
    <div style={{
      flex: 1, padding: '20px 16px', borderRadius: 12,
      background: isWinner
        ? `linear-gradient(135deg, ${color}22, ${color}08)`
        : 'rgba(255,255,255,0.03)',
      border: isWinner
        ? `1px solid ${color}40`
        : '1px solid rgba(255,255,255,0.06)',
      transition: 'all 0.3s',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {isWinner && (
        <div style={{
          position: 'absolute', top: 8, right: 8,
          fontSize: 10, fontWeight: 700, color,
          background: `${color}20`, padding: '2px 8px',
          borderRadius: 99, border: `1px solid ${color}40`,
        }}>예측 승리</div>
      )}

      {/* 팀 헤더 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 12,
          background: `${color}20`, border: `1px solid ${color}40`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 22,
        }}>{emoji}</div>
        <div>
          <div style={{ fontWeight: 800, fontSize: 18 }}>{team}</div>
          <div style={{ fontSize: 11, color: '#505070' }}>
            {pitcher || '선발 미정'}
          </div>
          {pitcherStats && (
            <div style={{ fontSize: 11, color: '#9090b0', marginTop: 2 }}>
              ERA {pitcherStats.era} · WHIP {pitcherStats.whip} · WAR {pitcherStats.war}
            </div>
          )}
        </div>
      </div>

      {/* 승률 바 */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 12, color: '#9090b0' }}>승리 확률</span>
          <span style={{ fontSize: 20, fontWeight: 800, color: isWinner ? color : '#f0f0ff' }}>
            {(winProb * 100).toFixed(1)}%
          </span>
        </div>
        <div className="progress-bar">
          <div className="progress-fill" style={{
            width: `${winProb * 100}%`,
            background: isWinner
              ? `linear-gradient(90deg, ${color}80, ${color})`
              : 'rgba(255,255,255,0.2)',
          }} />
        </div>
      </div>

      {/* 최근 성적 */}
      {recentStats && (
        <div style={{ fontSize: 12, color: '#9090b0' }}>
          <div style={{ display: 'flex', gap: 12, marginBottom: 6 }}>
            <span>최근 {recentStats.total}경기</span>
            <span style={{ color: '#22c55e' }}>
              {recentStats.wins}승
            </span>
            <span style={{ color: '#ef4444' }}>
              {recentStats.losses}패
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>폼</span>
            <FormDots form={recentStats.recent_form} />
          </div>
          <div style={{ marginTop: 4, display: 'flex', gap: 10 }}>
            <span>평균 {recentStats.avg_runs_scored}득점</span>
            <span>평균 {recentStats.avg_runs_allowed}실점</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default function PredictCard({ prediction, showDetail = false }) {
  const [expanded, setExpanded] = useState(showDetail)

  const {
    home_team, away_team,
    home_win_prob, away_win_prob,
    predicted_winner, confidence,
    home_recent_stats, away_recent_stats,
    home_pitcher, away_pitcher,
    game_time, prediction_method,
    status, home_score, away_score, actual_winner, date,
    home_pitcher_stats, away_pitcher_stats, pitcher_adjustment,
  } = prediction

  const conf = CONFIDENCE_CONFIG[confidence] || CONFIDENCE_CONFIG['낮음']

  return (
    <div className="card animate-fade-in" style={{ padding: 0, overflow: 'hidden' }}>
      {/* 경기 헤더 */}
      <div style={{
        padding: '12px 20px',
        background: 'rgba(99,102,241,0.06)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
          <span style={{ color: '#505070' }}>⚾</span>
          <span style={{ color: '#9090b0' }}>
            {date ? `${date} ` : ''}{game_time || ''}
          </span>
          {status === 'completed' && (
            <span style={{ color: '#22c55e', fontWeight: 700 }}>
              경기 종료
            </span>
          )}
          {status === 'scheduled' && (
            <span style={{ color: '#f59e0b', fontWeight: 700 }}>
              예정
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{
            padding: '3px 10px', borderRadius: 99, fontSize: 11, fontWeight: 600,
            background: conf.bg, color: conf.color,
            border: `1px solid ${conf.color}30`,
          }}>
            신뢰도 {conf.label}
          </div>
          <div style={{
            padding: '3px 10px', borderRadius: 99, fontSize: 11,
            background: 'rgba(255,255,255,0.06)', color: '#505070',
          }}>
            {prediction_method || 'AI 예측'}
          </div>
        </div>
      </div>

      {/* VS 레이아웃 */}
      <div style={{ padding: 20 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'stretch' }}>
          <TeamPanel
            team={away_team}
            winProb={away_win_prob}
            recentStats={away_recent_stats}
            pitcher={away_pitcher}
            pitcherStats={away_pitcher_stats}
            isWinner={predicted_winner === away_team}
          />

          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', padding: '0 8px', gap: 6,
          }}>
            <div style={{
              fontSize: 11, fontWeight: 700, color: '#505070',
              textTransform: 'uppercase', letterSpacing: '0.1em',
            }}>VS</div>
            <div style={{
              width: 1, height: 40,
              background: 'linear-gradient(to bottom, transparent, rgba(255,255,255,0.15), transparent)',
            }} />
            <div style={{ fontSize: 10, color: '#505070' }}>홈</div>
          </div>

          <TeamPanel
            team={home_team}
            winProb={home_win_prob}
            recentStats={home_recent_stats}
            pitcher={home_pitcher}
            pitcherStats={home_pitcher_stats}
            isWinner={predicted_winner === home_team}
          />
        </div>

        {/* 예측 결과 요약 */}
        <div style={{
          marginTop: 16, padding: '12px 16px', borderRadius: 10,
          background: 'rgba(99,102,241,0.08)',
          border: '1px solid rgba(99,102,241,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ fontSize: 14 }}>
            <span style={{ color: '#9090b0' }}>예측: </span>
            <span style={{ fontWeight: 700, color: '#818cf8' }}>
              {predicted_winner}
            </span>
            <span style={{ color: '#9090b0' }}> 승리</span>
          </div>
          <div style={{ fontSize: 13, color: '#505070' }}>
            확률 {(Math.max(home_win_prob, away_win_prob) * 100).toFixed(1)}%
          </div>
        </div>

        {pitcher_adjustment !== 0 && pitcher_adjustment != null && (
          <div style={{
            marginTop: 10, fontSize: 12, color: '#9090b0',
            padding: '8px 12px', borderRadius: 8,
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.06)',
          }}>
            선발투수 보정: 홈팀 기준 {(pitcher_adjustment * 100).toFixed(1)}%p
          </div>
        )}

        {status === 'completed' && home_score != null && away_score != null && (
          <div style={{
            marginTop: 10, padding: '10px 16px', borderRadius: 10,
            background: 'rgba(34,197,94,0.08)',
            border: '1px solid rgba(34,197,94,0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <div style={{ fontSize: 14 }}>
              <span style={{ color: '#9090b0' }}>실제 결과: </span>
              <span style={{ fontWeight: 800, color: '#f0f0ff' }}>
                {away_team} {away_score} : {home_score} {home_team}
              </span>
            </div>
            <div style={{ fontSize: 13, color: '#22c55e', fontWeight: 700 }}>
              승리 {actual_winner}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
