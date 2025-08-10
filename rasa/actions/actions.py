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
from backend.find_station import find_station
from backend.find_station import get_route_details
from backend.find_station import get_charging_station_availability
import pandas as pd

import csv #add to requirments.txt
import math #add to requirments.txt


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
# from rasa_sdk import Action, Tracker
# from rasa_sdk.executor import CollectingDispatcher
#
#
# class ActionHelloWorld(Action):
#
#     def name(self) -> Text:
#         return "action_hello_world"
#
#     def run(self, dispatcher: CollectingDispatcher,
#             tracker: Tracker,
#             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#
#         dispatcher.utter_message(text="Hello World!")
#
#         return []



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

            dispatcher.utter_message(text="I am finding the nearest charging station")
            result = find_station(user_location)
            location_of_station = str(result['Address'])
            dispatcher.utter_message(location_of_station)

            if result:            
                
                dispatcher.utter_message(text=f"Your closest charging station is {result['Name']}")
                dispatcher.utter_message(text=f"It is located at {result['Address']}")
                dispatcher.utter_message(text=f"It is about {result['Distance']} KM away")
                dispatcher.utter_message(text=f"This will take you about {result['ETA']} minutes")
                dispatcher.utter_message("Would you like directions or further information about this charging station")
                
               
                
                 
            else:
                dispatcher.utter_message("Sorry, no charger is currently available in your location")
        else:
            # No location available
            dispatcher.utter_message("Sorry, I couldn't retrieve your location.")
           
        with open("data\raw\ml_ev_charging_dataset.csv", "r") as file:
                reader = csv.reader(file)

                for row in reader:
                   if row[4].str.strip().str.lower() == result['Address'].str.strip().str.lower():
                       
                       charge_location_lat = row[3]
                       charge_location_long =row[2]
                       break 
                else:
                    print("sorry this location doesnt seem to have a charging station")

        return [SlotSet("station_latitude", charge_location_lat), SlotSet("station_longitude", charge_location_long)]
    

class ActionToChargingStation(Action):

    def name(self) -> Text:
        return "Action_To_Charging_Station" 
    
    

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        

        station = list(tracker.get_latest_entity_values("place")) #entity extraction
        metadata = tracker.latest_message.get('metadata', {})

        latitude = metadata.get("lat")
        longitude = metadata.get("lon")

        if not latitude and not longitude:
            latitude = -37.85580046992546
            longitude = 145.08025857057336
            # manual location due to geocoder not getting my location -37.85580046992546, 145.08025857057336

        
      
       #check if the location the user has specified as a charging station. 
        with open("data\raw\Co-oridnates.csv", "r") as file:
                reader = csv.reader(file)

                for row in reader:
                    if row[0].str.strip().str.lower() == station.str.strip().str.lower():
                        suburb_location_lat = row[1]
                        suburb_location_long = row[2]
                        break
                else:
                    print("sorry that location seems to not have a charging station.")
        


        #convert suburb location to charging station location. 
        with open("data\raw\ml_ev_charging_dataset.csv", "r") as file:
                reader = csv.reader(file)

                for row in reader:
                   if row[7] == suburb_location_lat and row[8] == suburb_location_long:
                       charge_location_lat = row[7]
                       charge_location_long =row[8]
                       break 
                else:
                    print("sorry this location doesnt seem to have a charging station")
        
        
    
        user_location = (longitude, latitude,)
        destination = (charge_location_long, charge_location_lat)
        
        if station:

            station_name = station[0]  
            dispatcher.utter_message("Would you like directions or further information about this charging station")
        else:
            
            dispatcher.utter_message(text="i did not extract a location")
     

        return [SlotSet("station_latitude", charge_location_lat), SlotSet("station_longitude", charge_location_long)]
    

       
    
    



class ActionHowLongToCharge(Action): 

    def name(self) -> Text:
        return "Action_How_Long_To_Charge" 
    

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        #all in kwh
        capacity = 100
        charge_rate = 5
        bat_charge = 0
        
        capacity_to_charge = capacity - (capacity * bat_charge)
        charge_time = capacity_to_charge/(charge_rate * 0.9)
        min, hour = math.modf(charge_time)
        min = round(min * 60)
        dispatcher.utter_message(text=f"it will take {int(hour)}hr {min}m to charge")
        
        return []
    
class ActionDistanceICanGo(Action):

    def name(self) -> Text:
        return "Action_Distence_I_Can_Go" 
    

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        #kwh
        capacity = 100
        #kwh/kelomity 
        consumption = 0.12


        bat_charge = 0.5
        capacity_to_charge = capacity - (capacity * bat_charge)
        distance = capacity_to_charge/consumption


        dispatcher.utter_message(text=f"you have about {distance}km before empty")
        
        return []

    

class ActionFilterStations(Action):

    def name(self) -> Text:
        return "Action_Filter_Stations"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        filter_preferences = tracker.get_slot("filter_preferences")

        if filter_preferences:
            dispatcher.utter_message(text=f"Filtering stations based on your preference: {filter_preferences}")
        else:
            dispatcher.utter_message(text="No filter preferences found. Showing all stations.")
        
        return []





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

        charge_location_lat = tracker.get_slot("station_latitude")
        charge_location_long = tracker.get_slot("station_longitude")

        if not charge_location_lat:
            dispatcher.utter_message(text="please tell us either a location or nearest location.")
            return []

        

        with open("data\raw\charger_info_mel.csv", "r") as file:
            reader = csv.reader(file)

            for row in reader:
                if row[9] == charge_location_lat and row[10] == charge_location_long:
                    dispatcher.utter_message(text="here is information about this charging startion.")
                    dispatcher.utter_message(text=f"power output {row[5]}")
                    dispatcher.utter_message(text=f"usage cost {row[6]}")
                    dispatcher.utter_message(text=f"number of chargers {row[7]}")
                    dispatcher.utter_message(text=f"connection types {row[8]}")
                else: 
                    dispatcher.utter_message(text="Sorry we dont have the required data for this charging station.")      
        
        return []
    

class ActionDefaultFallback(Action):

    def name(self) -> Text:
        return "Get_Directions_action"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        #get location in cords to the charging station through slots. then use "get ruite details" method to go to those coords

        metadata = tracker.latest_message.get('metadata', {})

        latitude = metadata.get("lat")
        longitude = metadata.get("lon")

        charge_location_lat = tracker.get_slot("station_latitude")
        charge_location_long = tracker.get_slot("station_longitude")

        if not latitude and not longitude:
            latitude = -37.85580046992546
            longitude = 145.08025857057336
            # manual location due to geocoder not getting my location -37.85580046992546, 145.08025857057336

        
        
        user_location = (longitude, latitude)
        station_location = (charge_location_long, charge_location_lat)

        result =  get_route_details(user_location, station_location)
        

        
        if "Instructions" in result:
            print("\nInstructions:")
            for i, instruction in enumerate(result["Instructions"], start=1):
                dispatcher.utter_message(text=(f"{i}. {instruction}"))


        print(result)

        return []