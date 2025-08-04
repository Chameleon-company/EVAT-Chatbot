# EV Charging Trip Prediction using Machine Learning

This project applies supervised machine learning models to predict electric vehicle (EV) charging trip characteristics, including estimated time of arrival (ETA) and the destination charging station.

## Dataset
`ml_ev_charging_dataset.csv`

Features include:
- Geospatial coordinates (vehicle and station)
- Categorical station identifiers
- Calculated Haversine distances

---

##  Project Objectives

1. **Regression** – Predict ETA (in minutes) using geospatial and categorical features.
2. **Binary Classification** – Categorize ETA as `Short` (≤ 5 min) or `Long`.
3. **Multi-Class Classification** – Predict the specific EV charging `Station_Name`.

---


