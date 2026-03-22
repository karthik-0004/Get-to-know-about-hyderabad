# Find Your Place - Hyderabad Real Estate Intelligence Platform

**Find Your Place** is an advanced real estate price prediction, locality analysis, and market intelligence platform exclusively tailored for Hyderabad, India. It combines Machine Learning, Live Geo-Spatial Analytics (Google Places + OpenStreetMap), and a Generative AI fallback (Groq's LLaMA 3.3) to provide accurate real estate prices and rich neighborhood insights.

---

## 📌 Key Features

- **Property Purchase & Rent Prediction:** Advanced ML models to estimate prices and rents for Apartments, Villas, Independent Houses, and Plots based on dimensions, BHK, and locality.
- **Deep Locality Analysis (Live Area Analytics):** Dynamic mapping of nearby amenities (hospitals, schools, malls, parks), IT hubs, and metro stations. Uses parallel concurrent requests to **Google Places API** and **OpenStreetMap (Overpass API)** for real-time locality scoring.
- **Market Pulse & Nearby Listings:** Provides the average price-per-square-foot for a specific area (sourced via ML data or AI fallback) and displays recent real property listings extracted from datasets.
- **Multi-Tiered AI Fallback System:** When a locality is entirely unknown to the ML models, the system prompts **Groq Cloud (LLaMA 3.3-70B)** to act as an expert local real-estate agent, synthesizing realistic estimates on the fly.
- **API Cost Management:** Includes a robust, file-based daily API usage counter to throttle expensive Google Places API calls, gracefully degrading the frontend UI instead of breaking it when limits are reached.
- **Interactive UI & Authentication:** A modern React + Vite dashboard utilizing Leaflet Maps for geometric visualizations, integrated with Google OAuth for secure, seamless login.

---

## 🧠 Core Systems & Engines

### 1. The Prediction Engine (`backend/prediction/views.py`)
Triggered when a user requests a price or rent estimate:
* **Tier 1 (Targeted ML):** Looks up a highly specialized, serialized `.pkl` Scikit-Learn model for the exact property type (e.g., `apartment_model.pkl`).
* **Tier 2 (General ML Backup):** If the locality isn't present in the targeted model, it routes to a generalized cross-property backup model.
* **Tier 3 (Generative AI):** If the location is obscure, it constructs a prompt containing the property stats and queries the LLM to fetch a market estimate.
* **Tier 4 (Ultimate Fallback):** Uses city-wide statistical medians if the AI API times out, ensuring zero application crashes.

### 2. Live Geo-Enrichment (`backend/mysite/api_views.py` & `locality_service.py`)
Triggered when a user explores a specific area on the map:
* **Parallel Execution:** Dispatches simultaneous threads to Google Places (for exact POI details and photos) and Overpass API (for high-speed amenity counts and road density).
* **Caching & Fallback:** Implements an LRU cache for rapid, repeated neighborhood clicks. It also calculates local geometric distances (Haversine distance to hardcoded Metro Stations and IT Hubs) to provide uninterrupted scores even if external servers fail.
* **Secure Media Proxying:** Fetches Google Place photos via a server-side proxy to ensure API keys are never leaked to the client.

### 3. Offline Data Engineering (`locality_enrichment.py` & others)
* Behind the scenes, scripts like `locality_enrichment.py` and `crime_score.py` mine OpenStreetMap (via `OSMnx`) and calculate structural features, merging everything into comprehensive datasets (`master_locality_data.csv`) that feed the ML models during training.

---

## 🏗️ Architecture & Project Structure

```text
find_your_place/
│
├── backend/                       # Django Backend
│   ├── mysite/                    # Main API routing, Live Area Analytics, Auth & Rate Limiting
│   │   ├── api_views.py           # Core views: Market pulse, Area analysis, Nearby listings
│   │   ├── auth_views.py          # Google OAuth handling
│   │   ├── locality_service.py    # Overpass API / OSM integrations and Geometric scoring
│   │   └── usage_counter.py       # API rate limit controller
│   ├── prediction/                # Core ML inference engine
│   │   ├── ml_models/             # Serialized joblib models (.pkl)
│   │   ├── train_models.py        # ML training script for purchase prices
│   │   └── views.py               # Tiered ML vs AI prediction endpoints
│   ├── requirements.txt           # Python backend dependencies
│   └── manage.py                  # Django core script
│
├── frontend/find_place/           # React + Vite Frontend Application
│   ├── src/
│   │   ├── components/            # UI components (AreaPanel, UsageBadge, PredictPriceModal)
│   │   ├── pages/                 # Full view routing (HyderabadMapPage, Dashboard)
│   │   └── services/              # API caller definitions
│   └── package.json               # Node.js dependencies
│
├── scrapped_data/                 # Raw datasets & XLSX files used for Nearby Listings mapping
├── find your place datasets/      # Cleaned and engineered CSV datasets
│
├── locality_enrichment.py         # Batch OSM data extraction script
├── crime_score.py                 # Script to compute locality crime risk
├── future_growth_score.py         # Script to compute future infrastructure growth index
└── merge_master_dataset.py        # Dataset aggregation script
```

---

## 🚀 Technologies Used

### Frontend
* **React 19 & Vite** (Fast application bundling)
* **React Leaflet & Google Maps API** (Maps, clustering, and visual overlays)
* **React Router** (Navigation)
* **Google OAuth (`@react-oauth/google`)** (Authentication)

### Backend
* **Django** (Robust Python web framework handling complex API tasks)
* **Scikit-Learn, Pandas, Joblib** (Data engineering and Machine Learning)
* **Groq SDK** (Integretion with LLaMA 3.3 for the generative fallback)
* **Concurrent Futures** (Thread pooling for faster map API responses)
* **SQLite** (Default database for user tracking)

### Geo-Spatial Processing
* **OpenStreetMap & Overpass API**
* **Google Places API**
* **OSMnx & Geopy**

---

## 🛠️ Setup & Installation

### 1. Prerequisites
* Python 3.9+ 
* Node.js v18+ & npm 
* **API Keys Required:**
  * Groq API Key (for the fallback AI predicting)
  * Google Maps / Places API Key (for frontend maps and backend area analysis)
  * Google OAuth Client ID (for user logins)

### 2. Backend Setup

1. Navigate to the backend folder and create a virtual environment:
   ```bash
   cd backend
   python -m venv env
   ```
2. Activate the environment:
   * **Windows:** `env\Scripts\activate`
   * **Mac/Linux:** `source env/bin/activate`
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file inside `backend/`:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   GOOGLE_PLACES_API_KEY=your_google_maps_key_here
   ```
5. Apply database migrations and start the server:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```
   The backend API operates at `http://localhost:8000/`.

### 3. Frontend Setup

1. Navigate to the React frontend folder:
   ```bash
   cd "frontend/find_place"
   ```
2. Install Node dependencies:
   ```bash
   npm install
   ```
3. Create a `.env` file in the frontend directory:
   ```env
   VITE_GOOGLE_MAPS_API_KEY=your_maps_key_here
   VITE_GOOGLE_CLIENT_ID=your_oauth_client_id_here
   ```
4. Start the Vite development server:
   ```bash
   npm run dev
   ```
   The application will be accessible at `http://localhost:5173/`.

---

## 🎯 Model Retraining Process

If you supply new property data into `scrapped_data/` and want to retrain the ML engines:
1. Ensure your terminal is at the project root and your Python `env` is activated.
2. Rebuild the master dataset: 
   ```bash
   python merge_master_dataset.py
   ```
3. Navigate to the prediction module and execute the training scripts:
   ```bash
   cd backend/prediction
   python train_models.py
   python train_rental_models.py
   ```
   This updates the `.pkl` binary files inside `backend/prediction/ml_models/`.
