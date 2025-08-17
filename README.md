# EVAT - Electric Vehicle Adoption Tools

A conversational AI chatbot designed to help electric vehicle users find charging stations and get relevant information using Rasa framework.

## 🚀 Features

- **Location-based charging station finder**
- **Real-time traffic-aware routing**
- **Charging station filtering by preferences**
- **Detailed station information and availability**
- **Machine learning-powered ETA predictions**
- **Web-based chat interface**

## 📁 Project Structure

```
evat-chatbot/
├── rasa/                 # Rasa chatbot configuration
│   ├── domain.yml       # Intent, entity, and action definitions
│   ├── config.yml       # NLU pipeline and policy configuration
│   ├── endpoints.yml    # API endpoints
│   ├── credentials.yml  # Authentication settings
│   ├── actions/         # Custom action implementations
│   └── data/           # Training data (intents, stories, rules)
├── backend/            # Core business logic
│   ├── find_station.py # Location and routing services
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
├── .gitignore        # Git ignore rules
└── env.example       # Environment template
```
