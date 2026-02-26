import { useCallback, useEffect, useRef, useMemo } from 'react'
import { GoogleMap, Marker, Polygon, Rectangle } from '@react-google-maps/api'

const MAP_CONTAINER_STYLE = { width: '100%', height: '100%' }

// Default options without a hardcoded mapTypeId to allow dynamic updating
const MAP_OPTIONS = {
  disableDefaultUI: false,
  streetViewControl: false,
  mapTypeControl: false,
  fullscreenControl: false,
}

/** Default area boundary style — blue */
const AREA_STYLE = {
  strokeColor: '#2563eb',
  strokeOpacity: 0.9,
  strokeWeight: 2,
  fillColor: '#2563eb',
  fillOpacity: 0.15,
  clickable: false,
  zIndex: 1,
}

/** Intro Hyderabad outline — hidden (no border) */
const INTRO_STYLE_BASE = {
  strokeColor: '#1a1a2e',
  strokeOpacity: 0,
  strokeWeight: 0,
  fillColor: '#1a1a2e',
  fillOpacity: 0,
  clickable: false,
  zIndex: 2,
}

/** Red prediction locality boundary */
const PREDICTION_STYLE = {
  strokeColor: '#dc2626',
  strokeOpacity: 0.95,
  strokeWeight: 2.5,
  fillColor: '#dc2626',
  fillOpacity: 0.15,
  clickable: false,
  zIndex: 3,
}

/** Red marker SVG icon */
const RED_MARKER_ICON = {
  path: 'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z',
  fillColor: '#dc2626',
  fillOpacity: 1,
  strokeColor: '#991b1b',
  strokeWeight: 1,
  scale: 1.8,
  anchor: { x: 12, y: 22 },
}

/**
 * MapView — renders the Google Map with multiple boundary layers
 *
 * Props:
 *   center, zoom, markerPosition, areaBoundary, onMapClick, onMapLoad
 *   introBoundary         — Hyderabad city polygon during intro
 *   introBoundaryVisible  — whether intro polygon is faded in
 *   predictionBoundary    — red boundary for prediction locality
 *   predictionMarker      — { lat, lng, label }
 */
export default function MapView({
  center, zoom = 13, markerPosition, areaBoundary,
  introBoundary, introBoundaryVisible, introActive,
  predictionBoundary, predictionMarker,
  onMapClick, onMapLoad,
}) {
  const mapRef = useRef(null)
  const prevBoundsRef = useRef(null)

  const onLoad = useCallback((map) => {
    mapRef.current = map
    if (onMapLoad) onMapLoad(map)
  }, [onMapLoad])

  // Fit map to area boundary bounds (skip during intro to avoid conflicts)
  useEffect(() => {
    if (!mapRef.current || introActive) return
    const bounds = areaBoundary?.bounds
    if (bounds && bounds !== prevBoundsRef.current) {
      prevBoundsRef.current = bounds
      mapRef.current.fitBounds(bounds, { top: 60, bottom: 20, left: 20, right: 20 })
    } else if (!bounds) {
      prevBoundsRef.current = null
      mapRef.current.panTo({ lat: center.lat, lng: center.lng })
      mapRef.current.setZoom(zoom)
    }
  }, [center.lat, center.lng, zoom, areaBoundary, introActive])

  const handleClick = useCallback(
    (event) => {
      const lat = event.latLng.lat()
      const lng = event.latLng.lng()
      onMapClick({ lat, lng })
    },
    [onMapClick],
  )

  // Fallback rectangle bounds
  const rectBounds = useMemo(() => {
    if (!areaBoundary || areaBoundary.paths) return null
    const b = areaBoundary.bounds
    if (!b) return null
    if (typeof b.getNorthEast === 'function') {
      const ne = b.getNorthEast()
      const sw = b.getSouthWest()
      return { north: ne.lat(), south: sw.lat(), east: ne.lng(), west: sw.lng() }
    }
    return b
  }, [areaBoundary])

  // Intro style with dynamic opacity for fade-in
  const introStyle = useMemo(() => ({
    ...INTRO_STYLE_BASE,
    fillOpacity: introBoundaryVisible ? 0.08 : 0,
    strokeOpacity: introBoundaryVisible ? 1.0 : 0,
  }), [introBoundaryVisible])

  return (
    <GoogleMap
      mapContainerStyle={MAP_CONTAINER_STYLE}
      mapContainerClassName="map-canvas"
      center={{ lat: center.lat, lng: center.lng }}
      zoom={zoom}
      options={MAP_OPTIONS}
      onLoad={onLoad}
      onClick={handleClick}
    >
      {/* ── Intro: Hyderabad city glow polygon ── */}
      {introBoundary?.paths?.map((path, i) => (
        <Polygon key={`intro-${i}`} paths={path} options={introStyle} />
      ))}

      {/* ── Area search boundary polygon(s) ── */}
      {areaBoundary?.paths?.map((path, i) => (
        <Polygon key={`area-${i}`} paths={path} options={AREA_STYLE} />
      ))}

      {/* ── Area search fallback rectangle ── */}
      {rectBounds && <Rectangle bounds={rectBounds} options={AREA_STYLE} />}

      {/* ── Prediction: red locality boundary ── */}
      {predictionBoundary?.paths?.map((path, i) => (
        <Polygon key={`pred-${i}`} paths={path} options={PREDICTION_STYLE} />
      ))}

      {/* ── Prediction: red marker with label ── */}
      {predictionMarker && (
        <Marker
          position={{ lat: predictionMarker.lat, lng: predictionMarker.lng }}
          icon={RED_MARKER_ICON}
          label={predictionMarker.label ? {
            text: predictionMarker.label,
            color: '#991b1b',
            fontSize: '11px',
            fontWeight: '600',
            className: 'pred-marker-label',
          } : undefined}
          animation={window.google?.maps?.Animation?.DROP}
        />
      )}

      {/* ── Default location marker ── */}
      {markerPosition && (
        <Marker
          position={{ lat: markerPosition.lat, lng: markerPosition.lng }}
          animation={window.google?.maps?.Animation?.DROP}
        />
      )}
    </GoogleMap>
  )
}