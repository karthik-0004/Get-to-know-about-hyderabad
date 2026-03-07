import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { GoogleLogin } from '@react-oauth/google'
import { registerUser, loginUser, googleLogin } from '../services/authApi'

/* ─── Phase constants ─── */
const PHASE_WORLD      = 0   // world map intro
const PHASE_AUTH       = 1   // login / register form
const PHASE_ENTERING   = 2   // "Entering into Hyderabad" text transition → dashboard

/* ─── Tile URL (OpenStreetMap) ─── */
const TILE = (z, x, y) => `https://tile.openstreetmap.org/${z}/${x}/${y}.png`

/* ─── Generate tile grid for a given zoom / center ─── */
function generateTiles(zoom, centerLat, centerLng, across = 7, down = 5) {
  const n = Math.pow(2, zoom)
  const centerX = Math.floor(((centerLng + 180) / 360) * n)
  const latRad = (centerLat * Math.PI) / 180
  const centerY = Math.floor(
    (1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2 * n,
  )

  const tiles = []
  for (let dy = -Math.floor(down / 2); dy <= Math.floor(down / 2); dy++) {
    for (let dx = -Math.floor(across / 2); dx <= Math.floor(across / 2); dx++) {
      const x = ((centerX + dx) % n + n) % n
      const y = centerY + dy
      if (y < 0 || y >= n) continue
      tiles.push({
        url: TILE(zoom, x, y),
        gridX: dx + Math.floor(across / 2),
        gridY: dy + Math.floor(down / 2),
        key: `${zoom}-${x}-${y}`,
      })
    }
  }
  return { tiles, tilesAcross: across, tilesDown: down }
}

/* ─── Reusable tile layer renderer ─── */
function TileLayer({ zoom, centerLat, centerLng, className, style }) {
  const { tiles, tilesAcross, tilesDown } = generateTiles(zoom, centerLat, centerLng)
  const tileSize = 256
  return (
    <div
      className={`story-map-container ${className || ''}`}
      style={{ width: tilesAcross * tileSize, height: tilesDown * tileSize, ...style }}
    >
      {tiles.map(t => (
        <img
          key={t.key}
          src={t.url}
          alt=""
          className="story-map-tile"
          style={{
            position: 'absolute',
            left: t.gridX * tileSize,
            top: t.gridY * tileSize,
            width: tileSize,
            height: tileSize,
          }}
          draggable={false}
        />
      ))}
    </div>
  )
}

export default function StoryLanding() {
  const navigate = useNavigate()
  const [phase, setPhase] = useState(PHASE_WORLD)

  /* auth form state */
  const [authMode, setAuthMode] = useState('login')
  const [formData, setFormData] = useState({ username: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  useEffect(() => {
    const user = sessionStorage.getItem('fyp_user')
    if (user) navigate('/dashboard', { replace: true })
  }, [navigate])

  /* Phase 0 (World) → auto-advance to Auth after 3 s */
  useEffect(() => {
    if (phase === PHASE_WORLD) {
      const t = setTimeout(() => setPhase(PHASE_AUTH), 3000)
      return () => clearTimeout(t)
    }
  }, [phase])

  /* Phase 2 (Entering) → show text, then navigate to dashboard after 3 s */
  useEffect(() => {
    if (phase !== PHASE_ENTERING) return
    const t = setTimeout(() => navigate('/dashboard'), 3000)
    return () => clearTimeout(t)
  }, [phase, navigate])

  /* ─── Auth handlers ─── */
  const handleChange = (e) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }))
    setError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      let result
      if (authMode === 'register') {
        await registerUser(formData)
        result = await loginUser({ identifier: formData.email, password: formData.password })
      } else {
        result = await loginUser({ identifier: formData.email, password: formData.password })
      }
      sessionStorage.setItem('fyp_user', JSON.stringify(result.user))
      /* After login → "Entering Hyderabad" transition */
      setPhase(PHASE_ENTERING)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleSuccess = async (credentialResponse) => {
    setError('')
    setLoading(true)
    try {
      const result = await googleLogin(credentialResponse.credential)
      sessionStorage.setItem('fyp_user', JSON.stringify(result.user))
      setPhase(PHASE_ENTERING)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  /* ─── Render ─── */
  return (
    <div className="story-landing">

      {/* ════════ PHASE 0 — World map ════════ */}
      {phase === PHASE_WORLD && (
        <div className="story-map-wrapper">
          <TileLayer zoom={2} centerLat={20} centerLng={0} />
          <div className="story-map-overlay">
            <div className="story-map-text-group">
              <div className="story-phase-text fade-up">
                <p className="story-eyebrow">FIND YOUR PLACE</p>
                <h1 className="story-big-title">Exploring the World…</h1>
                <p className="story-subtitle">Zooming in to where it all begins</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ════════ PHASE 1 — Auth (login / register) ════════ */}
      {phase === PHASE_AUTH && (
        <div className="story-auth-wrapper">
          <div className="story-auth-bg">
            <TileLayer zoom={2} centerLat={20} centerLng={0} />
          </div>
          <div className="story-auth-overlay" />

          <div className="story-auth-card fade-up">
            <div className="auth-logo">◆ FIND YOUR PLACE</div>
            <h2 className="auth-title">
              {authMode === 'login' ? 'Welcome Back' : 'Create Account'}
            </h2>
            <p className="auth-subtitle">
              {authMode === 'login'
                ? 'Log in to explore Hyderabad neighborhoods'
                : 'Register to start your journey'}
            </p>

            <form onSubmit={handleSubmit} className="auth-form">
              {authMode === 'register' && (
                <div className="auth-field">
                  <label htmlFor="username">Username</label>
                  <input
                    id="username"
                    name="username"
                    type="text"
                    value={formData.username}
                    onChange={handleChange}
                    placeholder="Choose a username"
                    required
                    autoComplete="username"
                  />
                </div>
              )}

              <div className="auth-field">
                <label htmlFor="email">Email</label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="your@email.com"
                  required
                  autoComplete="email"
                />
              </div>

              <div className="auth-field">
                <label htmlFor="password">Password</label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  value={formData.password}
                  onChange={handleChange}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  autoComplete={authMode === 'register' ? 'new-password' : 'current-password'}
                />
              </div>

              {error && <p className="auth-error">{error}</p>}

              <button type="submit" className="auth-submit" disabled={loading}>
                {loading
                  ? 'Please wait…'
                  : authMode === 'login' ? 'Log In' : 'Register'}
              </button>
            </form>

            <div className="auth-divider">
              <span>or</span>
            </div>

            <div className="auth-google-btn">
              <GoogleLogin
                onSuccess={handleGoogleSuccess}
                onError={() => setError('Google sign-in failed')}
                theme="filled_black"
                size="large"
                width="100%"
                text={authMode === 'login' ? 'signin_with' : 'signup_with'}
              />
            </div>

            <p className="auth-switch">
              {authMode === 'login' ? (
                <>
                  Don&apos;t have an account?{' '}
                  <button type="button" onClick={() => { setAuthMode('register'); setError('') }}>
                    Register
                  </button>
                </>
              ) : (
                <>
                  Already registered?{' '}
                  <button type="button" onClick={() => { setAuthMode('login'); setError('') }}>
                    Log In
                  </button>
                </>
              )}
            </p>
          </div>
        </div>
      )}

      {/* ════════ PHASE 2 — "Entering into Hyderabad" transition ════════ */}
      {phase === PHASE_ENTERING && (
        <div className="story-entering-wrapper">
          <div className="story-entering-text fade-up">
            <p className="story-eyebrow">ENTERING</p>
            <h1 className="story-big-title story-zoom-title">Hyderabad</h1>
            <p className="story-subtitle">The City of Pearls</p>
          </div>
        </div>
      )}
    </div>
  )
}
