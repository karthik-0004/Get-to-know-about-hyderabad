const PLATFORMS = [
  {
    name: 'Housing.com',
    logo: 'https://www.google.com/s2/favicons?domain=housing.com&sz=64',
    color: '#e8384f',
    buildUrl: (locality) =>
      `https://housing.com/in/buy/hyderabad/${locality.toLowerCase().replace(/\s+/g, '-')}`,
    description: 'Premium listings with verified photos',
  },
  {
    name: '99acres',
    logo: 'https://www.google.com/s2/favicons?domain=99acres.com&sz=64',
    color: '#1a73e8',
    buildUrl: (locality) =>
      `https://www.99acres.com/search/property/buy/residential/all/hyderabad?keyword=${encodeURIComponent(locality)}&preference=S&area_unit=1&budget_min=null&budget_max=null`,
    description: "India's largest property marketplace",
  },
  {
    name: 'NoBroker',
    logo: 'https://www.google.com/s2/favicons?domain=nobroker.in&sz=64',
    color: '#ff5a5f',
    buildUrl: (locality) => {
      const name = locality.charAt(0).toUpperCase() + locality.slice(1)
      return `https://www.nobroker.in/property/sale/hyderabad/${name}?searchParam=W3sibGF0IjoxNy4zODUsImxvbiI6NzguNDg2NywicGxhY2VOYW1lIjoiJHtuYW1lfSIsInNob3dNYXAiOmZhbHNlfV0=&radius=2.0&city=hyderabad&locality=${name}&isMetro=false`
    },
    description: 'Zero brokerage, direct from owners',
  },
]

export default function SellersPanel({ locality, onClose }) {
  const displayLocality = locality || 'Selected Area'

  return (
    <div className="sellers-panel">
      <div className="sellers-panel-header">
        <div>
          <h2 className="sellers-panel-title">Identify Sellers</h2>
          <p className="sellers-panel-subtitle">
            Properties in <strong>{displayLocality}</strong>
          </p>
        </div>
        <button
          type="button"
          className="dashboard-close"
          onClick={onClose}
          aria-label="Close"
        >
          ✕
        </button>
      </div>

      <div className="sellers-panel-body">
        <p className="sellers-panel-hint">
          Browse listings from top property portals for{' '}
          <strong>{displayLocality}, Hyderabad</strong>
        </p>

        <div className="sellers-cards">
          {PLATFORMS.map((p) => (
            <a
              key={p.name}
              href={p.buildUrl(displayLocality)}
              target="_blank"
              rel="noopener noreferrer"
              className="seller-card"
            >
              <img
                src={p.logo}
                alt={p.name}
                className="seller-card-logo"
              />
              <div className="seller-card-info">
                <h3 className="seller-card-name">{p.name}</h3>
                <p className="seller-card-desc">{p.description}</p>
              </div>
              <span className="seller-card-arrow">→</span>
            </a>
          ))}
        </div>

        <p className="sellers-panel-footer">
          Links open in a new tab with <strong>{displayLocality}</strong> pre-filled in search.
        </p>
      </div>
    </div>
  )
}
