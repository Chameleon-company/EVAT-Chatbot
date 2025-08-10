# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

import arrow
import dateparser
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from typing import Any, Text, Dict, List
from backend.find_station import find_available_station, find_station, get_coordinates, get_nearby_stations
from backend.find_station import get_route_details
from backend.find_station import get_charging_station_availability
import pandas as pd

class ActionGetNearestStation(Action):

    def name(self) -> Text:
        return "Action_Get_Nearest_Station"  

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Retrieve the latest message's metadata, it shoiuld have latitude and longitude
        metadata = tracker.latest_message.get('metadata', {})

        latitude = metadata.get("lat")
        longitude = metadata.get("lon")

        if not latitude and not longitude:
            latitude = -37.85580046992546
            longitude = 145.08025857057336
            # manual location due to geocoder not getting my location -37.85580046992546, 145.08025857057336

        
        
        user_location = (longitude, latitude)
        
        if latitude and longitude:

            dispatcher.utter_message(text="I am fetching the nearest station information.")
            result = find_station(user_location)
            

            if result:            
                
                dispatcher.utter_message(text=f"Your closest charging station is {result['Name']}")
                dispatcher.utter_message(text=f"It is located at {result['Address']}")
                dispatcher.utter_message(text=f"It is about {result['Distance']} KM away")
                dispatcher.utter_message(text=f"This will take you about {result['ETA']} minutes")
                dispatcher.utter_message("Would you like directions?")
                
                return [SlotSet("Charger Name", result['Address'])] 
            else:
                dispatcher.utter_message("Sorry, no charger is currently available in your location")
        else:
            # No location available
            dispatcher.utter_message("Sorry, I couldn't retrieve your location.")
            return []
    

class ActionToChargingStation(Action):

    def name(self) -> Text:
        return "Action_To_Charging_Station" 
    
    

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        area = station = list(tracker.get_latest_entity_values("place"))
        metadata = tracker.latest_message.get('metadata', {})

        latitude = metadata.get("lat")
        longitude = metadata.get("lon")

        # dispatcher.utter_message(text=f"I am fetching the route to the charging station in {station} with ({latitude},{longitude}) with metadata:{metadata}.\n latest message: {tracker.latest_message}")
        
        if not latitude and not longitude:
            latitude = -37.85580046992546
            longitude = 145.08025857057336
            # manual location due to geocoder not getting my location -37.85580046992546, 145.08025857057336
        user_location = (longitude, latitude,)

        nearby_stations = find_available_station(get_coordinates(area))
        # print("Nearby stations:", nearby_stations)
        dispatcher.utter_message(text=f"Nearby stations:  ")
        for station in nearby_stations:
            dispatcher.utter_message(text=f"{station['Name']} at {station['Address']} - {station['Distance']} KM away - {station['ETA']} minutes")
        # print("Nearby stations:", nearby_stations)
        # df = pd.read_csv("datasets/Co-oridnates.csv")
        # df = df.astype(str)
        # charging_station = df[df["suburb"].str.strip().str.lower() == station[0]]
        # station_info = charging_station.iloc[0]
        station_info = nearby_stations[0]
        destination = (station_info['Location'][0], station_info['Location'][1])
       
        if station:
            # station_name = station[0]  
            dispatcher.utter_message(text=f"I understand. Taking you to the {station_info['Name']} charging station from {user_location} to {destination}.")
            
            result = get_route_details(user_location, destination)

            if result:
                    directions = result["instructions"]
                    for step in directions:
                     dispatcher.utter_message(text=(step))
            else:
                print("Could not retrieve route directions.")
            
            

        else:
            
            dispatcher.utter_message(text="i did not extract a location")
        











        return []
    

       
    
    



class ActionHowLongToCharge(Action): 

    def name(self) -> Text:
        return "Action_How_Long_To_Charge" 
    

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text="It takes 20hr on slow, 12hr on 7kw fast, 7hr on 22kw fast, 1 hr on 43-50kw rapid, 30min on 150kw charge")
        
        
        return []
    
class ActionDistanceICanGo(Action):

    def name(self) -> Text:
        return "Action_Distence_I_Can_Go" 
    

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text="depending on your car and driving style. you can expect between. 320 to 480km on a full charge")
        
        
        return []

    

class ActionFilterStations(Action):

    def name(self) -> Text:
        return "Action_Filter_Stations"

    def get_connector_type_code(self, connector_type: str) -> str:
        connector_mapping = {
            'type 2': 'IEC_62196_2_TYPE_2',
            'ccs': 'IEC_62196_3_COMBO_2',
            'chademo': 'CHADEMO',
            'tesla': 'TESLA'
        }
        return connector_mapping.get(connector_type.lower())

    def get_power_level(self, speed: str) -> float:
        speed_mapping = {
            'ultra-fast': 150.0,
            'rapid': 100.0,
            'fast': 50.0,
            'standard': 22.0,
            'slow': 3.7
        }
        return speed_mapping.get(speed.lower(), 50.0)

    def extract_preferences_from_entities(self, tracker: Tracker) -> Dict[str, Any]:
        preferences = {
            'connectorTypes': [],
            'minPowerKW': None,
            'chargingSpeed': None,
            'availability': False,
            'pricePreference': None
        }
        
        # Extract connector types
        for connector in tracker.get_latest_entity_values("connector_type"):
            if code := self.get_connector_type_code(connector):
                preferences['connectorTypes'].append(code)
        
        # Extract charging speed and power level
        charging_speed = next(tracker.get_latest_entity_values("charging_speed"), None)
        power_level = next(tracker.get_latest_entity_values("power_level"), None)
        
        if power_level:
            preferences['minPowerKW'] = float(power_level)
            # Determine charging speed based on power level
            if float(power_level) >= 150:
                preferences['chargingSpeed'] = 'ultra-fast'
            elif float(power_level) >= 50:
                preferences['chargingSpeed'] = 'fast'
            else:
                preferences['chargingSpeed'] = 'standard'
        elif charging_speed:
            preferences['minPowerKW'] = self.get_power_level(charging_speed)
            preferences['chargingSpeed'] = charging_speed.lower()
        
        # Extract price preference
        price = next(tracker.get_latest_entity_values("price"), None)
        if price:
            if price.lower() in ['free', 'no cost']:
                preferences['pricePreference'] = 'free'
            elif any(word in price.lower() for word in ['cheap', 'affordable', '$']):
                preferences['pricePreference'] = 'low'
        
        return preferences

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        preferences = self.extract_preferences_from_entities(tracker)
        dispatcher.utter_message(f"{tracker.latest_message}")
        # print(f"Extracted preferences: {preferences}")
        # dispatcher.utter_message(f"Extracted preferences: {preferences}")
        
        if any(preferences.values()):
            response_text = "I understand you're looking for charging stations with these criteria:\n"
            
            # Connector types
            if preferences['connectorTypes']:
                connector_names = [conn.replace('IEC_62196_', '').replace('_', ' ').title() for conn in preferences['connectorTypes']]
                response_text += f"- Connector types: {', '.join(connector_names)}\n"
            
            # Charging speed and power level
            if preferences['chargingSpeed'] or preferences['minPowerKW']:
                speed_text = preferences['chargingSpeed'].replace('-', ' ').title() if preferences['chargingSpeed'] else ''
                power_text = f" ({preferences['minPowerKW']}+ kW)" if preferences['minPowerKW'] else ''
                response_text += f"- {speed_text} charging{power_text}\n"
            
            # Price preference
            if preferences['pricePreference']:
                response_text += f"- Price preference: {preferences['pricePreference'].title()}\n"
            
            dispatcher.utter_message(text=response_text)
            
            # Convert preferences to JSON string for storage
            import json
            preferences_json = json.dumps(preferences)
        else:
            dispatcher.utter_message(text="I couldn't identify specific preferences. You can specify:\n"
                                       "- Connector types (Type 2, CCS, CHAdeMO, Tesla)\n"
                                       "- Charging speed (Fast, Ultra-fast)\n"
                                       "- Power level (e.g., 50kW, 150kW)\n"
                                       "- Price preference (Free, Affordable)")
            preferences_json = "{}"
        
        return [SlotSet("filter_preferences", preferences_json)]





class ActionTrafficInfo(Action):

    def name(self) -> Text:
        return "Action_Traffic_Info"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="Sorry, I couldn't fetch traffic information at the moment. Please try again later.")
        return []






class ActionDefaultFallback(Action):

    def name(self) -> Text:
        return "action_default_fallback"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="Sorry, I didn't get that. Can you rephrase?")
        return []
    

class ActionChargerInfo(Action):

    def name(self) -> Text:
        return "Action_charger_info"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        df = pd.read_csv("datasets/charger_info_mel.csv")
        df = df.astype(str)
        address = tracker.get_slot("Charger Name")
        
        if not address:
            dispatcher.utter_message(text=f"Sorry, I couldn't find which charging station you meant {address}")
            return []
        
        print("\n\n\n", address, "\n\n\n")
        dispatcher.utter_message(text="Sure, here are important information about the charging station.")
        
        
        charging_station = df[df["Address"].str.strip().str.lower() == address.strip().lower()]
        print(address)
        print(address)
        print(address)
        print(charging_station)
            
        if not charging_station.empty:
            station_info = charging_station.iloc[0]  

            dispatcher.utter_message(text=f"Suburb: {station_info['City']}")
            dispatcher.utter_message(text=f"Power output: {station_info['Power (kW)']} kW")
            dispatcher.utter_message(text=f"Usage costs: {station_info['Usage Cost']}")
            dispatcher.utter_message(text=f"Total charges: {station_info['Number of Points']}")
            dispatcher.utter_message(text=f"Connection type: {station_info['Connection Types']}")
            #get_charging_station_availability()
        else:
            dispatcher.utter_message(text=f"sorry we are unable to get details from the {address} charging station")
            
        
        return []
    

class ActionDefaultFallback(Action):

    def name(self) -> Text:
        return "Get_Directions_action"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        

        metadata = tracker.latest_message.get('metadata', {})

        latitude = metadata.get("lat")
        longitude = metadata.get("lon")

        if not latitude and not longitude:
            latitude = -37.85580046992546
            longitude = 145.08025857057336
            # manual location due to geocoder not getting my location -37.85580046992546, 145.08025857057336

        
        
        user_location = (longitude, latitude)

        result = find_station(user_location)
        dispatcher.utter_message(text=f"Your closest charging station is {result['Instructions']}")
        
        if "Instructions" in result:
            print("\nInstructions:")
            for i, instruction in enumerate(result["Instructions"], start=1):
                dispatcher.utter_message(text=(f"{i}. {instruction}"))


        print(result)

        return []