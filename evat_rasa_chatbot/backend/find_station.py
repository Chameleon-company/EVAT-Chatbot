import requests
import os
from pymongo import MongoClient, errors
from math import radians, sin, cos, sqrt, atan2
from typing import Optional, Dict, List, Tuple, Any
from dotenv import load_dotenv

load_dotenv()

TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")

if not TOMTOM_API_KEY:
    print("WARNING: TOMTOM_API_KEY not set. Some features will use mock data.")
    TOMTOM_API_KEY = None

# Fixed options for limiting number of API calls
NUMBER_OF_RESULTS = 5  # Number of closest results to fetch per iteration
MAX_ITERATIONS = 3  # Maximum number of iterations to avoid excessive API calls


def get_route_details(USER_LOCATION: Tuple[float, float], destination: Tuple[float, float], api_key: str = None) -> Optional[Dict[str, Any]]:
    """
    Get route details from TomTom API with comprehensive error handling

    Args:
        USER_LOCATION: Tuple of (longitude, latitude)
        destination: Tuple of (longitude, latitude) 
        api_key: TomTom API key

    Returns:
        Route summary dict or None if error
    """
    # Use provided API key or fall back to global one
    if api_key is None:
        api_key = TOMTOM_API_KEY

    # If no API key available, return mock data
    if not api_key:
        return {
            "distance_km": 5.2,
            "eta_minutes": 12.5,
            "instructions": ["Mock route data - API key not available"]
        }

    try:
        # Validate input coordinates
        if not USER_LOCATION or not destination:
            print("ERROR: Invalid coordinates provided")
            return None

        if len(USER_LOCATION) != 2 or len(destination) != 2:
            print("ERROR: Coordinates must be tuples of length 2")
            return None

        # Validate coordinate values
        for coord in USER_LOCATION + destination:
            if not isinstance(coord, (int, float)) or coord < -180 or coord > 180:
                print(f"ERROR: Invalid coordinate value: {coord}")
                return None

        url = f"https://api.tomtom.com/routing/1/calculateRoute/{USER_LOCATION[1]},{USER_LOCATION[0]}:{destination[1]},{destination[0]}/json"
        params = {
            "routeType": "fastest",
            "instructionsType": "text",
            "traffic": "true",
            "travelMode": "car",
            "key": api_key
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # Raise exception for HTTP errors

        data = response.json()

        # Validate API response structure
        if not isinstance(data, dict):
            print("ERROR: Invalid API response format")
            return None

        if "routes" not in data or not data["routes"]:
            print("ERROR: No route data found in API response")
            return None

        route = data["routes"][0]

        # Validate route data structure
        if "summary" not in route or "guidance" not in route:
            print("ERROR: Incomplete route data from API")
            return None

        summary = route["summary"]
        guidance = route["guidance"]

        # Validate required fields with safe extraction
        try:
            distance_meters = summary.get("lengthInMeters")
            travel_time_seconds = summary.get("travelTimeInSeconds")

            if distance_meters is None or travel_time_seconds is None:
                print("ERROR: Missing distance or travel time in route data")
                return None

            # Convert meters to km
            distance_km = distance_meters / 1000
            # Convert seconds to minutes
            eta_minutes = travel_time_seconds / 60

            # Validate converted values
            if distance_km <= 0 or eta_minutes <= 0:
                print("ERROR: Invalid distance or time values")
                return None

        except (TypeError, ValueError) as e:
            print(f"ERROR: Failed to process route metrics: {e}")
            return None

        # Prepare route instructions with validation
        instructions = []
        if "instructions" in guidance and isinstance(guidance["instructions"], list):
            for instruction in guidance["instructions"]:
                if isinstance(instruction, dict) and "message" in instruction:
                    instructions.append(instruction["message"])

        route_summary = {
            "distance_km": round(distance_km, 2),
            "eta_minutes": round(eta_minutes, 1),
            "instructions": instructions,
            "full_json": data
        }

        print(
            f"DEBUG: Route calculated successfully - Distance: {distance_km}km, ETA: {eta_minutes}min")
        return route_summary

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Network error fetching route for {destination}: {e}")
        return None
    except requests.exceptions.Timeout:
        print(f"ERROR: Timeout fetching route for {destination}")
        return None
    except requests.exceptions.HTTPError as e:
        print(
            f"ERROR: HTTP error {e.response.status_code} fetching route for {destination}")
        return None
    except ValueError as e:
        print(f"ERROR: Invalid data in route response for {destination}: {e}")
        return None
    except Exception as e:
        print(f"ERROR: Unexpected error in get_route_details: {e}")
        return None


def get_charging_station_availability(station_id: str, TOMTOM_API_KEY: str = TOMTOM_API_KEY) -> int:
    """
    Fetch charging station availability with error handling

    Args:
        station_id: Station identifier
        TOMTOM_API_KEY: TomTom API key

    Returns:
        Number of available chargers or 0 if error
    """
    try:
        if not station_id:
            print("ERROR: Invalid station ID provided")
            return 0

        url = "https://api.tomtom.com/search/2/chargingAvailability.json"
        params = {
            "chargingAvailability": station_id,
            "key": TOMTOM_API_KEY
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            print(f"ERROR: Invalid response format for station {station_id}")
            return 0

        connectors = data.get("connectors", [])
        if not connectors:
            print(f"DEBUG: No connectors found for station {station_id}")
            return 0

        total_available = 0
        for connector in connectors:
            if isinstance(connector, dict):
                availability = connector.get("availability", {})
                if isinstance(availability, dict):
                    current = availability.get("current", {})
                    if isinstance(current, dict):
                        available = current.get("available", 0)
                        if isinstance(available, (int, float)) and available > 0:
                            total_available += int(available)

        print(
            f"DEBUG: Station {station_id} has {total_available} available chargers")
        return total_available

    except requests.exceptions.RequestException as e:
        print(
            f"ERROR: Network error fetching availability for station {station_id}: {e}")
        return 0
    except requests.exceptions.Timeout:
        print(f"ERROR: Timeout fetching availability for station {station_id}")
        return 0
    except requests.exceptions.HTTPError as e:
        print(
            f"ERROR: HTTP error {e.response.status_code} fetching availability for station {station_id}")
        return 0
    except Exception as e:
        print(
            f"ERROR: Unexpected error in get_charging_station_availability: {e}")
        return 0


def get_nearby_stations(USER_LOCATION: Tuple[float, float], NUMBER_OF_RESULTS: int = NUMBER_OF_RESULTS, TOMTOM_API_KEY: str = TOMTOM_API_KEY) -> List[Dict[str, Any]]:
    """
    Get nearby charging stations with error handling

    Args:
        USER_LOCATION: Tuple of (longitude, latitude)
        NUMBER_OF_RESULTS: Maximum number of results to return
        TOMTOM_API_KEY: TomTom API key

    Returns:
        List of station data or empty list if error
    """
    try:
        # Validate input coordinates
        if not USER_LOCATION or len(USER_LOCATION) != 2:
            print("ERROR: Invalid coordinates provided")
            return []

        lon, lat = USER_LOCATION
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            print("ERROR: Coordinates must be numeric values")
            return []

        if lon < -180 or lon > 180 or lat < -90 or lat > 90:
            print("ERROR: Coordinates out of valid range")
            return []

        url = f"https://api.tomtom.com/search/2/nearbySearch/.json"
        params = {
            "lat": lat,
            "lon": lon,
            "limit": min(NUMBER_OF_RESULTS, 50),  # Cap at 50 to prevent abuse
            "categorySet": 7309,  # 7309 is code for EV Charging Stations in TOM TOM
            "key": TOMTOM_API_KEY
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            print("ERROR: Invalid API response format")
            return []

        if "results" not in data:
            print("DEBUG: No nearby stations found")
            return []

        results = data["results"]
        if not isinstance(results, list):
            print("ERROR: Invalid results format in API response")
            return []

        # Validate and clean station data
        valid_stations = []
        for station in results:
            if isinstance(station, dict) and "position" in station and "poi" in station:
                # Validate position data
                position = station["position"]
                if "lat" in position and "lon" in position:
                    try:
                        lat_val = float(position["lat"])
                        lon_val = float(position["lon"])
                        if -90 <= lat_val <= 90 and -180 <= lon_val <= 180:
                            valid_stations.append(station)
                        else:
                            print(
                                f"WARNING: Skipping station with invalid coordinates: {lat_val}, {lon_val}")
                    except (ValueError, TypeError):
                        print(
                            f"WARNING: Skipping station with non-numeric coordinates")
                        continue
                else:
                    print(f"WARNING: Skipping station with missing position data")
            else:
                print(f"WARNING: Skipping station with incomplete data structure")

        print(f"DEBUG: Found {len(valid_stations)} valid nearby stations")
        return valid_stations[:NUMBER_OF_RESULTS]

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Network error fetching nearby stations: {e}")
        return []
    except requests.exceptions.Timeout:
        print("ERROR: Timeout fetching nearby stations")
        return []
    except requests.exceptions.HTTPError as e:
        print(
            f"ERROR: HTTP error {e.response.status_code} fetching nearby stations")
        return []
    except Exception as e:
        print(f"ERROR: Unexpected error in get_nearby_stations: {e}")
        return []


def get_multiple_nearby_stations(USER_LOCATION: Tuple[float, float], NUMBER_OF_RESULTS: int = 10, TOMTOM_API_KEY: str = TOMTOM_API_KEY) -> List[Dict[str, Any]]:
    """
    Get multiple nearby charging stations with route details and error handling

    Args:
        USER_LOCATION: Tuple of (longitude, latitude)
        NUMBER_OF_RESULTS: Maximum number of results to return
        TOMTOM_API_KEY: TomTom API key

    Returns:
        List of stations with route details or empty list if error
    """
    try:
        # Validate input
        if not USER_LOCATION:
            print("ERROR: Invalid coordinates provided")
            return []

        # Get nearby stations first
        stations = get_nearby_stations(
            USER_LOCATION, NUMBER_OF_RESULTS, TOMTOM_API_KEY)

        if not stations:
            print("DEBUG: No nearby stations found")
            return []

        stations_with_routes = []
        successful_routes = 0

        for i, station in enumerate(stations):
            try:
                # Extract position data safely
                if "position" not in station:
                    print(f"WARNING: Station {i} missing position data")
                    continue

                position = station["position"]
                if "lat" not in position or "lon" not in position:
                    print(f"WARNING: Station {i} has incomplete position data")
                    continue

                # Get route details for this station
                route_details = get_route_details(
                    USER_LOCATION,
                    (position["lon"], position["lat"]),
                    TOMTOM_API_KEY
                )

                if route_details:
                    # Extract station information safely
                    station_name = station.get("poi", {}).get(
                        "name", "Charging Station")
                    station_address = station.get("address", {}).get(
                        "freeformAddress", "Unknown address")

                    station_data = {
                        "Name": station_name,
                        "Address": station_address,
                        "Location": (position["lon"], position["lat"]),
                        "Distance": route_details["distance_km"],
                        "ETA": route_details["eta_minutes"],
                        "Instructions": route_details.get("instructions", [])
                    }

                    stations_with_routes.append(station_data)
                    successful_routes += 1
                else:
                    print(
                        f"WARNING: Could not get route details for station {i}")

            except Exception as e:
                print(f"ERROR: Failed to process station {i}: {e}")
                continue

        # Sort by distance and return top results
        if stations_with_routes:
            stations_with_routes.sort(
                key=lambda x: x.get("Distance", float('inf')))
            print(
                f"DEBUG: Successfully processed {successful_routes} stations with routes")
            return stations_with_routes[:NUMBER_OF_RESULTS]
        else:
            print("DEBUG: No stations with valid route data found")
            return []

    except Exception as e:
        print(f"ERROR: Unexpected error in get_multiple_nearby_stations: {e}")
        return []


def find_station(USER_LOCATION: Tuple[float, float], TOMTOM_API_KEY: str = TOMTOM_API_KEY, INCLUDE_NAVIGATION: bool = True, RETURN_FULL_JSON: bool = False) -> Optional[Dict[str, Any]]:
    """
    Find the best available charging station with comprehensive error handling

    Args:
        USER_LOCATION: Tuple of (longitude, latitude)
        TOMTOM_API_KEY: TomTom API key
        INCLUDE_NAVIGATION: Whether to include navigation instructions
        RETURN_FULL_JSON: Whether to return full JSON response

    Returns:
        Station data dict or None if error
    """
    try:
        # Validate input coordinates
        if not USER_LOCATION or len(USER_LOCATION) != 2:
            print("ERROR: Invalid coordinates provided")
            return None

        lon, lat = USER_LOCATION
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            print("ERROR: Coordinates must be numeric values")
            return None

        if lon < -180 or lon > 180 or lat < -90 or lat > 90:
            print("ERROR: Coordinates out of valid range")
            return None

        available_stations = []
        iteration = 0

        while iteration < MAX_ITERATIONS:
            print(f"DEBUG: Search iteration {iteration + 1}/{MAX_ITERATIONS}")

            # Get nearby stations
            stations = get_nearby_stations(USER_LOCATION, TOMTOM_API_KEY)

            if not stations:
                print("DEBUG: No stations found in iteration {iteration + 1}")
                break

            # Check availability for each station
            for station in stations:
                try:
                    station_id = station.get("id")
                    if not station_id:
                        print(
                            "WARNING: Station missing ID, skipping availability check")
                        continue

                    availability = get_charging_station_availability(
                        station_id, TOMTOM_API_KEY)

                    if availability >= 1:
                        # Get route details for available station
                        if "position" in station:
                            position = station["position"]
                            if "lat" in position and "lon" in position:
                                route_details = get_route_details(
                                    USER_LOCATION,
                                    (position["lon"], position["lat"]),
                                    TOMTOM_API_KEY
                                )

                                if route_details and route_details.get("distance_km") and route_details.get("eta_minutes"):
                                    available_stations.append(
                                        (station, route_details))
                                    print(
                                        f"DEBUG: Found available station with route: {station.get('poi', {}).get('name', 'Unknown')}")
                                else:
                                    print(
                                        f"WARNING: Station {station_id} has no valid route data")
                            else:
                                print(
                                    f"WARNING: Station {station_id} has incomplete position data")
                        else:
                            print(
                                f"WARNING: Station {station_id} missing position data")

                except Exception as e:
                    print(
                        f"ERROR: Failed to process station {station.get('id', 'Unknown')}: {e}")
                    continue

            # If we have available stations, break out of the loop
            if available_stations:
                print(
                    f"DEBUG: Found {len(available_stations)} available stations")
                break

            iteration += 1
            # If no stations available, try again with more stations
            if iteration < MAX_ITERATIONS:
                global NUMBER_OF_RESULTS
                NUMBER_OF_RESULTS += 3  # Fetch more stations in the next iteration
                print(
                    f"DEBUG: Increasing search radius for iteration {iteration + 1}")

        if available_stations:
            # Sort the available stations by ETA (shortest travel time first)
            available_stations.sort(
                key=lambda x: x[1].get("eta_minutes", float('inf')))

            # Get the top station (the one with the best ETA)
            top_station = available_stations[0]

            try:
                # Extract station data safely
                station_data = top_station[0]
                route_data = top_station[1]

                if "position" not in station_data:
                    print("ERROR: Top station missing position data")
                    return None

                position = station_data["position"]
                lat = position.get("lat")
                lon = position.get("lon")

                if lat is None or lon is None:
                    print("ERROR: Top station has invalid coordinates")
                    return None

                # Extract other data with safe defaults
                address = station_data.get("address", {}).get(
                    "freeformAddress", "Unknown address")
                name = station_data.get("poi", {}).get(
                    "name", "Charging Station")
                distance = route_data.get("distance_km")
                eta = route_data.get("eta_minutes")

                if distance is None or eta is None:
                    print("ERROR: Top station missing route metrics")
                    return None

                result = {
                    "Name": name,
                    "Location": (lon, lat),
                    "Address": address,
                    "Distance": distance,
                    "ETA": eta
                }

                if INCLUDE_NAVIGATION:
                    result["Instructions"] = route_data.get("instructions", [])

                if RETURN_FULL_JSON:
                    result["full_json"] = (
                        station_data, route_data.get("full_json"))

                print(
                    f"DEBUG: Successfully found best station: {name} at {address}")
                return result

            except Exception as e:
                print(f"ERROR: Failed to process top station data: {e}")
                return None

        else:
            print("DEBUG: No available charging stations found after multiple iterations")
            return None

    except Exception as e:
        print(f"ERROR: Unexpected error in find_station: {e}")
        return None
