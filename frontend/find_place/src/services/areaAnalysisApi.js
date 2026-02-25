const ANALYZE_ENDPOINT = 'http://127.0.0.1:8000/api/analyze-area/'

export async function analyzeArea(location) {
  const response = await fetch(ANALYZE_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      lat: location.lat,
      lng: location.lng,
      address: location.address,
    }),
  })

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