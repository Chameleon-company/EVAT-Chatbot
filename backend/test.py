import find_station
import json
import geocoder


# Main execution
if __name__ == "__main__":
    # Get the location based on IP address
    location = geocoder.ip("me") 
    # User location
    USER_LOCATION = (location.lng, location.lat) # (longitutde, latitude)



    # TomTom API key
    TOMTOM_API_KEY = "2p4OcGzjWEPmyw09G5I1hIDiwdX0Fd6i"

    # Configurable option
    INCLUDE_NAVIGATION = True
    RETURN_FULL_JSON = False  # Whether to return full route JSON or just the ETA/Route details


    top_station = find_station.find_station(USER_LOCATION, TOMTOM_API_KEY, INCLUDE_NAVIGATION, RETURN_FULL_JSON)
    if top_station:
        
        print("\nYour closest available charging station is", top_station['Name'], "\nLocated at", top_station['Address'], top_station['Location'])
        print(f"\nDistance: {top_station['Distance']:.2f} km")
        print(f"ETA: {top_station['ETA']:.2f} minutes")
        # print(f"Address: {top_station['Address']}")

        if "Instructions" in top_station:
            print("\nInstructions:")
            for i, instruction in enumerate(top_station["Instructions"], start=1):
                print(f"{i}. {instruction}")

        if "full_json" in top_station:
            print("\n--- Full JSON (raw routing data) ---")
            print(json.dumps(top_station["full_json"], indent=2))  # Nicely formatted JSON

    else:
        print("No available charging stations found.")