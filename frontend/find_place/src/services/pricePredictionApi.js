const PREDICT_ENDPOINT = 'http://127.0.0.1:8000/api/predict-price/'

/**
 * Call the Django prediction API.
 *
 * @param {{ locality: string, area_sqft: number, bhk: number, bathrooms: number, property_type: string, furnishing: string }} params
 * @returns {Promise<{ predicted_price_lakhs: number, predicted_price_crore: number, currency: string }>}
 */
export async function predictPrice({
    locality,
    area_sqft,
    bhk,
    bathrooms,
    property_type,
    furnishing,
}) {
    const response = await fetch(PREDICT_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            locality,
            area_sqft,
            bhk,
            bathrooms,
            property_type,
            furnishing,
        }),
    })

    let payload = null
    try {
        payload = await response.json()
    } catch {
        payload = null
    }

    if (!response.ok) {
        const message = payload?.error || 'Prediction request failed.'
        throw new Error(message)
    }

    return payload
}
