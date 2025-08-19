# EVAT - Electric Vehicle Adoption Tools

A conversational AI chatbot designed to help electric vehicle users find charging stations and get relevant information using Rasa framework.

## 🚀 Features

- **Location-based charging station finder**
- **Real-time traffic-aware routing**
- **Charging station filtering by preferences**
- **Detailed station information**
- **Web-based chat interface**
- Planned: **live connector availability**, **ML-powered ETA**

## 📁 Project Structure

```
EVAT_Chatbot/
├── rasa/                 # Rasa chatbot configuration
│   ├── domain.yml       # Intent, entity, and action definitions
│   ├── config.yml       # NLU pipeline and policy configuration
│   ├── endpoints.yml    # API endpoints
│   ├── credentials.yml  # Authentication settings
│   ├── actions/         # Custom action implementations
│   └── data/           # Training data (intents, stories, rules)
├── backend/            # Core business logic
│   ├── real_time_apis.py # TomTom client used by actions
│   └── utils/          # Utility functions
├── frontend/           # Web interface
│   ├── index.html      # Main chat interface
│   ├── script.js       # Frontend logic
│   └── style.css       # Styling
├── data/              # Datasets
│   └── raw/           # CSV files (charging stations, coordinates)
├── ml/                # Machine learning models
│   ├── classification.py # Station classification
│   ├── regression.py    # ETA prediction
│   └── README.md       # ML documentation
├── config/            # Configuration files
├── README.md          # Project overview
├── requirements.txt   # Dependencies
└── .gitignore        # Git ignore rules
```

## 🧩 How to use the chatbot (local setup)

### Quick setup
```bash
cd EVAT_Chatbot
python -m venv rasa_env && source rasa_env/bin/activate
pip install -r requirements.txt
cd rasa && rasa train

Tab 1: rasa run actions --port 5055
Tab 2: rasa run --enable-api --cors "*"
Open frontend/index.html (or serve frontend/ via python -m http.server 8080)
```

### Open the web chat
- Open `frontend/index.html` in your browser. It posts to `http://localhost:5005/webhooks/rest/webhook`.
- Ensure the Rasa server was started with `--cors "*"` so the browser can call it.


```bash
cd frontend
python -m http.server 8080
# open http://localhost:8080
```

### Interact (3 flows)
- Route planning: `1` → `from Carlton to Geelong` → `get_directions pls` → `get_traffic_info`
- Emergency charging: `2` → `Richmond` → type a station name → `get directions pls`
- Preferences: `3` → `fastest` (or `cheapest`/`premium`) → `Melbourne` → type a station name

### How it works
- Locations resolve from CSV names to coordinates; if a name isn’t in the CSV, you’ll be asked to try another.
- TomTom provides real-time distance/ETA/traffic when both start and destination coords exist.
- The frontend is wired to Rasa REST and also sends browser geolocation (`lat`, `lon`) as metadata; actions currently do not use this metadata yet.

### Real-time TomTom
Handled via `backend/real_time_apis.py` (used by Rasa actions)


## 🖥️ Frontend (current state)
- The chat UI in `frontend/` is already wired to the Rasa REST webhook.
- It sends `lat`/`lon` from the browser as `metadata` with each message.

- Limitations today:
  - Actions do not yet use the `metadata.lat/lon` to improve results.
  - Plain text rendering only (no quick-reply buttons or cards yet).
  - Live availability is not implemented.

## 📍 Data sources used
- `data/raw/Co-ordinates.csv` for suburb coordinates
- `data/raw/charger_info_mel.csv` for stations

## 🔄 Real-time readiness
- **Done**:
  - Key in `.env`(`TOMTOM_API_KEY`) used by backend
  - Real-time routing + traffic via TomTom (CSV-backed locations)
  - Frontend wired via REST; or use Rasa shell
- **How it works now**:
  - Names (start/end) resolve to coordinates via CSV only; then TomTom provides route/traffic
  - Frontend sends metadata lat/lon, but actions currently resolve start/end from CSV
- **Gaps**:
  - Start from user location (metadata lat/lon) not yet used by actions
  - Stations are CSV-based (no TomTom station search or availability yet)
  - Dataset: missing/null values; some station names/addresses inconsistent
  - Matching: station lookup is strict; fuzzy matching can be added for better tolerance
- **Next**:
1) Use browser lat/lon (metadata) as start coords; keep CSV for names.
2) Add along-route/nearby station search (TomTom) as fallback when CSV returns no results.
3) Add live availability (new API) and fold into ranking.
4) Add fuzzy matching + CSV cleanup.
5) Frontend: UI enhancements and interactivity — quick-reply buttons (send payloads), clickable options, station “cards” with details and CTAs (Get directions, Show traffic)...
6) Optional: incorporate ML ranking/ETA once wired into actions.

