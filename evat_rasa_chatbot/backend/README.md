# EV Charging Station Finder – Backend Module 🔌

This Python module helps find the **closest available EV charging station** based on the user’s current location using **TomTom APIs**.

---

## What This Does

- Finds **nearby charging stations** (using coordinates).
- Checks **real-time availability** of chargers.
- Calculates **distance** and **ETA**.
- (Optional) Returns **turn-by-turn instructions** and **full routing data** for frontend use.

---

## How to Use

1. **Location format**:  
   The input location must be in this format:  
   ```python
   USER_LOCATION = (longitude, latitude)
   ```

2. **Call the function**:  
   In your Python script, simply call:

   ```python
   from find_station import find_station

   result = find_station(USER_LOCATION)
   ```

   By default it does not return Navigation Instrcutions and Raw JSON
   To include those, or for using your own API key you can add one or all of these options:

   ```python
   result = find_station(USER_LOCATION, TOMTOM_API_KEY="your_api_key", INCLUDE_NAVIGATION=True, RETURN_FULL_JSON=True)
   ```

4. **What it returns**:
   ```python
   {
       "Name": "Station Name",
       "Location": (longitude, latitude),
       "Address": "Full address",
       "Distance": 4.3,  # in km
       "ETA": 8.1,       # in minutes
       "Instructions": [ ... ]  # Only if INCLUDE_NAVIGATION=True
   }
   ```

5. **Full route JSON** (optional):  
   Set `RETURN_FULL_JSON=True` if the frontend needs raw routing data.

---

## Important Notes

- TomTom expects location as **(longitude, latitude)** — not the usual (lat, lon).
- If no station is available nearby, it tries again by expanding the search.
- The code avoids unnecessary API calls by limiting the number of iterations.

---

## For Frontend Teammates

You’ll get all the data you need from the output dict. Just call the function, pass the current user location, and render the output as needed.

## Further uses

You can also use the individual functions in the module if needed as follows

```python

   get_nearby_stations(user_location, <optional> NUMBER_OF_RESULTS=x)
   # returns a specified number of nearest charging stations as a json response, default = 5

   get_route_details(user_location, destination)
   # returns route in the following format
   # {
   #    "distance_km": distance_km,
   #    "eta_minutes": eta_minutes,
   #    "instructions": instructions,
   #    "full_json": data
   # }

   get_charging_station_availability(station_id)
   # returns number of available chargers at the specified charging station
   # the station_id needed for this can only be retreived from TomTom's nearby search API

```

## APIs used

Search API: https://developer.tomtom.com/search-api/api-explorer
Availability API: https://developer.tomtom.com/ev-charging-stations-availability-api/api-explorer
Routing API: https://developer.tomtom.com/routing-api/api-explorer

