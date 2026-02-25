/**
 * Fetch real administrative / neighborhood boundary polygons from
 * OpenStreetMap via the Nominatim API.
 *
 * Returns { paths: [[{lat,lng},...]], bounds: google.maps.LatLngBounds }
 * or null when no polygon is available.
 */

const NOMINATIM_BASE = 'https://nominatim.openstreetmap.org'

/* ── helpers ── */

/** Convert a GeoJSON ring ([lng, lat] pairs) → [{lat, lng}, …] */
function toLatLngPath(ring) {
  return ring.map(([lng, lat]) => ({ lat, lng }))
}

/**
 * Extract an array of polygon paths from a GeoJSON geometry.
 * Returns null for Point / LineString / missing data.
 */
function extractPaths(geojson) {
  if (!geojson) return null

  if (geojson.type === 'Polygon' && geojson.coordinates?.length) {
    return [toLatLngPath(geojson.coordinates[0])] // outer ring
  }

  if (geojson.type === 'MultiPolygon' && geojson.coordinates?.length) {
    return geojson.coordinates.map((poly) => toLatLngPath(poly[0]))
  }

  return null // Point, LineString, etc.
}

/** Build LatLngBounds from an array of paths (for fitBounds). */
function boundsFromPaths(paths) {
  const b = new window.google.maps.LatLngBounds()
  for (const path of paths) {
    for (const pt of path) {
      b.extend(pt)
    }
  }
  return b
}

/* ── public API ── */

/**
 * Search Nominatim by place name and return the boundary polygon.
 * @param {string} placeName  e.g. "Musheerabad, Hyderabad"
 * @returns {Promise<{paths, bounds} | null>}
 */
export async function fetchBoundaryByName(placeName) {
  try {
    const params = new URLSearchParams({
      q: placeName,
      format: 'jsonv2',
      polygon_geojson: '1',
      limit: '1',
      countrycodes: 'in',
    })

    const res = await fetch(`${NOMINATIM_BASE}/search?${params}`, {
      headers: { Accept: 'application/json' },
    })
    if (!res.ok) return null

    const data = await res.json()
    if (!data?.length) return null

    const paths = extractPaths(data[0].geojson)
    if (!paths) return null

    return { paths, bounds: boundsFromPaths(paths) }
  } catch {
    return null
  }
}

/**
 * Reverse-geocode coordinates via Nominatim at suburb / neighbourhood level
 * and return the boundary polygon.
 * @param {number} lat
 * @param {number} lng
 * @returns {Promise<{paths, bounds} | null>}
 */
export async function fetchBoundaryByCoords(lat, lng) {
  try {
    const params = new URLSearchParams({
      lat: String(lat),
      lon: String(lng),
      format: 'jsonv2',
      polygon_geojson: '1',
      zoom: '14', // suburb / village level
    })

    const res = await fetch(`${NOMINATIM_BASE}/reverse?${params}`, {
      headers: { Accept: 'application/json' },
    })
    if (!res.ok) return null

    const data = await res.json()
    if (!data) return null

    const paths = extractPaths(data.geojson)
    if (!paths) return null

    return { paths, bounds: boundsFromPaths(paths) }
  } catch {
    return null
  }
}
