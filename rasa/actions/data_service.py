"""
Data Service for EVAT Chatbot
Loads and provides access to charging station data from CSV datasets
Uses ONLY data available in charger_info_mel.csv 
"""

import pandas as pd
import os
from typing import Dict, List, Tuple, Optional, Any
import difflib
from math import radians, sin, cos, sqrt, atan2
import logging
import re
from .config import CHARGING_CONFIG, SEARCH_CONFIG, LOCATION_CONFIG, DATA_CONFIG

# Import real-time APIs for enhanced functionality
try:
    import sys
    sys.path.append(os.path.join(
        os.path.dirname(__file__), '..', '..', 'backend'))
    from real_time_apis import api_manager
    REAL_TIME_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("Real-time APIs imported successfully")
except ImportError as e:
    REAL_TIME_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"Real-time APIs not available: {e}")

logger = logging.getLogger(__name__)


class ChargingStationDataService:
    """Service for accessing charging station data from datasets"""

    def __init__(self):
        self.charger_data = None
        self.coordinates_data = None
        self.ml_dataset = None
        self._load_datasets()

    def _load_datasets(self):
        """Load all CSV datasets"""
        try:
            # Get the path to the data directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(
                current_dir, '..', '..', 'data', 'raw')

            # Load charger information dataset - PRIMARY DATA SOURCE
            charger_path = os.path.join(
                data_dir, DATA_CONFIG['CHARGER_CSV_PATH'].split('/')[-1])
            if os.path.exists(charger_path):
                self.charger_data = pd.read_csv(charger_path)
                logger.info(
                    f"Loaded {len(self.charger_data)} charging stations from dataset")
            else:
                logger.error(f"Charger dataset not found at {charger_path}")
                self.charger_data = pd.DataFrame()

            # Load coordinates dataset (optional - for location lookup)
            coords_path = os.path.join(
                data_dir, DATA_CONFIG['COORDINATES_CSV_PATH'].split('/')[-1])
            if os.path.exists(coords_path):
                self.coordinates_data = pd.read_csv(coords_path)
                logger.info(
                    f"Loaded {len(self.coordinates_data)} suburb coordinates from dataset")
            else:
                logger.warning(
                    "Coordinates dataset not found - will use charger data for coordinates")
                self.coordinates_data = pd.DataFrame()

            # Load ML dataset (optional - for future enhancements)
            ml_path = os.path.join(
                data_dir, DATA_CONFIG['ML_DATASET_PATH'].split('/')[-1])
            if os.path.exists(ml_path):
                self.ml_dataset = pd.read_csv(ml_path)
                logger.info(
                    f"Loaded {len(self.ml_dataset)} ML dataset records")
            else:
                logger.warning(
                    "ML dataset not found - not critical for core functionality")
                self.ml_dataset = pd.DataFrame()

        except Exception as e:
            logger.error(f"Error loading datasets: {e}")
            self.charger_data = pd.DataFrame()
            self.coordinates_data = pd.DataFrame()
            self.ml_dataset = pd.DataFrame()

    def get_stations_by_suburb(self, suburb: str) -> List[Dict[str, Any]]:
        """Get all charging stations in a specific suburb"""
        if self.charger_data.empty:
            return []

        suburb_lower = suburb.lower()
        # Search in suburb column (case insensitive)
        mask = self.charger_data[DATA_CONFIG['CSV_COLUMNS']['SUBURB']].str.lower(
        ).str.contains(suburb_lower, na=False)
        stations = self.charger_data[mask]

        if stations.empty:
            return []

        result = []
        for _, station in stations.iterrows():
            station_info = {
                'name': station.get(DATA_CONFIG['CSV_COLUMNS']['CHARGER_NAME'], 'Unknown'),
                'address': station.get(DATA_CONFIG['CSV_COLUMNS']['ADDRESS'], 'Address not available'),
                'suburb': station.get(DATA_CONFIG['CSV_COLUMNS']['SUBURB'], 'Unknown'),
                'power': station.get(DATA_CONFIG['CSV_COLUMNS']['POWER_KW'], 'Power not available'),
                'cost': station.get(DATA_CONFIG['CSV_COLUMNS']['USAGE_COST'], 'Cost not available'),
                'points': station.get(DATA_CONFIG['CSV_COLUMNS']['NUMBER_OF_POINTS'], 'Points not available'),
                'latitude': station.get(DATA_CONFIG['CSV_COLUMNS']['LATITUDE'], 0.0),
                'longitude': station.get(DATA_CONFIG['CSV_COLUMNS']['LONGITUDE'], 0.0)
            }
            result.append(station_info)

        return result

    def get_nearby_stations(self, location: Tuple[float, float], radius_km: float = None) -> List[Dict[str, Any]]:
        """Get charging stations within specified radius of location"""
        if radius_km is None:
            radius_km = SEARCH_CONFIG['DEFAULT_RADIUS_KM']
        if self.charger_data.empty:
            return []

        user_lat, user_lon = location
        nearby_stations = []

        for _, station in self.charger_data.iterrows():
            try:
                station_lat = float(station.get(
                    DATA_CONFIG['CSV_COLUMNS']['LATITUDE'], 0))
                station_lon = float(station.get(
                    DATA_CONFIG['CSV_COLUMNS']['LONGITUDE'], 0))

                if station_lat == 0 or station_lon == 0:
                    continue

                distance = self._calculate_distance(
                    (user_lat, user_lon),
                    (station_lat, station_lon)
                )

                if distance <= radius_km:
                    station_info = {
                        'name': station.get(DATA_CONFIG['CSV_COLUMNS']['CHARGER_NAME'], 'Unknown'),
                        'address': station.get(DATA_CONFIG['CSV_COLUMNS']['ADDRESS'], 'Address not available'),
                        'suburb': station.get(DATA_CONFIG['CSV_COLUMNS']['SUBURB'], 'Unknown'),
                        'power': station.get(DATA_CONFIG['CSV_COLUMNS']['POWER_KW'], 'Power not available'),
                        'cost': station.get(DATA_CONFIG['CSV_COLUMNS']['USAGE_COST'], 'Cost not available'),
                        'points': station.get(DATA_CONFIG['CSV_COLUMNS']['NUMBER_OF_POINTS'], 'Points not available'),
                        'connection_types': station.get(DATA_CONFIG['CSV_COLUMNS']['CONNECTION_TYPES'], ''),
                        'latitude': station_lat,
                        'longitude': station_lon,
                        'distance_km': round(distance, 2)
                    }
                    nearby_stations.append(station_info)

            except (ValueError, TypeError):
                continue

        # Sort by distance
        nearby_stations.sort(key=lambda x: x['distance_km'])
        return nearby_stations

    def get_stations_by_preference(self, location: Tuple[float, float], preference: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get stations based on preference (cheapest, fastest, closest)"""
        if self.charger_data.empty:
            return []

        nearby_stations = self.get_nearby_stations(
            location, radius_km=SEARCH_CONFIG['ROUTE_RADIUS_KM'])

        if preference == "closest":
            # Already sorted by distance
            return nearby_stations[:limit]

        elif preference == "cheapest":
            # Sort by cost (extract numeric value from Usage Cost column)
            def extract_cost(station):
                cost_str = str(station.get('cost', '0'))
                try:
                    # Extract first number from cost string (e.g., "AUD 0.30 per kWh" -> 0.30)
                    numbers = re.findall(r'\d+\.?\d*', cost_str)
                    if numbers:
                        return float(numbers[0])
                    # Handle "Free" case
                    if 'free' in cost_str.lower():
                        return 0.0
                    return 999.0  # High cost for unknown
                except:
                    return 999.0

            sorted_stations = sorted(nearby_stations, key=extract_cost)
            return sorted_stations[:limit]

        elif preference == "fastest":
            # Sort by power (higher power = faster charging)
            def extract_power(station):
                power_str = str(station.get('power', '0'))
                try:
                    # Extract first number from power string (e.g., "75, 22" -> 75)
                    numbers = re.findall(r'\d+\.?\d*', power_str)
                    if numbers:
                        return float(numbers[0])
                    return 0.0
                except:
                    return 0.0

            sorted_stations = sorted(
                nearby_stations, key=extract_power, reverse=True)
            return sorted_stations[:limit]

        else:
            return nearby_stations[:limit]

    def get_route_stations(self, start_location: str, end_location: str) -> List[Dict[str, Any]]:
        """Get charging stations along a route between two locations with real-time integration"""
        logger.info(
            f"Planning route from '{start_location}' to '{end_location}'")

        # Get coordinates for both locations
        start_coords = self._get_location_coordinates(start_location)
        end_coords = self._get_location_coordinates(end_location)

        if not start_coords:
            logger.error(
                f"Could not find coordinates for start location: {start_location}")
            return []

        if not end_coords:
            logger.error(
                f"Could not find coordinates for end location: {end_location}")
            return []

        logger.info(
            f"Route coordinates: {start_location} ({start_coords}) -> {end_location} ({end_coords})")

        # Get real-time route information if available
        route_info = None
        if REAL_TIME_AVAILABLE:
            try:
                route_info = api_manager.get_real_time_route(
                    start_coords, end_coords)
                logger.info(f"Real-time route data: {route_info}")
            except Exception as e:
                logger.warning(f"Real-time route data unavailable: {e}")

        # Calculate route distance (use real-time data if available, otherwise calculate)
        if route_info and route_info.get('source') == 'tomtom':
            route_distance = route_info.get('distance_km', 0)
            logger.info(f"Real-time route distance: {route_distance:.1f} km")
        else:
            route_distance = self._calculate_distance(start_coords, end_coords)
            logger.info(f"Calculated route distance: {route_distance:.1f} km")

        # Get stations along the route using enhanced logic
        route_stations = self._get_stations_along_route(
            start_coords, end_coords, route_distance, route_info)

        if route_stations:
            logger.info(f"Found {len(route_stations)} stations along route")
            # Enhance station data with real-time information
            if REAL_TIME_AVAILABLE:
                route_stations = self._enhance_stations_with_real_time_data(
                    route_stations, start_coords, end_coords)
            return route_stations
        else:
            logger.warning("No stations found along route")
            return []

    def _get_stations_along_route(self, start_coords: Tuple[float, float],
                                  end_coords: Tuple[float, float],
                                  route_distance: float,
                                  route_info: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get stations strategically placed along the route"""
        if self.charger_data.empty:
            return []

        # Calculate optimal search radius based on route distance
        search_radius = min(route_distance * 0.3,
                            SEARCH_CONFIG['ROUTE_RADIUS_KM'])

        # Get all stations within the search area
        all_stations = []
        for _, station in self.charger_data.iterrows():
            try:
                station_lat = float(station.get(
                    DATA_CONFIG['CSV_COLUMNS']['LATITUDE'], 0))
                station_lon = float(station.get(
                    DATA_CONFIG['CSV_COLUMNS']['LONGITUDE'], 0))

                if station_lat != 0 and station_lon != 0:
                    station_coords = (station_lat, station_lon)

                    # Check if station is within search radius of the route
                    if self._is_station_along_route(start_coords, end_coords, station_coords, search_radius):
                        station_info = {
                            'name': station.get(DATA_CONFIG['CSV_COLUMNS']['CHARGER_NAME'], 'Unknown'),
                            'address': station.get(DATA_CONFIG['CSV_COLUMNS']['ADDRESS'], 'Address not available'),
                            'suburb': station.get(DATA_CONFIG['CSV_COLUMNS']['SUBURB'], 'Unknown'),
                            'power': station.get(DATA_CONFIG['CSV_COLUMNS']['POWER_KW'], 'Power not available'),
                            'cost': station.get(DATA_CONFIG['CSV_COLUMNS']['USAGE_COST'], 'Cost not available'),
                            'points': station.get(DATA_CONFIG['CSV_COLUMNS']['NUMBER_OF_POINTS'], 'Points not available'),
                            'latitude': station_lat,
                            'longitude': station_lon,
                            'distance_from_start': self._calculate_distance(start_coords, station_coords),
                            'distance_from_end': self._calculate_distance(station_coords, end_coords)
                        }
                        all_stations.append(station_info)
            except (ValueError, TypeError):
                continue

        if not all_stations:
            return []

        # Sort stations by optimal placement along route
        # Prefer stations that are roughly 1/3 and 2/3 along the route
        for station in all_stations:
            station['route_position_score'] = self._calculate_route_position_score(
                station['distance_from_start'], route_distance
            )

        # Sort by route position score (closer to optimal 1/3 and 2/3 positions)
        all_stations.sort(key=lambda x: x['route_position_score'])

        # Return top stations with route information
        return all_stations[:SEARCH_CONFIG['MAX_RESULTS']]

    def _enhance_stations_with_real_time_data(self, stations: List[Dict[str, Any]],
                                              start_coords: Tuple[float, float],
                                              end_coords: Tuple[float, float]) -> List[Dict[str, Any]]:
        """Enhance station data with real-time traffic and availability information"""
        if not REAL_TIME_AVAILABLE:
            return stations

        enhanced_stations = []
        for station in stations:
            enhanced_station = station.copy()

            try:
                # Get real-time station data
                station_coords = (station['latitude'], station['longitude'])
                real_time_data = api_manager.get_charging_station_real_time_data(
                    station.get('name', ''), station_coords
                )

                if real_time_data and real_time_data.get('source') == 'tomtom':
                    enhanced_station['real_time_available'] = real_time_data.get(
                        'available_connectors', 0)
                    enhanced_station['real_time_total'] = real_time_data.get(
                        'total_connectors', 0)
                    enhanced_station['real_time_speed'] = real_time_data.get(
                        'charging_speed', 'Unknown')
                    enhanced_station['real_time_updated'] = real_time_data.get(
                        'last_updated', 'Unknown')
                    enhanced_station['data_source'] = 'Real-time'
                else:
                    enhanced_station['data_source'] = 'CSV Database'

                # Get traffic information for route to this station
                if station_coords != start_coords:
                    traffic_info = api_manager.get_real_time_traffic(
                        start_coords, station_coords)
                    if traffic_info and traffic_info.get('source') == 'tomtom':
                        enhanced_station['traffic_status'] = traffic_info.get(
                            'traffic_status', 'Unknown')
                        enhanced_station['congestion_level'] = traffic_info.get(
                            'congestion_level', 0)
                        enhanced_station['estimated_delay'] = traffic_info.get(
                            'traffic_delay_seconds', 0)

            except Exception as e:
                logger.warning(
                    f"Could not enhance station {station.get('name', 'Unknown')} with real-time data: {e}")
                enhanced_station['data_source'] = 'CSV Database'

            enhanced_stations.append(enhanced_station)

        return enhanced_stations

    def _is_station_along_route(self, start_coords: Tuple[float, float],
                                end_coords: Tuple[float, float],
                                station_coords: Tuple[float, float],
                                max_distance: float) -> bool:
        """Check if a station is within reasonable distance of the route"""
        # Calculate perpendicular distance from station to route line
        # This is a simplified version - in production, you'd use proper geometric calculations

        # For now, check if station is within max_distance of either endpoint
        start_distance = self._calculate_distance(start_coords, station_coords)
        end_distance = self._calculate_distance(station_coords, end_coords)

        # Station should be reasonably close to the route
        return start_distance <= max_distance or end_distance <= max_distance

    def _calculate_route_position_score(self, distance_from_start: float, total_route_distance: float) -> float:
        """Calculate how well positioned a station is along the route"""
        if total_route_distance == 0:
            return 0

        # Calculate position as percentage along route (0 = start, 1 = end)
        position = distance_from_start / total_route_distance

        # Optimal positions are around 1/3 and 2/3 of the route
        # Score based on distance from optimal positions
        optimal_positions = [0.33, 0.67]
        min_distance = min(abs(position - opt) for opt in optimal_positions)

        # Lower score is better (closer to optimal position)
        return min_distance

    def get_emergency_stations(self, location: str) -> List[Dict[str, Any]]:
        """Get emergency charging stations near a location"""
        coords = self._get_location_coordinates(location)
        if coords:
            return self.get_nearby_stations(coords, radius_km=SEARCH_CONFIG['EMERGENCY_RADIUS_KM'])[:SEARCH_CONFIG['EMERGENCY_MAX_RESULTS']]
        return []

    def get_station_details(self, station_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific station"""
        if self.charger_data.empty:
            return None

        # Search by name (case insensitive)
        mask = self.charger_data[DATA_CONFIG['CSV_COLUMNS']['CHARGER_NAME']].str.lower().str.contains(
            station_name.lower(), na=False
        )
        station = self.charger_data[mask]

        if station.empty:
            return None

        station = station.iloc[0]

        # Calculate estimated charging time based on power from CSV
        power_str = str(station.get(
            DATA_CONFIG['CSV_COLUMNS']['POWER_KW'], '22'))
        try:
            numbers = re.findall(r'\d+\.?\d*', power_str)
            power = float(numbers[0]) if numbers else 22.0
        except:
            power = 22.0

        # Use configuration-based charging time estimates
        charging_time = "Unknown"
        for power_range, (min_power, max_power, time_estimate) in CHARGING_CONFIG['CHARGING_TIME_ESTIMATES'].items():
            if min_power <= power <= max_power:
                charging_time = time_estimate
                break

        return {
            'name': station.get(DATA_CONFIG['CSV_COLUMNS']['CHARGER_NAME'], 'Unknown'),
            'address': station.get(DATA_CONFIG['CSV_COLUMNS']['ADDRESS'], 'Address not available'),
            'power': f"{power}kW",
            'points': f"{station.get(DATA_CONFIG['CSV_COLUMNS']['NUMBER_OF_POINTS'], 'Unknown')} points",
            'cost': station.get(DATA_CONFIG['CSV_COLUMNS']['USAGE_COST'], 'Cost not available'),
            'estimated_cost': self._estimate_charging_cost(station.get(DATA_CONFIG['CSV_COLUMNS']['USAGE_COST'], '0')),
            'charging_time': charging_time,
            'trip_time': "Calculating..."  # Will use TomTom API later
        }

    def _get_location_coordinates(self, location_name: str) -> Optional[Tuple[float, float]]:
        """Get coordinates for a location name with enhanced fuzzy matching"""
        if not location_name:
            return None

        # Clean and normalize location name
        location_clean = location_name.lower().strip()

        # Handle common variations and abbreviations
        location_variations = self._get_location_variations(location_clean)

        # Try coordinates dataset first with fuzzy matching
        if not self.coordinates_data.empty:
            for variation in location_variations:
                # Exact match first
                mask = self.coordinates_data['suburb'].str.lower() == variation
                location_data = self.coordinates_data[mask]

                if location_data.empty:
                    # Partial match
                    mask = self.coordinates_data['suburb'].str.lower(
                    ).str.contains(variation, na=False)
                    location_data = self.coordinates_data[mask]

                if not location_data.empty:
                    location_row = location_data.iloc[0]
                    try:
                        lat = float(location_row.get('latitude', 0))
                        lon = float(location_row.get('longitude', 0))
                        if lat != 0 and lon != 0:
                            logger.info(
                                f"Found coordinates for '{location_name}' -> '{location_row.get('suburb')}': ({lat}, {lon})")
                            return (lat, lon)
                    except (ValueError, TypeError):
                        pass

        logger.warning(
            f"Could not find coordinates for location: '{location_name}'")
        return None

    def _get_location_variations(self, location_name: str) -> List[str]:
        """Generate location name variations for better matching.

        Uses fuzzy matching against known suburb lists from coordinates data if
        available, otherwise falls back to suburbs present in the charger data.
        """
        variations: List[str] = [location_name]
        try:
            candidates: List[str] = []
            if self.coordinates_data is not None and not self.coordinates_data.empty:
                try:
                    candidates = (
                        self.coordinates_data['suburb']
                        .dropna()
                        .astype(str)
                        .str.lower()
                        .unique()
                        .tolist()
                    )
                except Exception:
                    candidates = []
            if not candidates and self.charger_data is not None and not self.charger_data.empty:
                try:
                    candidates = (
                        self.charger_data[DATA_CONFIG['CSV_COLUMNS']['SUBURB']]
                        .dropna()
                        .astype(str)
                        .str.lower()
                        .unique()
                        .tolist()
                    )
                except Exception:
                    candidates = []

            if candidates:
                close_matches = difflib.get_close_matches(
                    location_name, candidates, n=5, cutoff=0.6
                )
                for match in close_matches:
                    if match not in variations:
                        variations.append(match)
        except Exception:
            # If fuzzy match fails for any reason, return the original only
            return variations

        return variations

    def _calculate_distance(self, point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
        """Calculate distance between two points using Haversine formula"""
        lat1, lon1 = point1
        lat2, lon2 = point2

        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        # Use configuration for Earth's radius
        radius = LOCATION_CONFIG['EARTH_RADIUS_KM']
        return radius * c

    def _estimate_charging_cost(self, cost_str: str) -> str:
        """Estimate charging cost for 80% charge using actual CSV data"""
        try:
            # Handle "Free" case
            if 'free' in cost_str.lower():
                return "Free charging"

            # Extract numeric cost from Usage Cost column
            numbers = re.findall(r'\d+\.?\d*', cost_str)
            if numbers:
                rate = float(numbers[0])
                # Use configuration values for charge amount
                min_kwh = CHARGING_CONFIG['MIN_CHARGE_AMOUNT']
                max_kwh = CHARGING_CONFIG['MAX_CHARGE_AMOUNT']
                charge_percentage = CHARGING_CONFIG['CHARGE_PERCENTAGE']
                cost_margin = CHARGING_CONFIG['COST_MARGIN']

                # Calculate cost range
                min_cost = rate * min_kwh
                max_cost = rate * max_kwh
                max_cost_with_margin = max_cost * cost_margin

                return f"${min_cost:.0f}-{max_cost_with_margin:.0f} for {charge_percentage*100:.0f}% charge"
        except:
            pass
        return "Cost calculation not available"


# Global instance
data_service = ChargingStationDataService()
