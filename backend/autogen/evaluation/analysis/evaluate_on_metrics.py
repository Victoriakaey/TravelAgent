import json
import pprint
import logging
import statistics
from pathlib import Path
from collections import Counter
from typing import Dict, List, Iterable, Tuple, Any

from .helpers import (
    compute_mean,
    compute_median,
    compute_stddev,
    compute_variance,
    compute_percentage_above_threshold,
)

# -------------------------------------------------------------
# 1.1 - Human Evaluation Metrics (from human_1_scores.jsonl)
# -------------------------------------------------------------
# Compute:
#   - mean
#   - median
#   - standard deviation
#   - % scores ≥ 4
#   - distribution histogram (#1, #2, #3, #4, #5)
# Interpretation:
#   - Higher → better
#   - Compare how critic and fallback affect improvement.

SCORE_KEYS = [
    "confidence",
    "relevance",
    "accuracy",
    "safety",
    "feasibility",
    "personalization",
]

def split_scores_by_dimension(scores):
    result = {}

    for case, score_list in scores.items():
        confidence_scores = []
        relevance_scores = []
        accuracy_scores = []
        safety_scores = []
        feasibility_scores = []
        personalization_scores = []
        for score in score_list:
            for key, value in score.items():
                
                if key == "confidence":
                    confidence_scores.append(int(value))
                elif key == "relevance":
                    relevance_scores.append(int(value))
                elif key == "accuracy":
                    accuracy_scores.append(int(value))
                elif key == "safety":
                    safety_scores.append(int(value))
                elif key == "feasibility":
                    feasibility_scores.append(int(value))
                elif key == "personalization":
                    personalization_scores.append(int(value))

        if confidence_scores:
            result[case] = {
                "confidence": confidence_scores,
                "relevance": relevance_scores,
                "accuracy": accuracy_scores,
                "safety": safety_scores,
                "feasibility": feasibility_scores,
                "personalization": personalization_scores,
            }
        else:
            result[case] = {
                "relevance": relevance_scores,
                "accuracy": accuracy_scores,
                "safety": safety_scores,
                "feasibility": feasibility_scores,
                "personalization": personalization_scores,
            }

    # print(result)
    return result

def analyze_scores(scores: Dict[str, Dict[str, List[int]]]) -> Dict[str, Any]:
    scores_by_dimension = split_scores_by_dimension(scores)
    analysis_result = {}

    for case, dimensions in scores_by_dimension.items():
        analysis_result[case] = {}
        for dimension, scores in dimensions.items():
            analysis_result[case][dimension] = {
                "mean": compute_mean(scores),
                "median": compute_median(scores),
                "stddev": compute_stddev(scores),
                "percentage_above_4": compute_percentage_above_threshold(scores, 4),
                "histogram": dict(Counter(scores))
            }

    return analysis_result

# -------------------------------------------------------------
# 1.2 - Human Evaluation Metrics (from human_1_decision.jsonl)
# -------------------------------------------------------------
# Compute:
#   - Acceptance rate: % ACCEPT
#   - Rewrite / Fail rate: % REWRITE or equivalent
# Interpretation:
#   - High acceptance → stable, reliable pipeline
#   - Differences between C and D isolate critic vs fallback

def analyze_decisions(data):

    result = {}
    for case, decisions in data.items():
        count = dict(Counter(decisions))
        total = sum(count.values())
        accept_rate = (count.get("ACCEPT", 0) / total) * 100 if total > 0 else 0.0
        rewrite_rate = (count.get("RE-WRITE", 0) / total) * 100 if total > 0 else 0.0

        result[case] = {
            "total": total,
            "accept_count": count.get("ACCEPT", 0),
            "rewrite_count": count.get("RE-WRITE", 0),
            "accept_rate": accept_rate,
            "rewrite_rate": rewrite_rate,
        }

    return result

# -------------------------------------------------------------
# 2.1 - Agent Behavior Metrics (from number_of_rounds.jsonl)
# -------------------------------------------------------------
# Report per-condition averages:
#   - web_scraper_agent_rounds
#   - search_agent_rounds
#   - content_generation_agent_rounds
#   - critic_agent_rounds
#   - transaction_agent_rounds
# Insights:
#   - Fallback increases rounds (Condition B, D)
#   - Critic increases content generation rounds (Condition C, D)
#   - Baseline (A) should always be (1,1,1,1)

def split_rounds_by_dimension(rounds):
    result = {}
    for case, score_list in rounds.items():
        web_scraper_agent_rounds = []
        search_agent_rounds = []
        content_generation_agent_rounds = []
        critic_agent_rounds = []
        transaction_agent_rounds = []
        for score in score_list:
            for key, value in score.items():
                if key == "web_scraper_agent_rounds":
                    web_scraper_agent_rounds.append(int(value))
                elif key == "search_agent_rounds":
                    search_agent_rounds.append(int(value))
                elif key == "content_generation_agent_rounds":
                    content_generation_agent_rounds.append(int(value))
                elif key == "critic_agent_rounds":
                    critic_agent_rounds.append(int(value))
                elif key == "transaction_agent_rounds":
                    transaction_agent_rounds.append(int(value))
        result[case] = {
            "web_scraper_agent_rounds": web_scraper_agent_rounds,
            "search_agent_rounds": search_agent_rounds,
            "content_generation_agent_rounds": content_generation_agent_rounds,
            "critic_agent_rounds": critic_agent_rounds,
            "transaction_agent_rounds": transaction_agent_rounds,
        }

    return result

def analyze_agent_rounds(rounds):
    rounds_by_dimension = split_rounds_by_dimension(rounds)
    analysis_result = {}

    for case, dimensions in rounds_by_dimension.items():
        analysis_result[case] = {}
        for dimension, scores in dimensions.items():
            analysis_result[case][dimension] = {
                "data": scores,
                "mean": compute_mean(scores),
                "median": compute_median(scores),
                "stddev": compute_stddev(scores),
                "variance": compute_variance(scores),
            }
    
    return analysis_result

# -------------------------------------------------------------
# 2.2 - Agent Behavior Metrics (from run_time.jsonl)
# -------------------------------------------------------------
# For each stage (e.g., `webscraper:1_web_scraping`, etc.):
# Compute:
#   - mean runtime
#   - variance
#   - total E2E runtime per case
#   - per-agent runtime % breakdown
# Interpretation:
#   - Fallback should increase scraping/searching runtime.
#   - Critic-only increases generation runtime (multiple rewrites).
#   - Full system increases both.
# You can produce a nice stacked runtime bar chart per condition.

def calculate_total_runtime_per_agent(runtimes):
    result = {}
    for case, iteration in runtimes.items():
        # total_runtime = 0.0
        ls = []
        for run in iteration:
            overall_runtime = 0.0
            agent_runtimes = {}
            for agent, runtime in run.items():
                # print(f"Case: {case}, Stage: {agent}, Runtime: {runtime}")
                overall_runtime += sum(runtime)
                agent_runtimes[agent] = round(sum(runtime), 2)
            agent_runtimes["overall_runtime"] = round(overall_runtime, 2)
            ls.append(agent_runtimes)

        result[case] = ls
    return result

def analyze_run_times(run_times):
    total_runtime_per_agent = calculate_total_runtime_per_agent(run_times)

    result = {}
    for case, iterations in total_runtime_per_agent.items():
        web_ls = []
        content_ls = []
        search_ls = []
        critic_ls = []
        transaction_ls = []
        overall_ls = []

        for iteration in iterations:
            # print(iteration)
            for key, value in iteration.items():
                if key == "WebScraperAgent":
                    web_ls.append(value)
                elif key == "ContentGeneratorAgent":
                    content_ls.append(value)
                elif key == "SearchAgent":
                    search_ls.append(value)
                elif key == "CriticAgent":
                    critic_ls.append(value)
                elif key == "TransactionAgent":
                    transaction_ls.append(value)
                elif key == "overall_runtime":
                    overall_ls.append(value)

        result[case] = {
            "web_scraper_agent": {
                "mean": compute_mean(web_ls),
                "median": compute_median(web_ls),
                "standard_deviation": compute_stddev(web_ls),
                "variance": compute_variance(web_ls),
                "data": web_ls
            },
            "content_generation_agent": {
                "mean": compute_mean(content_ls),
                "median": compute_median(content_ls),
                "standard_deviation": compute_stddev(content_ls),
                "variance": compute_variance(content_ls),
                "data": content_ls
            },
            "search_agent": {
                "mean": compute_mean(search_ls),
                "median": compute_median(search_ls),
                "standard_deviation": compute_stddev(search_ls),
                "variance": compute_variance(search_ls),
                "data": search_ls
            },
            "critic_agent": {
                "mean": compute_mean(critic_ls),
                "median": compute_median(critic_ls),
                "standard_deviation": compute_stddev(critic_ls),
                "variance": compute_variance(critic_ls),
                "data": critic_ls
            },
            "transaction_agent": {
                "mean": compute_mean(transaction_ls),
                "median": compute_median(transaction_ls),
                "standard_deviation": compute_stddev(transaction_ls),
                "variance": compute_variance(transaction_ls),
                "data": transaction_ls
            },
            "overall_runtime": {
                "mean": compute_mean(overall_ls),
                "median": compute_median(overall_ls),
                "standard_deviation": compute_stddev(overall_ls),
                "variance": compute_variance(overall_ls),
                "data": overall_ls
            }
        }
            
    return result
