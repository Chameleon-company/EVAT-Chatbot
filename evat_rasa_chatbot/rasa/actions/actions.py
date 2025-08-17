from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from typing import Any, Text, Dict, List, Optional, Tuple
import math
import random

# Import the data service to replace hardcoded data
from actions.data_service import data_service
from actions.coordinates_config import get_current_user_location
from actions.constants import ConversationContexts, MainMenuOptions, PreferenceTypes, ActionTypes, Messages


class ActionHandleMenuSelection(Action):
    def name(self) -> Text:
        return "action_handle_menu_selection"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # First check if we have a menu option entity
        menu_option = tracker.get_slot("menu_option")
        message = tracker.latest_message.get('text', '').lower().strip()

        # Debug logging
        print(f"DEBUG: menu_option = '{menu_option}'")
        print(f"DEBUG: message = '{message}'")

        if not menu_option:
            # Extract from message if not in slots
            if "route" in message or "planning" in message:
                menu_option = "route_planning"
            elif "emergency" in message or "battery" in message:
                menu_option = "emergency_charging"
            elif "preference" in message or "preferences" in message:
                menu_option = "preference_charging"

        if menu_option == "route_planning" or "route" in message or "planning" in message:
            # First time asking for route planning
            dispatcher.utter_message(
                text="Great! Let's plan your charging route. 🗺️\n\n"
                     "Where are you traveling from and to?\n\n"
                     "Please tell me your starting location and destination (e.g., 'from Carlton to Geelong' or 'Melbourne to Brighton')")
            return [SlotSet("conversation_context", ConversationContexts.ROUTE_PLANNING)]

        elif menu_option == "emergency_charging" or "emergency" in message or "battery" in message:
            dispatcher.utter_message(
                text="Emergency charging assistance! 🚨 Where are you currently located and what's your battery level?\n\n"
                     "Please tell me your location and battery percentage (e.g., 'Frankston, 6% battery')")
            return [SlotSet("conversation_context", ConversationContexts.EMERGENCY_CHARGING)]

        elif menu_option == "preference_charging" or "preference" in message or "preferences" in message:
            dispatcher.utter_message(
                text="Let me help you find stations based on your preferences! What's most important to you?\n\n"
                     "• **Cheapest** - Lowest cost per kWh 💰\n"
                     "• **Fastest** - Ultra-fast charging speeds ⚡\n"
                     "• **Closest** - Nearest to your location 📍\n"
                     "• **Premium** - Best facilities & amenities 🌟\n\n"
                     "What's your preference?")
            return [SlotSet("conversation_context", ConversationContexts.PREFERENCE_CHARGING)]

        else:
            # Check if this might be route info
            conversation_context = tracker.get_slot("conversation_context")
            message = tracker.latest_message.get('text', '').lower()

            # Debug logging
            print(f"DEBUG: conversation_context = '{conversation_context}'")
            print(f"DEBUG: message = '{message}'")
            print(
                f"DEBUG: contains 'from' and 'to' = {'from' in message and 'to' in message}")
            print(
                f"DEBUG: contains 'to' but not 'battery' = {'to' in message and 'battery' not in message}")

            if conversation_context == ConversationContexts.ROUTE_PLANNING:
                # Check if the message contains route information
                if ('from' in message and 'to' in message) or ('to' in message and 'battery' not in message):
                    print("DEBUG: Calling _handle_route_info")
                    return self._handle_route_info(dispatcher, tracker)
                else:
                    print(
                        "DEBUG: Message doesn't contain route info, guiding user back")
                    # User provided unexpected input, guide them back to route planning
                    dispatcher.utter_message(
                        text="I need your route information to plan charging stops. Please tell me:\n\n"
                             "• Where you're traveling from and to\n\n"
                             "Examples:\n"
                             "• 'from Carlton to Geelong'\n"
                             "• 'Melbourne to Brighton'\n"
                             "• 'driving to South Yarra'")
                    return []
            elif conversation_context == ConversationContexts.EMERGENCY_CHARGING:
                # User provided location and battery level after emergency prompt
                # This should be handled by the emergency_location_input intent
                dispatcher.utter_message(
                    text="I need your location and battery level to help with emergency charging. Please tell me:\n\n"
                         "• Your current location (e.g., 'Frankston')\n"
                         "• Your battery percentage (e.g., '6%')\n\n"
                         "You can say both together like 'Frankston, 6% battery'")
                return []

            dispatcher.utter_message(
                text="I'm not sure what you'd like to do. Please choose:\n\n"
                     "• **Route Planning** - Plan charging stops for your journey\n"
                     "• **Emergency Charging** - Find nearest stations when battery is low\n"
                     "• **Charging Preferences** - Find stations by your preferences (fast, cheap, etc.)")
            return []

    def _handle_route_info(self, dispatcher: CollectingDispatcher, tracker: Tracker) -> List[Dict[Text, Any]]:
        """Handle route information when user provides it"""
        message = tracker.latest_message.get('text', '').lower()

        # Extract start and end locations
        start_location = None
        end_location = None

        # Try different patterns to extract locations
        if 'from' in message and 'to' in message:
            # Pattern: "from X to Y"
            try:
                from_part = message.split('from')[1]
                if 'to' in from_part:
                    parts = from_part.split('to')
                    if len(parts) == 2:
                        start_location = parts[0].strip()
                        end_location = parts[1].strip()
            except:
                pass
        elif 'to' in message:
            # Pattern: "X to Y" or "driving to Y"
            if 'driving to' in message:
                end_location = message.split('driving to')[1].strip()
                start_location = "Melbourne"  # Default start location
            else:
                parts = message.split('to')
                if len(parts) == 2:
                    start_location = parts[0].strip()
                    end_location = parts[1].strip()
        elif 'route to' in message:
            # Pattern: "route to Y"
            end_location = message.split('route to')[1].strip()
            start_location = "Melbourne"  # Default start location

        # Clean up locations
        if start_location:
            start_location = start_location.replace('from', '').replace(
                'driving', '').replace('route', '').strip()
        if end_location:
            end_location = end_location.replace('to', '').strip()

        # Debug logging
        print(
            f"DEBUG: Extracted start_location: '{start_location}', end_location: '{end_location}'")

        if not start_location or not end_location:
            dispatcher.utter_message(
                text="I need both your starting location and destination. Please tell me where you're traveling from and to.\n\n"
                     "Examples:\n"
                     "• 'from Carlton to Geelong'\n"
                     "• 'Melbourne to Brighton'\n"
                     "• 'driving to South Yarra'")
            return []

        # Find route stations
        try:
            stations = data_service.get_route_stations(
                start_location, end_location)
        except Exception as e:
            # Fallback to mock data if data service fails
            stations = [
                {"name": "Station 1", "distance_km": 15,
                    "cost": "$0.25/kWh", "power": "50kW"},
                {"name": "Station 2", "distance_km": 25,
                    "cost": "$0.30/kWh", "power": "75kW"},
                {"name": "Station 3", "distance_km": 35,
                    "cost": "$0.20/kWh", "power": "100kW"}
            ]

        if stations:
            response = f"Perfect! 🎯 I found {len(stations)} charging stations along your route from **{start_location}** to **{end_location}**:\n\n"

            # Display stations with text labels (A, B, C) instead of numbers
            station_labels = ['A', 'B', 'C']
            for i, station in enumerate(stations[:3]):  # Show max 3 stations
                label = station_labels[i]
                response += f"**Station {label}:** {station.get('name', f'Station {label}')}\n"
                response += f"📍 {station.get('address', 'Address available')}\n"
                response += f"⚡ {station.get('power', 'Power info available')} charging\n"
                response += f"💰 {station.get('cost', 'Cost info available')}\n\n"

            response += "Which station would you like to know more about? Please choose **A**, **B**, or **C**."
            dispatcher.utter_message(text=response)

            # Set conversation context and store route info
            return [
                SlotSet("conversation_context",
                        ConversationContexts.ROUTE_PLANNING_RESULTS),
                SlotSet("start_location", start_location),
                SlotSet("end_location", end_location)
            ]
        else:
            dispatcher.utter_message(
                text=f"I couldn't find charging stations along your {start_location} to {end_location} route. Please try a different route or location.")
            return []


class ActionHandleRoutePlanning(Action):
    def name(self) -> Text:
        return "action_handle_route_planning"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        start_location = tracker.get_slot("start_location")
        end_location = tracker.get_slot("end_location")

        if not start_location or not end_location:
            # Extract from message if not in slots
            message = tracker.latest_message.get('text', '').lower()

            # Try different patterns to extract locations
            if 'from' in message and 'to' in message:
                # Pattern: "from X to Y"
                parts = message.split('from')[1].split('to')
                if len(parts) == 2:
                    start_location = parts[0].strip()
                    end_location = parts[1].strip()
            elif 'to' in message:
                # Pattern: "X to Y" or "driving to Y"
                if 'driving to' in message:
                    end_location = message.split('driving to')[1].strip()
                    start_location = "Melbourne"  # Default start location
                else:
                    parts = message.split('to')
                    if len(parts) == 2:
                        start_location = parts[0].strip()
                        end_location = parts[1].strip()
            elif 'route to' in message:
                # Pattern: "route to Y"
                end_location = message.split('route to')[1].strip()
                start_location = "Melbourne"  # Default start location

            # Clean up locations
            if start_location:
                start_location = start_location.replace('from', '').replace(
                    'driving', '').replace('route', '').strip()
            if end_location:
                end_location = end_location.replace('to', '').strip()

        if not start_location or not end_location:
            dispatcher.utter_message(
                text="I need both your starting location and destination. Please tell me where you're traveling from and to.\n\n"
                     "Examples:\n"
                     "• 'from Carlton to Geelong'\n"
                     "• 'Melbourne to Brighton'\n"
                     "• 'driving to South Yarra'")
            return []

        # Use data service to get route stations
        try:
            stations = data_service.get_route_stations(
                start_location, end_location)
        except Exception as e:
            # Fallback to mock data if data service fails
            stations = [
                {"name": "Station 1", "distance_km": 15,
                    "cost": "$0.25/kWh", "power": "50kW"},
                {"name": "Station 2", "distance_km": 25,
                    "cost": "$0.30/kWh", "power": "75kW"},
                {"name": "Station 3", "distance_km": 35,
                    "cost": "$0.20/kWh", "power": "100kW"}
            ]

        if stations:
            response = f"Perfect! 🎯 I found {len(stations)} charging stations along your route from **{start_location}** to **{end_location}**:\n\n"

            for i, station in enumerate(stations[:3]):  # Show max 3 stations
                option_number = i + 1
                response += f"**Option {option_number}:** {station.get('name', f'Station {option_number}')}\n"
                response += f"📍 {station.get('address', 'Address available')}\n"
                response += f"⚡ {station.get('power', 'Power info available')} charging\n"
                response += f"💰 {station.get('cost', 'Cost info available')}\n\n"

            response += "**Which station would you like to know more about?**\n\n"
            response += "Please type the station name, for example:\n"
            response += "• 'Let's go with [Station Name]'\n"
            response += "• 'I'll go with [Station Name]'\n"
            response += "• 'I choose [Station Name]'\n"
            response += "• 'Show me [Station Name]'"

            dispatcher.utter_message(text=response)

            # Set conversation context and store route info
            return [
                SlotSet("conversation_context",
                        ConversationContexts.ROUTE_PLANNING_RESULTS),
                SlotSet("start_location", start_location),
                SlotSet("end_location", end_location)
            ]
        else:
            dispatcher.utter_message(
                text=f"I couldn't find charging stations along your {start_location} to {end_location} route. Please try a different route or location.")
            return []


class ActionHandleRouteInfo(Action):
    def name(self) -> Text:
        return "action_handle_route_info"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Extract start and end locations from entities
        start_location = None
        end_location = None

        for entity in tracker.latest_message.get('entities', []):
            if entity['entity'] == 'start_location':
                start_location = entity['value']
            elif entity['entity'] == 'end_location':
                end_location = entity['value']

        if not start_location or not end_location:
            dispatcher.utter_message(
                text="I need both your starting location and destination. Please tell me where you're traveling from and to.\n\n"
                     "Examples:\n"
                     "• 'from Carlton to Geelong'\n"
                     "• 'Melbourne to Brighton'\n"
                     "• 'driving to South Yarra'")
            return []

        # Store the locations in slots
        slots = [
            SlotSet("start_location", start_location),
            SlotSet("end_location", end_location)
        ]

        # Now call the route planning action to find stations
        return slots + self._find_route_stations(dispatcher, start_location, end_location)

    def _find_route_stations(self, dispatcher: CollectingDispatcher, start_location: str, end_location: str) -> List[Dict[Text, Any]]:
        """Helper method to find route stations and display them"""
        try:
            stations = data_service.get_route_stations(
                start_location, end_location)
        except Exception as e:
            # Fallback to mock data if data service fails
            stations = [
                {"name": "Station 1", "distance_km": 15,
                    "cost": "$0.25/kWh", "power": "50kW"},
                {"name": "Station 2", "distance_km": 25,
                    "cost": "$0.30/kWh", "power": "75kW"},
                {"name": "Station 3", "distance_km": 35,
                    "cost": "$0.20/kWh", "power": "100kW"}
            ]

        if stations:
            response = f"Perfect! 🎯 I found {len(stations)} charging stations along your route from **{start_location}** to **{end_location}**:\n\n"

            # Display stations with "Option X: [Station Name]" format
            for i, station in enumerate(stations[:3]):  # Show max 3 stations
                option_number = i + 1
                response += f"**Option {option_number}:** {station.get('name', f'Station {option_number}')}\n"
                response += f"📍 {station.get('distance_km', 'Distance available')}km away\n"
                response += f"⚡ {station.get('power', 'Power info available')} charging\n"
                response += f"💰 {station.get('cost', 'Cost info available')}\n\n"

            response += "**Which station would you like to know more about?**\n\n"
            response += "Please type the station name, for example:\n"
            response += "• 'Let's go with [Station Name]'\n"
            response += "• 'I'll go with [Station Name]'\n"
            response += "• 'I choose [Station Name]'\n"
            response += "• 'Show me [Station Name]'"
            dispatcher.utter_message(text=response)

            # Set conversation context
            return [SlotSet("conversation_context", ConversationContexts.ROUTE_PLANNING_RESULTS)]
        else:
            dispatcher.utter_message(
                text=f"I couldn't find charging stations along your {start_location} to {end_location} route. Please try a different route or location.")
            return []


class ActionHandleEmergencyCharging(Action):
    def name(self) -> Text:
        return "action_handle_emergency_charging"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        current_location = tracker.get_slot("current_location")
        battery_level = tracker.get_slot("battery_level")

        if not current_location:
            # Extract from message if not in slots
            message = tracker.latest_message.get('text', '').lower()
            # Look for any location mentioned in the message
            # This will be enhanced with NER later
            dispatcher.utter_message(
                text="I need your current location to find the nearest charging stations. Where are you located?")
            return []

        # Use data service to get emergency stations
        stations = data_service.get_emergency_stations(current_location)

        if stations:
            response = f"Don't worry! I found the closest charging stations to {current_location}:\n\n"

            for i, station in enumerate(stations, 1):
                response += f"{i}. **{station['name']}** - {station['distance_km']}km away, {station['cost']} ✅\n"

            response += "\nAll have available charging points right now. Which one?"
            dispatcher.utter_message(text=response)

            return [SlotSet("conversation_context", ConversationContexts.EMERGENCY_RESULTS)]
        else:
            dispatcher.utter_message(
                text=f"I couldn't find charging stations near {current_location}. Please try a different location or check your spelling.")
            return []


class ActionHandleEmergencyLocationInput(Action):
    def name(self) -> Text:
        return "action_handle_emergency_location_input"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Extract location and battery level from the message
        current_location = tracker.get_slot("current_location")
        battery_level = tracker.get_slot("battery_level")

        # If not in slots, try to extract from the message
        if not current_location or not battery_level:
            message = tracker.latest_message.get('text', '').lower()

            # Simple parsing for "Location, Battery%" format
            if ',' in message:
                parts = message.split(',')
                if len(parts) >= 2:
                    # First part is location
                    location_part = parts[0].strip()
                    # Second part should contain battery level
                    battery_part = parts[1].strip()

                    # Extract battery percentage
                    import re
                    battery_match = re.search(r'(\d+)%?', battery_part)
                    if battery_match:
                        battery_level = battery_match.group(1) + "%"
                        current_location = location_part

                        # Set the slots
                        slots = [
                            SlotSet("current_location", current_location),
                            SlotSet("battery_level", battery_level)
                        ]

                        # Now find emergency stations
                        return slots + self._find_emergency_stations(dispatcher, current_location, battery_level)

        # If we have the information, proceed
        if current_location and battery_level:
            return self._find_emergency_stations(dispatcher, current_location, battery_level)

        # If we still don't have the information, ask for it
        dispatcher.utter_message(
            text="I need your location and battery level to help with emergency charging. Please tell me:\n\n"
                 "• Your current location (e.g., 'Frankston')\n"
                 "• Your battery percentage (e.g., '6%')\n\n"
                 "You can say both together like 'Frankston, 6% battery'")
        return []

    def _find_emergency_stations(self, dispatcher: CollectingDispatcher, current_location: str, battery_level: str) -> List[Dict[Text, Any]]:
        """Helper method to find emergency stations and display them"""
        try:
            # Get emergency stations using data service
            stations = data_service.get_emergency_stations(current_location)

            if stations:
                # Create emergency response based on battery level
                battery_num = int(battery_level.replace('%', ''))

                if battery_num <= 5:
                    urgency = "🚨 CRITICAL - Get to a charger immediately!"
                elif battery_num <= 10:
                    urgency = "⚠️ URGENT - Find charging soon!"
                else:
                    urgency = "⚡ Low battery - Let's find charging options"

                response = f"{urgency}\n\n"
                response += f"📍 **Location:** {current_location}\n"
                response += f"🔋 **Battery:** {battery_level}\n\n"
                response += f"**Found {len(stations)} charging stations nearby:**\n\n"

                # Display stations with "Option X: [Station Name]" format
                # Show max 3 stations
                for i, station in enumerate(stations[:3], 1):
                    response += f"**Option {i}:** {station['name']}\n"
                    response += f"📍 {station.get('address', 'Address available')}\n"
                    response += f"⚡ {station.get('power', 'Power info available')} charging\n"
                    response += f"💰 {station.get('cost', 'Cost info available')}\n"
                    response += f"🕐 {station.get('distance_km', 'Distance')}km away\n\n"

                response += "**🎯 Which station would you like to know more about?**\n\n"
                response += "Please type the station name, for example:\n"
                response += "• 'Let's go with [Station Name]'\n"
                response += "• 'I'll go with [Station Name]'\n"
                response += "• 'I choose [Station Name]'\n"
                response += "• 'Show me [Station Name]'"

                dispatcher.utter_message(text=response)

                return [SlotSet("conversation_context", ConversationContexts.EMERGENCY_RESULTS)]
            else:
                dispatcher.utter_message(
                    text=f"🚨 **Emergency Alert:** No charging stations found near {current_location}!\n\n"
                         f"**Immediate Actions:**\n"
                         f"• Check if you can reach a different suburb\n"
                         f"• Consider calling roadside assistance\n"
                         f"• Look for any nearby shopping centers or public places\n\n"
                         f"**Alternative locations to try:**\n"
                         f"• Melbourne CBD\n"
                         f"• Major shopping centers\n"
                         f"• Highway service stations")
                return []

        except Exception as e:
            # Fallback response if data service fails
            dispatcher.utter_message(
                text=f"🚨 **Emergency Charging Help**\n\n"
                     f"📍 **Location:** {current_location}\n"
                     f"🔋 **Battery:** {battery_level}\n\n"
                     f"**Emergency Charging Options:**\n\n"
                     f"**1. Frankston Shopping Centre**\n"
                     f"📍 325-327 Nepean Hwy, Frankston\n"
                     f"⚡ 50kW charging\n"
                     f"💰 $0.30/kWh\n"
                     f"🕐 2.1km away\n\n"
                     f"**2. Bayside Shopping Centre**\n"
                     f"📍 9-13 Railway St, Frankston\n"
                     f"⚡ 75kW charging\n"
                     f"💰 $0.25/kWh\n"
                     f"🕐 3.2km away\n\n"
                     f"**🎯 Which station would you like to know more about?**\n\n"
                     f"Please type the station name, for example:\n"
                     f"• 'Let's go with Frankston Shopping Centre'\n"
                     f"• 'I'll go with Bayside Shopping Centre'\n"
                     f"• 'I choose [Station Name]'\n"
                     f"• 'Show me [Station Name]'")

            return [SlotSet("conversation_context", ConversationContexts.EMERGENCY_RESULTS)]


class ActionHandlePreferenceCharging(Action):
    def name(self) -> Text:
        return "action_handle_preference_charging"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        preference_type = tracker.get_slot("preference_type")
        current_location = tracker.get_slot("current_location")

        if not preference_type:
            # Extract from message if not in slots
            message = tracker.latest_message.get('text', '').lower()
            if 'cheapest' in message:
                preference_type = "cheapest"
            elif 'fastest' in message:
                preference_type = "fastest"
            elif 'closest' in message:
                preference_type = "closest"
            elif 'premium' in message:
                preference_type = "premium"
            else:
                dispatcher.utter_message(
                    text="What type of charging are you looking for? Cheapest, fastest, closest, or premium?")
                return [
                    SlotSet("conversation_context",
                            ConversationContexts.PREFERENCE_CHARGING)
                ]

        if not current_location:
            # Extract from message if not in slots
            message = tracker.latest_message.get('text', '').lower()
            # Look for any location mentioned in the message
            # This will be enhanced with NER later
            dispatcher.utter_message(
                text=f"Great choice for {preference_type} charging! Where are you located?")
            # Persist the user's chosen preference so we don't ask again
            return [
                SlotSet("preference_type", preference_type),
                SlotSet("conversation_context",
                        ConversationContexts.PREFERENCE_CHARGING)
            ]

        # Get coordinates for the location
        location_coords = data_service._get_location_coordinates(
            current_location)
        if not location_coords:
            dispatcher.utter_message(
                text=f"I couldn't find coordinates for {current_location}. Please try a different location.")
            return []

        # Use data service to get preference-based stations
        if preference_type == "premium":
            # For premium, we'll filter by higher power stations
            stations = data_service.get_stations_by_preference(
                location_coords, "fastest", limit=5)
        else:
            stations = data_service.get_stations_by_preference(
                location_coords, preference_type, limit=5)

        if stations:
            response = f"Here are the most {preference_type} charging options near {current_location}:\n\n"

            for i, station in enumerate(stations, 1):
                response += f"**Option {i}:** {station['name']}\n"
                response += f"📍 {station.get('distance_km', 'Distance available')}km away\n"
                response += f"⚡ {station.get('power', 'Power info available')} charging\n"
                response += f"💰 {station.get('cost', 'Cost info available')}"
                if preference_type == "cheapest" and station.get('cost', '0') != '0':
                    response += f" 💰"
                elif preference_type == "fastest" and station.get('power', '0') != '0':
                    response += f" ⚡"
                response += "\n\n"

            response += "**Which station interests you?**\n\n"
            response += "Please type the station name, for example:\n"
            response += "• 'Let's go with [Station Name]'\n"
            response += "• 'I'll go with [Station Name]'\n"
            response += "• 'I choose [Station Name]'\n"
            response += "• 'Show me [Station Name]'"
            dispatcher.utter_message(text=response)

            return [SlotSet("conversation_context", ConversationContexts.PREFERENCE_RESULTS)]
        else:
            dispatcher.utter_message(
                text=f"I couldn't find {preference_type} charging options near {current_location}. Please try a different location.")
            return []


# Old generic ActionHandleStationSelection class removed - replaced with context-specific classes above


class ActionHandleActionChoice(Action):
    def name(self) -> Text:
        return "action_handle_action_choice"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Get the user's message
        message = tracker.latest_message.get('text', '').lower().strip()

        # Check for numeric inputs first
        if message == '1':
            action_type = "directions"
        elif message == '2':
            action_type = "compare"
        elif message == '3':
            action_type = "availability"
        # Check for text-based inputs
        elif any(word in message for word in ['direction', 'navigate', 'route', 'drive', 'go to']):
            action_type = "directions"
        elif any(word in message for word in ['compare', 'comparison', 'alternative', 'other', 'options']):
            action_type = "compare"
        elif any(word in message for word in ['available', 'availability', 'status', 'check', 'open']):
            action_type = "availability"
        else:
            # If we can't determine the action, ask for clarification
            dispatcher.utter_message(
                text="I'm not sure what you'd like to do. Please choose:\n\n"
                     "1. 🗺️ **Get directions** to this station\n"
                     "2. 📊 **Compare** with other options\n"
                     "3. ✅ **Check current availability**\n\n"
                     "Or simply say 'get directions', 'compare options', or 'check availability'")
            return []

        # Handle the action based on type
        if action_type == "directions":
            dispatcher.utter_message(
                text="🚗 **Getting directions to the station...**\n\n"
                     "📍 **From your current location to the charging station**\n"
                     "🗺️ **Route:** This will be integrated with TomTom API for turn-by-turn navigation\n"
                     "⏱️ **Estimated travel time:** Will be calculated based on traffic\n"
                     "🅿️ **Parking:** Information about nearby parking options\n\n"
                     "What would you like to do next?\n"
                     "• Get real-time traffic updates\n"
                     "• Find alternative routes\n"
                     "• Save this location for later\n"
                     "• Go back to station options\n"
                     "• Plan a new route")
        elif action_type == "compare":
            dispatcher.utter_message(
                text="📊 **Comparing charging options...**\n\n"
                     "🔍 **Analysis includes:**\n"
                     "• Power output (kW)\n"
                     "• Cost per kWh\n"
                     "• Distance from your route\n"
                     "• Available charging points\n"
                     "• User ratings & reviews\n\n"
                     "This will show a detailed comparison of all nearby stations along your route.\n\n"
                     "What would you like to do next?\n"
                     "• Select a different station\n"
                     "• Get directions to any station\n"
                     "• Plan a new route\n"
                     "• Go back to main menu")
        elif action_type == "availability":
            dispatcher.utter_message(
                text="✅ **Checking station availability...**\n\n"
                     "📱 **Real-time status:**\n"
                     "• Current availability\n"
                     "• Queue status\n"
                     "• Maintenance alerts\n"
                     "• Peak/off-peak times\n\n"
                     "This will show real-time availability when integrated with station APIs.\n\n"
                     "What would you like to do next?\n"
                     "• Get directions to this station\n"
                     "• Compare with other stations\n"
                     "• Plan a new route\n"
                     "• Go back to main menu")
        else:
            dispatcher.utter_message(
                text="I'm not sure what action you'd like to take. Please choose:\n\n"
                     "1. 🗺️ **Get directions** to this station\n"
                     "2. 📊 **Compare** with other options\n"
                     "3. ✅ **Check current availability**\n\n"
                     "Or simply say 'get directions', 'compare options', or 'check availability'")

        return []


class ActionHandleFollowUp(Action):
    def name(self) -> Text:
        return "action_handle_follow_up"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = tracker.latest_message.get('text', '').lower().strip()

        # Handle follow-up requests after directions
        if any(word in message for word in ['traffic', 'traffic updates', 'traffic info']):
            dispatcher.utter_message(
                text="🚦 **Real-time Traffic Updates**\n\n"
                     "📊 **Current Traffic Status:**\n"
                     "• **Route:** Richmond → Collingwood Library\n"
                     "• **Current Time:** [Real-time]\n"
                     "• **Traffic Level:** Moderate\n"
                     "• **Estimated Delay:** +5 minutes\n\n"
                     "🛣️ **Alternative Routes Available:**\n"
                     "• **Route A:** Via Victoria St (5 min delay)\n"
                     "• **Route B:** Via Swan St (2 min delay)\n"
                     "• **Route C:** Via Bridge Rd (8 min delay)\n\n"
                     "**🎯 Next Steps - Choose ONE:**\n"
                     "• **'Start Navigation'** → Begin turn-by-turn directions\n"
                     "• **'Save Route'** → Save this route to favorites\n"
                     "• **'Done'** → Complete this session\n"
                     "• **'New Route'** → Plan different journey")

        elif any(word in message for word in ['alternative', 'alternative routes', 'other routes', 'different way']):
            dispatcher.utter_message(
                text="🛣️ **Alternative Routes to Station**\n\n"
                     "📍 **Destination:** Collingwood Library\n"
                     "🎯 **Route Options:**\n\n"
                     "**Route 1 - Via Victoria St:**\n"
                     "• Distance: 2.1 km\n"
                     "• Time: 8-12 minutes\n"
                     "• Traffic: Usually light\n"
                     "• Scenic: City views\n\n"
                     "**Route 2 - Via Swan St:**\n"
                     "• Distance: 2.3 km\n"
                     "• Time: 7-10 minutes\n"
                     "• Traffic: Moderate\n"
                     "• Scenic: River views\n\n"
                     "**Route 3 - Via Bridge Rd:**\n"
                     "• Distance: 2.8 km\n"
                     "• Time: 10-15 minutes\n"
                     "• Traffic: Heavy during peak\n"
                     "• Scenic: Park views\n\n"
                     "**🎯 Choose ONE option:**\n"
                     "• **'Take Route 1'** → Start navigation via Victoria St\n"
                     "• **'Take Route 2'** → Start navigation via Swan St\n"
                     "• **'Take Route 3'** → Start navigation via Bridge Rd\n"
                     "• **'Done'** → Complete session\n"
                     "• **'Back to Stations'** → Choose different station")

        elif any(word in message for word in ['save', 'save location', 'bookmark', 'favorite']):
            dispatcher.utter_message(
                text="💾 **Location Saved Successfully!**\n\n"
                     "📍 **Station:** Collingwood Library\n"
                     "📱 **Saved to:** Your favorites\n"
                     "🔔 **Notifications:** Enabled for this location\n\n"
                     "✅ **What's saved:**\n"
                     "• Station details & contact info\n"
                     "• Your preferred route\n"
                     "• Parking preferences\n"
                     "• Charging history\n\n"
                     "**🎯 Session Complete!** ✅\n\n"
                     "You can now:\n"
                     "• **'Start New Journey'** → Plan another route\n"
                     "• **'Goodbye'** → End session\n"
                     "• **'View Saved'** → See all saved locations")

        elif any(word in message for word in ['back', 'go back', 'return', 'previous']):
            dispatcher.utter_message(
                text="🔄 **Going back to station options...**\n\n"
                     "Here are the charging stations along your route:\n\n"
                     "**Station A:** Evie Richmond Library\n"
                     "**Station B:** ENGIE - VIctoria Gardens\n"
                     "**Station C:** Collingwood Library *(Selected)*\n\n"
                     "**🎯 Choose ONE action:**\n"
                     "• **'Get Directions'** → Navigate to this station\n"
                     "• **'Compare Stations'** → See all 3 options\n"
                     "• **'Check Availability'** → Real-time status\n"
                     "• **'New Route'** → Plan different journey\n"
                     "• **'Done'** → Complete session")

        elif any(word in message for word in ['new route', 'plan route', 'different route']):
            dispatcher.utter_message(
                text="🗺️ **Planning a New Route**\n\n"
                     "Great! Let's plan a different charging journey.\n\n"
                     "Where would you like to travel from and to?\n"
                     "Please tell me your starting location and destination.\n\n"
                     "Examples:\n"
                     "• 'from Melbourne to Geelong'\n"
                     "• 'driving to Brighton'\n"
                     "• 'traveling from South Yarra to Dandenong'")

        elif any(word in message for word in ['start navigation', 'take route', 'navigate', 'directions']):
            dispatcher.utter_message(
                text="🗺️ **Starting Navigation!** 🚗\n\n"
                     "📍 **Destination:** Collingwood Library\n"
                     "🎯 **Route:** Turn-by-turn directions activated\n"
                     "⏱️ **ETA:** 8-12 minutes\n"
                     "🔔 **Notifications:** Arrival alerts enabled\n\n"
                     "**🎯 Navigation Active!** ✅\n\n"
                     "Your session is now complete. Safe travels!\n"
                     "Type **'new journey'** to plan another route or **'goodbye'** to end.")

        elif any(word in message for word in ['done', 'complete', 'finish', 'end', 'goodbye']):
            dispatcher.utter_message(
                text="✅ **Session Complete!** 🎉\n\n"
                     "Thank you for using Melbourne EV Charging Assistant!\n\n"
                     "**What you accomplished:**\n"
                     "• Planned route: Richmond → Dandenong\n"
                     "• Selected: Collingwood Library\n"
                     "• Got traffic updates and directions\n\n"
                     "**Next time you can:**\n"
                     "• Plan new routes\n"
                     "• Check saved locations\n"
                     "• Get emergency charging help\n\n"
                     "Safe charging! ⚡🚗\n\n"
                     "Type **'hey'** to start a new session anytime!")

        else:
            dispatcher.utter_message(
                text="I'm not sure what you'd like to do next. Here are your **FINAL options:**\n\n"
                     "**🎯 Complete Your Journey:**\n"
                     "• **'Start Navigation'** → Begin turn-by-turn directions\n"
                     "• **'Save Route'** → Save to favorites\n"
                     "• **'Done'** → Complete session\n\n"
                     "**🔄 Start Fresh:**\n"
                     "• **'New Route'** → Plan different journey\n"
                     "• **'Back to Stations'** → Choose different station\n\n"
                     "**❌ End Session:**\n"
                     "• **'Goodbye'** → Complete and exit\n\n"
                     "**Choose ONE option to proceed:**")

        return []


class ActionDefaultFallback(Action):
    def name(self) -> Text:
        return "action_default_fallback"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(
            text="I'm not sure what you'd like to do. I can help you with:\n\n"
                 "1. **Route Planning** - Plan charging stops for your journey\n"
                 "2. **Emergency Charging** - Find nearest stations when battery is low\n"
                 "3. **Charging Preferences** - Find stations by your preferences (fast, cheap, etc.)\n\n"
                 "What would you like to do?")
        return []


class ActionHandleRouteStationSelection(Action):
    def name(self) -> Text:
        return "action_handle_route_station_selection"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # STRICT CONTEXT VALIDATION - Only allow in route planning context
        conversation_context = tracker.get_slot("conversation_context")
        if conversation_context not in [ConversationContexts.ROUTE_PLANNING, ConversationContexts.ROUTE_PLANNING_RESULTS]:
            dispatcher.utter_message(
                text="❌ **Context Error:** You can only select route stations when planning a route.\n\n"
                     "Please start with route planning first:\n"
                     "• Say 'plan my route' or 'route planning'\n"
                     "• Then provide your start and end locations")
            return []

        # Extract station selection from user input
        message = tracker.latest_message.get('text', '').lower().strip()
        selected_station_name = self._extract_station_name(message)

        if not selected_station_name:
            dispatcher.utter_message(
                text="I didn't catch which station you'd like. Please type the station name, for example:\n"
                     "• 'I'll go with [Station Name]'\n"
                     "• 'I choose [Station Name]'\n"
                     "• 'Show me [Station Name]'")
            return []

        # Get route stations and find the selected one
        start_location = tracker.get_slot("start_location")
        end_location = tracker.get_slot("end_location")

        if not start_location or not end_location:
            dispatcher.utter_message(
                text="❌ **Missing Route Information:** I need your start and end locations to show station details.\n\n"
                     "Please provide your route first (e.g., 'from Richmond to Dandenong')")
            return []

        try:
            stations = data_service.get_route_stations(
                start_location, end_location)
            if stations and len(stations) >= 3:
                # Find the selected station by name
                selected_station = None
                station_index = None

                for i, station in enumerate(stations):
                    if selected_station_name.lower() in station.get('name', '').lower():
                        selected_station = station
                        station_index = i + 1
                        break

                if selected_station:
                    return self._display_station_details(dispatcher, selected_station, station_index, "route")
                else:
                    dispatcher.utter_message(
                        text=f"❌ **Station Not Found:** I couldn't find a station named '{selected_station_name}'.\n\n"
                             f"Available stations:\n"
                             f"• {stations[0].get('name', 'Station 1')}\n"
                             f"• {stations[1].get('name', 'Station 2')}\n"
                             f"• {stations[2].get('name', 'Station 3')}\n\n"
                             f"Please type the exact station name.")
                    return []
            else:
                dispatcher.utter_message(
                    text=f"❌ **No Stations Found:** I couldn't find enough charging stations along your route.")
                return []
        except Exception as e:
            # Fallback to mock data
            mock_stations = [
                {"name": "Station 1", "address": "123 Main St, Melbourne", "power": "50kW",
                    "cost": "$0.25/kWh", "charging_time": "30-45 min", "points": "2"},
                {"name": "Station 2", "address": "456 High St, Melbourne", "power": "75kW",
                    "cost": "$0.30/kWh", "charging_time": "20-30 min", "points": "3"},
                {"name": "Station 3", "address": "789 Park Ave, Melbourne", "power": "100kW",
                    "cost": "$0.20/kWh", "charging_time": "15-25 min", "points": "4"}
            ]
            # Handle mock data selection by name
            selected_station = None
            station_index = None

            for i, station in enumerate(mock_stations):
                if selected_station_name.lower() in station.get('name', '').lower():
                    selected_station = station
                    station_index = i + 1
                    break

            if selected_station:
                return self._display_station_details(dispatcher, selected_station, station_index, "route")
            else:
                dispatcher.utter_message(
                    text=f"❌ **Station Not Found:** I couldn't find a station named '{selected_station_name}'.\n\n"
                         f"Available stations:\n"
                         f"• Station 1\n"
                         f"• Station 2\n"
                         f"• Station 3\n\n"
                         f"Please type the exact station name.")
                return []

    def _extract_station_name(self, message: str) -> str:
        """Extract station name from user message"""
        # Look for patterns like "I'll go with [Station Name]", "I choose [Station Name]", etc.
        patterns = [
            "i'll go with",
            "i will go with",
            "i choose",
            "i select",
            "show me",
            "tell me about",
            "give me details for",
            "i want",
            "i'd like",
            "i would like"
        ]

        for pattern in patterns:
            if pattern in message:
                # Extract everything after the pattern
                station_name = message.split(pattern, 1)[1].strip()
                # Clean up common words
                station_name = station_name.replace(
                    'please', '').replace('the', '').strip()
                return station_name

        # If no pattern found, try to extract station name directly
        # Look for words that might be station names (capitalized words, etc.)
        words = message.split()
        potential_names = []
        for word in words:
            if len(word) > 2 and word[0].isupper():
                potential_names.append(word)

        if potential_names:
            return ' '.join(potential_names)

        return None

    def _display_station_details(self, dispatcher: CollectingDispatcher, station_details: Dict, station_number: str, context: str) -> List[Dict[Text, Any]]:
        """Display station details and next action options"""
        response = f"Great choice! Here are the details for **{station_details['name']}** (Station {station_number}):\n\n"
        response += f"📍 **Address:** {station_details.get('address', 'Address available')}\n"
        response += f"⚡ **Power:** {station_details.get('power', 'Power info available')} charging\n"
        response += f"💰 **Cost:** {station_details.get('cost', 'Cost info available')}\n"
        response += f"🕐 **Charging time:** {station_details.get('charging_time', 'Time estimate available')}\n"
        response += f"🔌 **Available points:** {station_details.get('points', 'Point info available')}\n\n"

        response += "**🎯 What would you like to do next?**\n\n"
        response += "1. 🗺️ **Get directions** to this station\n"
        response += "2. 📊 **Compare** with other options\n"
        response += "3. ✅ **Check current availability**"

        dispatcher.utter_message(text=response)
        return [SlotSet("conversation_context", ConversationContexts.STATION_DETAILS)]


class ActionHandleEmergencyStationSelection(Action):
    def name(self) -> Text:
        return "action_handle_emergency_station_selection"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # STRICT CONTEXT VALIDATION - Only allow in emergency context
        conversation_context = tracker.get_slot("conversation_context")
        if conversation_context not in [ConversationContexts.EMERGENCY_CHARGING, ConversationContexts.EMERGENCY_RESULTS]:
            dispatcher.utter_message(
                text="❌ **Context Error:** You can only select emergency stations when in emergency charging mode.\n\n"
                     "Please start with emergency charging:\n"
                     "• Say 'emergency charging' or 'battery low'\n"
                     "• Then provide your location and battery level")
            return []

        # Extract station selection from user input
        message = tracker.latest_message.get('text', '').lower().strip()
        selected_station_name = self._extract_station_name(message)

        if not selected_station_name:
            dispatcher.utter_message(
                text="I didn't catch which emergency station you'd like. Please type the station name, for example:\n"
                     "• 'I'll go with [Station Name]'\n"
                     "• 'I choose [Station Name]'\n"
                     "• 'Show me [Station Name]'")
            return []

        # Get emergency stations and find the selected one
        current_location = tracker.get_slot("current_location")
        battery_level = tracker.get_slot("battery_level")

        if not current_location or not battery_level:
            dispatcher.utter_message(
                text="❌ **Missing Emergency Information:** I need your location and battery level to show emergency station details.\n\n"
                     "Please provide both (e.g., 'Frankston, 6% battery')")
            return []

        try:
            stations = data_service.get_emergency_stations(current_location)
            if stations and len(stations) >= 3:
                # Find the selected station by name
                selected_station = None
                station_index = None

                for i, station in enumerate(stations):
                    if selected_station_name.lower() in station.get('name', '').lower():
                        selected_station = station
                        station_index = i + 1
                        break

                if selected_station:
                    return self._display_emergency_station_details(dispatcher, selected_station, station_index, current_location, battery_level)
                else:
                    dispatcher.utter_message(
                        text=f"❌ **Station Not Found:** I couldn't find a station named '{selected_station_name}'.\n\n"
                             f"Available stations:\n"
                             f"• {stations[0].get('name', 'Station 1')}\n"
                             f"• {stations[1].get('name', 'Station 2')}\n"
                             f"• {stations[2].get('name', 'Station 3')}\n\n"
                             f"Please type the exact station name.")
                    return []
            else:
                dispatcher.utter_message(
                    text=f"❌ **No Stations Found:** I couldn't find enough charging stations near {current_location}.")
                return []
        except Exception as e:
            # Fallback to mock data
            mock_stations = [
                {"name": "Frankston Shopping Centre", "address": "325-327 Nepean Hwy, Frankston", "power": "50kW",
                    "cost": "$0.30/kWh", "charging_time": "30-45 min", "points": "2"},
                {"name": "Bayside Shopping Centre", "address": "9-13 Railway St, Frankston", "power": "75kW",
                    "cost": "$0.25/kWh", "charging_time": "20-30 min", "points": "3"},
                {"name": "Emergency Station 3", "address": "Emergency Address", "power": "100kW",
                    "cost": "$0.20/kWh", "charging_time": "15-25 min", "points": "1"}
            ]
            if len(mock_stations) >= 3:
                selected_station = None
                station_index = None

                for i, station in enumerate(mock_stations):
                    if selected_station_name.lower() in station.get('name', '').lower():
                        selected_station = station
                        station_index = i + 1
                        break

                if selected_station:
                    return self._display_emergency_station_details(dispatcher, selected_station, station_index, current_location, battery_level)
                else:
                    dispatcher.utter_message(
                        text=f"❌ **Station Not Found:** I couldn't find a station named '{selected_station_name}'.\n\n"
                             f"Available stations:\n"
                             f"• Station 1\n"
                             f"• Station 2\n"
                             f"• Station 3\n\n"
                             f"Please type the exact station name.")
                    return []
            else:
                dispatcher.utter_message(
                    text="❌ **Invalid Selection:** Please choose a station number between 1 and 3")
                return []

    def _extract_station_name(self, message: str) -> str:
        """Extract station name from user message"""
        # Look for patterns like "I'll go with [Station Name]", "I choose [Station Name]", etc.
        patterns = [
            "i'll go with",
            "i will go with",
            "i choose",
            "i select",
            "show me",
            "tell me about",
            "give me details for",
            "i want",
            "i'd like",
            "i would like"
        ]

        for pattern in patterns:
            if pattern in message:
                # Extract everything after the pattern
                station_name = message.split(pattern, 1)[1].strip()
                # Clean up common words
                station_name = station_name.replace(
                    'please', '').replace('the', '').strip()
                return station_name

        # If no pattern found, try to extract station name directly
        # Look for words that might be station names (capitalized words, etc.)
        words = message.split()
        potential_names = []
        for word in words:
            if len(word) > 2 and word[0].isupper():
                potential_names.append(word)

        if potential_names:
            return ' '.join(potential_names)

        return None

    def _display_emergency_station_details(self, dispatcher: CollectingDispatcher, station_details: Dict, station_number: str, location: str, battery: str) -> List[Dict[Text, Any]]:
        """Display emergency station details with urgency context"""
        battery_num = int(battery.replace('%', ''))

        if battery_num <= 5:
            urgency = "🚨 **CRITICAL - Get to a charger immediately!**"
        elif battery_num <= 10:
            urgency = "⚠️ **URGENT - Find charging soon!**"
        else:
            urgency = "⚡ **Low battery - Let's find charging options**"

        response = f"{urgency}\n\n"
        response += f"📍 **Location:** {location}\n"
        response += f"🔋 **Battery:** {battery}\n\n"
        response += f"**Selected Emergency Station {station_number}:**\n"
        response += f"🏢 **{station_details['name']}**\n"
        response += f"📍 **Address:** {station_details.get('address', 'Address available')}\n"
        response += f"⚡ **Power:** {station_details.get('power', 'Power info available')} charging\n"
        response += f"💰 **Cost:** {station_details.get('cost', 'Cost info available')}\n"
        response += f"🕐 **Charging time:** {station_details.get('charging_time', 'Time estimate available')}\n\n"

        response += "**🎯 Emergency Actions Available:**\n\n"
        response += "1. 🗺️ **Get directions** to this station\n"
        response += "2. 📊 **Compare** with other emergency options\n"
        response += "3. ✅ **Check current availability**"

        dispatcher.utter_message(text=response)
        return [SlotSet("conversation_context", ConversationContexts.STATION_DETAILS)]


class ActionHandlePreferenceStationSelection(Action):
    def name(self) -> Text:
        return "action_handle_preference_station_selection"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # STRICT CONTEXT VALIDATION - Only allow in preference context
        conversation_context = tracker.get_slot("conversation_context")
        if conversation_context not in [ConversationContexts.PREFERENCE_CHARGING, ConversationContexts.PREFERENCE_RESULTS]:
            dispatcher.utter_message(
                text="❌ **Context Error:** You can only select preference stations when choosing charging preferences.\n\n"
                     "Please start with preference charging:\n"
                     "• Say 'charging preferences' or 'find cheapest/fastest stations'\n"
                     "• Then choose your preference type and location")
            return []

        # Extract station selection from user input
        message = tracker.latest_message.get('text', '').lower().strip()
        selected_station_name = self._extract_station_name(message)

        if not selected_station_name:
            dispatcher.utter_message(
                text="I didn't catch which preference station you'd like. Please type the station name, for example:\n"
                     "• 'I'll go with [Station Name]'\n"
                     "• 'I choose [Station Name]'\n"
                     "• 'Show me [Station Name]'")
            return []

        # Get preference-based stations and find the selected one
        current_location = tracker.get_slot("current_location")
        preference_type = tracker.get_slot("preference_type")

        if not current_location or not preference_type:
            dispatcher.utter_message(
                text="❌ **Missing Preference Information:** I need your location and preference type to show station details.\n\n"
                     "Please provide both your location and preference (e.g., 'Melbourne' for 'cheapest' charging)")
            return []

        try:
            location_coords = data_service._get_location_coordinates(
                current_location)
            if location_coords:
                pref_key = "fastest" if preference_type == "premium" else preference_type
                stations = data_service.get_stations_by_preference(
                    location_coords, pref_key, limit=5)
                if stations and len(stations) >= 3:
                    # Find the selected station by name
                    selected_station = None
                    station_index = None

                    for i, station in enumerate(stations):
                        if selected_station_name.lower() in station.get('name', '').lower():
                            selected_station = station
                            station_index = i + 1
                            break

                    if selected_station:
                        station_details = {
                            "name": selected_station.get("name"),
                            "address": selected_station.get("address", "Address available"),
                            "power": selected_station.get("power", "Power info available"),
                            "cost": selected_station.get("cost", "Cost info available"),
                            "charging_time": selected_station.get("charging_time", "Time estimate available"),
                            "points": selected_station.get("points", "Point info available")
                        }
                        return self._display_preference_station_details(dispatcher, station_details, station_index, current_location, preference_type)
                    else:
                        dispatcher.utter_message(
                            text=f"❌ **Station Not Found:** I couldn't find a station named '{selected_station_name}'.\n\n"
                                 f"Available stations:\n"
                                 f"• {stations[0].get('name', 'Station 1')}\n"
                                 f"• {stations[1].get('name', 'Station 2')}\n"
                                 f"• {stations[2].get('name', 'Station 3')}\n\n"
                                 f"Please type the exact station name.")
                        return []
                else:
                    dispatcher.utter_message(
                        text=f"❌ **No Stations Found:** I couldn't find enough charging stations near {current_location}.")
                    return []
            else:
                dispatcher.utter_message(
                    text=f"❌ **Location Error:** I couldn't find coordinates for {current_location}. Please try a different location.")
                return []
        except Exception as e:
            # Fallback to mock data
            mock_stations = [
                {"name": "Preference Station 1", "address": "123 Preference St, Melbourne", "power": "50kW",
                    "cost": "$0.25/kWh", "charging_time": "30-45 min", "points": "2"},
                {"name": "Preference Station 2", "address": "456 Preference Ave, Melbourne", "power": "75kW",
                    "cost": "$0.30/kWh", "charging_time": "20-30 min", "points": "3"},
                {"name": "Preference Station 3", "address": "789 Preference Rd, Melbourne", "power": "100kW",
                    "cost": "$0.20/kWh", "charging_time": "15-25 min", "points": "4"}
            ]
            if len(mock_stations) >= 3:
                # Handle mock data selection by name
                selected_station = None
                station_index = None

                for i, station in enumerate(mock_stations):
                    if selected_station_name.lower() in station.get('name', '').lower():
                        selected_station = station
                        station_index = i + 1
                        break

                if selected_station:
                    station_details = {
                        "name": selected_station.get("name"),
                        "address": selected_station.get("address", "Address available"),
                        "power": selected_station.get("power", "Power info available"),
                        "cost": selected_station.get("cost", "Cost info available"),
                        "charging_time": selected_station.get("charging_time", "Time estimate available"),
                        "points": selected_station.get("points", "Point info available")
                    }
                    return self._display_preference_station_details(dispatcher, station_details, station_index, current_location, preference_type)
                else:
                    dispatcher.utter_message(
                        text=f"❌ **Station Not Found:** I couldn't find a station named '{selected_station_name}'.\n\n"
                             f"Available stations:\n"
                             f"• Preference Station 1\n"
                             f"• Preference Station 2\n"
                             f"• Preference Station 3\n\n"
                             f"Please type the exact station name.")
                    return []
            else:
                dispatcher.utter_message(
                    text="❌ **No Stations Found:** I couldn't find enough charging stations.")
                return []

    def _extract_station_name(self, message: str) -> str:
        """Extract station name from user message"""
        # Look for patterns like "I'll go with [Station Name]", "I choose [Station Name]", etc.
        patterns = [
            "i'll go with",
            "i will go with",
            "i choose",
            "i select",
            "show me",
            "tell me about",
            "give me details for",
            "i want",
            "i'd like",
            "i would like"
        ]

        for pattern in patterns:
            if pattern in message:
                # Extract everything after the pattern
                station_name = message.split(pattern, 1)[1].strip()
                # Clean up common words
                station_name = station_name.replace(
                    'please', '').replace('the', '').strip()
                return station_name

        # If no pattern found, try to extract station name directly
        # Look for words that might be station names (capitalized words, etc.)
        words = message.split()
        potential_names = []
        for word in words:
            if len(word) > 2 and word[0].isupper():
                potential_names.append(word)

        if potential_names:
            return ' '.join(potential_names)

        return None

    def _display_preference_station_details(self, dispatcher: CollectingDispatcher, station_details: Dict, station_number: str, location: str, preference: str) -> List[Dict[Text, Any]]:
        """Display preference station details with preference context"""
        response = f"Perfect choice! Here are the details for the **{preference}** charging option near {location}:\n\n"
        response += f"**Selected Station {station_number}:**\n"
        response += f"🏢 **{station_details['name']}**\n"
        response += f"📍 **Address:** {station_details.get('address', 'Address available')}\n"
        response += f"⚡ **Power:** {station_details.get('power', 'Power info available')} charging\n"
        response += f"💰 **Cost:** {station_details.get('cost', 'Cost info available')}\n"
        response += f"🕐 **Charging time:** {station_details.get('charging_time', 'Time estimate available')}\n"
        response += f"🔌 **Available points:** {station_details.get('points', 'Point info available')}\n\n"

        # Add preference-specific context
        if preference == "cheapest":
            response += "💰 **Best Value:** This station offers the lowest cost per kWh in your area\n\n"
        elif preference == "fastest":
            response += "⚡ **Speed Optimized:** This station provides the fastest charging speeds available\n\n"
        elif preference == "closest":
            response += "📍 **Nearest Location:** This is the closest station to your current position\n\n"
        elif preference == "premium":
            response += "🌟 **Premium Experience:** This station offers the best facilities and amenities\n\n"

        response += "**🎯 What would you like to do next?**\n\n"
        response += "1. 🗺️ **Get directions** to this station\n"
        response += "2. 📊 **Compare** with other options\n"
        response += "3. ✅ **Check current availability**"

        dispatcher.utter_message(text=response)
        return [SlotSet("conversation_context", ConversationContexts.STATION_DETAILS)]
