import os
import json
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
import datetime

_station_cache: Dict[str, Dict[str, Any]] = {}
try:
    from dotenv import load_dotenv

    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(current_dir, '..'))
    env_dir = os.path.join(repo_root, 'env')

    if os.path.exists(os.path.join(env_dir, '.env')):
        load_dotenv(os.path.join(env_dir, '.env'))
    elif os.path.exists(os.path.join(repo_root, '.env')):
        load_dotenv(os.path.join(repo_root, '.env'))
except Exception:
    pass


class ApiManager:

    def __init__(self, api_key: Optional[str] = None, timeout_seconds: int = 15) -> None:
        self.api_key = api_key or os.environ.get('TOMTOM_API_KEY') or ''
        self.timeout_seconds = timeout_seconds
        self.base_url = 'https://api.tomtom.com'

    def _has_key(self) -> bool:
        return isinstance(self.api_key, str) and len(self.api_key.strip()) > 0

    def get_real_time_route(self, start_coords: Tuple[float, float], end_coords: Tuple[float, float]) -> Optional[Dict[str, Any]]:
        """Return route with traffic-aware summary.

        Coords are (lat, lon).
        """
        if not self._has_key():
            return None
        try:
            start_lat, start_lon = start_coords
            end_lat, end_lon = end_coords
            path = f"/routing/1/calculateRoute/{start_lat},{start_lon}:{end_lat},{end_lon}/json"
            url = f"{self.base_url}{path}"
            params = {
                'routeType': 'fastest',
                'traffic': 'true',
                'travelMode': 'car',
                'instructionsType': 'text',
                'key': self.api_key,
            }
            resp = requests.get(url, params=params,
                                timeout=self.timeout_seconds)
            resp.raise_for_status()
            data = resp.json()
            routes = data.get('routes', [])
            if not routes:
                return None
            route = routes[0]
            summary = route.get('summary', {})
            distance_km = float(summary.get('lengthInMeters', 0)) / 1000.0
            duration_min = float(summary.get('travelTimeInSeconds', 0)) / 60.0
            delay_min = float(summary.get('trafficDelayInSeconds', 0)) / 60.0

            instructions: List[str] = []
            try:
                for inst in route.get('guidance', {}).get('instructions', []) or []:
                    msg = inst.get('message')
                    if msg:
                        instructions.append(str(msg))
            except Exception:
                instructions = []

            return {
                'source': 'tomtom',
                'distance_km': distance_km,
                'duration_minutes': duration_min,
                'traffic_delay_minutes': delay_min,
                'instructions': instructions,
            }
        except Exception:
            return None

    def get_real_time_traffic(self, start_coords: Tuple[float, float], end_coords: Tuple[float, float]) -> Optional[Dict[str, Any]]:
        """Return traffic details for a route. Uses route summary as a proxy.

        Coords are (lat, lon).
        """
        # Use route summary to derive delay; TomTom traffic details API could be added later
        route = self.get_real_time_route(start_coords, end_coords)
        if not route:
            return None
        estimated_delay_minutes = route.get('traffic_delay_minutes', 0)
        # Speed metrics not available without traffic flow API; return N/A
        return {
            'source': 'tomtom',
            'traffic_status': 'Available',
            'congestion_level': None,
            'current_speed_kmh': None,
            'free_flow_speed_kmh': None,
            'estimated_delay_minutes': estimated_delay_minutes,
        }

    def get_charging_station_real_time_data(self, x: Union[float, str], y: Union[float, Tuple[float, float]], radius_km: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Two modes:
        - Nearby mode: (lat: float, lon: float, radius_km: float) → returns stations list
        - Per-station mode: (station_name: str, (lat, lon)) → not supported by TomTom without ID; returns None
        """
        if not self._has_key():
            return None

        # Nearby stations mode
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            lat = float(x)
            lon = float(y)
            radius = float(radius_km or 15.0)
            try:
                url = f"{self.base_url}/search/2/nearbySearch/.json"
                params = {
                    'lat': lat,
                    'lon': lon,
                    'limit': 10,
                    'radius': int(radius * 1000),
                    'categorySet': 7309,  # EV Charging Stations
                    'key': self.api_key,
                }
                resp = requests.get(url, params=params,
                                    timeout=self.timeout_seconds)
                resp.raise_for_status()
                data = resp.json()
                results = data.get('results', [])
                stations: List[Dict[str, Any]] = []
                for r in results:
                    poi = r.get('poi', {})
                    addr = r.get('address', {})
                    pos = r.get('position', {})
                    stations.append({
                        'name': poi.get('name', 'Unknown Station'),
                        'address': addr.get('freeformAddress', 'Unknown'),
                        'power_kw': None,  # Not available in nearby API; can be enriched later
                        'cost_per_kwh': None,
                        'available_points': None,
                        'total_connectors': None,
                        'charging_speed': None,
                        'distance_km': r.get('dist', 0) / 1000.0 if isinstance(r.get('dist'), (int, float)) else None,
                        'lat': pos.get('lat'),
                        'lon': pos.get('lon'),
                    })
                return {
                    'source': 'tomtom',
                    'stations': stations,
                }
            except Exception:
                return None

        return None

    def geocode(self, query: str) -> Optional[Tuple[float, float]]:
        """Resolve a free-form place/query to (lat, lon) using TomTom Geocoding.
        Returns None if not found or key missing.
        """
        if not self._has_key() or not query:
            return None
        try:
            url = f"{self.base_url}/search/2/geocode/{requests.utils.quote(query)}.json"
            params = {
                'key': self.api_key,
                'limit': 1,
            }
            resp = requests.get(url, params=params,
                                timeout=self.timeout_seconds)
            resp.raise_for_status()
            data = resp.json()
            results = data.get('results') or []
            if not results:
                return None
            pos = results[0].get('position') or {}
            lat = pos.get('lat')
            lon = pos.get('lon')
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                return float(lat), float(lon)
        except Exception:
            return None
        return None
    
    def get_charging_availability(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Get basic availability of a charging station near given coordinates.

        Returns:
            {
                "available": True/False/None,
                "updated_at": ISO timestamp or None,
                "data": full JSON from TomTom or error info
            }
        """
        station_key = f"{lat:.4f},{lon:.4f}"
        api_key = "azlqdL59gO4rrlVHkqtjxy0L0SOI3W7l"
        
        # --- Cache check ---
        if station_key in _station_cache:
            if _station_cache[station_key]["expiry"] > datetime.datetime.utcnow():
                return _station_cache[station_key]["data"]

        try:
            # Step 1: Find nearest EV charging station (categorySet=7309)
            nearby_url = (
                f"https://api.tomtom.com/search/2/nearbySearch/.json?"
                f"lat={lat}&lon={lon}&key={api_key}&radius=500&limit=1&categorySet=7309"
            )
            resp1 = requests.get(nearby_url, timeout=5)
            resp1.raise_for_status()
            nearby_data = resp1.json()

            if not nearby_data.get("results"):
                return {"available": None, "updated_at": None, "data": "No station found"}

            station_id = nearby_data["results"][0]["id"]
            # print("Nearest stationId:", station_id)

            # Step 2: Get real-time availability
            avail_url = "https://api.tomtom.com/search/2/chargingAvailability.json"
            params = {
                "key": api_key,
                "chargingAvailability": station_id,
                "minPowerKW": 1,
                "maxPowerKW": 100,
            }
            resp2 = requests.get(avail_url, params=params, timeout=5)
            resp2.raise_for_status()
            avail_data = resp2.json()
            # print("Availability response:", avail_data)

            # Simplified peek
            available = None
            updated_at = None

            ca = avail_data.get("chargingAvailability", {})
            connectors = avail_data.get("connectors", [])

            if connectors:
                free_count = sum(c.get("available", 0) for c in connectors)
                available = free_count > 0
                updated_at = datetime.datetime.utcnow().isoformat()

            result = {"available": available, "updated_at": updated_at, "data": avail_data}

            # --- Cache store (10 min TTL) ---
            _station_cache[station_key] = {
                "data": result,
                "expiry": datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
            }
            return result

        except Exception as e:
            return {"available": None, "updated_at": None, "data": f"Exception: {e}"}

# Global instance as expected by imports in Rasa actions
api_manager = ApiManager()
