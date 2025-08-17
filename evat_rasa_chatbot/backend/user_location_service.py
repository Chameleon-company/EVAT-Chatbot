"""
User Location Service for EVAT Chatbot
Handles real-time user location detection and management
"""

import requests
import json
import time
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from .real_time_apis import api_manager
import logging

logger = logging.getLogger(__name__)


class UserLocationService:
    """Service for managing user location in real-time"""

    def __init__(self):
        self.user_locations = {}  # Store user locations with timestamps
        self.location_history = {}  # Store location history for users
        self.location_accuracy = {}  # Store accuracy information
        self.max_history_size = 50  # Maximum location history entries per user

        # Location detection methods priority
        self.detection_methods = [
            'browser_geolocation',  # Most accurate - requires user permission
            'gps_coordinates',      # Direct GPS input
            'address_search',       # Address/landmark search
            'ip_geolocation',      # Least accurate - IP-based
            'manual_input'          # User manually entered location
        ]

        logger.info("UserLocationService initialized")

    def detect_user_location(self, user_id: str,
                             method: str = 'auto',
                             input_data: Any = None) -> Optional[Tuple[float, float]]:
        """
        Detect user location using specified method or auto-detect

        Args:
            user_id: Unique identifier for the user
            method: Detection method ('auto', 'browser', 'gps', 'address', 'ip', 'manual')
            input_data: Data for the specified method

        Returns:
            Tuple of (latitude, longitude) or None if detection failed
        """
        try:
            if method == 'auto':
                return self._auto_detect_location(user_id, input_data)
            elif method == 'browser':
                return self._detect_from_browser(user_id, input_data)
            elif method == 'gps':
                return self._detect_from_gps(user_id, input_data)
            elif method == 'address':
                return self._detect_from_address(user_id, input_data)
            elif method == 'ip':
                return self._detect_from_ip(user_id, input_data)
            elif method == 'manual':
                return self._detect_from_manual(user_id, input_data)
            else:
                logger.warning(f"Unknown detection method: {method}")
                return None

        except Exception as e:
            logger.error(f"Error detecting user location: {e}")
            return None

    def _auto_detect_location(self, user_id: str, input_data: Any = None) -> Optional[Tuple[float, float]]:
        """Automatically detect location using best available method"""

        # Try browser geolocation first (most accurate)
        if input_data and isinstance(input_data, dict) and 'browser_location' in input_data:
            location = self._detect_from_browser(
                user_id, input_data['browser_location'])
            if location:
                return location

        # Try GPS coordinates
        if input_data and isinstance(input_data, dict) and 'gps_coordinates' in input_data:
            location = self._detect_from_gps(
                user_id, input_data['gps_coordinates'])
            if location:
                return location

        # Try address search
        if input_data and isinstance(input_data, str):
            location = self._detect_from_address(user_id, input_data)
            if location:
                return location

        # Fallback to IP geolocation
        location = self._detect_from_ip(user_id)
        if location:
            return location

        logger.warning(f"Could not auto-detect location for user {user_id}")
        return None

    def _detect_from_browser(self, user_id: str, browser_data: Dict) -> Optional[Tuple[float, float]]:
        """Detect location from browser geolocation API"""
        try:
            if not browser_data:
                return None

            lat = browser_data.get('latitude')
            lon = browser_data.get('longitude')
            accuracy = browser_data.get('accuracy', 0)

            if lat is not None and lon is not None:
                location = (float(lat), float(lon))

                # Store location with high accuracy
                self._store_user_location(
                    user_id, location, 'browser_geolocation', accuracy)

                logger.info(
                    f"Location detected from browser for user {user_id}: {location} (accuracy: {accuracy}m)")
                return location

            return None

        except Exception as e:
            logger.error(f"Error detecting location from browser: {e}")
            return None

    def _detect_from_gps(self, user_id: str, gps_data: Any) -> Optional[Tuple[float, float]]:
        """Detect location from GPS coordinates"""
        try:
            if isinstance(gps_data, (list, tuple)) and len(gps_data) == 2:
                lat, lon = gps_data
                location = (float(lat), float(lon))

                # Store location with high accuracy
                self._store_user_location(
                    user_id, location, 'gps_coordinates', 5.0)

                logger.info(
                    f"Location detected from GPS for user {user_id}: {location}")
                return location

            elif isinstance(gps_data, dict):
                lat = gps_data.get('latitude') or gps_data.get('lat')
                lon = gps_data.get('longitude') or gps_data.get(
                    'lon') or gps_data.get('lng')

                if lat is not None and lon is not None:
                    location = (float(lat), float(lon))

                    # Store location with high accuracy
                    self._store_user_location(
                        user_id, location, 'gps_coordinates', 5.0)

                    logger.info(
                        f"Location detected from GPS dict for user {user_id}: {location}")
                    return location

            return None

        except Exception as e:
            logger.error(f"Error detecting location from GPS: {e}")
            return None

    def _detect_from_address(self, user_id: str, address: str) -> Optional[Tuple[float, float]]:
        """Detect location from address search using geocoding"""
        try:
            if not address or not isinstance(address, str):
                return None

            # Use TomTom Search API for geocoding
            location = self._geocode_address(address)

            if location:
                # Store location with medium accuracy (geocoding accuracy)
                self._store_user_location(
                    user_id, location, 'address_search', 100.0)

                logger.info(
                    f"Location detected from address for user {user_id}: {location} (address: {address})")
                return location

            return None

        except Exception as e:
            logger.error(f"Error detecting location from address: {e}")
            return None

    def _detect_from_ip(self, user_id: str, ip_address: str = None) -> Optional[Tuple[float, float]]:
        """Detect location from IP address"""
        try:
            location = api_manager.get_user_location_from_ip(ip_address)

            if location:
                # Store location with low accuracy (IP geolocation accuracy)
                self._store_user_location(
                    user_id, location, 'ip_geolocation', 5000.0)

                logger.info(
                    f"Location detected from IP for user {user_id}: {location}")
                return location

            return None

        except Exception as e:
            logger.error(f"Error detecting location from IP: {e}")
            return None

    def _detect_from_manual(self, user_id: str, manual_data: Any) -> Optional[Tuple[float, float]]:
        """Detect location from manual user input"""
        try:
            if isinstance(manual_data, (list, tuple)) and len(manual_data) == 2:
                lat, lon = manual_data
                location = (float(lat), float(lon))

                # Store location with user-specified accuracy
                self._store_user_location(
                    user_id, location, 'manual_input', 100.0)

                logger.info(
                    f"Location detected from manual input for user {user_id}: {location}")
                return location

            return None

        except Exception as e:
            logger.error(f"Error detecting location from manual input: {e}")
            return None

    def _geocode_address(self, address: str) -> Optional[Tuple[float, float]]:
        """Geocode address to coordinates using TomTom API"""
        try:
            if not api_manager.tomtom_api_key:
                logger.warning("TomTom API key not available for geocoding")
                return None

            # TomTom Search API for geocoding
            url = "https://api.tomtom.com/search/2/geocode/search.json"
            params = {
                'query': address,
                'key': api_manager.tomtom_api_key,
                'limit': 1,
                'countrySet': 'AU'  # Limit to Australia
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if 'results' in data and data['results']:
                result = data['results'][0]
                position = result.get('position', {})

                lat = position.get('lat')
                lon = position.get('lon')

                if lat is not None and lon is not None:
                    return (float(lat), float(lon))

            return None

        except Exception as e:
            logger.error(f"Error geocoding address: {e}")
            return None

    def _store_user_location(self, user_id: str, location: Tuple[float, float],
                             method: str, accuracy: float):
        """Store user location with metadata"""
        timestamp = datetime.now()

        # Store current location
        self.user_locations[user_id] = {
            'coordinates': location,
            'method': method,
            'accuracy_meters': accuracy,
            'timestamp': timestamp,
            'source': method
        }

        # Store in history
        if user_id not in self.location_history:
            self.location_history[user_id] = []

        history_entry = {
            'coordinates': location,
            'method': method,
            'accuracy_meters': accuracy,
            'timestamp': timestamp,
            'source': method
        }

        self.location_history[user_id].append(history_entry)

        # Limit history size
        if len(self.location_history[user_id]) > self.max_history_size:
            self.location_history[user_id] = self.location_history[user_id][-self.max_history_size:]

        # Store accuracy information
        self.location_accuracy[user_id] = {
            'current_accuracy': accuracy,
            'method': method,
            'last_updated': timestamp
        }

    def get_user_location(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get current user location with metadata"""
        if user_id in self.user_locations:
            return self.user_locations[user_id]
        return None

    def get_location_history(self, user_id: str,
                             hours: int = 24) -> List[Dict[str, Any]]:
        """Get user location history for specified time period"""
        if user_id not in self.location_history:
            return []

        cutoff_time = datetime.now() - timedelta(hours=hours)
        history = self.location_history[user_id]

        # Filter by time
        recent_history = [
            entry for entry in history
            if entry['timestamp'] > cutoff_time
        ]

        return recent_history

    def get_location_accuracy(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get current location accuracy information"""
        if user_id in self.location_accuracy:
            return self.location_accuracy[user_id]
        return None

    def update_user_location(self, user_id: str,
                             location: Tuple[float, float],
                             method: str = 'manual_update',
                             accuracy: float = 100.0):
        """Manually update user location"""
        self._store_user_location(user_id, location, method, accuracy)
        logger.info(
            f"Location updated for user {user_id}: {location} (method: {method})")

    def clear_user_location(self, user_id: str):
        """Clear user location data"""
        if user_id in self.user_locations:
            del self.user_locations[user_id]
        if user_id in self.location_history:
            del self.location_history[user_id]
        if user_id in self.location_accuracy:
            del self.location_accuracy[user_id]

        logger.info(f"Location data cleared for user {user_id}")

    def get_nearby_landmarks(self, location: Tuple[float, float],
                             radius_km: float = 5.0) -> List[Dict[str, Any]]:
        """Get nearby landmarks for location context"""
        try:
            if not api_manager.tomtom_api_key:
                return []

            # TomTom Search API for nearby landmarks
            url = "https://api.tomtom.com/search/2/nearbySearch/.json"
            params = {
                'lat': location[0],
                'lon': location[1],
                'radius': int(radius_km * 1000),  # Convert to meters
                'key': api_manager.tomtom_api_key,
                'limit': 10,
                # Landmarks, monuments, etc.
                'categorySet': '7315,7316,7317,7318,7319'
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            landmarks = []
            for result in data.get('results', []):
                landmark = {
                    'name': result.get('poi', {}).get('name', 'Unknown'),
                    'coordinates': (
                        result.get('position', {}).get('lat', 0),
                        result.get('position', {}).get('lon', 0)
                    ),
                    'category': result.get('poi', {}).get('categorySet', [{}])[0].get('name', 'Unknown'),
                    'distance_meters': result.get('dist', 0)
                }
                landmarks.append(landmark)

            return landmarks

        except Exception as e:
            logger.error(f"Error getting nearby landmarks: {e}")
            return []


# Global instance
location_service = UserLocationService()
