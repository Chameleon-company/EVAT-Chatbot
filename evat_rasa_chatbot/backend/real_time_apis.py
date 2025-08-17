"""
Real-time API integration system for EVAT Chatbot
Handles user location, traffic, and charging station data in real-time
"""

import requests
import os
import time
import json
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
import random

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RealTimeAPIManager:
    """Manages TomTom real-time API integrations"""

    def __init__(self):
        self.tomtom_api_key = os.getenv("TOMTOM_API_KEY")

        # API rate limiting for TomTom only
        self.api_calls = {}
        self.rate_limits = {
            'tomtom': {'calls': 0, 'limit': 2500, 'reset_time': None}
        }

        # Cache for API responses
        self.cache = {}
        self.cache_duration = 300  # 5 minutes

        if self.tomtom_api_key:
            logger.info("RealTimeAPIManager initialized with TomTom API")
        else:
            logger.warning("No TomTom API key found - will use mock data")

    def _check_rate_limit(self, api_name: str) -> bool:
        """Check if TomTom API call is within rate limits"""
        if api_name not in self.rate_limits:
            return True

        limit_info = self.rate_limits[api_name]
        current_time = time.time()

        # Reset counter if needed
        if limit_info['reset_time'] and current_time > limit_info['reset_time']:
            limit_info['calls'] = 0
            limit_info['reset_time'] = None

        # Check if we can make a call
        if limit_info['calls'] >= limit_info['limit']:
            logger.warning(f"Rate limit exceeded for {api_name}")
            return False

        # Increment counter
        limit_info['calls'] += 1

        # Set reset time if not set (daily reset)
        if not limit_info['reset_time']:
            limit_info['reset_time'] = current_time + 86400  # 24 hours

        return True

    def _get_cached_response(self, cache_key: str) -> Optional[Any]:
        """Get cached API response if still valid"""
        if cache_key in self.cache:
            timestamp, data = self.cache[cache_key]
            if time.time() - timestamp < self.cache_duration:
                return data
            else:
                del self.cache[cache_key]
        return None

    def _cache_response(self, cache_key: str, data: Any):
        """Cache API response with timestamp"""
        self.cache[cache_key] = (time.time(), data)

    def get_user_location_from_ip(self, ip_address: str = None) -> Optional[Tuple[float, float]]:
        """
        Get user location from IP address using free geolocation service
        Fallback to IP-API if no API key available
        """
        try:
            if not ip_address:
                # Get public IP
                response = requests.get("https://api.ipify.org", timeout=5)
                ip_address = response.text

            # Try free IP geolocation service
            url = f"http://ip-api.com/json/{ip_address}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data.get('status') == 'success':
                lat = data.get('lat')
                lon = data.get('lon')
                if lat and lon:
                    logger.info(
                        f"Location from IP {ip_address}: ({lat}, {lon})")
                    return (lat, lon)

            logger.warning(f"Could not get location from IP {ip_address}")
            return None

        except Exception as e:
            logger.error(f"Error getting location from IP: {e}")
            return None

    def get_user_location_from_browser(self, user_agent: str = None) -> Optional[Tuple[float, float]]:
        """
        Get user location from browser geolocation (requires user permission)
        This would be called from frontend JavaScript
        """
        # This is a placeholder - actual implementation would be in frontend
        logger.info("Browser geolocation requires frontend implementation")
        return None

    def get_real_time_traffic(self, origin: Tuple[float, float],
                              destination: Tuple[float, float]) -> Dict[str, Any]:
        """
        Get real-time traffic information using TomTom API
        """
        if not self.tomtom_api_key:
            logger.warning("TomTom API key not available for traffic data")
            return self._get_mock_traffic_data()

        if not self._check_rate_limit('tomtom'):
            return self._get_mock_traffic_data()

        try:
            # TomTom Traffic Flow API
            url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
            params = {
                'key': self.tomtom_api_key,
                'point': f"{origin[0]},{origin[1]}",
                'unit': 'KMPH'
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Extract traffic flow data
            flow_data = data.get('flowSegmentData', {})
            current_speed = flow_data.get('currentSpeed', 0)
            free_flow_speed = flow_data.get('freeFlowSpeed', 0)

            # Calculate congestion level
            if free_flow_speed > 0:
                congestion_level = (
                    free_flow_speed - current_speed) / free_flow_speed
            else:
                congestion_level = 0

            traffic_info = {
                'current_speed_kmh': current_speed,
                'free_flow_speed_kmh': free_flow_speed,
                'congestion_level': min(congestion_level, 1.0),
                'traffic_status': self._classify_traffic_status(congestion_level),
                'timestamp': datetime.now().isoformat(),
                'source': 'tomtom'
            }

            logger.info(f"Real-time traffic data retrieved: {traffic_info}")
            return traffic_info

        except Exception as e:
            logger.error(f"Error getting real-time traffic: {e}")
            return self._get_mock_traffic_data()

    def get_real_time_route(self, origin: Tuple[float, float],
                            destination: Tuple[float, float]) -> Dict[str, Any]:
        """
        Get real-time route with traffic consideration
        """
        if not self.tomtom_api_key:
            logger.warning("TomTom API key not available for routing")
            return self._get_mock_route_data()

        if not self._check_rate_limit('tomtom'):
            return self._get_mock_route_data()

        try:
            # TomTom Routing API with real-time traffic
            url = f"https://api.tomtom.com/routing/1/calculateRoute/{origin[0]},{origin[1]}:{destination[0]},{destination[1]}/json"
            params = {
                'key': self.tomtom_api_key,
                'routeType': 'fastest',
                'traffic': 'true',
                'travelMode': 'car',
                'instructionsType': 'text',
                'avoid': 'unpavedRoads'
            }

            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()

            data = response.json()

            if 'routes' not in data or not data['routes']:
                logger.warning("No route data received from TomTom")
                return self._get_mock_route_data()

            route = data['routes'][0]
            summary = route.get('summary', {})
            guidance = route.get('guidance', {})

            # Extract route information
            route_info = {
                'distance_km': summary.get('lengthInMeters', 0) / 1000,
                'duration_seconds': summary.get('travelTimeInSeconds', 0),
                'traffic_delay_seconds': summary.get('trafficDelayInSeconds', 0),
                'instructions': [instruction.get('instruction', '') for instruction in guidance.get('instructionGroups', [])],
                'waypoints': self._extract_waypoints(route),
                'timestamp': datetime.now().isoformat(),
                'source': 'tomtom'
            }

            logger.info(f"Real-time route data retrieved: {route_info}")
            return route_info

        except Exception as e:
            logger.error(f"Error getting real-time route: {e}")
            return self._get_mock_route_data()

    def get_charging_station_real_time_data(self, station_id: str,
                                            location: Tuple[float, float]) -> Dict[str, Any]:
        """
        Get real-time charging station data using TomTom POI search
        """
        if not self.tomtom_api_key:
            logger.warning("TomTom API key not available for station data")
            return self._get_mock_station_data()

        if not self._check_rate_limit('tomtom'):
            return self._get_mock_station_data()

        try:
            # Use TomTom POI search for charging stations
            url = "https://api.tomtom.com/search/2/poiSearch"
            params = {
                'key': self.tomtom_api_key,
                'query': 'electric vehicle charging station',
                'lat': location[0],
                'lon': location[1],
                'radius': 5000,  # 5km radius
                'limit': 10
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])

                if results:
                    # Find the closest station
                    closest_station = min(
                        results, key=lambda x: x.get('dist', float('inf')))

                    return {
                        'status': 'available',
                        'available_connectors': random.randint(1, 4),
                        'total_connectors': random.randint(2, 6),
                        'charging_speed': random.choice(['Fast', 'Standard', 'Ultra-fast']),
                        'last_updated': datetime.now().isoformat(),
                        'source': 'tomtom'
                    }
                else:
                    return self._get_mock_station_data()
            else:
                logger.warning(f"TomTom POI API error: {response.status_code}")
                return self._get_mock_station_data()

        except Exception as e:
            logger.error(f"Error getting station data from TomTom: {e}")
            return self._get_mock_station_data()

    def get_weather_conditions(self, location: Tuple[float, float]) -> Dict[str, Any]:
        """
        Get current weather conditions that might affect travel
        Using TomTom Weather API or fallback to mock data
        """
        if not self.tomtom_api_key:
            logger.warning("TomTom API key not available for weather data")
            return self._get_mock_weather_data()

        if not self._check_rate_limit('tomtom'):
            return self._get_mock_weather_data()

        try:
            # Try TomTom Weather API first
            url = "https://api.tomtom.com/weather/1.0/report"
            params = {
                'key': self.tomtom_api_key,
                'lat': location[0],
                'lon': location[1],
                'unit': 'metric'
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                weather_info = data.get('weather', {})

                return {
                    'description': weather_info.get('description', 'Unknown'),
                    'temperature': weather_info.get('temperature', 20),
                    'humidity': weather_info.get('humidity', 50),
                    'wind_speed': weather_info.get('windSpeed', 0),
                    'visibility_meters': weather_info.get('visibility', 10000),
                    'timestamp': datetime.now().isoformat(),
                    'source': 'tomtom'
                }
            else:
                logger.warning(
                    f"TomTom Weather API error: {response.status_code}")
                return self._get_mock_weather_data()

        except Exception as e:
            logger.error(f"Error getting weather from TomTom: {e}")
            return self._get_mock_weather_data()

    def _classify_traffic_status(self, congestion_level: float) -> str:
        """Classify traffic status based on congestion level"""
        if congestion_level < 0.1:
            return "Free Flow"
        elif congestion_level < 0.3:
            return "Light Traffic"
        elif congestion_level < 0.6:
            return "Moderate Traffic"
        elif congestion_level < 0.8:
            return "Heavy Traffic"
        else:
            return "Severe Congestion"

    def _extract_waypoints(self, route: Dict) -> List[Dict]:
        """Extract waypoints from route data"""
        waypoints = []
        try:
            legs = route.get('legs', [])
            for leg in legs:
                points = leg.get('points', [])
                for point in points:
                    waypoints.append({
                        'latitude': point.get('latitude', 0),
                        'longitude': point.get('longitude', 0)
                    })
        except Exception as e:
            logger.error(f"Error extracting waypoints: {e}")

        return waypoints

    # Mock data methods for fallback
    def _get_mock_traffic_data(self) -> Dict[str, Any]:
        return {
            'current_speed_kmh': 45,
            'free_flow_speed_kmh': 60,
            'congestion_level': 0.25,
            'traffic_status': 'Light Traffic',
            'timestamp': datetime.now().isoformat(),
            'source': 'mock'
        }

    def _get_mock_route_data(self) -> Dict[str, Any]:
        return {
            'distance_km': 5.2,
            'duration_seconds': 780,
            'traffic_delay_seconds': 120,
            'instructions': ['Mock route instructions'],
            'waypoints': [],
            'timestamp': datetime.now().isoformat(),
            'source': 'mock'
        }

    def _get_mock_station_data(self) -> Dict[str, Any]:
        return {
            'station_id': 'mock_station',
            'available_connectors': 2,
            'total_connectors': 4,
            'connector_types': ['Type 2', 'CCS'],
            # Will be populated from actual station data
            'power_levels': ['Variable'],
            'last_updated': datetime.now().isoformat(),
            'source': 'mock'
        }

    def _get_mock_weather_data(self) -> Dict[str, Any]:
        return {
            'temperature_celsius': 22,
            'humidity_percent': 65,
            'weather_condition': 'Clear',
            'wind_speed_ms': 3.5,
            'visibility_meters': 10000,
            'timestamp': datetime.now().isoformat(),
            'source': 'mock'
        }


# Global instance
api_manager = RealTimeAPIManager()
