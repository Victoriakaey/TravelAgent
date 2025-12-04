import os
import json

DUMMY_USER_PROFILE = {
    "user_id": 1,
    "age": 45,
    "date_of_birth": "1978-05-15",
    "name": "Alice Johnson",
    "first_name": "Alice",
    "last_name": "Johnson",
    "email": "alice.johnson@example.com",
    "preferred_language": "Chinese",
    "gender": "female",
    "transportation": [
        "Alaska Airline",
        "BART",
    ],
    "accommodation": [
        "Hilton Hotel",
        "Airbnb",
    ],
    "preferences": [
        "traditional arts",
        "local cuisine",
        "cultural experiences",
        "market exploration",
        "seafood",
    ],
    "constraints": [
        "moderate budget",
        "medium activity level"
    ],
}

DUMMY_USER_TRAVEL_DETAILS = {
    "user_id": 1,
    "origin": "San Francisco, CA, USA",
    "destination": "Tokyo, Japan",
    "travelers": 1,
    "travel_companions": "",
    "duration": "7 days",
    "start_date": "2025-10-10",
    "end_date": "2025-10-16",
    "currency": "USD",
}

def get_dummy_scraped_content():
    dummy_scraped_content_file = os.path.join(
        os.path.dirname(__file__),
        "scraped_content.json"
    )
    try:
        with open(dummy_scraped_content_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Dummy scraped content file not found: {dummy_scraped_content_file}")
        return {}