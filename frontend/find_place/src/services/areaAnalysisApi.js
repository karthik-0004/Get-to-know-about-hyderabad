const BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const ANALYZE_ENDPOINT = `${BASE}/api/analyze-area/`
// const USAGE_ENDPOINT = 'http://127.0.0.1:8000/api/usage-counter/'

/**
 * Custom error class so the caller can distinguish a "daily limit reached"
 * response from other network / API errors.
 */
export class DailyLimitError extends Error {
  constructor(message, usage) {
    super(message)
    this.name = 'DailyLimitError'
    this.usage = usage // { date, count, limit, limit_reached }
  }
}

export async function analyzeArea(location) {
  const lat = typeof location.lat === 'function' ? location.lat() : Number(location.lat)
  const lng = typeof location.lng === 'function' ? location.lng() : Number(location.lng)

  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    throw new Error('Invalid coordinates. Please select a location on the map first.')
  }

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 45000)

  let response
  try {
    response = await fetch(ANALYZE_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        lat,
        lng,
        address: location.address || '',
      }),
      signal: controller.signal,
    })
  } catch (err) {
    clearTimeout(timeoutId)
    if (err.name === 'AbortError') {
      throw new Error('Analysis timed out. Please try again.')
    }
    throw new Error('Network error. Please check your connection.')
  }
  clearTimeout(timeoutId)

  let payload = null
  try {
    payload = await response.json()
  } catch {
    payload = null
  }

  // ── Handle 429 (daily limit reached) specially ──
  if (response.status === 429 && payload?.error === 'daily_limit_reached') {
    throw new DailyLimitError(
      payload.message || 'Daily API limit reached.',
      payload.usage || null,
    )
  }

  if (!response.ok) {
    const message = payload?.error || 'Failed to analyze the selected area.'
    throw new Error(message)
  }

  return payload
}

/**
 * Fetch the current daily API usage counter from the backend.
 * Returns { date, count, limit, limit_reached }
 */
export async function fetchUsageCounter() {
  try {
    const resp = await fetch(USAGE_ENDPOINT)
    if (!resp.ok) return null
    return await resp.json()
  } catch {
    return null
  }
}