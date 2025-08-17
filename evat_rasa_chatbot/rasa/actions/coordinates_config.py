# Configuration file for user coordinates and location settings
# This file makes it easy to change hardcoded coordinates for testing

# HARDCODED CURRENT USER LOCATION for ETA calculations
# Change these coordinates to set the user's current location
# This will be replaced with TomTom API integration later
CURRENT_USER_LOCATION = {
    "latitude": -37.8136,    # Melbourne CBD - CHANGE THIS TO YOUR LOCATION
    "longitude": 144.9631,   # Melbourne CBD - CHANGE THIS TO YOUR LOCATION
    "name": "Melbourne CBD",  # Location name for display
    "suburb": "Melbourne CBD"
}


def get_current_user_location() -> tuple:
    """
    Get the hardcoded current user location for ETA calculations
    This will be replaced with TomTom API integration later

    Returns:
        tuple: (latitude, longitude) coordinates of current user location
    """
    return (CURRENT_USER_LOCATION["latitude"], CURRENT_USER_LOCATION["longitude"])


def get_current_user_location_info() -> dict:
    """
    Get complete information about the current user location
    This will be replaced with TomTom API integration later

    Returns:
        dict: Complete location information including name and suburb
    """
    return CURRENT_USER_LOCATION.copy()
