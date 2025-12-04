import json
from pathlib import Path
from autogen.agents.source._user_query_generation import generate_user_query

def main():

    base_dir = Path(__file__).resolve().parent
    user_cases_path = base_dir / "data/user_cases.json"
    queries_output_path = base_dir / "data/generated_user_queries.json"

    queries = []

    with open(user_cases_path, 'r') as f:
        user_cases = json.load(f)

    for case in user_cases:
        user_query = generate_user_query(case['user_profile'], case['user_travel_details'])
        print(f"User Case: {case}")
        print(f"Generated User Query: {user_query}")
        print("-" * 40)
        queries.append(user_query)

    with open(queries_output_path, 'w') as f:
        json.dump(queries, f, indent=4)
    
if __name__ == "__main__":
    main()