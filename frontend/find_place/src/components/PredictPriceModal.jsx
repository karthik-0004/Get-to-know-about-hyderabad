import { useState } from 'react'
import './PredictPriceModal.css'

const PROPERTY_TYPES = [
  { key: 'apartment', label: 'Apartment', icon: '🏢' },
  { key: 'villa', label: 'Villa', icon: '🏡' },
  { key: 'independent_house', label: 'Independent House', icon: '🏠' },
  { key: 'plot', label: 'Plot', icon: '🟫' },
]

const RENTAL_BHK_OPTIONS = [
  { key: '1bhk', label: '1 BHK' },
  { key: '2bhk', label: '2 BHK' },
  { key: '3bhk', label: '3 BHK' },
]

const FURNISHING_OPTIONS = [
  { key: 'furnished', label: 'Furnished' },
  { key: 'semi-furnished', label: 'Semi-Furnished' },
  { key: 'unfurnished', label: 'Unfurnished' },
]

const RENTAL_PROPERTY_TYPES = [
  { key: 'flat', label: 'Flat', icon: '🏢' },
  { key: 'independent house', label: 'Independent House', icon: '🏠' },
  { key: 'builder floor', label: 'Builder Floor', icon: '🏗️' },
]

function formatIndianPrice(num) {
  if (num >= 10000000) return `₹ ${(num / 10000000).toFixed(2)} Cr`
  if (num >= 100000) return `₹ ${(num / 100000).toFixed(2)} L`
  return `₹ ${num.toLocaleString('en-IN')}`
}

function formatRent(num) {
  return `₹ ${Math.round(num).toLocaleString('en-IN')} / month`
}

export default function PredictPriceModal({ locality, onClose }) {
  const [activeTab, setActiveTab] = useState('buy')

  // Buy / Sale state
  const [localityInput, setLocalityInput] = useState(locality || '')
  const [propertyType, setPropertyType] = useState('')
  const [bhk, setBhk] = useState(2)
  const [sqft, setSqft] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  // Rentals state
  const [rentLocality, setRentLocality] = useState(locality || '')
  const [rentBhk, setRentBhk] = useState('')
  const [rentSqft, setRentSqft] = useState('')
  const [rentFurnishing, setRentFurnishing] = useState('')
  const [rentPropertyType, setRentPropertyType] = useState('')
  const [rentLoading, setRentLoading] = useState(false)
  const [rentResult, setRentResult] = useState(null)
  const [rentError, setRentError] = useState('')

  const hasBhk = propertyType && propertyType !== 'plot'

  // ── Buy / Sale handlers ──
  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!propertyType) { setError('Please select a property type'); return }
    if (!sqft || Number(sqft) <= 0) { setError('Please enter a valid area in sq.ft'); return }

    setError('')
    setLoading(true)
    setResult(null)

    try {
      const payload = {
        locality: localityInput,
        property_type: propertyType,
        bhk: hasBhk ? bhk : null,
        sqft: Number(sqft),
      }
      const resp = await fetch('http://127.0.0.1:8000/api/predict/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.error || 'Prediction failed')
      setResult(data)
    } catch (err) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setResult(null)
    setError('')
    setPropertyType('')
    setBhk(2)
    setSqft('')
  }

  // ── Rentals handlers ──
  const handleRentSubmit = async (e) => {
    e.preventDefault()
    if (!rentBhk) { setRentError('Please select a BHK type'); return }
    if (!rentSqft || Number(rentSqft) <= 0) { setRentError('Please enter a valid area in sq.ft'); return }
    if (!rentFurnishing) { setRentError('Please select furnishing status'); return }
    if (!rentPropertyType) { setRentError('Please select a property type'); return }

    setRentError('')
    setRentLoading(true)
    setRentResult(null)

    try {
      const payload = {
        locality: rentLocality,
        bhk: rentBhk,
        sqft: Number(rentSqft),
        furnishing: rentFurnishing,
        property_type: rentPropertyType,
      }
      const resp = await fetch('http://127.0.0.1:8000/api/predict/rent/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.error || 'Prediction failed')
      setRentResult(data)
    } catch (err) {
      setRentError(err.message || 'Something went wrong')
    } finally {
      setRentLoading(false)
    }
  }

  const handleRentReset = () => {
    setRentResult(null)
    setRentError('')
    setRentBhk('')
    setRentSqft('')
    setRentFurnishing('')
    setRentPropertyType('')
  }

  const switchTab = (tab) => {
    setActiveTab(tab)
    setError('')
    setRentError('')
  }

  return (
    <div className="pp-overlay" onClick={onClose}>
      <div className="pp-modal" onClick={(e) => e.stopPropagation()}>
        {/* Close */}
        <button className="pp-close" onClick={onClose} aria-label="Close">✕</button>

        <h2 className="pp-heading">Price Prediction</h2>
        <p className="pp-subheading">Get an estimated property price for any Hyderabad locality</p>

        {/* ── Tab Toggle ── */}
        <div className="pp-tabs">
          <button
            type="button"
            className={`pp-tab${activeTab === 'buy' ? ' pp-tab--active' : ''}`}
            onClick={() => switchTab('buy')}
          >
            🏠 Buy / Sale
          </button>
          <button
            type="button"
            className={`pp-tab${activeTab === 'rent' ? ' pp-tab--active' : ''}`}
            onClick={() => switchTab('rent')}
          >
            🔑 Rentals
          </button>
        </div>

        {/* ══════════ BUY / SALE FORM ══════════ */}
        {activeTab === 'buy' && (
          <div className="pp-tab-content">
            <form className="pp-form" onSubmit={handleSubmit}>
              <div className="pp-field pp-field--anim" style={{ animationDelay: '0.05s' }}>
                <label className="pp-label">Enter Street / Locality</label>
                <input
                  className="pp-input"
                  type="text"
                  value={localityInput}
                  onChange={(e) => setLocalityInput(e.target.value)}
                  placeholder="e.g. Banjara Hills, Jubilee Hills Road No. 36…"
                />
              </div>

              <div className="pp-field pp-field--anim" style={{ animationDelay: '0.12s' }}>
                <label className="pp-label">Select Property Type</label>
                <div className="pp-type-grid">
                  {PROPERTY_TYPES.map((pt) => (
                    <button
                      key={pt.key}
                      type="button"
                      className={`pp-type-card${propertyType === pt.key ? ' pp-type-card--active' : ''}`}
                      onClick={() => setPropertyType(pt.key)}
                    >
                      <span className="pp-type-icon">{pt.icon}</span>
                      <span className="pp-type-label">{pt.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {hasBhk && (
                <div className="pp-field pp-field--anim" style={{ animationDelay: '0.19s' }}>
                  <label className="pp-label">Number of BHK</label>
                  <div className="pp-stepper">
                    <button type="button" className="pp-stepper-btn" onClick={() => setBhk((b) => Math.max(1, b - 1))}>−</button>
                    <span className="pp-stepper-val">{bhk}</span>
                    <button type="button" className="pp-stepper-btn" onClick={() => setBhk((b) => Math.min(6, b + 1))}>+</button>
                  </div>
                </div>
              )}

              <div className="pp-field pp-field--anim" style={{ animationDelay: hasBhk ? '0.26s' : '0.19s' }}>
                <label className="pp-label">Total Area (sq.ft)</label>
                <input
                  className="pp-input"
                  type="number"
                  min="1"
                  value={sqft}
                  onChange={(e) => setSqft(e.target.value)}
                  placeholder="e.g. 1200"
                />
              </div>

              {error && <p className="pp-error">{error}</p>}

              {!result && (
                <button type="submit" className="pp-submit" disabled={loading}>
                  {loading ? <span className="pp-spinner" /> : 'Get Price Estimate →'}
                </button>
              )}
            </form>

            {result && (
              <div className="pp-result">
                <span className="pp-result-label">Estimated Price</span>
                <span className="pp-result-price">{formatIndianPrice(result.predicted_price)}</span>
                {result.sqft_range && result.sqft_range.min > 0 && (
                  <span className="pp-result-sqft-range">
                    📐 Sqft Range: <strong>{result.sqft_range.min.toLocaleString('en-IN')}</strong> – <strong>{result.sqft_range.max.toLocaleString('en-IN')}</strong> sq.ft
                  </span>
                )}
                {!result.locality_found && (
                  <span className="pp-result-note">Locality not found in primary data — used general model</span>
                )}
                <button type="button" className="pp-try-again" onClick={handleReset}>Try Another</button>
              </div>
            )}
          </div>
        )}

        {/* ══════════ RENTALS FORM ══════════ */}
        {activeTab === 'rent' && (
          <div className="pp-tab-content">
            <form className="pp-form" onSubmit={handleRentSubmit}>
              {/* Locality */}
              <div className="pp-field pp-field--anim" style={{ animationDelay: '0.05s' }}>
                <label className="pp-label">Enter Street / Locality</label>
                <input
                  className="pp-input"
                  type="text"
                  value={rentLocality}
                  onChange={(e) => setRentLocality(e.target.value)}
                  placeholder="e.g. Kondapur, Madhapur…"
                />
              </div>

              {/* BHK Type */}
              <div className="pp-field pp-field--anim" style={{ animationDelay: '0.12s' }}>
                <label className="pp-label">Select BHK Type</label>
                <div className="pp-pill-row">
                  {RENTAL_BHK_OPTIONS.map((opt) => (
                    <button
                      key={opt.key}
                      type="button"
                      className={`pp-pill${rentBhk === opt.key ? ' pp-pill--active' : ''}`}
                      onClick={() => setRentBhk(opt.key)}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Total Area */}
              <div className="pp-field pp-field--anim" style={{ animationDelay: '0.19s' }}>
                <label className="pp-label">Total Area (sq.ft)</label>
                <input
                  className="pp-input"
                  type="number"
                  min="1"
                  value={rentSqft}
                  onChange={(e) => setRentSqft(e.target.value)}
                  placeholder="e.g. 650"
                />
              </div>

              {/* Furnishing Status */}
              <div className="pp-field pp-field--anim" style={{ animationDelay: '0.26s' }}>
                <label className="pp-label">Furnishing Status</label>
                <div className="pp-pill-row">
                  {FURNISHING_OPTIONS.map((opt) => (
                    <button
                      key={opt.key}
                      type="button"
                      className={`pp-pill${rentFurnishing === opt.key ? ' pp-pill--active' : ''}`}
                      onClick={() => setRentFurnishing(opt.key)}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Property Type */}
              <div className="pp-field pp-field--anim" style={{ animationDelay: '0.33s' }}>
                <label className="pp-label">Property Type</label>
                <div className="pp-pill-row">
                  {RENTAL_PROPERTY_TYPES.map((pt) => (
                    <button
                      key={pt.key}
                      type="button"
                      className={`pp-pill pp-pill--wide${rentPropertyType === pt.key ? ' pp-pill--active' : ''}`}
                      onClick={() => setRentPropertyType(pt.key)}
                    >
                      <span>{pt.icon}</span> {pt.label}
                    </button>
                  ))}
                </div>
              </div>

              {rentError && <p className="pp-error">{rentError}</p>}

              {!rentResult && (
                <button type="submit" className="pp-submit" disabled={rentLoading}>
                  {rentLoading ? <span className="pp-spinner" /> : 'Get Rent Estimate →'}
                </button>
              )}
            </form>

            {rentResult && (
              <div className="pp-result">
                <span className="pp-result-label">Estimated Monthly Rent</span>
                <span className="pp-result-price">{formatRent(rentResult.predicted_rent)}</span>
                <span className="pp-result-model">
                  Predicted using: {rentResult.model_used.replace(/_/g, ' ').replace('model', 'Model')}
                </span>
                {!rentResult.locality_found && (
                  <span className="pp-result-note">
                    ⚠️ Locality not found in {rentBhk.toUpperCase()} data — used general rental model
                  </span>
                )}
                <button type="button" className="pp-try-again" onClick={handleRentReset}>Try Another</button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
