import { useCallback, useEffect, useRef, useState } from 'react'
import './AmenityPanel.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

const TAG_META = {
  metro_stations: { icon: '🚇', label: 'Metro Stations' },
  schools:        { icon: '🏫', label: 'Schools' },
  hospitals:      { icon: '🏥', label: 'Hospitals' },
  malls:          { icon: '🛒', label: 'Malls' },
  cinemas:        { icon: '🎭', label: 'Theatres' },
  restaurants:    { icon: '🍽️', label: 'Restaurants' },
}

function buildGoogleMapsUrl(place) {
  if (place.place_id) {
    return `https://www.google.com/maps/place/?q=place_id:${place.place_id}`
  }
  const lat = place.location?.lat
  const lng = place.location?.lng
  if (lat && lng) {
    return `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`
  }
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place.name || '')}`
}

function formatDistance(meters) {
  if (!meters && meters !== 0) return ''
  if (meters >= 1000) return `${(meters / 1000).toFixed(1)} km`
  return `${Math.round(meters)} m`
}

export default function AmenityPanel({ activeTag, analysisResult, onClose }) {
  const meta = TAG_META[activeTag] || { icon: '📍', label: activeTag }
  const rawPlaces = analysisResult?.[activeTag] || []

  // Sort by nearest distance first
  const places = [...rawPlaces].sort(
    (a, b) => (a.distance_m ?? Infinity) - (b.distance_m ?? Infinity),
  )

  /* ── Resizable width ── */
  const MIN_WIDTH = 300
  const MAX_WIDTH = 800
  const [panelWidth, setPanelWidth] = useState(400)
  const isDragging = useRef(false)
  const startX = useRef(0)
  const startWidth = useRef(panelWidth)

  const onMouseDown = useCallback((e) => {
    e.preventDefault()
    isDragging.current = true
    startX.current = e.clientX
    startWidth.current = panelWidth
    document.body.style.cursor = 'ew-resize'
    document.body.style.userSelect = 'none'
  }, [panelWidth])

  useEffect(() => {
    const onMouseMove = (e) => {
      if (!isDragging.current) return
      // Dragging left edge → moving left increases width
      const delta = startX.current - e.clientX
      const newWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startWidth.current + delta))
      setPanelWidth(newWidth)
    }
    const onMouseUp = () => {
      if (isDragging.current) {
        isDragging.current = false
        document.body.style.cursor = ''
        document.body.style.userSelect = ''
      }
    }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [])

  return (
    <div className="amenity-panel" style={{ width: panelWidth }}>
      {/* Resize handle */}
      <div className="amenity-panel__resize-handle" onMouseDown={onMouseDown} />

      <div className="amenity-panel__header">
        <h3 className="amenity-panel__title">
          <span className="amenity-panel__title-icon">{meta.icon}</span>
          {meta.label}
          <span className="amenity-panel__count">({places.length})</span>
        </h3>
        <button className="amenity-panel__close" onClick={onClose} aria-label="Close">✕</button>
      </div>

      <div className="amenity-panel__body">
        {places.length > 0 ? (
          places.map((place, i) => {
            const mapsUrl = buildGoogleMapsUrl(place)
            return (
              <a
                key={i}
                className="amenity-panel__card"
                href={mapsUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                {place.photo_url ? (
                  <img
                    className="amenity-panel__card-photo"
                    src={`${API_BASE}${place.photo_url}`}
                    alt={place.name}
                    loading="lazy"
                  />
                ) : (
                  <div className="amenity-panel__card-photo-placeholder">
                    {meta.icon}
                  </div>
                )}
                <div className="amenity-panel__card-body">
                  <p className="amenity-panel__card-name">{place.name || 'Unknown'}</p>
                  {place.formatted_address && (
                    <p className="amenity-panel__card-address">{place.formatted_address}</p>
                  )}
                  <div className="amenity-panel__card-meta">
                    {place.rating != null && (
                      <span className="amenity-panel__card-rating">⭐ {place.rating}</span>
                    )}
                    {place.distance_m != null && (
                      <span className="amenity-panel__card-distance">{formatDistance(place.distance_m)}</span>
                    )}
                    <span className="amenity-panel__card-link">View on Maps →</span>
                  </div>
                </div>
              </a>
            )
          })
        ) : (
          <div className="amenity-panel__empty">
            <span className="amenity-panel__empty-icon">{meta.icon}</span>
            <p className="amenity-panel__empty-text">No {meta.label.toLowerCase()} found nearby</p>
          </div>
        )}
      </div>
    </div>
  )
}
