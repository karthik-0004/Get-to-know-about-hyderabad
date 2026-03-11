import { useEffect, useState } from 'react'
import './AreaPanel.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

const TAGS = [
  { key: 'metro_stations', icon: '🚇', label: 'Metro Access' },
  { key: 'schools',        icon: '🏫', label: 'Schools' },
  { key: 'hospitals',      icon: '🏥', label: 'Hospitals' },
  { key: 'malls',          icon: '🛒', label: 'Malls' },
  { key: 'cinemas',        icon: '🎭', label: 'Theatres' },
  { key: 'restaurants',    icon: '🍽️', label: 'Dining' },
]

const PLATFORMS = [
  {
    name: 'Housing.com',
    icon: '🏠',
    color: '#e8384f',
    buildUrl: (loc) => {
      const slug = loc.toLowerCase().replace(/\s+/g, '-')
      return `https://housing.com/in/buy/hyderabad/${slug}`
    },
  },
  {
    name: '99acres',
    icon: '🏗️',
    color: '#1a73e8',
    buildUrl: (loc) => {
      const slug = loc.toLowerCase().replace(/\s+/g, '-')
      return `https://www.99acres.com/property-in-${slug}-hyderabad-ffid?city=21&preference=S&area_unit=1&res_com=R`
    },
  },
  {
    name: 'MagicBricks',
    icon: '🏢',
    color: '#e2473b',
    buildUrl: (loc) =>
      `https://www.magicbricks.com/property-for-sale/residential-real-estate?bedroom=2,3&proptype=Multistorey-Apartment,Builder-Floor-Apartment,Penthouse,Studio-Apartment,Residential-House,Villa&Locality=${encodeURIComponent(loc)}&cityName=Hyderabad`,
  },
]

function getDemandColor(score) {
  if (score >= 75) return '#34d399'
  if (score >= 50) return '#fbbf24'
  if (score >= 25) return '#fb923c'
  return '#f87171'
}

function getDemandLabel(score) {
  if (score >= 75) return 'High Demand'
  if (score >= 50) return 'Moderate'
  if (score >= 25) return 'Growing'
  return 'Low'
}

export default function AreaPanel({
  locality,
  analysisResult,
  isLoading,
  onClose,
  onOpenPredict,
  onTagClick,
  activeTag,
  limitReached = false,
}) {
  const [marketData, setMarketData] = useState(null)

  // Fetch market pulse when locality changes
  useEffect(() => {
    if (!locality) return
    setMarketData(null)

    const ctrl = new AbortController()
    fetch(`${API_BASE}/api/market-pulse/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ locality }),
      signal: ctrl.signal,
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data) setMarketData(data.price_data) })
      .catch(() => {})
    return () => ctrl.abort()
  }, [locality])

  const scores = analysisResult?.locality_scores || {}
  const amenity = scores.amenity_score ?? 0
  const connectivity = scores.connectivity_score ?? 0

  // Build demand score from multiple signals — robust even when Overpass is down
  const placesHospitals = analysisResult?.hospitals?.length ?? 0
  const placesSchools = analysisResult?.schools?.length ?? 0
  const placesMalls = analysisResult?.malls?.length ?? 0
  const placesCinemas = analysisResult?.cinemas?.length ?? 0
  const placesRestaurants = analysisResult?.restaurants?.length ?? 0
  const placesHotels = analysisResult?.hotels?.length ?? 0
  const metroKm = scores.metro_distance_km ?? 20
  const itHubKm = scores.it_hub_distance_km ?? 30

  // Google Places amenity signal (0-40 pts)
  const placesAmenity = Math.min(40,
    Math.min(placesHospitals, 5) * 2 +
    Math.min(placesSchools, 5) * 2 +
    Math.min(placesMalls, 3) * 3 +
    Math.min(placesCinemas, 3) * 2 +
    Math.min(placesRestaurants, 5) * 1 +
    Math.min(placesHotels, 3) * 1
  )

  // Metro proximity (0-25 pts): within 2km = 25, within 5km = 15, etc.
  const metroPts = metroKm <= 1 ? 25 : metroKm <= 2 ? 22 : metroKm <= 3 ? 18
    : metroKm <= 5 ? 14 : metroKm <= 8 ? 8 : metroKm <= 12 ? 4 : 0

  // IT hub proximity (0-15 pts)
  const itHubPts = itHubKm <= 3 ? 15 : itHubKm <= 5 ? 12 : itHubKm <= 10 ? 9
    : itHubKm <= 15 ? 6 : itHubKm <= 25 ? 3 : 0

  // Overpass scores bonus (0-20 pts) — when available
  const overpassBonus = Math.round(((amenity + connectivity) / 20) * 20)

  const demandScore = Math.min(100, placesAmenity + metroPts + itHubPts + overpassBonus)
  const demandColor = getDemandColor(demandScore)

  const hospitalCount = scores.hospital_count ?? 0
  const schoolCount = scores.school_count ?? 0
  const mallCount = scores.mall_count ?? 0

  return (
    <div className="area-panel">
      {/* ── Header ── */}
      <div className="area-panel__header">
        <div className="area-panel__header-row">
          <div>
            <h2 className="area-panel__locality">{locality || 'Selected Area'}</h2>
            <p className="area-panel__sub">Hyderabad, Telangana</p>
          </div>
          <button className="area-panel__close" onClick={onClose} aria-label="Close panel">✕</button>
        </div>
      </div>

      {/* ── Body ── */}
      <div className="area-panel__body">
        {isLoading ? (
          <div className="area-panel__loading">
            <div className="area-panel__shimmer area-panel__shimmer--wide" />
            <div className="area-panel__shimmer area-panel__shimmer--med" />
            <div className="area-panel__shimmer area-panel__shimmer--sm" />
            <div className="area-panel__shimmer area-panel__shimmer--wide" />
            <div className="area-panel__shimmer area-panel__shimmer--med" />
          </div>
        ) : (
          <>
            {/* Quick Stats */}
            <div className="area-panel__stats-row">
              <div className="area-panel__stat">
                <span className="area-panel__stat-value">{amenity.toFixed(1)}</span>
                <span className="area-panel__stat-label">Amenity</span>
              </div>
              <div className="area-panel__stat">
                <span className="area-panel__stat-value">{connectivity.toFixed(1)}</span>
                <span className="area-panel__stat-label">Connect</span>
              </div>
              <div className="area-panel__stat">
                <span className="area-panel__stat-value">
                  {scores.metro_distance_km != null ? `${scores.metro_distance_km.toFixed(1)}km` : '—'}
                </span>
                <span className="area-panel__stat-label">Metro</span>
              </div>
            </div>

            {/* Demand Index */}
            <div className="area-panel__demand">
              <h4 className="area-panel__section-title">Demand Index</h4>
              <div className="area-panel__demand-bar-bg">
                <div
                  className="area-panel__demand-bar-fill"
                  style={{ width: `${demandScore}%`, background: demandColor }}
                />
              </div>
              <div className="area-panel__demand-labels">
                <span>{getDemandLabel(demandScore)}</span>
                <span className="area-panel__demand-score">{demandScore}/100</span>
              </div>
            </div>

            {/* Limit-reached banner */}
            {limitReached && (
              <div className="area-panel__limit-banner">
                <span className="area-panel__limit-banner-icon">📊</span>
                <span>Amenity data unavailable — daily limit reached. Map & price features still active.</span>
              </div>
            )}

            {/* Interactive Tags — hidden when limit reached */}
            {!limitReached && (
              <>
                <h4 className="area-panel__section-title">Nearby Amenities</h4>
                <div className="area-panel__tags">
                  {TAGS.map((tag) => (
                    <button
                      key={tag.key}
                      className={`area-panel__tag ${activeTag === tag.key ? 'area-panel__tag--active' : ''}`}
                      onClick={() => onTagClick(activeTag === tag.key ? null : tag.key)}
                    >
                      <span className="area-panel__tag-icon">{tag.icon}</span>
                      {tag.label}
                      {tag.key === 'hospitals' && hospitalCount > 0 && ` (${hospitalCount})`}
                      {tag.key === 'schools' && schoolCount > 0 && ` (${schoolCount})`}
                      {tag.key === 'malls' && mallCount > 0 && ` (${mallCount})`}
                    </button>
                  ))}
                </div>
              </>
            )}

            {/* Market Pulse */}
            <div className="area-panel__market">
              <h4 className="area-panel__section-title">Market Pulse</h4>
              {marketData && Object.keys(marketData).length > 0 ? (
                <div className="area-panel__market-grid">
                  {Object.entries(marketData).map(([type, data]) => (
                    <div key={type} className="area-panel__market-card">
                      <span className="area-panel__market-type">
                        {type.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                      </span>
                      <div>
                        <div className="area-panel__market-price">₹{data.avg_price_sqft?.toLocaleString('en-IN')}/sqft</div>
                        <div className="area-panel__market-range">
                          ₹{data.min_price_sqft?.toLocaleString('en-IN')} – ₹{data.max_price_sqft?.toLocaleString('en-IN')}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="area-panel__market-empty">No pricing data available for this area</p>
              )}
            </div>

            {/* Nearby Listings — Platform Links */}
            <div className="area-panel__listings">
              <h4 className="area-panel__section-title">Browse Listings</h4>
              {PLATFORMS.map((platform) => (
                <a
                  key={platform.name}
                  className="area-panel__listing-card area-panel__listing-link"
                  href={platform.buildUrl(locality)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <div className="area-panel__listing-top">
                    <span className="area-panel__listing-type">
                      {platform.icon} {platform.name}
                    </span>
                    <span className="area-panel__listing-arrow">→</span>
                  </div>
                  <div className="area-panel__listing-details">
                    Search {locality} properties on {platform.name}
                  </div>
                </a>
              ))}
            </div>
          </>
        )}
      </div>

      {/* ── Bottom Action Button ── */}
      <div className="area-panel__actions">
        <button className="area-panel__action-btn area-panel__action-btn--predict" onClick={onOpenPredict}>
          💰 Predict Price
        </button>
      </div>
    </div>
  )
}
