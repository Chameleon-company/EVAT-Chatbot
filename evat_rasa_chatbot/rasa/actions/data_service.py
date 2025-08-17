"""
Data Service for EVAT Chatbot
Loads and provides access to charging station data from CSV datasets
Uses ONLY data available in charger_info_mel.csv 
"""

import pandas as pd
import os
from typing import Dict, List, Tuple, Optional, Any
from math import radians, sin, cos, sqrt, atan2
import logging
import re
from .config import CHARGING_CONFIG, SEARCH_CONFIG, LOCATION_CONFIG, DATA_CONFIG

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
        """Get charging stations along a route between two locations"""
        # For now, return stations near the start location
        # Will be enhanced with TomTom API for actual route planning
        start_coords = self._get_location_coordinates(start_location)
        if start_coords:
            return self.get_nearby_stations(start_coords, radius_km=SEARCH_CONFIG['ROUTE_RADIUS_KM'])[:SEARCH_CONFIG['MAX_RESULTS']]
        return []

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
        """Get coordinates for a location name"""
        if self.coordinates_data.empty:
            # Fallback: search in charger dataset for suburb
            if not self.charger_data.empty:
                mask = self.charger_data[DATA_CONFIG['CSV_COLUMNS']['SUBURB']].str.lower(
                ).str.contains(location_name.lower(), na=False)
                charger_data = self.charger_data[mask]

                if not charger_data.empty:
                    station = charger_data.iloc[0]
                    try:
                        lat = float(station.get(
                            DATA_CONFIG['CSV_COLUMNS']['LATITUDE'], 0))
                        lon = float(station.get(
                            DATA_CONFIG['CSV_COLUMNS']['LONGITUDE'], 0))
                        if lat != 0 and lon != 0:
                            return (lat, lon)
                    except (ValueError, TypeError):
                        pass
            return None

        # Try coordinates dataset first
        location_lower = location_name.lower()
        mask = self.coordinates_data['suburb'].str.lower(
        ).str.contains(location_lower, na=False)
        location_data = self.coordinates_data[mask]

        if not location_data.empty:
            location_row = location_data.iloc[0]
            try:
                lat = float(location_row.get('latitude', 0))
                lon = float(location_row.get('longitude', 0))
                if lat != 0 and lon != 0:
                    return (lat, lon)
            except (ValueError, TypeError):
                pass

        # Fallback: search in charger dataset for suburb
        if not self.charger_data.empty:
            mask = self.charger_data[DATA_CONFIG['CSV_COLUMNS']['SUBURB']].str.lower(
            ).str.contains(location_lower, na=False)
            charger_data = self.charger_data[mask]

            if not charger_data.empty:
                station = charger_data.iloc[0]
                try:
                    lat = float(station.get(
                        DATA_CONFIG['CSV_COLUMNS']['LATITUDE'], 0))
                    lon = float(station.get(
                        DATA_CONFIG['CSV_COLUMNS']['LONGITUDE'], 0))
                    if lat != 0 and lon != 0:
                        return (lat, lon)
                except (ValueError, TypeError):
                    pass

        return None

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
