const PLACEHOLDER_IMAGE = 'https://placehold.co/400x250/f1f5f9/94a3b8?text=No+Photo'

function PlaceCard({ place }) {
  const imageUrl = place.photo_url || PLACEHOLDER_IMAGE
  const mapsUrl = `https://www.google.com/maps/place/?q=place_id:${place.place_id}`

  return (
    <a
      href={mapsUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="place-card"
    >
      <div className="place-card-img-wrap">
        <img
          src={imageUrl}
          alt={place.name}
          className="place-card-img"
          loading="lazy"
          onError={(e) => {
            e.target.src = PLACEHOLDER_IMAGE
          }}
        />
      </div>
      <div className="place-card-body">
        <h4 className="place-card-name">{place.name}</h4>
        {place.rating != null ? (
          <span className="place-card-rating">⭐ {place.rating}</span>
        ) : (
          <span className="place-card-rating place-card-rating--none">No rating</span>
        )}
        <p className="place-card-address">{place.address}</p>
      </div>
    </a>
  )
}

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

export default function ResultsPanel({ result, onClose }) {
  const { area, radius_meters: radiusMeters, hospitals, malls, cinemas } = result

  return (
    <aside className="results-panel" aria-label="Area analysis results">
      <div className="results-panel-header">
        <div>
          <h2 className="results-title">Area Insights</h2>
          <p className="results-meta-line">{area} · {radiusMeters}m radius</p>
        </div>
        <button type="button" className="results-close" onClick={onClose} aria-label="Close panel">
          ✕
        </button>
      </div>

      <div className="results-panel-body">
        <PlaceSection icon="🏥" title="Hospitals" places={hospitals} />
        <PlaceSection icon="🛍️" title="Malls" places={malls} />
        <PlaceSection icon="🎬" title="Movie Theatres" places={cinemas} />
      </div>
    </aside>
  )
}