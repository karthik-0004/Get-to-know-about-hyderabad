import { useNavigate } from 'react-router-dom'
import '../App.css'

export default function RealEstateDashboard() {
  const navigate = useNavigate()
  const user = JSON.parse(sessionStorage.getItem('fyp_user') || '{}')

  const handleLogout = () => {
    sessionStorage.removeItem('fyp_user')
    navigate('/', { replace: true })
  }

  return (
    <div className="re-dashboard">
      {/* Top bar */}
      <header className="re-header">
        <div className="re-brand">◆ FIND YOUR PLACE</div>
        <div className="re-header-right">
          {user.username && <span className="re-user">Hi, {user.username}</span>}
          <button className="re-logout-btn" onClick={handleLogout}>Logout</button>
        </div>
      </header>

      {/* Hero section */}
      <section className="re-hero">
        <p className="re-hero-eyebrow">HYDERABAD REAL ESTATE</p>
        <h1 className="re-hero-title">Your Gateway to<br />Hyderabad Living</h1>
        <p className="re-hero-subtitle">
          Discover neighborhoods, analyze property trends, predict prices, and find your perfect place in the City of Pearls.
        </p>
        <button className="re-explore-btn" onClick={() => navigate('/explore')}>
          Explore Hyderabad
        </button>
      </section>

      {/* Feature cards */}
      <section className="re-features">
        <div className="re-feature-card">
          <div className="re-feature-icon">📍</div>
          <h3>Area Analysis</h3>
          <p>Get deep insights on any locality — amenities, safety scores, growth potential, and more.</p>
        </div>
        <div className="re-feature-card">
          <div className="re-feature-icon">💰</div>
          <h3>Price Prediction</h3>
          <p>ML-powered price estimates for apartments, villas, independent houses, and plots.</p>
        </div>
        <div className="re-feature-card">
          <div className="re-feature-icon">🏷️</div>
          <h3>Identify Sellers</h3>
          <p>Browse real listings and connect with sellers in your chosen neighborhood.</p>
        </div>
      </section>

      {/* Footer hint */}
      <footer className="re-footer">
        <p>Powered by AI &amp; Open Data — Built for Hyderabad</p>
      </footer>
    </div>
  )
}
