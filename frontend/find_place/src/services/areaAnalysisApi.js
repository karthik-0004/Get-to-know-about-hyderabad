const ANALYZE_ENDPOINT = 'http://127.0.0.1:8000/api/analyze-area/'

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

  if (!response.ok) {
    const message = payload?.error || 'Failed to analyze the selected area.'
    throw new Error(message)
  }

  return payload
}