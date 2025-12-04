import json
import uuid
import asyncio
import logging
import argparse
from pathlib import Path

from autogen.agents import AgentGroup
from autogen.services import user_input_func, no_block_user_input
from autogen.agents.source import generate_user_query, DUMMY_USER_PROFILE, DUMMY_USER_TRAVEL_DETAILS

logger = logging.getLogger(__name__)

async def run_test(
        agent_name: str, 
        case_num: int,
        folder: str,
        user_profile: dict, 
        user_travel_details: dict, 
        plan: str = "", 
        test_filter: bool = False, 
        filter_mode: str = "nlp", 
        test_critic: bool = False,
        testing_mode: bool = True
    ):

    session_id = str(uuid.uuid4())

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

    test_agent = AgentGroup(
        case_num = case_num, 
        folder = folder,
        session_id=session_id, 
        user_profile=user_profile, 
        user_travel_details=user_travel_details, 
        user_input_func=no_block_user_input if (testing_mode and not fallback_enabled) else user_input_func,
        plan=plan, 
        test_filter=test_filter, 
        filter_mode=filter_mode, 
        test_critic=test_critic,
        fallback_enabled=fallback_enabled,
        critic_enabled=critic_enabled,
    )

    if agent_name == "scraper":
        await test_agent.test_web_scraper_agent()
    elif agent_name == "search":
        await test_agent.test_search_agent()
    elif agent_name == "content":
        await test_agent.test_content_generation_agent()
    elif agent_name == "critic":
        await test_agent.test_critic_agent()
    elif agent_name == "transaction":
        await test_agent.test_transaction_agent()
    else:
        logger.info(f"Unknown agent name: {agent_name}")

def get_test_critic_cases():
    base_dir = Path(__file__).resolve().parent
    critic_test_cases_path = base_dir / "critic_test_cases.json"

    with open(critic_test_cases_path, "r") as f:
        test_cases = json.load(f)

    return test_cases

def test_web_scraper_agent_without_fallback(user_case: dict):
    logger.info(f"Running test for WebScraperAgent on 'scraper' test mode")
    asyncio.run(run_test(
        agent_name="scraper", 
        case_num=1,
        folder=f"test_web_scraper_without_fallback", 
        user_profile=user_case['user_profile'], 
        user_travel_details=user_case['user_travel_details']
    ))

def test_web_scraper_agent_with_fallback(user_case: dict):
    logger.info(f"Running test for WebScraperAgent on 'scraper' test mode")
    asyncio.run(run_test(
        agent_name="scraper", 
        case_num=2,
        folder=f"test_web_scraper_with_fallback", 
        user_profile=user_case['user_profile'], 
        user_travel_details=user_case['user_travel_details']
    ))

def test_nlp_filter_feature_from_web(user_case: dict):
    logger.info(f"Running test for WebScraperAgent on 'nlp_filter_feature' test mode")
    asyncio.run(run_test(
        agent_name="scraper", 
        case_num=1,
        folder=f"test_nlp_filter_feature", 
        user_profile=user_case['user_profile'], 
        user_travel_details=user_case['user_travel_details'], 
        test_filter=True
    )),

def test_llm_filter_feature_from_web(user_case: dict):
    logger.info(f"Running test for WebScraperAgent on 'llm_filter_feature' test mode")
    asyncio.run(run_test(
        agent_name="scraper", 
        case_num=1,
        folder=f"test_llm_filter_feature", 
        user_profile=user_case['user_profile'], 
        user_travel_details=user_case['user_travel_details'],
        test_filter=True,
        filter_mode="llm"
    )),

def test_search_agent_without_fallback(user_case: dict):
    logger.info(f"Running test for SearchAgent on 'search' test mode")
    asyncio.run(run_test(
        agent_name="search", 
        case_num=1, 
        folder=f"test_search_without_fallback", 
        user_profile=user_case['user_profile'], 
        user_travel_details=user_case['user_travel_details']
    ))

def test_content_generation_agent(user_case: dict):
    logger.info(f"Running test for ContentGenerationAgent on 'content generation' test mode")
    asyncio.run(run_test(
        agent_name="content", 
        case_num=1,
        folder=f"test_content_generation", 
        user_profile=user_case['user_profile'], 
        user_travel_details=user_case['user_travel_details']
    ))

def test_critic_agent(test_cases: list):
    for case in test_cases:
        logger.info(f"Running test case {case['test_id']} for agent 'critic'")
        asyncio.run(run_test(
            agent_name="critic", 
            case_num=3,
            folder=f"test_critic/{case['test_id']}", 
            user_profile=case['user_profile'], 
            user_travel_details=case['user_travel_details'], 
            plan=case['itinerary_text'],
            test_critic=True
        ))
            
def test_transaction_agent(user_case: dict):
    logger.info(f"Running test for TransactionAgent on 'transaction' test mode")
    asyncio.run(run_test(
        agent_name="transaction", 
        case_num=1,
        folder=f"test_transaction", 
        user_profile=user_case['user_profile'], 
        user_travel_details=user_case['user_travel_details']
    ))

TEST_FUNCTIONS = {
    "webscraper": lambda uc: test_web_scraper_agent_without_fallback(user_case=uc),
    "webscraper_fallback": lambda uc: test_web_scraper_agent_with_fallback(user_case=uc),
    "nlp_filter": lambda uc: test_nlp_filter_feature_from_web(user_case=uc),
    "llm_filter": lambda uc: test_llm_filter_feature_from_web(user_case=uc),
    "search": lambda uc: test_search_agent_without_fallback(user_case=uc),
    "content": lambda uc: test_content_generation_agent(user_case=uc),
    "critic": lambda _: test_critic_agent(test_cases=get_test_critic_cases()),
    "transaction": lambda uc: test_transaction_agent(user_case=uc),
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run selected TravelAgent tests.")
    parser.add_argument("--test", type=str, required=True, choices=TEST_FUNCTIONS.keys(), help="Name of the test to run.")
    args = parser.parse_args()

    test_user_case = {
        "user_profile": DUMMY_USER_PROFILE,
        "user_travel_details": DUMMY_USER_TRAVEL_DETAILS
    }

    # Run requested test
    TEST_FUNCTIONS[args.test](test_user_case)

    print(f"Test '{args.test}' completed.")

# python -m autogen.test.test_agents --test <test-mode>
