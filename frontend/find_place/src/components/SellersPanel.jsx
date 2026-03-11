const PLATFORMS = [
  {
    name: 'Housing.com',
    logo: 'https://www.google.com/s2/favicons?domain=housing.com&sz=64',
    color: '#e8384f',
    buildUrl: (locality) => {
      const slug = locality.toLowerCase().replace(/\s+/g, '-')
      return `https://housing.com/in/buy/hyderabad/${slug}`
    },
    description: 'Premium listings with verified photos',
  },
  {
    name: '99acres',
    logo: 'https://www.google.com/s2/favicons?domain=99acres.com&sz=64',
    color: '#1a73e8',
    buildUrl: (locality) => {
      const slug = locality.toLowerCase().replace(/\s+/g, '-')
      return `https://www.99acres.com/property-in-${slug}-hyderabad-ffid?city=21&preference=S&area_unit=1&res_com=R`
    },
    description: "India's largest property marketplace",
  },
  {
    name: 'MagicBricks',
    logo: 'https://www.google.com/s2/favicons?domain=magicbricks.com&sz=64',
    color: '#e2473b',
    buildUrl: (locality) =>
      `https://www.magicbricks.com/property-for-sale/residential-real-estate?bedroom=2,3&proptype=Multistorey-Apartment,Builder-Floor-Apartment,Penthouse,Studio-Apartment,Residential-House,Villa&Locality=${encodeURIComponent(locality)}&cityName=Hyderabad`,
    description: 'Trusted property search platform',
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
