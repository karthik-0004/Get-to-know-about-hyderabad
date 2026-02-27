import { useState, useCallback, useEffect, useRef } from 'react'
import { predictPrice } from '../services/pricePredictionApi'

const BHK_OPTIONS = [1, 2, 3, 4, '4+']
const BATH_OPTIONS = [1, 2, 3, 4, '4+']
const PROPERTY_TYPES = ['Apartment', 'Independent House', 'Villa', 'Plot']
const FURNISHING_OPTIONS = ['Furnished', 'Semi-Furnished', 'Unfurnished']

/**
 * PricePredictionModal
 *
 * Props:
 *  - onClose ()
 *  - onLocalitySelect({ name, lat, lng })
 *  - onViewInsights ()
 */
export default function PricePredictionModal({ onClose, onLocalitySelect, onViewInsights }) {
    /* ── Locality state ── */
    const [selectedLocality, setSelectedLocality] = useState(null) // { name, lat, lng }
    const localityInputRef = useRef(null)
    const autocompleteRef = useRef(null)

    /* ── Form state ── */
    const [bhk, setBhk] = useState(null)
    const [bathrooms, setBathrooms] = useState(null)
    const [areaSqFt, setAreaSqFt] = useState('')
    const [propertyType, setPropertyType] = useState(null)
    const [furnishing, setFurnishing] = useState(null)

    /* ── UI state ── */
    const [errors, setErrors] = useState({})
    const [isLoading, setIsLoading] = useState(false)
    const [apiError, setApiError] = useState('')
    const [result, setResult] = useState(null)

    /* ══════════════════════════════════════════════════════════════
       Wire Google Places Autocomplete directly on the input ref
       ══════════════════════════════════════════════════════════════ */
    useEffect(() => {
        let pollId = null

        const initializeAutocomplete = () => {
            if (autocompleteRef.current) return true
            if (!localityInputRef.current || !window.google?.maps?.places) return false

            const autocomplete = new window.google.maps.places.Autocomplete(
                localityInputRef.current,
                {
                    bounds: new window.google.maps.LatLngBounds(
                        { lat: 17.2, lng: 78.2 },
                        { lat: 17.6, lng: 78.8 }
                    ),
                    strictBounds: true,
                    componentRestrictions: { country: 'in' },
                    fields: ['geometry', 'name', 'formatted_address'],
                }
            )

            autocomplete.addListener('place_changed', () => {
                const place = autocomplete.getPlace()
                if (!place?.geometry?.location) return

                const lat = place.geometry.location.lat()
                const lng = place.geometry.location.lng()
                const name = place.name || place.formatted_address?.split(',')[0] || 'Selected Area'

                const locality = { name, lat, lng }
                setSelectedLocality(locality)
                setErrors((prev) => ({ ...prev, locality: '' }))

                if (onLocalitySelect) onLocalitySelect(locality)
            })

            autocompleteRef.current = autocomplete
            return true
        }

        if (!initializeAutocomplete()) {
            pollId = setInterval(() => {
                if (initializeAutocomplete() && pollId) {
                    clearInterval(pollId)
                }
            }, 200)
        }

        return () => {
            if (pollId) clearInterval(pollId)
            if (window.google?.maps?.event && autocompleteRef.current) {
                window.google.maps.event.clearInstanceListeners(autocompleteRef.current)
            }
            autocompleteRef.current = null
        }
    }, [onLocalitySelect])

    /* ── Auto-focus after modal slide-up animation ── */
    useEffect(() => {
        const timer = setTimeout(() => {
            if (localityInputRef.current) localityInputRef.current.focus()
        }, 400)
        return () => clearTimeout(timer)
    }, [])

    /* ── Validate ── */
    const validate = useCallback(() => {
        const e = {}
        if (!selectedLocality) e.locality = 'Select a locality first'
        if (!bhk) e.bhk = 'Select BHK'
        if (!bathrooms) e.bathrooms = 'Select bathrooms'
        if (!areaSqFt || Number(areaSqFt) < 100) e.areaSqFt = 'Enter area (min 100 sq ft)'
        if (!propertyType) e.propertyType = 'Select property type'
        if (!furnishing) e.furnishing = 'Select furnishing'
        setErrors(e)
        return Object.keys(e).length === 0
    }, [selectedLocality, bhk, bathrooms, areaSqFt, propertyType, furnishing])

    /* ── Submit ── */
    const handlePredict = async () => {
        if (!validate()) return
        setIsLoading(true)
        setApiError('')
        try {
            const res = await predictPrice({
                locality: selectedLocality.name,
                area_sqft: Number(areaSqFt),
                bhk: bhk === '4+' ? 5 : Number(bhk),
                bathrooms: bathrooms === '4+' ? 5 : Number(bathrooms),
                property_type: propertyType,
                furnishing,
            })
            setResult(res)
        } catch (err) {
            setApiError(err.message || 'Something went wrong.')
        } finally {
            setIsLoading(false)
        }
    }

    const handleRefine = () => {
        setResult(null)
        setApiError('')
    }

    /* ═══════ Result card ═══════ */
    if (result) {
        return (
            <div className="ppm-overlay" onClick={onClose}>
                <div className="ppm-modal ppm-modal--result" onClick={(e) => e.stopPropagation()}>
                    <button className="ppm-close" onClick={onClose} aria-label="Close">×</button>

                    <div className="ppm-result-icon">🏠</div>
                    <h2 className="ppm-result-title">Price Estimate</h2>

                    <div className="ppm-result-summary">
                        <span>{selectedLocality?.name}</span>
                        <span className="ppm-dot">·</span>
                        <span>{bhk} BHK</span>
                        <span className="ppm-dot">·</span>
                        <span>{areaSqFt} sq ft</span>
                        <span className="ppm-dot">·</span>
                        <span>{propertyType}</span>
                    </div>

                    <div className="ppm-result-price">
                        <span className="ppm-price-label">Estimated Price</span>
                        <span className="ppm-price-crore">₹{result.predicted_price_crore} Crore</span>
                        <span className="ppm-price-lakhs">≈ ₹{result.predicted_price_lakhs} Lakhs</span>
                    </div>

                    <div className="ppm-result-actions">
                        <button className="ppm-btn ppm-btn--outline" onClick={handleRefine}>Refine Estimate</button>
                        <button className="ppm-btn ppm-btn--primary" onClick={() => { onClose(); onViewInsights(selectedLocality); }}>
                            View Area Insights
                        </button>
                    </div>
                </div>
            </div>
        )
    }

    /* ═══════ Form ═══════ */
    return (
        <div className="ppm-overlay" onClick={onClose}>
            <div className="ppm-modal" onClick={(e) => e.stopPropagation()}>
                <button className="ppm-close" onClick={onClose} aria-label="Close">×</button>

                <h2 className="ppm-title">Get Price Estimate</h2>

                {/* ══ LOCALITY INPUT — Google Places Autocomplete wired directly ══ */}
                <div className="ppm-locality-section">
                    <label className="ppm-locality-label">Select Locality</label>
                    <div className="ppm-locality-input-wrapper">
                        <span className="ppm-locality-search-icon">🔍</span>
                        <input
                            ref={localityInputRef}
                            type="text"
                            className={`ppm-locality-input ${errors.locality ? 'ppm-locality-input--error' : ''}`}
                            placeholder="Type locality name, e.g. Gachibowli, Banjara Hills..."
                            autoFocus={true}
                            onChange={() => {
                                if (selectedLocality) setSelectedLocality(null)
                            }}
                        />
                    </div>
                    {errors.locality && <span className="ppm-error-text">{errors.locality}</span>}

                    {/* Confirmed locality badge */}
                    {selectedLocality && (
                        <div className="ppm-locality-confirmed">
                            <span className="ppm-locality-confirmed-icon">✅</span>
                            {selectedLocality.name}
                        </div>
                    )}
                </div>

                {/* ══ PROPERTY FIELDS — slide down after locality picked ══ */}
                <div className={`ppm-fields-reveal ${selectedLocality ? 'ppm-fields-reveal--open' : ''}`}>

                    {/* BHK */}
                    <div className="ppm-field">
                        <label className="ppm-label">BHK</label>
                        <div className="ppm-segmented">
                            {BHK_OPTIONS.map((opt) => (
                                <button
                                    key={opt} type="button"
                                    className={`ppm-seg-btn ${bhk === opt ? 'ppm-seg-btn--active' : ''}`}
                                    onClick={() => { setBhk(opt); setErrors((p) => ({ ...p, bhk: '' })) }}
                                >{opt}</button>
                            ))}
                        </div>
                        {errors.bhk && <span className="ppm-error-text">{errors.bhk}</span>}
                    </div>

                    {/* Bathrooms */}
                    <div className="ppm-field">
                        <label className="ppm-label">Bathrooms</label>
                        <div className="ppm-segmented">
                            {BATH_OPTIONS.map((opt) => (
                                <button
                                    key={opt} type="button"
                                    className={`ppm-seg-btn ${bathrooms === opt ? 'ppm-seg-btn--active' : ''}`}
                                    onClick={() => { setBathrooms(opt); setErrors((p) => ({ ...p, bathrooms: '' })) }}
                                >{opt}</button>
                            ))}
                        </div>
                        {errors.bathrooms && <span className="ppm-error-text">{errors.bathrooms}</span>}
                    </div>

                    {/* Area */}
                    <div className="ppm-field">
                        <label className="ppm-label">Area (sq ft)</label>
                        <input
                            type="number"
                            className={`ppm-input ${errors.areaSqFt ? 'ppm-input--error' : ''}`}
                            placeholder="e.g. 1200"
                            value={areaSqFt}
                            onChange={(e) => { setAreaSqFt(e.target.value); setErrors((p) => ({ ...p, areaSqFt: '' })) }}
                            min="100"
                        />
                        {errors.areaSqFt && <span className="ppm-error-text">{errors.areaSqFt}</span>}
                    </div>

                    {/* Property Type */}
                    <div className="ppm-field">
                        <label className="ppm-label">Property Type</label>
                        <div className="ppm-pills">
                            {PROPERTY_TYPES.map((opt) => (
                                <button
                                    key={opt} type="button"
                                    className={`ppm-pill ${propertyType === opt ? 'ppm-pill--active' : ''}`}
                                    onClick={() => { setPropertyType(opt); setErrors((p) => ({ ...p, propertyType: '' })) }}
                                >{opt}</button>
                            ))}
                        </div>
                        {errors.propertyType && <span className="ppm-error-text">{errors.propertyType}</span>}
                    </div>

                    {/* Furnishing */}
                    <div className="ppm-field">
                        <label className="ppm-label">Furnishing</label>
                        <div className="ppm-pills">
                            {FURNISHING_OPTIONS.map((opt) => (
                                <button
                                    key={opt} type="button"
                                    className={`ppm-pill ${furnishing === opt ? 'ppm-pill--active' : ''}`}
                                    onClick={() => { setFurnishing(opt); setErrors((p) => ({ ...p, furnishing: '' })) }}
                                >{opt}</button>
                            ))}
                        </div>
                        {errors.furnishing && <span className="ppm-error-text">{errors.furnishing}</span>}
                    </div>

                    {apiError && <div className="ppm-api-error">{apiError}</div>}

                    <button
                        type="button"
                        className="ppm-submit"
                        onClick={handlePredict}
                        disabled={isLoading}
                    >
                        {isLoading ? (
                            <span className="ppm-submit-loading">
                                <span className="loading-dot" aria-hidden="true" />
                                Predicting…
                            </span>
                        ) : (
                            'Get Price Estimate →'
                        )}
                    </button>
                </div>
            </div>
        </div>
    )
}
