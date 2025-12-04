from datetime import datetime

search_description="Handles secure payment processing, booking through travel provider APIs, reservation management, and compliance with financial regulations."

search_prompt="""You are an agent specialized in searching for travel services using the Amadeus API.
You can search for flights using the search_flights tool. You need origin, destination, departure date, and optionally return date. **IMPORTANT: The user may provide the name of the origin/destinations, you must first convert it to IATA 3-letter codes then call functions.**
**IMPORTANT: Today's date is """+str(datetime.now().date())+""". Always ensure all search dates are in the future.If the user mentions a date without a year or with a past year, assume they mean the next occurrence of that date.**
You can search for hotels using the search_hotels tool.For hotels, you need city code only. 
The user may provide different format of dates, you must convert them to YYYY-MM-DD format then call functions.
After getting the search results, you should ask the user to confirm their choice. List the options and ask them to choose one. Then call the verify_flight_price tool to confirm the price and availability."""

AMENITIES = {
    "FITNESS_CENTER": "Fitness center / Gym",
    "AIR_CONDITIONING": "Air conditioning in rooms or common areas",
    "RESTAURANT": "On-site restaurant(s)",
    "PARKING": "Parking available",
    "PETS_ALLOWED": "Pets are allowed at the property",
    "AIRPORT_SHUTTLE": "Shuttle service to/from airport",
    "BUSINESS_CENTER": "Business center services (PCs, printers, etc.)",
    "DISABLED_FACILITIES": "Accessible facilities for disabled guests",
    "WIFI": "Wi-Fi (general access)",
    "MEETING_ROOMS": "Meeting or conference rooms available",
    "NO_KID_ALLOWED": "Adults-only property (children not allowed)",
    "TENNIS": "Tennis courts available",
    "GOLF": "Golf course access",
    "KITCHEN": "Kitchen facilities available",
    "ANIMAL_WATCHING": "Animal watching / Wildlife tours nearby",
    "BABY_SITTING": "Babysitting or childcare services",
    "BEACH": "Beach access / Beachfront property",
    "CASINO": "On-site casino",
    "JACUZZI": "Jacuzzi / Hot tub",
    "SAUNA": "Sauna available",
    "SOLARIUM": "Solarium / Sun deck",
    "MASSAGE": "Massage services / Spa treatments",
    "VALET_PARKING": "Valet parking service",
    "BAR": "Bar or lounge",
    "KIDS_WELCOME": "Family-friendly property (children welcome)",
    "NO_PORN_FILMS": "No pornographic TV/films available",
    "MINIBAR": "Minibar in rooms",
    "TELEVISION": "Television in rooms",
    "WI-FI_IN_ROOM": "In-room Wi-Fi",
    "ROOM_SERVICE": "Room service available",
    "GUARDED_PARKG": "Guarded / Secured parking",
    "SERV_SPEC_MENU": "Special dietary menus available (e.g. vegetarian, halal, gluten-free)"
}

amenities_str = "\n".join([f"- {code}: {desc}" for code, desc in AMENITIES.items()])

system_message = f"""
You are an agent specialized in searching for travel services using the Amadeus API.

### Flights
- Use the `search_flights` tool.  
- Required: origin, destination, departure date.  
- Optional: return date.  
- **Always convert city/airport names into IATA 3-letter codes before calling.**  
- **Today's date is {datetime.now().date()}. Ensure all search dates are in the future.**  
  - If the user provides a date without a year or with a past year, assume the *next occurrence* of that date.  
- After retrieving results, simply return them.  
- If a specific flight is selected by another agent, call `verify_flight_price` to confirm price & availability.  
- **Do NOT ask the user for confirmation.**

---

### Hotels
- Use `search_hotels_by_city` (via IATA city code) or `search_hotels_by_geocode` (via latitude/longitude).  
- Accept optional filters: amenities, radius.  
- Translate amenities into the following valid codes: {amenities_str}.
- Return results directly. **Do NOT ask questions.**

---

### Places
- You can search for places directly using a text query.  
- Return results only.  

---

### Routes
- Use the `compute_routes` tool.  
- Mode of transport is optional (default = driving).  
- Return results directly.  

---

### Tours
- Use the `search_tours` tool.  
- Requires: geolocation (latitude & longitude).  
- Optional: radius in kilometers.  
- Return results directly.  

---

### Dates
- Users may provide dates in many formats.  
- Normalize all dates into **YYYY-MM-DD** format before calling tools.  

---

### Interaction Policy
- **Do NOT ask the user any questions.**  
- **Do NOT request confirmation.**  
- Only execute tool calls and return results.  
"""

# - All clarifications or user-facing questions must be handled by the PlanningAgent via the UserProxyAgent.  

system_message_old="""You are an agent specialized in searching for travel services using the Amadeus API.
        You can search for flights using the search_flights tool. You need origin, destination, departure date, and optionally return date. 
        **IMPORTANT: The user may provide the name of the origin/destinations, you must first convert it to IATA 3-letter codes then call functions.**
        **IMPORTANT: Today's date is """+str(datetime.now().date())+""". 
        Always ensure all search dates are in the future.If the user mentions a date without a year or with a past year, assume they mean the next occurrence of that date.**
        You can search for hotels either by city IATA code (search_hotels_by_city) or by geocode (search_hotels_by_geocode) You can also specify amenities and search radius in the search_hotels tool. 
        Translate the amenities to the following:
        - FITNESS_CENTER
        - AIR_CONDITIONING
        - RESTAURANT
        - PARKING
        - PETS_ALLOWED
        - AIRPORT_SHUTTLE
        - BUSINESS_CENTER
        - DISABLED_FACILITIES
        - WIFI
        - MEETING_ROOMS
        - NO_KID_ALLOWED
        - TENNIS
        - GOLF
        - KITCHEN
        - ANIMAL_WATCHING
        - BABY-SITTING
        - BEACH
        - CASINO
        - JACUZZI
        - SAUNA
        - SOLARIUM
        - MASSAGE
        - VALET_PARKING
        - BAR or LOUNGE
        - KIDS_WELCOME
        - NO_PORN_FILMS
        - MINIBAR
        - TELEVISION
        - WI-FI_IN_ROOM
        - ROOM_SERVICE
        - GUARDED_PARKG
        - SERV_SPEC_MENU
        The user may provide different format of dates, you must convert them to YYYY-MM-DD format then call functions.
        After getting the search results, you should ask the user to confirm their choice. List the options and ask them to choose one. 
        After getting user's selection, you should call the verify_flight_price tool to confirm the price and availability of the selected flight.

        You can also search places use text query directly.

        You can also compute routes using the compute_routes tool. You need optionally mode of transport (default is driving).

        You can also search for tours using the search_tours tool. You need the geolocation coordinates (latitude and longitude) and optionally a radius in kilometers. 
        """

places = [{'formattedAddress': '2218 E Cliff Dr, Santa Cruz, CA 95062, USA', 'location': {'latitude': 36.9632457, 'longitude': -122.00138079999999}, 'displayName': {'text': "Crow's Nest Restaurant", 'languageCode': 'en'}}, {'formattedAddress': '110 Walnut Ave, Santa Cruz, CA 95060, USA', 'location': {'latitude': 36.9735678, 'longitude': -122.0266168}, 'displayName': {'text': 'The Salty Otter Sports Grill', 'languageCode': 'en'}}, {'formattedAddress': '18 Clubhouse Rd, Santa Cruz, CA 95060, USA', 'location': {'latitude': 37.0040264, 'longitude': -122.025948}, 'displayName': {'text': 'Mackenzie Bar & Grill', 'languageCode': 'en'}}, {'formattedAddress': '611 Ocean St, Santa Cruz, CA 95060, USA', 'location': {'latitude': 36.976774899999995, 'longitude': -122.0207896}, 'displayName': {'text': 'Solaire Restaurant + Bar', 'languageCode': 'en'}}, {'formattedAddress': '119 Madrone St, Santa Cruz, CA 95060, USA', 'location': {'latitude': 36.982596099999995, 'longitude': -122.0304718}, 'displayName': {'text': 'Woodhouse Blending & Brewing', 'languageCode': 'en'}}, {'formattedAddress': '316 Capitola Ave, Capitola, CA 95010, USA', 'location': {'latitude': 36.9736927, 'longitude': -121.95254469999999}, 'displayName': {'text': 'Trestles Restaurant', 'languageCode': 'en'}}, {'formattedAddress': '106 Beach St, Santa Cruz, CA 95060, USA', 'location': {'latitude': 36.9627127, 'longitude': -122.02328010000001}, 'displayName': {'text': 'Ideal Bar & Grill', 'languageCode': 'en'}}, {'formattedAddress': '49A Municipal Wharf, Santa Cruz, CA 95060, USA', 'location': {'latitude': 36.9589407, 'longitude': -122.01841809999999}, 'displayName': {'text': 'Makai Island Kitchen & Groggery', 'languageCode': 'en'}}, {'formattedAddress': '401 Upper Park Rd, Santa Cruz, CA 95065, USA', 'location': {'latitude': 36.9972685, 'longitude': -122.0013766}, 'displayName': {'text': 'The Grille at DeLaveaga', 'languageCode': 'en'}}, {'formattedAddress': '1308 Pacific Ave, Santa Cruz, CA 95060, USA', 'location': {'latitude': 36.973822, 'longitude': -122.02571899999998}, 'displayName': {'text': 'Gobi Mongolian BBQ', 'languageCode': 'en'}}, {'formattedAddress': 'Inside the Inn at Pasatiempo, 555 CA-17, Santa Cruz, CA 95060, USA', 'location': {'latitude': 36.999288299999996, 'longitude': -122.0224942}, 'displayName': {'text': 'Back Nine Grill & Bar', 'languageCode': 'en'}}, {'formattedAddress': '3744 Capitola Rd, Santa Cruz, CA 95062, USA', 'location': {'latitude': 36.973487399999996, 'longitude': -121.9685067}, 'displayName': {'text': 'Pono Hawaiian Kitchen & Tap', 'languageCode': 'en'}}, {'formattedAddress': '203 Esplanade, Capitola, CA 95010, USA', 'location': {'latitude': 36.9718922, 'longitude': -121.9518947}, 'displayName': {'text': "Zelda's on the beach", 'languageCode': 'en'}}, {'formattedAddress': '910 Cedar St, Santa Cruz, CA 95060, USA', 'location': {'latitude': 36.9746917, 'longitude': -122.02751389999999}, 'displayName': {'text': 'Gabriella Café', 'languageCode': 'en'}}, {'formattedAddress': '1411 Pacific Ave, Santa Cruz, CA 95060, USA', 'location': {'latitude': 36.975037799999996, 'longitude': -122.0266371}, 'displayName': {'text': 'Mad Yolks', 'languageCode': 'en'}}, {'formattedAddress': '59 Municipal Wharf, Santa Cruz, CA 95060, USA', 'location': {'latitude': 36.9582529, 'longitude': -122.01781000000001}, 'displayName': {'text': 'Stagnaro Bros.', 'languageCode': 'en'}}, {'formattedAddress': '519 Seabright Ave UNIT 107, Santa Cruz, CA 95062, USA', 'location': {'latitude': 36.967531199999996, 'longitude': -122.00831090000001}, 'displayName': {'text': 'Seabright Social', 'languageCode': 'en'}}, {'formattedAddress': '115 Cliff St, Santa Cruz, CA 95060, USA', 'location': {'latitude': 36.964276399999996, 'longitude': -122.02055929999999}, 'displayName': {'text': 'Coasters Bar & Grill', 'languageCode': 'en'}}, {'formattedAddress': '3101 N Main St, Soquel, CA 95073, USA', 'location': {'latitude': 36.989627299999995, 'longitude': -121.9549786}, 'displayName': {'text': 'HOME', 'languageCode': 'en'}}, {'formattedAddress': '175 W Cliff Dr, Santa Cruz, CA 95060, USA', 'location': {'latitude': 36.962323399999995, 'longitude': -122.0243879}, 'displayName': {'text': "Jack O'Neill Restaurant & Lounge", 'languageCode': 'en'}}]