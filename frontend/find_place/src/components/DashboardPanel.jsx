import { useState } from 'react'

const PLACEHOLDER_IMAGE = 'https://placehold.co/400x250/f1f5f9/94a3b8?text=No+Photo'

/* ─── Locality score card config ─── */
const SCORE_CARDS = [
  { key: 'amenity_score',       icon: '🏪', label: 'Amenity Score',       max: 10,    unit: '',   suffix: '/ 10' },
  { key: 'connectivity_score',  icon: '🔗', label: 'Connectivity Score',  max: 10,    unit: '',   suffix: '/ 10' },
  { key: 'metro_distance_km',   icon: '🚇', label: 'Metro Distance',     max: 50,    unit: 'km', invert: true, suffix: 'km' },
  { key: 'it_hub_distance_km',  icon: '💻', label: 'IT Hub Distance',    max: 60,    unit: 'km', invert: true, suffix: 'km' },
  { key: 'hospital_count',      icon: '🏥', label: 'Hospitals',          max: 50,    unit: '',   suffix: 'nearby' },
  { key: 'school_count',        icon: '🏫', label: 'Schools',            max: 60,    unit: '',   suffix: 'nearby' },
  { key: 'mall_count',          icon: '🛍️', label: 'Malls',              max: 15,    unit: '',   suffix: 'nearby' },
  { key: 'park_count',          icon: '🌳', label: 'Parks',              max: 30,    unit: '',   suffix: 'nearby' },
  { key: 'road_density',        icon: '🛣️', label: 'Road Density',       max: 300,   unit: '',   suffix: 'roads' },
]

/* ─── Category config for display order, icon & label ─── */
const SECTIONS = [
  { key: 'hospitals',       icon: '🏥', title: 'Hospitals' },
  { key: 'malls',           icon: '🛍️', title: 'Malls' },
  { key: 'cinemas',         icon: '🎬', title: 'Movie Theatres' },
  { key: 'schools',         icon: '🏫', title: 'Schools' },
  { key: 'hotels',          icon: '🏨', title: 'Hotels' },
  { key: 'restaurants',     icon: '🍽️', title: 'Restaurants' },
  { key: 'bus_stops',       icon: '🚌', title: 'Bus Stops' },
  { key: 'metro_stations',  icon: '🚇', title: 'Metro Stations' },
]

/* ─── PlaceCard ─── */
function PlaceCard({ place, distanceLabel }) {
  const imageUrl = place.photo_url || PLACEHOLDER_IMAGE
  const mapsUrl = `https://www.google.com/maps/place/?q=place_id:${place.place_id}`

  return (
    <a href={mapsUrl} target="_blank" rel="noopener noreferrer" className="place-card">
      <div className="place-card-img-wrap">
        <img
          src={imageUrl}
          alt={place.name}
          className="place-card-img"
          loading="lazy"
          onError={(e) => { e.target.src = PLACEHOLDER_IMAGE }}
        />
      </div>
      <div className="place-card-body">
        <h4 className="place-card-name">{place.name}</h4>
        {place.rating != null ? (
          <span className="place-card-rating">⭐ {place.rating}</span>
        ) : (
          <span className="place-card-rating place-card-rating--none">No rating</span>
        )}
        {distanceLabel ? (
          <span className="place-card-distance">{distanceLabel}</span>
        ) : null}
        <p className="place-card-address">{place.formatted_address}</p>
      </div>
    </a>
  )
}

/* ─── PlaceSection (array of places) ─── */
function PlaceSection({ icon, title, places }) {
  if (!places || places.length === 0) {
    return (
      <section className="place-section">
        <h3 className="place-section-title">{icon} {title}</h3>
        <p className="place-section-empty">No results found nearby.</p>
      </section>
    )
  }

  return (
    <section className="place-section">
      <h3 className="place-section-title">{icon} {title}</h3>
      <div className="place-card-grid">
        {places.map((place) => (
          <PlaceCard key={place.place_id} place={place} />
        ))}
      </div>
    </section>
  )
}

/* ─── Format metres into a human-readable string ─── */
function formatDistance(metres) {
  if (metres == null) return null
  if (metres < 1000) return `${metres} m away`
  return `${(metres / 1000).toFixed(1)} km away`
}

/* ─── NearestStation (single place object) ─── */
function NearestStation({ station }) {
  return (
    <section className="place-section">
      <h3 className="place-section-title">🚆 Nearest Railway Station</h3>
      {station ? (
        <div className="place-card-grid">
          <PlaceCard
            place={station}
            distanceLabel={formatDistance(station.distance_m)}
          />
        </div>
      ) : (
        <p className="place-section-empty">No railway station found nearby.</p>
      )}
    </section>
  )
}

/* ─── LocalityScores ─── */
function LocalityScores({ scores }) {
  if (!scores) return null

  return (
    <section className="locality-scores">
      <h3 className="place-section-title">📊 Locality Scores — {scores.locality}</h3>
      <div className="locality-scores-grid">
        {SCORE_CARDS.map(({ key, icon, label, max, unit, invert, suffix }) => {
          const raw = scores[key]
          if (raw == null) return null
          // For distance metrics, lower is better → invert the fill
          const pct = invert
            ? Math.max(0, Math.min(100, ((max - raw) / max) * 100))
            : Math.max(0, Math.min(100, (raw / max) * 100))
          const barColor = invert
            ? (raw <= max * 0.25 ? '#22c55e' : raw <= max * 0.5 ? '#eab308' : '#ef4444')
            : (pct >= 60 ? '#22c55e' : pct >= 30 ? '#eab308' : '#ef4444')

          const displayValue = typeof raw === 'number' ? raw.toFixed(2) : raw

          return (
            <div key={key} className="score-card">
              <div className="score-card-header">
                <span className="score-card-icon">{icon}</span>
                <span className="score-card-label">{label}</span>
              </div>
              <div className="score-card-value">
                {displayValue} <span className="score-card-max">{suffix}</span>
              </div>
              <div className="score-bar-track">
                <div
                  className="score-bar-fill"
                  style={{ width: `${pct}%`, background: barColor }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

/* ─── Radius options in metres ─── */
const RADIUS_OPTIONS = [
  { value: 1000,  label: '1 km' },
  { value: 2000,  label: '2 km' },
  { value: 3000,  label: '3 km' },
  { value: 5000,  label: '5 km' },
]

/* ─── RadiusSlider ─── */
function RadiusSlider({ value, onChange }) {
  const idx = RADIUS_OPTIONS.findIndex(o => o.value === value)

  return (
    <div className="radius-slider-wrap">
      <span className="radius-slider-label">📍 Search Radius</span>
      <div className="radius-slider-row">
        <input
          type="range"
          className="radius-slider"
          min={0}
          max={RADIUS_OPTIONS.length - 1}
          step={1}
          value={idx}
          onChange={e => onChange(RADIUS_OPTIONS[+e.target.value].value)}
        />
        <span className="radius-slider-value">{RADIUS_OPTIONS[idx].label}</span>
      </div>
      <div className="radius-slider-ticks">
        {RADIUS_OPTIONS.map(o => (
          <span key={o.value} className="radius-tick">{o.label}</span>
        ))}
      </div>
    </div>
  )
}

/* ─── Filter places by distance ─── */
function filterByRadius(places, radiusM) {
  if (!places) return []
  return places.filter(p => {
    if (p.distance_m == null) return true   // keep places without distance data
    return p.distance_m <= radiusM
  })
}

/* ─── DashboardPanel ─── */
export default function DashboardPanel({ result, onClose }) {
  const { area, radius_meters: radiusMeters } = result
  const [selectedRadius, setSelectedRadius] = useState(3000)

  return (
    <aside className="dashboard-panel" aria-label="Area analysis results">
      <div className="dashboard-panel-header">
        <div>
          <h2 className="dashboard-title">Area Insights</h2>
          <p className="dashboard-meta">{area} · {radiusMeters}m radius</p>
        </div>
        <button
          type="button"
          className="dashboard-close"
          onClick={onClose}
          aria-label="Close panel"
        >
          ✕
        </button>
      </div>

      <div className="dashboard-panel-body">
        <LocalityScores scores={result.locality_scores} />

        <RadiusSlider value={selectedRadius} onChange={setSelectedRadius} />

        {SECTIONS.map(({ key, icon, title }) => (
          <PlaceSection
            key={key}
            icon={icon}
            title={title}
            places={filterByRadius(result[key], selectedRadius)}
          />
        ))}

        <NearestStation station={result.nearest_railway_station} />
      </div>
    </aside>
  )
}
