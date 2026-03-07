import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useJsApiLoader } from '@react-google-maps/api'

import SearchBar from '../components/LocationSearch'
import MapView from '../components/MapView'
import DashboardPanel from '../components/DashboardPanel'
import SellersPanel from '../components/SellersPanel'
import PredictPriceModal from '../components/PredictPriceModal'
import useResizable from '../hooks/useResizable'
import { analyzeArea } from '../services/areaAnalysisApi'
import {
  fetchBoundaryByName,
  fetchBoundaryByCoords,
} from '../services/boundaryService'
import '../App.css'

const HYDERABAD_CENTER = { lat: 17.385, lng: 78.4867 }
const MAPS_LIBRARIES = ['places']

export default function HyderabadMapPage() {
  const navigate = useNavigate()
  const mapsApiKey = (import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '').trim()

  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: mapsApiKey,
    libraries: MAPS_LIBRARIES,
    authReferrerPolicy: 'origin',
  })

  /* ── Core map state ── */
  const [mapCenter, setMapCenter] = useState(HYDERABAD_CENTER)
  const [mapZoom, setMapZoom] = useState(13)
  const [selectedLocation, setSelectedLocation] = useState(null)
  const [searchValue, setSearchValue] = useState('')
  const [areaBoundary, setAreaBoundary] = useState(null)

  const mapRef = useRef(null)

  /* ── Analysis state ── */
  const [analysisResult, setAnalysisResult] = useState(null)
  const [showAnalysis, setShowAnalysis] = useState(false)
  const [analysisError, setAnalysisError] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [mapRuntimeError, setMapRuntimeError] = useState('')
  const analysisCacheRef = useRef(new Map()) // key: "lat,lng" → result

  /* ── Sellers panel state ── */
  const [showSellers, setShowSellers] = useState(false)

  /* ── Predict price modal state ── */
  const [showPredictModal, setShowPredictModal] = useState(false)

  /* ── Resizable panel ── */
  const { width: panelWidth, handleMouseDown } = useResizable({
    defaultWidth: 420,
    minWidth: 350,
    maxWidth: 700,
  })
  const panelOpen = !!analysisResult && showAnalysis

  useEffect(() => {
    const previousAuthFailureHandler = window.gm_authFailure

    const handleAuthFailure = () => {
      setMapRuntimeError('Google Maps authorization failed.')
      if (typeof previousAuthFailureHandler === 'function') {
        previousAuthFailureHandler()
      }
    }

    window.gm_authFailure = handleAuthFailure

    return () => {
      if (window.gm_authFailure === handleAuthFailure) {
        if (typeof previousAuthFailureHandler === 'function') {
          window.gm_authFailure = previousAuthFailureHandler
        } else {
          delete window.gm_authFailure
        }
      }
    }
  }, [])

  /* ── Simple map load — start directly at Hyderabad ── */
  const handleMapLoaded = useCallback((map) => {
    mapRef.current = map
    map.setCenter(HYDERABAD_CENTER)
    map.setZoom(13)
    map.setMapTypeId('roadmap')
  }, [])

  /* ── Back to dashboard ──*/
  const handleBack = () => navigate('/dashboard')

  /* ── Map click ── */
  const reverseGeocode = useCallback((lat, lng) => {
    if (!window.google?.maps?.Geocoder) {
      return
    }

    const geocoder = new window.google.maps.Geocoder()
    geocoder.geocode({ location: { lat, lng } }, async (results, status) => {
      const topResult = status === 'OK' ? results?.[0] : null
      const address = topResult
        ? topResult.formatted_address
        : `Selected point (${lat.toFixed(5)}, ${lng.toFixed(5)})`
      setSelectedLocation({ lat, lng, address })
      setSearchValue(address)
      const boundary = await fetchBoundaryByCoords(lat, lng)
      if (boundary) {
        setAreaBoundary(boundary)
      } else {
        const viewport = topResult?.geometry?.viewport || null
        setAreaBoundary(viewport ? { paths: null, bounds: viewport } : null)
      }
    })
  }, [])

  const handleMapClick = useCallback(
    ({ lat, lng }) => {
      setMapCenter({ lat, lng })
      setAnalysisError('')
      reverseGeocode(lat, lng)
    },
    [reverseGeocode],
  )

  /* ── Search selection ── */
  const handleSelectFromSearch = useCallback(async (location) => {
    setMapCenter({ lat: location.lat, lng: location.lng })
    setSelectedLocation(location)
    setSearchValue(location.address || '')
    setAnalysisError('')
    const searchQuery = location.name || location.address || ''
    const boundary = await fetchBoundaryByName(searchQuery)
    if (boundary) {
      setAreaBoundary(boundary)
    } else if (location.viewport) {
      setAreaBoundary({ paths: null, bounds: location.viewport })
      setMapZoom(16)
    } else {
      setAreaBoundary(null)
      setMapZoom(16)
    }
  }, [])

  /* ── Analyze flow (with cache) ── */
  const handleAnalyze = async (overrideLocation = null) => {
    const locationToUse = overrideLocation
      ? { lat: overrideLocation.lat, lng: overrideLocation.lng, address: overrideLocation.name || overrideLocation.address }
      : selectedLocation
    if (!locationToUse) return

    const cacheKey = `${Number(locationToUse.lat).toFixed(5)},${Number(locationToUse.lng).toFixed(5)}`
    const cached = analysisCacheRef.current.get(cacheKey)
    if (cached) {
      setAnalysisResult(cached)
      setShowAnalysis(true)
      setShowSellers(false)
      return
    }

    setIsAnalyzing(true)
    setAnalysisError('')
    try {
      const response = await analyzeArea(locationToUse)
      analysisCacheRef.current.set(cacheKey, response)
      setAnalysisResult(response)
      setShowAnalysis(true)
    } catch (error) {
      setAnalysisResult(null)
      setShowAnalysis(false)
      setAnalysisError(error.message || 'Unable to analyze selected area right now.')
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handleClosePanel = () => {
    setShowAnalysis(false)
    setAnalysisError('')
  }

  /* ── Sellers flow ── */
  const handleOpenSellers = () => {
    setShowSellers(true)
  }

  const handleCloseSellers = () => {
    setShowSellers(false)
  }

  /* ── Loading / error ── */
  if (loadError || mapRuntimeError || !mapsApiKey) {
    return (
      <div className="map-load-error">
        <p>Failed to load Google Maps.</p>
        <p>
          {!mapsApiKey
            ? 'Missing VITE_GOOGLE_MAPS_API_KEY in frontend/find_place/.env'
            : (mapRuntimeError || 'Please verify API key restrictions for this origin and port.')}
        </p>
      </div>
    )
  }

  if (!isLoaded) {
    return (
      <div className="map-loading">
        <span className="loading-dot" aria-hidden="true" />
        Loading map...
      </div>
    )
  }

  return (
    <main className="map-page">
      {/* Back to dashboard button */}
      <button className="map-back-btn" onClick={handleBack}>← Dashboard</button>

      <section className="map-container">
        <MapView
          center={mapCenter}
          zoom={mapZoom}
          markerPosition={selectedLocation}
          areaBoundary={areaBoundary}
          onMapClick={handleMapClick}
          onMapLoad={handleMapLoaded}
        />

        {/* Floating search */}
        <div className="floating-search-wrapper visible">
          <SearchBar
            searchValue={searchValue}
            onSearchValueChange={setSearchValue}
            onSelectLocation={handleSelectFromSearch}
          />
        </div>

        {analysisError && <div className="analysis-error">{analysisError}</div>}

        {/* ── ACTION BUTTONS — appear after selecting a locality ── */}
        {selectedLocation && (
          <div className="action-buttons-bar">
            <button
              type="button"
              className="action-btn action-btn--sellers"
              onClick={handleOpenSellers}
            >
              Identify Sellers 🏷️
            </button>
            <button
              type="button"
              className="action-btn action-btn--predict"
              onClick={() => setShowPredictModal(true)}
            >
              Predict Price 💰
            </button>
            <button
              type="button"
              className="action-btn action-btn--analyze"
              onClick={() => handleAnalyze()}
              disabled={isAnalyzing}
            >
              {isAnalyzing ? (
                <span className="analyze-loading">
                  <span className="loading-dot" aria-hidden="true" />
                  Analyzing…
                </span>
              ) : (
                'Analyse Area 📍'
              )}
            </button>
          </div>
        )}
      </section>

      {/* ── SELLERS PANEL (LEFT) ── */}
      <div className={`sellers-shell ${showSellers ? 'open' : ''}`}>
        {showSellers && (
          <SellersPanel
            locality={selectedLocation?.address?.split(',')[0]?.trim() || ''}
            onClose={handleCloseSellers}
          />
        )}
      </div>

      {/* ── ANALYSIS PANEL (RIGHT) ── */}
      <div
        className={`dashboard-shell ${panelOpen ? 'open' : ''}`}
        style={panelOpen ? { width: panelWidth } : undefined}
      >
        <div className="resize-handle" onMouseDown={handleMouseDown} />
        {analysisResult && showAnalysis && <DashboardPanel result={analysisResult} onClose={handleClosePanel} />}
      </div>

      {/* ── PREDICT PRICE MODAL ── */}
      {showPredictModal && (
        <PredictPriceModal
          locality={selectedLocation?.address?.split(',')[0]?.trim() || ''}
          onClose={() => setShowPredictModal(false)}
        />
      )}

    </main>
  )
}