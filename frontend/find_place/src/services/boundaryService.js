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

/**
 * From a GeoJSON geometry, extract ONLY the single largest polygon
 * (most coordinate points). For a Polygon, returns it as-is.
 * For a MultiPolygon, picks the sub-polygon with the most points.
 */
function extractLargestPolygonPath(geojson) {
  if (!geojson) return null

  if (geojson.type === 'Polygon' && geojson.coordinates?.length) {
    return [toLatLngPath(geojson.coordinates[0])]
  }

  if (geojson.type === 'MultiPolygon' && geojson.coordinates?.length) {
    let largestRing = null
    let maxPoints = 0

    for (const poly of geojson.coordinates) {
      const outerRing = poly[0]
      if (outerRing && outerRing.length > maxPoints) {
        maxPoints = outerRing.length
        largestRing = outerRing
      }
    }

    if (largestRing) {
      return [toLatLngPath(largestRing)]
    }
  }

  return null
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

/**
 * Perpendicular distance from point P to line segment AB (lat/lng).
 */
function perpendicularDist(p, a, b) {
  const dx = b.lng - a.lng
  const dy = b.lat - a.lat
  const lenSq = dx * dx + dy * dy
  if (lenSq === 0) return Math.sqrt((p.lng - a.lng) ** 2 + (p.lat - a.lat) ** 2)
  const t = Math.max(0, Math.min(1, ((p.lng - a.lng) * dx + (p.lat - a.lat) * dy) / lenSq))
  const projLng = a.lng + t * dx
  const projLat = a.lat + t * dy
  return Math.sqrt((p.lng - projLng) ** 2 + (p.lat - projLat) ** 2)
}

/**
 * Douglas-Peucker polygon simplification.
 * epsilon is in degrees — ~0.005 ≈ 500m tolerance, gives a smooth outline.
 */
function simplifyPath(points, epsilon = 0.005) {
  if (points.length <= 2) return points

  let maxDist = 0
  let maxIdx = 0
  const first = points[0]
  const last = points[points.length - 1]

  for (let i = 1; i < points.length - 1; i++) {
    const d = perpendicularDist(points[i], first, last)
    if (d > maxDist) {
      maxDist = d
      maxIdx = i
    }
  }

  if (maxDist > epsilon) {
    const left = simplifyPath(points.slice(0, maxIdx + 1), epsilon)
    const right = simplifyPath(points.slice(maxIdx), epsilon)
    return left.slice(0, -1).concat(right)
  }
  return [first, last]
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
 * Fetch ONLY the single outermost boundary of a city.
 * Queries for "Greater Hyderabad Municipal Corporation" or similar,
 * then picks the largest polygon (most coordinate points), discarding
 * all internal subdivision polygons.
 *
 * @param {string} cityName  e.g. "Hyderabad"
 * @returns {Promise<{paths, bounds} | null>}
 */
export async function fetchCityOuterBoundary(cityName) {
  /**
   * Helper: extract largest polygon, simplify it so the outline is smooth,
   * and return { paths, bounds }.
   */
  const processGeojson = (geojson) => {
    if (!geojson) return null
    if (geojson.type !== 'Polygon' && geojson.type !== 'MultiPolygon') return null

    const rawPaths = extractLargestPolygonPath(geojson)
    if (!rawPaths?.length) return null

    // Simplify with ~0.004° tolerance (~400m) for a smooth outline
    const smoothed = rawPaths.map((path) => simplifyPath(path, 0.004))
    return { paths: smoothed, bounds: boundsFromPaths(smoothed) }
  }

  // Method 1: Structured search — most reliable for Indian cities
  try {
    const structuredParams = new URLSearchParams({
      city: cityName,
      state: 'Telangana',
      country: 'India',
      format: 'jsonv2',
      polygon_geojson: '1',
      limit: '1',
    })

    const res = await fetch(`${NOMINATIM_BASE}/search?${structuredParams}`, {
      headers: { Accept: 'application/json', 'User-Agent': 'FindYourPlace/1.0' },
    })
    if (res.ok) {
      const data = await res.json()
      if (data?.length) {
        const result = processGeojson(data[0].geojson)
        if (result) return result
      }
    }
  } catch { /* ignore */ }

  // Method 2: Free-form search with multiple terms
  const searchTerms = [
    `Greater ${cityName} Municipal Corporation, Telangana`,
    `${cityName}, Telangana, India`,
    `${cityName} district, Telangana`,
  ]

  for (const term of searchTerms) {
    try {
      const params = new URLSearchParams({
        q: term,
        format: 'jsonv2',
        polygon_geojson: '1',
        limit: '5',
        countrycodes: 'in',
      })

      const res = await fetch(`${NOMINATIM_BASE}/search?${params}`, {
        headers: { Accept: 'application/json', 'User-Agent': 'FindYourPlace/1.0' },
      })
      if (!res.ok) continue

      const data = await res.json()
      for (const item of (data || [])) {
        const result = processGeojson(item.geojson)
        if (result) return result
      }
    } catch {
      continue
    }
  }

  return null
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
