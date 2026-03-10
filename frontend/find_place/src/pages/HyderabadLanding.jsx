import { useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import './HyderabadLanding.css'

export default function HyderabadLanding() {
  const navigate = useNavigate()
  const user = JSON.parse(sessionStorage.getItem('fyp_user') || '{}')

  const dotRef = useRef(null)
  const ringRef = useRef(null)
  const lightRef = useRef(null)
  const canvasRef = useRef(null)
  const heroTitleRef = useRef(null)
  const mousePos = useRef({ x: 0, y: 0, rx: 0, ry: 0 })
  const animFrameRef = useRef(null)
  const particleFrameRef = useRef(null)

  const handleLogout = () => {
    sessionStorage.removeItem('fyp_user')
    navigate('/', { replace: true })
  }

  // ─── CURSOR & LIGHT FOLLOW ───
  const handleMouseMove = useCallback((e) => {
    const { clientX, clientY } = e
    mousePos.current.x = clientX
    mousePos.current.y = clientY
    if (dotRef.current) {
      dotRef.current.style.left = clientX + 'px'
      dotRef.current.style.top = clientY + 'px'
    }
    if (lightRef.current) {
      lightRef.current.style.left = clientX + 'px'
      lightRef.current.style.top = clientY + 'px'
    }
  }, [])

  // ─── HERO TITLE TEXT SHADOW ───
  const handleTitleMouseMove = useCallback((e) => {
    const el = heroTitleRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width
    const y = (e.clientY - rect.top) / rect.height
    el.style.textShadow = `
      ${(x - 0.5) * 20}px ${(y - 0.5) * 10}px 40px rgba(201,168,76,0.3),
      0 0 80px rgba(201,168,76,0.1)
    `
  }, [])

  const handleTitleMouseLeave = useCallback(() => {
    if (heroTitleRef.current) heroTitleRef.current.style.textShadow = ''
  }, [])

  useEffect(() => {
    // ─── RING ANIMATION ───
    function animateRing() {
      const m = mousePos.current
      m.rx += (m.x - m.rx) * 0.12
      m.ry += (m.y - m.ry) * 0.12
      if (ringRef.current) {
        ringRef.current.style.left = m.rx + 'px'
        ringRef.current.style.top = m.ry + 'px'
      }
      animFrameRef.current = requestAnimationFrame(animateRing)
    }
    animFrameRef.current = requestAnimationFrame(animateRing)

    // ─── PARTICLE SYSTEM ───
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight

    const GOLD_HEX = [201, 168, 76]
    const particles = []

    class Particle {
      constructor() { this.reset() }
      reset() {
        this.x = Math.random() * canvas.width
        this.y = Math.random() * canvas.height
        this.size = Math.random() * 1.5 + 0.3
        this.speedX = (Math.random() - 0.5) * 0.3
        this.speedY = -Math.random() * 0.4 - 0.1
        this.life = 1
        this.decay = Math.random() * 0.003 + 0.001
        this.opacity = Math.random() * 0.6 + 0.2
      }
      update() {
        this.x += this.speedX
        this.y += this.speedY
        this.life -= this.decay
        if (this.life <= 0) this.reset()
      }
      draw() {
        ctx.beginPath()
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${GOLD_HEX[0]},${GOLD_HEX[1]},${GOLD_HEX[2]},${this.life * this.opacity})`
        ctx.fill()
      }
    }

    for (let i = 0; i < 80; i++) particles.push(new Particle())

    function animateParticles() {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      particles.forEach(p => { p.update(); p.draw() })
      particleFrameRef.current = requestAnimationFrame(animateParticles)
    }
    particleFrameRef.current = requestAnimationFrame(animateParticles)

    const handleResize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
    }
    window.addEventListener('resize', handleResize)

    // ─── SCROLL REVEAL ───
    const observer = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if (e.isIntersecting) e.target.classList.add('visible')
      })
    }, { threshold: 0.2 })

    document.querySelectorAll('.hyd-card, .hyd-stat').forEach(el => observer.observe(el))

    // ─── COUNTER ANIMATION ───
    function animateCounter(el) {
      const target = el.textContent
      const num = parseFloat(target.replace(/[^0-9.]/g, ''))
      const suffix = target.replace(/[0-9.]/g, '')
      const startTime = performance.now()
      const duration = 1500
      function tick(now) {
        const elapsed = now - startTime
        const progress = Math.min(elapsed / duration, 1)
        const eased = 1 - Math.pow(1 - progress, 3)
        const current = Math.round(num * eased)
        el.textContent = current + suffix
        if (progress < 1) requestAnimationFrame(tick)
      }
      requestAnimationFrame(tick)
    }

    const statObserver = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.querySelectorAll('.hyd-stat-num').forEach(animateCounter)
          statObserver.unobserve(e.target)
        }
      })
    }, { threshold: 0.5 })

    const statsEl = document.querySelector('.hyd-stats')
    if (statsEl) statObserver.observe(statsEl)

    return () => {
      cancelAnimationFrame(animFrameRef.current)
      cancelAnimationFrame(particleFrameRef.current)
      window.removeEventListener('resize', handleResize)
      observer.disconnect()
      statObserver.disconnect()
    }
  }, [])

  // ─── CARD TILT ───
  const handleCardMouseMove = (e) => {
    const card = e.currentTarget
    const rect = card.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width - 0.5
    const y = (e.clientY - rect.top) / rect.height - 0.5
    card.style.transform = `translateY(-8px) rotateX(${-y * 8}deg) rotateY(${x * 8}deg)`
  }
  const handleCardMouseLeave = (e) => {
    e.currentTarget.style.transform = ''
    e.currentTarget.style.transition = 'transform 0.6s cubic-bezier(.34,1.56,.64,1)'
  }

  // ─── INTERACTIVE CURSOR SCALE ───
  const handleInteractEnter = () => {
    if (dotRef.current) {
      dotRef.current.style.transform = 'translate(-50%,-50%) scale(2)'
      dotRef.current.style.background = 'var(--gold-light)'
    }
  }
  const handleInteractLeave = () => {
    if (dotRef.current) {
      dotRef.current.style.transform = 'translate(-50%,-50%) scale(1)'
      dotRef.current.style.background = 'var(--gold)'
    }
  }

  return (
    <div className="hyd-landing" onMouseMove={handleMouseMove}>
      {/* Side glows */}
      <div className="hyd-side-glow-left" />
      <div className="hyd-side-glow-right" />

      {/* Mouse follow light */}
      <div className="hyd-mouse-light" ref={lightRef} />

      {/* Custom cursors */}
      <div className="hyd-cursor-dot" ref={dotRef} />
      <div className="hyd-cursor-ring" ref={ringRef} />

      {/* Particle canvas */}
      <canvas className="hyd-particle-canvas" ref={canvasRef} />

      {/* NAVBAR */}
      <nav className="hyd-nav">
        <div
          className="hyd-nav-logo"
          onMouseEnter={handleInteractEnter}
          onMouseLeave={handleInteractLeave}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
          </svg>
          Find Your Place
        </div>
        <div className="hyd-nav-right">
          {user.username && (
            <span className="hyd-nav-greeting">
              Hi, <span>{user.username}</span>
            </span>
          )}
          <button
            className="hyd-btn-logout"
            onClick={handleLogout}
            onMouseEnter={handleInteractEnter}
            onMouseLeave={handleInteractLeave}
          >
            Logout
          </button>
        </div>
      </nav>

      {/* HERO */}
      <section className="hyd-hero">
        <div className="hyd-hero-bg-grid" />

        <div className="hyd-hero-eyebrow">Hyderabad Real Estate</div>

        <h1
          className="hyd-hero-title"
          ref={heroTitleRef}
          onMouseMove={handleTitleMouseMove}
          onMouseLeave={handleTitleMouseLeave}
        >
          Your Gateway to<br />
          <span className="accent">Hyderabad</span>
          <span className="line2">Living</span>
        </h1>

        <p className="hyd-hero-sub">
          Discover neighborhoods, analyze property trends, predict prices, and find your perfect place in the City of Pearls.
        </p>

        <button
          className="hyd-btn-explore"
          onClick={() => navigate('/explore')}
          onMouseEnter={handleInteractEnter}
          onMouseLeave={handleInteractLeave}
        >
          <div className="shine" />
          <span>Explore Hyderabad</span>
        </button>

        <div className="hyd-scroll-hint">
          <div className="hyd-scroll-line" />
          scroll
        </div>
      </section>

      {/* FEATURE CARDS */}
      <section className="hyd-features">
        {[
          { num: '01', icon: '📍', title: 'Area Analysis', desc: 'Get deep insights on any locality — amenities, safety scores, growth potential and more. Make informed decisions with real data.' },
          { num: '02', icon: '💰', title: 'Price Prediction', desc: 'ML-powered price estimates for apartments, villas, independent houses, and plots. Know the market before you invest.' },
          { num: '03', icon: '🏷️', title: 'Identify Sellers', desc: 'Browse real listings and connect with sellers in your chosen neighborhood. No middlemen, no friction — just direct connections.' },
        ].map((card) => (
          <div
            key={card.num}
            className="hyd-card"
            onMouseMove={handleCardMouseMove}
            onMouseLeave={handleCardMouseLeave}
            onMouseEnter={handleInteractEnter}
          >
            <span className="hyd-card-number">{card.num}</span>
            <div className="hyd-card-side-glow" />
            <span className="hyd-card-icon">{card.icon}</span>
            <h3>{card.title}</h3>
            <p>{card.desc}</p>
          </div>
        ))}
      </section>

      {/* STATS */}
      <div className="hyd-stats">
        <div className="hyd-stat">
          <span className="hyd-stat-num">90%</span>
          <span className="hyd-stat-label">Price Accuracy</span>
        </div>
        <div className="hyd-stat">
          <span className="hyd-stat-num">200+</span>
          <span className="hyd-stat-label">Localities Mapped</span>
        </div>
      </div>

      <footer className="hyd-footer">© 2026 Find Your Place · Hyderabad · All Rights Reserved</footer>
    </div>
  )
}
