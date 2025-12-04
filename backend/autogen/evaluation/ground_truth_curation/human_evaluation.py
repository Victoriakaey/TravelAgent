import logging
from pathlib import Path
from typing import Dict, List, Iterable

from .helpers import load_any
from autogen.agents.source import extract_user_query
from autogen.services import setup_logging, saving_object_to_jsonl

logger = logging.getLogger(__name__)

def run_human_evaluation(user_profile: dict, user_travel_details: dict, plans: str, folder: str = "log/ground_truth_evaluation/human-2"):

    file_starter = f"{folder}/{user_profile['user_id']}"
    info_log_filename = file_starter + "/info_runtime.log"
    verbose_log_filename = file_starter + "/verbose_runtime.log"

    setup_logging(
            log_to_file=True,
            info_log_file= info_log_filename,  # INFO Level
            verbose_log_file= verbose_log_filename  # VERBOSE Level
        )

    logger.info(f"Saving info logs to {info_log_filename}")
    logger.info(f"Saving verbose logs to {verbose_log_filename}")

    query = extract_user_query(user_profile, user_travel_details)

    logger.info(f"Running critic auto-evaluation iteration for user_id {user_profile['user_id']}")
    logger.info(f"\nUser Profile:\n\n{user_profile}\n")
    logger.info(f"\nUser Travel Details:\n\n{user_travel_details}\n")
    
    for i, plan in enumerate(plans):
        scores_path = f"{folder}/artifacts/case_{i+1}/scores.jsonl"
        decisions_path = f"{folder}/artifacts/case_{i+1}/decisions.jsonl"
        memo_path = f"{folder}/artifacts/case_{i+1}/memos.jsonl"

        logger.info(f"\n\n========================================\nPlan being evaluated (Plan {i+1}):\n\n{plan}\n\n")
        
        logger.info("#A. Query Relevance: How well the itinerary aligns with the user profile and travel details.")
        logger.info("Rubric:\n1. Irrelevant: Largely ignores the user’s query/profile (destination, dates, preferences not reflected).\n2. Weak relevance: Covers only a small portion of the user query/profile, most details mismatched or missing.\n3. Moderate relevance: Partially aligned; some preferences/constraints are reflected, but coverage is incomplete.\n4. Strong relevance: Mostly aligned with the user query/profile, with only minor gaps.\n5. Fully relevant: Perfectly aligned with the user’s query/profile; all details respected.\n")
        logger.info("User Query: " + query)
        query_relevance_score = input("Query Relevance Score (1-5): ").strip()
        logger.info(f"Query Relevance Score (1-5): {query_relevance_score}")

        logger.info("#B. Factual Accuracy: Degree to which itinerary contents (e.g., place names, URLs, operating hours) are factually correct.")
        logger.info("Rubric:\n1. Highly inaccurate: Many factual errors; multiple places/URLs are wrong or fabricated.\n2. Inaccurate: Several errors; itinerary is unreliable.\n3. Partially accurate: Some minor errors, but itinerary is usable with corrections.\n4. Mostly accurate: Only 1–2 small factual issues, overall correct.\n5. Fully accurate: All facts verified, no errors.")
        factual_accuracy_score = input("Factual Accuracy Score (1-5): ").strip()
        logger.info(f"Factual Accuracy Score (1-5): {factual_accuracy_score}")

        logger.info("#C. Safety: Whether the itinerary avoids unsafe, misleading, or unsuitable recommendations for the user (context-aware).")
        logger.info("Rubric:\n1. Unsafe: Includes clearly dangerous/misleading recommendations.\n2. Questionable safety: Contains multiple recommendations that may pose risks or be unsuitable.\n3. Mostly safe: Minor concerns but generally acceptable.\n4. Safe: No significant risks, all recommendations appropriate.\n5. Very safe: Completely safe, user context fully considered (e.g., constraints like age, budget, accessibility).")
        safety_score = input("Safety Score (1-5): ").strip()
        logger.info(f"Safety Score (1-5): {safety_score}")

        logger.info("#D. Clarity & Readability: How clearly and logically the itinerary is structured and whether a user can easily follow it.")
        logger.info("Rubric:\n1. Very confusing: Poorly structured, hard to read or follow.\n2. Confusing: Structure exists but many unclear/ambiguous parts.\n3. Moderately clear: Usable but requires effort to interpret.\n4. Clear: Easy to follow with logical flow.\n5. Very clear: Exceptionally well-structured, easy to follow without effort.")
        clarity_score = input("Clarity & Readability Score (1-5): ").strip()
        logger.info(f"Clarity & Readability Score (1-5): {clarity_score}")

        logger.info("#E. Logical Feasibility: Logical feasibility of the plan (e.g., no impossible schedules, no unreasonable assumptions like multiple cities in one day).")
        logger.info("Rubric:\n1. Illogical: Contains clear impossibilities (e.g., multiple cities in a day, overnight transport without rest).\n2. Weak logic: Multiple questionable assumptions or unrealistic timings.\n3. Mostly logical: Generally reasonable but with some inconsistencies.\n4. Logical: Well thought-out with only minor issues.\n5. Perfectly logical: Fully feasible and realistic schedule.")
        logical_feasibility_score = input("Logical Feasibility Score (1-5): ").strip()
        logger.info(f"Logical Feasibility Score (1-5): {logical_feasibility_score}")

        logger.info("#F. Personalization: To what extent the plan reflects the user’s specific preferences and constraints beyond generic itineraries.")
        logger.info("Rubric:\n1. Generic: No personalization; could apply to anyone.\n2. Low personalization: Only superficial personalization (e.g., mentions one preference).\n3. Moderate personalization: Some preferences/constraints reflected, but incomplete.\n4. Strong personalization: Most preferences/constraints covered, feels tailored.\n5. Fully personalized: All preferences/constraints integrated in a natural, user-specific way.")    
        personalization_score = input("Personalization Score (1-5): ").strip()
        logger.info(f"Personalization Score (1-5): {personalization_score}")

        decision = input("Final Decision (ACCEPT or RE-WRITE): ").strip().upper()
        while decision not in {"ACCEPT", "RE-WRITE"}:
            decision = input("Invalid input. Please enter either ACCEPT or RE-WRITE: ").strip().upper()
        logger.info(f"Final Decision (ACCEPT or RE-WRITE): {decision}")

        memo = input("Any additional comments or notes? (optional): ").strip()
        logger.info(f"Any additional comments or notes? (optional): {memo}")

        scores = {
            "query_relevance": query_relevance_score,
            "factual_accuracy": factual_accuracy_score,
            "safety": safety_score,
            "clarity_readability": clarity_score,
            "logical_feasibility": logical_feasibility_score,
            "personalization": personalization_score
        }

        saving_object_to_jsonl(scores, scores_path)
        saving_object_to_jsonl(decision, decisions_path)
        saving_object_to_jsonl(memo, memo_path)

# ------------------------------
# Batch runner (main)
# ------------------------------

def _load_users(users_path: Path) -> List[Dict]:
    logger.info(f"Loading users from {users_path}")
    users = load_any(users_path)
    if not isinstance(users, list):
        raise TypeError(f"Expected users to be a list, got {type(users)}")
    logger.info(f"Loaded {len(users)} users")
    return users

def _load_case_plans(paths: Iterable[Path]) -> List[List[str]]:
    """Load each case file; log sizes; type-check."""
    all_cases: List[List[str]] = []
    for idx, p in enumerate(paths, start=1):
        logger.info(f"Loading ground-truth plans from {p}")
        plans = load_any(p)
        if not isinstance(plans, list):
            raise TypeError(f"Expected plans to be a list, got {type(plans)} at case {idx}")
        logger.info(f"Loaded {len(plans)} plans for case_{idx}")
        all_cases.append(plans)
    return all_cases

def _aligned_length(users: List[Dict], cases: List[List[str]]) -> int:
    """Return minimum length across users and all case lists; warn on mismatch."""
    lengths = [len(users)] + [len(c) for c in cases]
    if len(set(lengths)) != 1:
        logger.warning(
            "Users/Plans length mismatch: " +
            ", ".join([f"users={len(users)}"] + [f"case_{i+1}={len(c)}" for i, c in enumerate(cases)]) +
            ". Proceeding with the minimum length."
        )
    return min(lengths)

if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent

    users_path = base_dir / "data/user_cases.jsonl"
    case_paths = [
        base_dir / "data/case_1_plans.jsonl",
        base_dir / "data/case_2_plans.jsonl",
        base_dir / "data/case_3_plans.jsonl",
        base_dir / "data/case_4_plans.jsonl",
    ]

    users = _load_users(users_path)
    case_lists = _load_case_plans(case_paths)
    n = _aligned_length(users, case_lists)

    for i in range(n):
        current_user = users[i]
        # Fail fast if structure drifts
        if "user_profile" not in current_user or "user_travel_details" not in current_user:
            logger.error(f"User record at index {i} missing expected keys: {list(current_user.keys())}")
            continue

        user_profile = current_user["user_profile"]
        user_travel_details = current_user["user_travel_details"]
        current_plans = [case_lists[0][i], case_lists[1][i], case_lists[2][i], case_lists[3][i]]

        run_human_evaluation(
            user_profile=user_profile,
            user_travel_details=user_travel_details,
            plans=current_plans,  # FIXED: pass the list of plans
            folder="log/ground_truth_evaluation/human-3",
        )

# python -m autogen.evaluation.ground_truth_curation.human_evaluation
