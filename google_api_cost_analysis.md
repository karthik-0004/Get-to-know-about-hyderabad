# Google API Cost Analysis for "Find Your Place"

Based on the codebase analysis, your application heavily relies on the **Google Maps Platform**. Google provides a **$200 monthly recurring credit** for Maps APIs, effectively making a certain volume of requests free.

Here is a detailed breakdown of the exact APIs your project uses, their costs, and how many times you can run your core application workflows before incurring charges.

---

## 1. APIs Used & Base Costs (per 1,000 requests)

1. **Places API (Legacy) - Nearby Search**: **$32.00** / 1,000 requests
2. **Places API - Photos**: **$7.00** / 1,000 requests
3. **Places API - Autocomplete (Session)**: **$17.00** / 1,000 sessions
4. **Maps JavaScript API (Dynamic Maps)**: **$7.00** / 1,000 map loads
5. **Geocoding API**: **$5.00** / 1,000 requests

---

## 2. Cost Per Action in Your Project

### **Action A: Analyzing an Area (The most expensive operation)**
When a point is selected on the map or searched, `analyzeArea` is called. In [backend/mysite/places_service.py](file:///c:/Users/3541/Desktop/find%20your%20place/backend/mysite/places_service.py), your application fires **9 concurrent Nearby Search requests** to find various amenities:
*   *Hospitals, Malls, Cinemas, Schools, Hotels, Restaurants, Bus Stops, Metro Stations, and Train Stations (9 total).*
*   **Cost**: 9 requests × $0.032 = **$0.288 per fetch**.

### **Action B: Map Interaction & Searching**
*   **Clicking the Map**: Triggers a Reverse Geocode (`$0.005`).
*   **Searching via Bar**: Triggers an Autocomplete Session (`$0.017`).
*   **Loading the Map**: Costs `$0.007` per page refresh/load.

### **Action C: Fetching Images (Place Photos)**
*   When the frontend requests photos for the amenities via `/api/place-photo/`, each unique photo fetched from Google costs **$0.007**.
*   *Assuming an average of 5 photos viewed per area: 5 × $0.007 = **$0.035**.*

---

## 3. Total Cost of a Single "Complete Workflow"

Let's look at one standard user flow:
1. User loads the map page: `$0.007`
2. User searches a location (Autocomplete): `$0.017`
3. The app auto-analyzes the area (9 Nearby searches): `$0.288`
4. The user views ~5 photos of places: `$0.035`

**Total Estimated Cost per full interaction**: `~ $0.347`
**(If no photos are viewed / no autocomplete used)**: `~ $0.300` (Map Load + Map Click + 9 Searches)

---

## 4. The Magic Numbers: How many fetches can you make?

To stay within the **$200 monthly free tier**, and assuming your primary cost driver is the **"Analyze Area"** function (the 9 concurrent requests):

### If we assume a conservative **$0.33 per complete analysis** (including map loads, clicks, some photos):
*   **Monthly Fetch Limit:** `$200 ÷ $0.33` ≈ **606 area analyses per month**
*   **Daily Fetch Limit:** `606 ÷ 30 days` ≈ **20 area analyses per day**

### If we calculate purely based on the raw [analyze_area](file:///c:/Users/3541/Desktop/find%20your%20place/backend/mysite/places_service.py#372-391) background fetches (9 Nearby Searches = $0.288):
*   **Monthly Fetch Limit:** `$200 ÷ $0.288` ≈ **694 area analyses per month**
*   **Daily Fetch Limit:** `694 ÷ 30 days` ≈ **23 area analyses per day**

---
## 💡 Cost Saving Recommendations
1. **Reduce Categories**: Currently `_CATEGORY_CONFIG` has 8 categories plus 1 hardcoded train search. Removing just 2 non-critical categories (like Cinemas or Hotels) will reduce the cost from 9 to 7 searches (-$0.064 per fetch) and immediately boost your daily limit to **~30 fetches per day**.
2. **Caching**: If multiple users search the exact same location (or within slightly overlapping coordinates), cache the results in a database so you don't hit the Google Places API again. Your frontend currently maintains brief memory caching (`analysisCacheRef`), but a persistent backend cache would be significantly cheaper.
3. **Lazy Load Photos**: Ensure photos are only requested explicitly when a user clicks on an amenity, rather than pre-fetching them.
