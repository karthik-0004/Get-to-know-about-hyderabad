import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Fully controlled SearchBar with two-way sync.
 *
 *  Props:
 *   - searchValue (string)   — display text, set by parent (e.g. after reverse-geocode)
 *   - onSearchValueChange(v) — parent must update its searchValue state
 *   - onSelectLocation({ lat, lng, address }) — called when user picks a suggestion
 */
export default function SearchBar({ searchValue, onSearchValueChange, onSelectLocation }) {
  const [predictions, setPredictions] = useState([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1) // keyboard highlight index
  const serviceRef = useRef(null)
  const placesServiceRef = useRef(null)
  const sessionTokenRef = useRef(null)
  const wrapperRef = useRef(null)
  const inputRef = useRef(null)

  /* ── Lazy-init services ── */
  const getAutocompleteService = useCallback(() => {
    if (!serviceRef.current && window.google?.maps?.places) {
      serviceRef.current = new window.google.maps.places.AutocompleteService()
    }
    return serviceRef.current
  }, [])

  const getPlacesService = useCallback(() => {
    if (!placesServiceRef.current && window.google?.maps?.places) {
      // PlacesService needs a DOM node or map; a hidden div works fine
      const div = document.createElement('div')
      placesServiceRef.current = new window.google.maps.places.PlacesService(div)
    }
    return placesServiceRef.current
  }, [])

  const getSessionToken = useCallback(() => {
    if (!sessionTokenRef.current && window.google?.maps?.places) {
      sessionTokenRef.current = new window.google.maps.places.AutocompleteSessionToken()
    }
    return sessionTokenRef.current
  }, [])

  const resetSessionToken = useCallback(() => {
    if (window.google?.maps?.places) {
      sessionTokenRef.current = new window.google.maps.places.AutocompleteSessionToken()
    }
  }, [])

  /* ── Reset active index when predictions change ── */
  useEffect(() => {
    setActiveIndex(-1)
  }, [predictions])

  /* ── Fetch predictions when user types ── */
  useEffect(() => {
    const svc = getAutocompleteService()
    if (!svc || !searchValue || searchValue.length < 2) {
      setPredictions([])
      return
    }

    const token = getSessionToken()

    svc.getPlacePredictions(
      {
        input: searchValue,
        sessionToken: token,
        componentRestrictions: { country: 'in' },
      },
      (results, status) => {
        if (status === window.google.maps.places.PlacesServiceStatus.OK && results) {
          setPredictions(results.slice(0, 5))
        } else {
          setPredictions([])
        }
      },
    )
  }, [searchValue, getAutocompleteService, getSessionToken])

  /* ── When user picks a suggestion ── */
  const handleSelect = useCallback(
    (prediction) => {
      const pSvc = getPlacesService()
      if (!pSvc) return

      pSvc.getDetails(
        {
          placeId: prediction.place_id,
          fields: ['geometry', 'formatted_address', 'name'],
          sessionToken: getSessionToken(),
        },
        (place, status) => {
          if (status !== window.google.maps.places.PlacesServiceStatus.OK || !place?.geometry?.location) return

          const lat = place.geometry.location.lat()
          const lng = place.geometry.location.lng()
          const address = place.formatted_address || place.name || prediction.description

          // Extract viewport bounds (fallback) + name for Nominatim boundary lookup
          const viewport = place.geometry.viewport || null
          const name = place.name || prediction.description

          onSearchValueChange(address)
          onSelectLocation({ lat, lng, address, viewport, name })
          setPredictions([])
          setShowDropdown(false)
          resetSessionToken()
        },
      )
    },
    [getPlacesService, getSessionToken, resetSessionToken, onSelectLocation, onSearchValueChange],
  )

  /* ── Close dropdown when clicking outside ── */
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  /* ── Clear input ── */
  const handleClear = useCallback(() => {
    onSearchValueChange('')
    setPredictions([])
    setShowDropdown(false)
    setActiveIndex(-1)
    if (inputRef.current) inputRef.current.focus()
  }, [onSearchValueChange])

  /* ── Keyboard navigation ── */
  const handleKeyDown = useCallback(
    (e) => {
      if (!showDropdown || predictions.length === 0) return

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setActiveIndex((prev) => (prev < predictions.length - 1 ? prev + 1 : 0))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setActiveIndex((prev) => (prev > 0 ? prev - 1 : predictions.length - 1))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        if (activeIndex >= 0 && activeIndex < predictions.length) {
          handleSelect(predictions[activeIndex])
        }
      } else if (e.key === 'Escape') {
        setShowDropdown(false)
        setActiveIndex(-1)
      }
    },
    [showDropdown, predictions, activeIndex, handleSelect],
  )

  return (
    <div className="floating-search" ref={wrapperRef}>
      <div className="search-input-wrapper">
        <input
          ref={inputRef}
          type="text"
          className="search-input"
          placeholder="Search a place in Hyderabad"
          value={searchValue}
          onChange={(e) => {
            onSearchValueChange(e.target.value)
            setShowDropdown(true)
          }}
          onFocus={() => {
            if (predictions.length > 0) setShowDropdown(true)
          }}
          onKeyDown={handleKeyDown}
        />
        {searchValue && (
          <button
            type="button"
            className="search-clear-btn"
            onClick={handleClear}
            aria-label="Clear search"
          >
            ×
          </button>
        )}
      </div>

      {showDropdown && predictions.length > 0 && (
        <ul className="suggestions-list" role="listbox">
          {predictions.map((p, i) => (
            <li key={p.place_id} role="option" aria-selected={i === activeIndex}>
              <button
                type="button"
                className={`suggestion-item${i === activeIndex ? ' suggestion-item--active' : ''}`}
                onClick={() => handleSelect(p)}
                onMouseEnter={() => setActiveIndex(i)}
              >
                {p.description}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}