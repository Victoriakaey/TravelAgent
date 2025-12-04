import os
import json
import asyncio
import logging
import argparse

from autogen.agents import AgentGroup
from .agents.source import generate_user_query
from autogen.services import user_input_func, no_block_user_input, saving_object_to_jsonl

OUTPUT_FOLDER = "" 
logger = logging.getLogger(__name__)

async def run_autogen_agent(message: str, user_profile: dict, user_travel_details: dict, case_num: int, folder: str = "", testing_mode: bool = True) -> dict:

    plan_output_path = f"log/case_{case_num}/artifacts/generated_plans.jsonl"
    number_of_rounds_output_path = f"log/case_{case_num}/artifacts/number_of_rounds.jsonl"
    scraping_history_output_path = f"log/case_{case_num}/artifacts/scraping_history.jsonl"
    search_activities_output_path = f"log/case_{case_num}/artifacts/search_activities.jsonl"

    if case_num == 1: # Baseline
        fallback_enabled = False
        critic_enabled = False
    elif case_num == 2: # With Fallback Only
        fallback_enabled = True
        critic_enabled = False
    elif case_num == 3: # With Critic Only
        fallback_enabled = False
        critic_enabled = True
    else: # Full System
        fallback_enabled = True
        critic_enabled = True

    group = AgentGroup(
        user_profile=user_profile, 
        case_num=case_num,
        user_travel_details=user_travel_details, 
        user_input_func=no_block_user_input if (testing_mode and not fallback_enabled) else user_input_func, # TODO: REPLACE THIS WITH user_input_func AFTER TESTING!!
        folder=folder,
        fallback_enabled=fallback_enabled,
        critic_enabled=critic_enabled,
    )
    
    final_plan = await group.process_user_message(message, user_profile=user_profile, user_travel_details=user_travel_details) # Final Generated Plan
    saving_object_to_jsonl(final_plan, plan_output_path) # Final Generated Plan
    number_of_rounds = group.get_all_number_of_rounds_from_agents() # Number of Rounds for Each Agents
    saving_object_to_jsonl(number_of_rounds, number_of_rounds_output_path) 
    scraping_history = group.get_list_of_scraping_history() # WebScraperAgent Artifacts
    saving_object_to_jsonl(scraping_history, scraping_history_output_path)
    search_modes_and_errors = group.get_list_of_search_modes_and_errors() # SearchAgent Artifacts
    saving_object_to_jsonl(search_modes_and_errors, search_activities_output_path)

def run_system(case_num: int, folder: str = ""):
    # print(f"Starting Autogen Agent Ablation Study with case number {case_num}.")
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    user_cases_path = os.path.join(ROOT_DIR, "user_cases_ablation_study.json")

    with open(user_cases_path, "r") as f:
        test_cases = json.load(f)

    for i, case in enumerate(test_cases):
        logger.info(f"Running autogen agent iteration {i+1} for user_id {case['user_profile']['user_id']}")
        query = "Hello, I need help with my travel plans. " + generate_user_query(case['user_profile'], case['user_travel_details'])
        asyncio.run(
            run_autogen_agent(
                query, 
                user_profile=case['user_profile'], 
                user_travel_details=case['user_travel_details'],
                case_num=case_num, 
                folder=folder
            )
        )
        logger.info(f"Finished autogen agent iteration {i+1} for user_id {case['user_profile']['user_id']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run TravelAgent ablation experiment.")

    parser.add_argument(
        "--case_num",
        type=int,
        required=True,
        choices=[1, 2, 3, 4],
        help="Ablation condition: 1=baseline, 2=fallback, 3=critic, 4=full system"
    )

    args = parser.parse_args()

    run_system(case_num=args.case_num)

# python -m autogen.main --case_num <case-num>
