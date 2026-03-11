import { useEffect, useState } from 'react'
import './ClimateCard.css'

const WMO_CODES = {
  0: { icon: '☀️', label: 'Clear sky' },
  1: { icon: '🌤️', label: 'Mainly clear' },
  2: { icon: '⛅', label: 'Partly cloudy' },
  3: { icon: '☁️', label: 'Overcast' },
  45: { icon: '🌫️', label: 'Foggy' },
  48: { icon: '🌫️', label: 'Rime fog' },
  51: { icon: '🌦️', label: 'Light drizzle' },
  53: { icon: '🌦️', label: 'Drizzle' },
  55: { icon: '🌧️', label: 'Heavy drizzle' },
  61: { icon: '🌧️', label: 'Light rain' },
  63: { icon: '🌧️', label: 'Rain' },
  65: { icon: '🌧️', label: 'Heavy rain' },
  71: { icon: '❄️', label: 'Light snow' },
  73: { icon: '❄️', label: 'Snow' },
  75: { icon: '❄️', label: 'Heavy snow' },
  80: { icon: '🌦️', label: 'Rain showers' },
  81: { icon: '🌧️', label: 'Moderate showers' },
  82: { icon: '⛈️', label: 'Heavy showers' },
  95: { icon: '⛈️', label: 'Thunderstorm' },
  96: { icon: '⛈️', label: 'Thunderstorm + hail' },
  99: { icon: '⛈️', label: 'Severe thunderstorm' },
}

export default function ClimateCard({ lat, lng }) {
  const [weather, setWeather] = useState(null)
  const [weatherLoading, setWeatherLoading] = useState(false)

  useEffect(() => {
    if (lat == null || lng == null) return
    setWeatherLoading(true)
    const ctrl = new AbortController()

    fetch(
      `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lng}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m`,
      { signal: ctrl.signal }
    )
      .then((r) => r.json())
      .then((data) => {
        if (data.current) {
          setWeather(data.current)
        }
        setWeatherLoading(false)
      })
      .catch(() => setWeatherLoading(false))

    return () => ctrl.abort()
  }, [lat, lng])

  const wmo = WMO_CODES[weather?.weather_code] || { icon: '🌡️', label: 'Unknown' }

  return (
    <div className="climate-card">
      {weatherLoading || !weather ? (
        <div className="climate-card__loading">Loading weather…</div>
      ) : (
        <div className="climate-card__weather">
          <div className="climate-card__weather-header">
            <h4 className="climate-card__weather-title">Climate Now</h4>
            <span className="climate-card__weather-icon">{wmo.icon}</span>
          </div>
          <div className="climate-card__temp">{Math.round(weather.temperature_2m)}°C</div>
          <div className="climate-card__condition">{wmo.label}</div>
          <div className="climate-card__details">
            <div className="climate-card__detail">
              <span className="climate-card__detail-value">{weather.relative_humidity_2m}%</span>
              <span className="climate-card__detail-label">Humidity</span>
            </div>
            <div className="climate-card__detail">
              <span className="climate-card__detail-value">{weather.wind_speed_10m} km/h</span>
              <span className="climate-card__detail-label">Wind</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
