const PLACEHOLDER_IMAGE = 'https://placehold.co/400x250/f1f5f9/94a3b8?text=No+Photo'

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

/* ─── DashboardPanel ─── */
export default function DashboardPanel({ result, onClose }) {
  const { area, radius_meters: radiusMeters } = result

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
        {SECTIONS.map(({ key, icon, title }) => (
          <PlaceSection
            key={key}
            icon={icon}
            title={title}
            places={result[key]}
          />
        ))}

        <NearestStation station={result.nearest_railway_station} />
      </div>
    </aside>
  )
}
