from datetime import datetime

def to_list(value):
    if isinstance(value, list):
        return value
    elif isinstance(value, str):
        return [value]
    return []

def extract_user_query(user_profile, travel_details):
    origin = travel_details.get("origin", "")
    destination = travel_details.get("destination", "")
    duration = travel_details.get("duration", "")
    travelers = travel_details.get("travelers", 0)
    companions = travel_details.get("travel_companions", "")
    start_date = travel_details.get("start_date", "")
    end_date = travel_details.get("end_date", "")

    def to_list(val):
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            return [val]
        return []

    accommodation = ", ".join(to_list(user_profile.get("accommodation", [])))
    transportation = ", ".join(to_list(user_profile.get("transportation", [])))
    preferences = ", ".join(to_list(user_profile.get("preferences", [])))
    constraints = ", ".join(to_list(user_profile.get("constraints", [])))

    # Format date more naturally
    def fmt_date(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d").strftime("%B %d, %Y")
        except:
            return d

    start_fmt = fmt_date(start_date)
    end_fmt = fmt_date(end_date)

    # Compose sentence parts
    trip_intro = f"I'm planning a {duration} trip from {origin} to {destination}, starting on {start_fmt} and ending on {end_fmt}. "
    if travelers == 1 and not companions:
        people_part = "I'll be traveling alone"
    else:
        people_part = f"I'll be traveling with {companions}" if companions else f"There will be {travelers} of us traveling"

    stay_part = f"and would prefer to stay at either {accommodation}" if accommodation else ""
    transport_part = f"I plan to get around using {transportation}" if transportation else ""

    preferences_part = f"I'm especially interested in {preferences}" if preferences else ""
    constraints_part = f"though I do have some limitations, such as {constraints}" if constraints else ""

    sentence_1 = f"{trip_intro} {people_part}, {stay_part}. {transport_part}.".strip()
    sentence_2 = f"{preferences_part} — {constraints_part}.".strip()

    return f"{sentence_1} {sentence_2}"


def get_user_keywords(user_profile):
    preferences = user_profile.get("preferences", [])
    constraints = user_profile.get("constraints", [])
    return preferences + constraints

def generate_user_query(user_profile, travel_details):
    query = extract_user_query(user_profile, travel_details)

    return query

# if __name__ == "__main__":
    
#     dummy_user_query = generate_user_query(user_profile_new, user_travel_details)
#     dummy_keywords = get_user_keywords(user_profile_new)

#     print("Dummy User Profile:\n")
#     print(user_profile_new)
#     print("Generated User Query:\n")
#     print(dummy_user_query)
#     print("\nExtracted Keywords:")
#     print(dummy_keywords)
