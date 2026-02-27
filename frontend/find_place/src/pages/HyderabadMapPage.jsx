import { useCallback, useEffect, useRef, useState } from 'react'
import { useJsApiLoader } from '@react-google-maps/api'

import SearchBar from '../components/LocationSearch'
import MapView from '../components/MapView'
import DashboardPanel from '../components/DashboardPanel'
import PricePredictionModal from '../components/PricePredictionModal'
import useResizable from '../hooks/useResizable'
import { analyzeArea } from '../services/areaAnalysisApi'
import {
  fetchBoundaryByName,
  fetchBoundaryByCoords,
  fetchCityOuterBoundary,
} from '../services/boundaryService'
import '../App.css'

const INDIA_CENTER = { lat: 20.5937, lng: 78.9629 }
const HYDERABAD_CENTER = { lat: 17.385, lng: 78.4867 }
const MAPS_LIBRARIES = ['places']

export default function HyderabadMapPage() {
  const mapsApiKey = (import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '').trim()

  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: mapsApiKey,
    libraries: MAPS_LIBRARIES,
    authReferrerPolicy: 'origin',
  })

  /* ── Core map state ── */
  const [mapCenter, setMapCenter] = useState(INDIA_CENTER)
  const [mapZoom, setMapZoom] = useState(4)
  const [selectedLocation, setSelectedLocation] = useState(null)
  const [searchValue, setSearchValue] = useState('')
  const [areaBoundary, setAreaBoundary] = useState(null)

  /* ── Intro state ── */
  const [introPhase, setIntroPhase] = useState('start')
  const [introOverlayOpacity, setIntroOverlayOpacity] = useState(0.45)
  const [introTextScale, setIntroTextScale] = useState(1.0)
  const [introTextVisible, setIntroTextVisible] = useState(false)
  const [introBoundary, setIntroBoundary] = useState(null)
  const [introBoundaryVisible, setIntroBoundaryVisible] = useState(false)
  const mapRef = useRef(null)
  const introReadyRef = useRef(false) // true once user can press Enter
  const introTimers = useRef([])

  /* ── Prediction modal state ── */
  const [showPredictionModal, setShowPredictionModal] = useState(false)
  const [predictionBoundary, setPredictionBoundary] = useState(null)
  const [predictionMarker, setPredictionMarker] = useState(null)

  /* ── Analysis state ── */
  const [analysisResult, setAnalysisResult] = useState(null)
  const [analysisError, setAnalysisError] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [mapRuntimeError, setMapRuntimeError] = useState('')

  /* ── Resizable panel ── */
  const { width: panelWidth, handleMouseDown } = useResizable({
    defaultWidth: 420,
    minWidth: 350,
    maxWidth: 700,
  })
  const panelOpen = !!analysisResult

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

  /* ══════════════════════════════════════════════════════════════
     CINEMATIC INTRO — satellite: World → India → Hyderabad
     Stops at Hyderabad with GHMC red boundary. Enter → roadmap.
     ══════════════════════════════════════════════════════════════ */
  const ghmcBoundaryRef = useRef(null)
  const ghmcPromiseRef = useRef(null)

  // Pre-fetch the GHMC boundary as early as possible (component mount)
  useEffect(() => {
    if (!ghmcPromiseRef.current) {
      ghmcPromiseRef.current = fetchCityOuterBoundary('Hyderabad').then((b) => {
        if (b) ghmcBoundaryRef.current = b
        return b
      })
    }
  }, [])

  const handleMapLoaded = useCallback((map) => {
    mapRef.current = map

    // Start at world view, satellite
    setMapCenter(INDIA_CENTER)
    setMapZoom(3)
    map.setCenter(INDIA_CENTER)
    map.setZoom(3)

    // Phase 1 — Disable controls, satellite mode
    map.setOptions({
      disableDefaultUI: true,
      zoomControl: false,
      streetViewControl: false,
      mapTypeControl: false,
      fullscreenControl: false,
      keyboardShortcuts: false,
    })
    map.setMapTypeId('hybrid')

    // Title fades in after map is visible
    const tText = setTimeout(() => setIntroTextVisible(true), 1500)

    // Phase 2 — World → India (satellite)
    const tZoom1 = setTimeout(() => {
      setIntroPhase('zooming')
      setMapZoom(5)
      map.setZoom(5)
      map.panTo(INDIA_CENTER)
      setIntroOverlayOpacity(0.2)
      setIntroTextScale(1.03)
    }, 800)

    // Phase 3 — India → Hyderabad (satellite)
    const tZoom2 = setTimeout(() => {
      setMapZoom(11)
      setMapCenter(HYDERABAD_CENTER)
      map.setZoom(11)
      map.panTo(HYDERABAD_CENTER)
      setIntroOverlayOpacity(0.05)
      setIntroTextScale(1.06)
    }, 2500)

    // Phase 4 — Switch to normal map, fit to Hyderabad area, STOP here
    const tHighlight = setTimeout(async () => {
      setIntroPhase('highlighting')
      setIntroOverlayOpacity(0)
      setIntroTextVisible(false)

      // Wait for pre-fetched GHMC boundary
      let boundary = ghmcBoundaryRef.current
      if (!boundary && ghmcPromiseRef.current) {
        boundary = await ghmcPromiseRef.current
      }

      // Switch to normal roadmap for Hyderabad
      if (mapRef.current) {
        mapRef.current.setMapTypeId('roadmap')

        if (boundary?.paths?.length) {
          // Show the red boundary and fit the map to it
          setIntroBoundary(boundary)
          setIntroBoundaryVisible(true)
          const bounds = new window.google.maps.LatLngBounds()
          boundary.paths.forEach((ring) => ring.forEach((pt) => bounds.extend(pt)))
          mapRef.current.fitBounds(bounds, { top: 50, right: 50, bottom: 50, left: 50 })
        } else {
          // Fallback — just zoom to Hyderabad center
          mapRef.current.panTo(HYDERABAD_CENTER)
          mapRef.current.setZoom(12)
        }
      }

      // Go straight to ready
      setTimeout(() => {
        setIntroPhase('ready')
        introReadyRef.current = true
      }, 500)
    }, 4000)

    introTimers.current = [tText, tZoom1, tZoom2, tHighlight]
  }, [])

  // Cleanup
  useEffect(() => {
    return () => introTimers.current.forEach((t) => {
      clearTimeout(t)
      clearInterval(t)
    })
  }, [])

  /* ── Phase 5 — User presses ENTER to transition into interactive mode ── */
  const handleIntroNext = useCallback(() => {
    if (!introReadyRef.current) return

    introReadyRef.current = false

    // Remove red boundary overlay
    setIntroBoundary(null)
    setIntroBoundaryVisible(false)

    // Re-enable map controls
    if (mapRef.current) {
      mapRef.current.setOptions({
        disableDefaultUI: false,
        zoomControl: true,
        keyboardShortcuts: true,
      })
    }

    // Fade out overlay, then switch to roadmap + closer zoom
    setIntroPhase('fading')
    setTimeout(() => {
      setIntroPhase('done')
      setMapZoom(13)
      setMapCenter(HYDERABAD_CENTER)
      if (mapRef.current) {
        mapRef.current.setMapTypeId('roadmap') // switch to normal map
        mapRef.current.setZoom(13)
        mapRef.current.panTo(HYDERABAD_CENTER)
      }
    }, 500)
  }, [])

  /* ── Listen for Enter key only ── */
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Enter' && introReadyRef.current) {
        handleIntroNext()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleIntroNext])

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
      if (introPhase !== 'done') return
      setMapCenter({ lat, lng })
      setAnalysisError('')
      reverseGeocode(lat, lng)
    },
    [introPhase, reverseGeocode],
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

  /* ── Prediction flow ── */
  const handleOpenPredict = () => setShowPredictionModal(true)

  const handlePredictionLocalitySelect = useCallback(async ({ name, lat, lng }) => {
    const boundary = await fetchBoundaryByName(name)
    setPredictionBoundary(boundary)
    setPredictionMarker({ lat, lng, label: name })
    setMapCenter({ lat, lng })
    setMapZoom(14)
  }, [])

  const handleClosePredictionModal = useCallback(() => {
    setShowPredictionModal(false)
    setPredictionBoundary(null)
    setPredictionMarker(null)
  }, [])

  /* ── Analyze flow ── */
  const handleAnalyze = async (overrideLocation = null) => {
    const locationToUse = overrideLocation
      ? { lat: overrideLocation.lat, lng: overrideLocation.lng, address: overrideLocation.name || overrideLocation.address }
      : selectedLocation
    if (!locationToUse) return
    setIsAnalyzing(true)
    setAnalysisError('')
    try {
      const response = await analyzeArea(locationToUse)
      setAnalysisResult(response)
    } catch (error) {
      setAnalysisResult(null)
      setAnalysisError(error.message || 'Unable to analyze selected area right now.')
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handleClosePanel = () => {
    setAnalysisResult(null)
    setAnalysisError('')
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

  const introDone = introPhase === 'done'

  return (
    <main className="map-page">
      <section className="map-container">
        <MapView
          center={mapCenter}
          zoom={mapZoom}
          markerPosition={selectedLocation}
          areaBoundary={areaBoundary}
          introBoundary={introBoundary}
          introBoundaryVisible={introBoundaryVisible}
          introActive={!introDone}
          predictionBoundary={predictionBoundary}
          predictionMarker={predictionMarker}
          onMapClick={handleMapClick}
          onMapLoad={handleMapLoaded}
        />

        {/* ══ CINEMATIC INTRO OVERLAY ══ */}
        {introPhase !== 'done' && (
          <div
            className={`intro-overlay ${introPhase === 'fading' ? 'intro-overlay--fading' : ''}`}
            style={{ backgroundColor: `rgba(0, 0, 0, ${introOverlayOpacity})`, pointerEvents: 'none' }}
          >
            <div className="intro-text-block">
              <h1
                className={`intro-title title-glow ${introTextVisible ? 'intro-title--visible' : ''}`}
                style={{ transform: `scale(${introTextScale})` }}
              >
                Get to know about hyderabad
              </h1>
            </div>

            {/* Press Enter prompt — visible only when ready */}
            {introPhase === 'ready' && (
              <div className="intro-enter-prompt">
                Press <kbd>Enter</kbd> to explore
              </div>
            )}
          </div>
        )}

        {/* Floating search — visible during ready phase and after intro */}
        {(introDone || introPhase === 'ready') && (
          <div className="floating-search-wrapper visible">
            <SearchBar
              searchValue={searchValue}
              onSearchValueChange={setSearchValue}
              onSelectLocation={handleSelectFromSearch}
            />
          </div>
        )}

        {analysisError && <div className="analysis-error">{analysisError}</div>}

        {/* ── TWO ACTION BUTTONS — appear after selecting a locality ── */}
        {selectedLocation && !analysisResult && introDone && (
          <div className="action-buttons-bar">
            <button
              type="button"
              className="action-btn action-btn--predict"
              onClick={handleOpenPredict}
            >
              Predict Price 🏠
            </button>
            <button
              type="button"
              className="action-btn action-btn--analyze"
              onClick={handleAnalyze}
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

      {/* ── DASHBOARD PANEL ── */}
      <div
        className={`dashboard-shell ${panelOpen ? 'open' : ''}`}
        style={panelOpen ? { width: panelWidth } : undefined}
      >
        <div className="resize-handle" onMouseDown={handleMouseDown} />
        {analysisResult && <DashboardPanel result={analysisResult} onClose={handleClosePanel} />}
      </div>

      {/* ── PRICE PREDICTION MODAL ── */}
      {showPredictionModal && (
        <PricePredictionModal
          onClose={handleClosePredictionModal}
          onLocalitySelect={handlePredictionLocalitySelect}
          onViewInsights={(location) => { handleClosePredictionModal(); handleAnalyze(location); }}
        />
      )}
    </main>
  )
}