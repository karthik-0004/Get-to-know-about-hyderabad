import { useCallback, useEffect, useRef, useMemo } from 'react'
import { GoogleMap, Marker, Polygon, Rectangle } from '@react-google-maps/api'

const MAP_CONTAINER_STYLE = { width: '100%', height: '100%' }

const MAP_OPTIONS = {
  disableDefaultUI: false,
  zoomControl: true,
  streetViewControl: false,
  mapTypeControl: false,
  fullscreenControl: false,
}

/** Red border style for the area polygon / fallback rectangle */
const AREA_STYLE = {
  strokeColor: '#DC2626',
  strokeOpacity: 0.9,
  strokeWeight: 2.5,
  fillColor: '#DC2626',
  fillOpacity: 0.06,
  clickable: false,
  zIndex: 1,
}

/**
 * areaBoundary shape:
 *   { paths: [[{lat,lng},…], …] | null, bounds: LatLngBounds }
 *   – paths present  → render Polygon(s)
 *   – paths null      → render Rectangle fallback from bounds
 */
export default function MapView({ center, zoom = 13, markerPosition, areaBoundary, onMapClick }) {
  const mapRef = useRef(null)
  const prevBoundsRef = useRef(null)

  const onLoad = useCallback((map) => {
    mapRef.current = map
  }, [])

  // Fit map to boundary bounds, or pan+zoom when cleared
  useEffect(() => {
    if (!mapRef.current) return

    const bounds = areaBoundary?.bounds
    if (bounds && bounds !== prevBoundsRef.current) {
      prevBoundsRef.current = bounds
      mapRef.current.fitBounds(bounds, { top: 60, bottom: 20, left: 20, right: 20 })
    } else if (!bounds) {
      prevBoundsRef.current = null
      mapRef.current.panTo({ lat: center.lat, lng: center.lng })
      mapRef.current.setZoom(zoom)
    }
  }, [center.lat, center.lng, zoom, areaBoundary])

  const handleClick = useCallback(
    (event) => {
      const lat = event.latLng.lat()
      const lng = event.latLng.lng()
      onMapClick({ lat, lng })
    },
    [onMapClick],
  )

  // Fallback: convert LatLngBounds → { north, south, east, west } for Rectangle
  const rectBounds = useMemo(() => {
    if (!areaBoundary || areaBoundary.paths) return null // Polygon takes priority
    const b = areaBoundary.bounds
    if (!b) return null
    if (typeof b.getNorthEast === 'function') {
      const ne = b.getNorthEast()
      const sw = b.getSouthWest()
      return { north: ne.lat(), south: sw.lat(), east: ne.lng(), west: sw.lng() }
    }
    return b
  }, [areaBoundary])

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
      {/* Real boundary polygon(s) from Nominatim */}
      {areaBoundary?.paths?.map((path, i) => (
        <Polygon key={i} paths={path} options={AREA_STYLE} />
      ))}

      {/* Fallback viewport rectangle when no polygon available */}
      {rectBounds && <Rectangle bounds={rectBounds} options={AREA_STYLE} />}

      {/* Marker */}
      {markerPosition ? (
        <Marker
          position={{ lat: markerPosition.lat, lng: markerPosition.lng }}
          animation={window.google?.maps?.Animation?.DROP}
        />
      ) : null}
    </GoogleMap>
  )
}