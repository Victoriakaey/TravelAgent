import json
from datetime import datetime
from typing import List, Dict, Union

def dataframe_to_markdown(df):
    headers = "| " + " | ".join(df.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    rows = ["| " + " | ".join(str(x) for x in row) + " |" for row in df.values]
    return "\n".join([headers, separator] + rows)

def format_datetime(dt_str: str) -> str:
    """Convert ISO datetime string into human-readable format."""
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).strftime("%b %d, %Y - %I:%M %p")
    except Exception:
        return dt_str or "—"

def flights_to_markdown(flights: List[Dict]) -> str:
    sections = ["=== Flights ==="]
    for idx, flight in enumerate(flights, start=1):
        itineraries = flight.get("itineraries", [])
        price = f"{flight['price']['currency']} {flight['price']['grandTotal']}"
        segments_out = itineraries[0]["segments"]
        dep_airport = segments_out[0]["departure"]["iataCode"]
        arr_airport = segments_out[-1]["arrival"]["iataCode"]
        dep_time = format_datetime(segments_out[0]["departure"]["at"])

        segments_return = itineraries[1]["segments"] if len(itineraries) > 1 else []
        return_time = format_datetime(segments_return[0]["departure"]["at"]) if segments_return else "—"
        arrival_return = format_datetime(segments_return[-1]["arrival"]["at"]) if segments_return else "—"

        duration_out = itineraries[0].get("duration", "—")
        duration_back = itineraries[1].get("duration", "—") if len(itineraries) > 1 else "—"
        airline_numbers = ", ".join([f"{s['carrierCode']} {s['number']}" for s in segments_out + segments_return])

        fares = " / ".join([f"{seg['cabin']} (Class {seg['class']})"
                            for tp in flight["travelerPricings"]
                            for seg in tp["fareDetailsBySegment"]])
        bags = " / ".join([f"{seg.get('includedCheckedBags',{}).get('quantity',0)} checked, "
                           f"{seg.get('includedCabinBags',{}).get('quantity',0) if seg.get('includedCabinBags') else 0} carry-on"
                           for tp in flight["travelerPricings"]
                           for seg in tp["fareDetailsBySegment"]])

        amenities = set()
        for tp in flight["travelerPricings"]:
            for seg in tp.get("fareDetailsBySegment", []):
                if "amenities" in seg:
                    amenities.update([a["description"] for a in seg["amenities"]])

        sections.append(
            f"flight {idx}:\n"
            f"  route: {dep_airport} → {arr_airport}\n"
            f"  departure: {dep_time} (Terminal {segments_out[0]['departure'].get('terminal','—')})\n"
            f"  return: {arrival_return} (Terminal {segments_return[-1]['arrival'].get('terminal','—') if segments_return else '—'})\n"
            f"  duration: outbound {duration_out}, return {duration_back}\n"
            f"  fare: {fares}\n"
            f"  bags: {bags}\n"
            f"  amenities: {', '.join(amenities) if amenities else '—'}\n"
            f"  price: {price}\n"
            f"  ticket_by: {flight.get('lastTicketingDate','—')}\n"
            f"  flights: {airline_numbers}\n---"
        )
    return "\n\n".join(sections)

def hotels_to_markdown(hotels: List[Dict]) -> str:
    sections = ["=== Hotels ==="]
    for idx, h in enumerate(hotels, start=1):
        name = h.get("name", "—")
        lat = h.get("geoCode", {}).get("latitude", "—")
        lon = h.get("geoCode", {}).get("longitude", "—")
        address_parts = h.get("address", {})
        address = ", ".join(address_parts.get("lines", [])) + \
                  (f", {address_parts.get('cityName','')}" if address_parts.get("cityName") else "") + \
                  (f", {address_parts.get('postalCode','')}" if address_parts.get("postalCode") else "") + \
                  (f", {address_parts.get('countryCode','')}" if address_parts.get("countryCode") else "")
        amenities = ", ".join(h.get("amenities", [])) if h.get("amenities") else "—"

        sections.append(
            f"hotel {idx}:\n"
            f"  name: {name}\n"
            f"  chain: {h.get('chainCode','—')}\n"
            f"  iata: {h.get('iataCode','—')}\n"
            f"  hotel_id: {h.get('hotelId','—')}\n"
            f"  address: {address.strip(', ')}\n"
            f"  latitude: {lat}\n"
            f"  longitude: {lon}\n"
            f"  distance_km: {h.get('distance', {}).get('value', '—')}\n"
            f"  amenities: {amenities}\n"
            f"  last_update: {h.get('lastUpdate','—')}\n---"
        )
    return "\n\n".join(sections)



def places_to_markdown(places: List[Dict]) -> str:
    sections = ["=== Places ==="]
    for idx, p in enumerate(places, start=1):
        lat, lon = p["location"]["latitude"], p["location"]["longitude"]
        sections.append(
            f"place {idx}:\n"
            f"  name: {p['displayName']['text']}\n"
            f"  address: {p.get('formattedAddress','—')}\n"
            f"  rating: {p.get('rating','—')}\n"
            f"  types: {', '.join(p.get('types',[]))}\n"
            f"  latitude: {lat}\n"
            f"  longitude: {lon}\n"
            f"  currently_open: {'yes' if p.get('currentOpeningHours',{}).get('openNow') else 'no/unknown'}\n"
            f"  next_open: {p.get('currentOpeningHours',{}).get('nextCloseTime','N/A')}\n---"
        )
    return "\n\n".join(sections)

def tours_to_markdown(tours: List[Dict]) -> str:
    sections = ["=== Tours ==="]
    for idx, t in enumerate(tours, start=1):
        description = t.get("description","").replace("<div>","").replace("</div>","").strip()
        highlights = ". ".join(description.split(".")[:2]).strip() + "." if description else "—"
        sections.append(
            f"tour {idx}:\n"
            f"  name: {t.get('name','—')}\n"
            f"  price: {t.get('price',{}).get('currencyCode','')} {t.get('price',{}).get('amount','')}\n"
            f"  duration: {t.get('minimumDuration','—')}\n"
            f"  booking_link: {t.get('bookingLink','—')}\n"
            f"  highlights: {highlights}\n"
            f"  description: >\n    {description}\n---"
        )
    return "\n\n".join(sections)

def read_json_file(file_path: str) -> Union[List[Dict], Dict]:
    """
    Reads a JSON file and returns it as a Python object (list or dict).
    Automatically strips BOM characters and validates content.
    """
    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:  # utf-8-sig handles BOM if present
            content = f.read().strip()

        # Ensure the file is not empty
        if not content:
            raise ValueError(f"The file '{file_path}' is empty.")

        # Parse JSON safely
        data = json.loads(content)
        if not isinstance(data, (list, dict)):
            raise ValueError(f"The file '{file_path}' does not contain a valid JSON list or object.")
        return data

    except FileNotFoundError:
        raise FileNotFoundError(f"The file '{file_path}' was not found.")
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from '{file_path}': {e}")

# flight_data = read_json_file("./test_data/flight_3.json")
# hotel_data = read_json_file("./test_data/hotel_3.json")
# places_data = read_json_file("./test_data/places_3.json")
# tour_data = read_json_file("./test_data/tour_3.json")

# flights_markdown = flights_to_markdown(flight_data)
# hotels_markdown = hotels_to_markdown(hotel_data)
# places_markdown = places_to_markdown(places_data)
# tours_markdown = tours_to_markdown(tour_data)

# print(flights_markdown)
# print()
# print(hotels_markdown)
# print()
# print(places_markdown)
# print()
# print(tours_markdown)
