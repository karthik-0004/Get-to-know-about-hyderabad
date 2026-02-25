import { useCallback, useState } from 'react'
import { useJsApiLoader } from '@react-google-maps/api'

import SearchBar from '../components/LocationSearch'
import MapView from '../components/MapView'
import DashboardPanel from '../components/DashboardPanel'
import useResizable from '../hooks/useResizable'
import { analyzeArea } from '../services/areaAnalysisApi'
import { fetchBoundaryByName, fetchBoundaryByCoords } from '../services/boundaryService'
import '../App.css'

const HYDERABAD_CENTER = { lat: 17.385, lng: 78.4867 }
const MAPS_LIBRARIES = ['places']

export default function HyderabadMapPage() {
  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY,
    libraries: MAPS_LIBRARIES,
  })

  /* ── Single source of truth ── */
  const [mapCenter, setMapCenter] = useState(HYDERABAD_CENTER)
  const [mapZoom, setMapZoom] = useState(13)
  const [selectedLocation, setSelectedLocation] = useState(null)
  const [searchValue, setSearchValue] = useState('')
  const [areaBoundary, setAreaBoundary] = useState(null) // { paths, bounds } | null

  /* ── Analysis state ── */
  const [analysisResult, setAnalysisResult] = useState(null)
  const [analysisError, setAnalysisError] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  /* ── Right-side resizable panel ── */
  const { width: panelWidth, handleMouseDown } = useResizable({
    defaultWidth: 420,
    minWidth: 350,
    maxWidth: 700,
  })
  const panelOpen = !!analysisResult

  /* ── Map click → reverse geocode → update search bar ── */
  const reverseGeocode = useCallback((lat, lng) => {
    const geocoder = new window.google.maps.Geocoder()

    geocoder.geocode({ location: { lat, lng } }, async (results, status) => {
      const topResult = status === 'OK' ? results?.[0] : null
      const address = topResult
        ? topResult.formatted_address
        : `Selected point (${lat.toFixed(5)}, ${lng.toFixed(5)})`

      setSelectedLocation({ lat, lng, address })
      setSearchValue(address)

      // Try real boundary polygon from Nominatim, fall back to viewport rect
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
      // Keep current zoom on click — don't snap to a fixed level
      setAnalysisError('')
      reverseGeocode(lat, lng)
    },
    [reverseGeocode],
  )

  /* ── Search bar selection → zoom into the selected address ── */
  const handleSelectFromSearch = useCallback(async (location) => {
    setMapCenter({ lat: location.lat, lng: location.lng })
    setSelectedLocation(location)
    setSearchValue(location.address || '')
    setAnalysisError('')

    // Try real boundary polygon from Nominatim
    const searchQuery = location.name || location.address || ''
    const boundary = await fetchBoundaryByName(searchQuery)
    if (boundary) {
      setAreaBoundary(boundary)
    } else if (location.viewport) {
      // Fallback to viewport rectangle
      setAreaBoundary({ paths: null, bounds: location.viewport })
      setMapZoom(16)
    } else {
      setAreaBoundary(null)
      setMapZoom(16)
    }
  }, [])

  /* ── Analyze action ── */
  const handleAnalyze = async () => {
    if (!selectedLocation) return

    setIsAnalyzing(true)
    setAnalysisError('')

    try {
      const response = await analyzeArea(selectedLocation)
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

  /* ── Loading / error states ── */
  if (loadError) {
    return (
      <div className="map-load-error">
        <p>Failed to load Google Maps.</p>
        <p>Please check your API key and try again.</p>
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
      {/* ── MAP (fills remaining space) ── */}
      <section className="map-container">
        <MapView
          center={mapCenter}
          zoom={mapZoom}
          markerPosition={selectedLocation}
          areaBoundary={areaBoundary}
          onMapClick={handleMapClick}
        />

        {/* Floating search overlaid on map */}
        <SearchBar
          searchValue={searchValue}
          onSearchValueChange={setSearchValue}
          onSelectLocation={handleSelectFromSearch}
        />

        {/* Error toast */}
        {analysisError ? (
          <div className="analysis-error">{analysisError}</div>
        ) : null}

        {/* Analyze button (only when no panel) */}
        {!analysisResult ? (
          <button
            type="button"
            className="analyze-button"
            onClick={handleAnalyze}
            disabled={!selectedLocation || isAnalyzing}
          >
            {isAnalyzing ? (
              <span className="analyze-loading">
                <span className="loading-dot" aria-hidden="true" />
                Analyzing…
              </span>
            ) : (
              'Analyze This Area'
            )}
          </button>
        ) : null}
      </section>

      {/* ── RIGHT-SIDE DASHBOARD PANEL ── */}
      <div
        className={`dashboard-shell ${panelOpen ? 'open' : ''}`}
        style={panelOpen ? { width: panelWidth } : undefined}
      >
        {/* Drag handle (left border) */}
        <div className="resize-handle" onMouseDown={handleMouseDown} />

        {analysisResult ? (
          <DashboardPanel result={analysisResult} onClose={handleClosePanel} />
        ) : null}
      </div>
    </main>
  )
}