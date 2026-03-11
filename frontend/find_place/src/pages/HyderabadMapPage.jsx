import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useJsApiLoader } from '@react-google-maps/api'

import SearchBar from '../components/LocationSearch'
import MapView from '../components/MapView'
import AreaPanel from '../components/AreaPanel'
import ClimateCard from '../components/ClimateCard'
import AmenityPanel from '../components/AmenityPanel'
import PredictPriceModal from '../components/PredictPriceModal'
import UsageBadge from '../components/UsageBadge'
import { analyzeArea, fetchUsageCounter, DailyLimitError } from '../services/areaAnalysisApi'
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
  const [mapTypeId, setMapTypeId] = useState('roadmap')

  const mapRef = useRef(null)

  /* ── Analysis state ── */
  const [analysisResult, setAnalysisResult] = useState(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState('')
  const [mapRuntimeError, setMapRuntimeError] = useState('')
  const analysisCacheRef = useRef(new Map())

  /* ── Panel states ── */
  const [showAreaPanel, setShowAreaPanel] = useState(false)
  const [showPredictModal, setShowPredictModal] = useState(false)
  const [activeTag, setActiveTag] = useState(null)

  /* ── Usage counter state ── */
  const [usageInfo, setUsageInfo] = useState(null) // { date, count, limit, limit_reached }
  const [limitReached, setLimitReached] = useState(false)

  // Fetch counter on mount
  useEffect(() => {
    fetchUsageCounter().then((data) => {
      if (data) {
        setUsageInfo(data)
        setLimitReached(data.limit_reached)
      }
    })
  }, [])

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

  const handleMapLoaded = useCallback((map) => {
    mapRef.current = map
    map.setCenter(HYDERABAD_CENTER)
    map.setZoom(13)
    map.setMapTypeId('roadmap')
  }, [])

  const handleBack = () => navigate('/dashboard')

  /* ── Auto-analyze helper ── */
  const runAnalysis = useCallback(async (location) => {
    if (!location) return

    const cacheKey = `${Number(location.lat).toFixed(5)},${Number(location.lng).toFixed(5)}`
    const cached = analysisCacheRef.current.get(cacheKey)
    if (cached) {
      setAnalysisResult(cached)
      setShowAreaPanel(true)
      setActiveTag(null)
      return
    }

    setIsAnalyzing(true)
    setShowAreaPanel(true)
    setActiveTag(null)
    setAnalysisError('')
    try {
      const response = await analyzeArea(location)
      analysisCacheRef.current.set(cacheKey, response)
      setAnalysisResult(response)
      // Update usage counter from response
      if (response.usage) {
        setUsageInfo(response.usage)
        setLimitReached(response.usage.limit_reached)
      }
    } catch (error) {
      if (error instanceof DailyLimitError) {
        // Limit reached — update state, keep panel open in degraded mode
        if (error.usage) {
          setUsageInfo(error.usage)
        }
        setLimitReached(true)
        setAnalysisResult(null)
        setAnalysisError('')
      } else {
        setAnalysisResult(null)
        setAnalysisError(error.message || 'Unable to analyze selected area right now.')
      }
    } finally {
      setIsAnalyzing(false)
    }
  }, [])



  /* ── Search selection → auto-analyze ── */
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
    // Auto-trigger analysis
    runAnalysis(location)
  }, [runAnalysis])

  /* ── Panel controls ── */
  const handleCloseAreaPanel = () => {
    setShowAreaPanel(false)
    setActiveTag(null)
    setAnalysisError('')
  }

  const handleTagClick = (tag) => setActiveTag(tag)
  const handleClearTag = () => setActiveTag(null)

  /* ── Extract locality name ── */
  const localityName = selectedLocation?.address?.split(',')[0]?.trim() || ''

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
      {/* Back to dashboard */}
      <button className="map-back-btn" onClick={handleBack}>← Dashboard</button>

      {/* Usage counter badge */}
      <UsageBadge usageInfo={usageInfo} />

      <section className="map-container">
        <MapView
          center={mapCenter}
          zoom={mapZoom}
          markerPosition={selectedLocation}
          areaBoundary={areaBoundary}
          onMapLoad={handleMapLoaded}
          mapTypeId={mapTypeId}
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

        {/* ── LEFT AREA PANEL — appears after locality selection ── */}
        {showAreaPanel && selectedLocation && (
          <AreaPanel
            locality={localityName}
            analysisResult={analysisResult}
            isLoading={isAnalyzing}
            onClose={handleCloseAreaPanel}
            onOpenPredict={() => setShowPredictModal(true)}
            onTagClick={handleTagClick}
            activeTag={activeTag}
            limitReached={limitReached}
          />
        )}

        {/* ── RIGHT: CLIMATE CARD (no tag) or AMENITY PANEL (tag active) ── */}
        {showAreaPanel && selectedLocation && analysisResult && !activeTag && !limitReached && (
          <ClimateCard
            lat={selectedLocation.lat}
            lng={selectedLocation.lng}
          />
        )}

        {showAreaPanel && selectedLocation && analysisResult && activeTag && !limitReached && (
          <AmenityPanel
            activeTag={activeTag}
            analysisResult={analysisResult}
            onClose={handleClearTag}
          />
        )}
      </section>

      {/* ── PREDICT PRICE MODAL ── */}
      {showPredictModal && (
        <PredictPriceModal
          locality={localityName}
          onClose={() => setShowPredictModal(false)}
        />
      )}
    </main>
  )
}