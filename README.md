# Find Your Place - Hyderabad Real Estate Predictor

**Find Your Place** is a comprehensive real estate price and rental prediction platform specifically tailored for Hyderabad, India. The application leverages Machine Learning, geographical data enrichment, and an AI-powered fallback mechanism (using Groq's LLaMA engine) to provide users with accurate real estate pricing and locality insights.

## 📌 Features

- **Property Purchase Prediction:** Estimate prices for Apartments, Villas, Independent Houses, and Plots based on size (sqft), BHK, and locality.
- **Rental Price Estimate:** Estimate monthly rent for different property types in Hyderabad, factoring in furnishing status and size.
- **AI Fallback System:** Uses the Groq Cloud API (LLaMA 3) to generate dynamic estimates when a locality is not present in the historical ML models.
- **Locality Enrichment:** Uses OpenStreetMap (`osmnx`) and `geopy` to generate geographic features for a locality (e.g., nearest Metro, IT Hub distance, count of hospitals, parks, schools).
- **Interactive UI:** A modern web interface built with React, Vite, and Leaflet Maps for visualizing real estate data.
- **Authentication:** Integrated Google OAuth for secure user login.

## 🧠 How Predictions Work (Under the Hood)

When a user submits a query on the frontend for a property purchase or rental estimate, a multi-tiered prediction funnel is triggered to ensure they always get a realistic value:

1. **User Input Gathering:**
   - The user inputs the `Locality`, `Property Type` (Apartment, Villa, Plot, etc.), `BHK`, and `Sqft` area via the React UI.
   - The frontend sends a JSON payload to the Django REST API (`/api/predict/` or `/api/predict/rent/`).

2. **Input Validation:**
   - Django validates the input, ensuring parameters like `sqft` are logically correct and making sure `BHK` is provided if the property is a house or apartment.

3. **Tiered Prediction Engine (`views.py`):**
   - **Tier 1 (Primary Model):** The system first checks if a specialized ML model (`.pkl` file) exists for the requested property type (e.g., `apartment_model.pkl`). If the model exists and the entered `Locality` is part of its training data vocabulary, it computes the feature vector (Target Encoding, Min/Max/Avg Sqft prices) and generates a prediction using the trained Scikit-Learn model.
   - **Tier 2 (Backup Model):** If the `Locality` is absent from the primary model's vocabulary but exists in a generalized `backup_model` (trained on a broader dataset), the system routes the request to the backup model to generate a safe estimate.
   - **Tier 3 (AI Fallback via Groq LLaMA):** If the locality is completely new or extremely niche and not found in any historical ML data, the system gracefully falls back to a generative AI layer. It constructs a dynamic prompt containing the property stats and queries the **Groq LLaMA 3.3-70B model**. The LLM acts as an expert Hyderabad real estate agent and returns an up-to-date market estimate in INR.
   - **Tier 4 (Ultimate Fallback):** If the Groq API fails to parse or timeout occurs, the system uses the backup ML model populated with median city-wide statistical numbers to ensure the app never crashes.

4. **Response Delivery:**
   - Logarithmic predictions from ML models are converted back to real-world INR values using `np.expm1`.
   - A JSON response containing the final `predicted_price` (or `predicted_rent`), the name of the `model_used`, and whether the `locality_found` boolean flag was triggered, is sent back to the frontend.

5. **UI Rendering:**
   - The React frontend displays the estimated price beautifully to the user, alongside contextual map boundaries and locality stats.

---

## 🏗️ Project Architecture & Structure

```text
find_your_place/
│
├── backend/                       # Django Backend
│   ├── prediction/                # Core ML inference and API views
│   │   ├── ml_models/             # Serialized joblib models (.pkl)
│   │   ├── train_models.py        # ML training script for purchase prices
│   │   ├── train_rental_models.py # ML training script for rental prices
│   │   └── views.py               # API endpoints (/api/predict/, /api/predict/rent/)
│   ├── requirements.txt           # Python dependencies
│   └── manage.py                  # Django core script
│
├── frontend/find_place/           # React + Vite Frontend
│   ├── src/                       # Source files (components, pages, assets)
│   ├── package.json               # Node.js dependencies
│   └── vite.config.js             # Vite configuration
│
├── scrapped_data/                 # Raw datasets (apartments, villas, plots, rent)
├── find your place datasets/      # Additional processed dataset files
│
├── locality_enrichment.py         # Script to mine geographical POI data via OSM/Geopy
├── crime_score.py                 # Script to compute locality crime risk
├── future_growth_score.py         # Script to compute locality future growth potential
├── merge_master_dataset.py        # Merges all locality metrics into 'master_locality_data.csv'
└── *_.csv                         # Multiple output CSV datasets
```

---

## 🚀 Technologies Used

### Frontend
* **React 19 & Vite:** Fast UI framework and build tool.
* **React Router:** For seamless single-page application navigation.
* **Leaflet & React-Leaflet:** For interactive maps.
* **Google Maps API:** Used for advanced mapping features and places search.
* **Google OAuth:** `@react-oauth/google` for identity mapping.

### Backend
* **Django:** Robust Python web framework handling the API requests.
* **Scikit-Learn & Joblib:** Used to train and serialize Machine Learning models.
* **Pandas & NumPy:** For data wrangling, preprocessing, and ML feature creation.
* **Groq SDK (LLaMA):** Used as an intelligent fallback to predict real estate numbers for missing localities.

### Data Engineering
* **OSMnx & Geopy:** To extract real-world coordinates and calculate distances to IT corridors and Metro Stations.

---

## 📊 Data Pipeline

1. **Scraping**: Raw data is fetched and stored in Excel/CSV formats under `scrapped_data/`.
2. **Geographical Enrichment**: 
   - `locality_enrichment.py` pulls POIs (hospitals, malls, etc.) from OSM for a defined set of localities.
   - Outputs a core `locality_features.csv`.
3. **Scoring Systems**:
   - `crime_score.py` builds the crime risk indexes.
   - `future_growth_score.py` aggregates data reflecting infrastructure growth.
4. **Merge Matrix**:
   - `merge_master_dataset.py` joins everything together into `master_locality_data.csv`.
5. **Model Training**:
   - `backend/prediction/train_models.py` uses this data to map predictions.

---

## 🛠️ Setup & Installation

### 1. Pre-requisites
* Python 3.9+ 
* Node.js v18+ & npm 
* A Groq API Key (for the AI fallback)

### 2. Backend Setup
Navigate into the backend folder, create a virtual environment, and install requirements:

```bash
cd backend
python -m venv env
source env/bin/activate  # On Windows use: env\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file inside the `backend/` directory:
```env
GROQ_API_KEY=your_groq_api_key_here
```

Run the Django server:
```bash
python manage.py runserver
```
The API is now running at `http://localhost:8000/`.

### 3. Frontend Setup
Navigate into the React frontend directory:

```bash
cd frontend/find_place
npm install
```

Optionally, setup `.env` for the React app with your Google Client ID and Google Maps API Keys (if configured):
```env
VITE_GOOGLE_MAPS_API_KEY=your_maps_key
VITE_GOOGLE_CLIENT_ID=your_oauth_client_id
```

Run the development server:
```bash
npm run dev
```
Access the application on the local port defined by Vite (usually `http://localhost:5173/`).

---

## 🎯 Model Training

To retrain the Machine Learning models (for example, if you introduce new data in `scrapped_data`), navigate to `backend/prediction/` and execute the training scripts:

```bash
python train_models.py
python train_rental_models.py
```
This updates the `.pkl` models located in `backend/prediction/ml_models/`.
