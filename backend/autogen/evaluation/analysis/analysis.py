import pprint
from pathlib import Path

from .helpers import read_jsonl_file, split_by_separator
from .evaluate_on_metrics import (
    analyze_scores, 
    analyze_decisions,
    analyze_agent_rounds,
    analyze_run_times,
    calculate_total_runtime_per_agent
)
from .correlation_confusion_matrix import get_correlation_and_confusion_matrix

def display_analysis(human_scores_analysis, critic_scores_analysis, human_decision_analysis, critic_decision_analysis, rounds_analysis, runtimes_analysis):
    print("===================Human Scores Analysis:====================\n")
    pprint.pprint(human_scores_analysis)

    print("\n===================Critic Scores Analysis:====================\n")
    pprint.pprint(critic_scores_analysis)

    print("\n===================Human Decisions Analysis:====================\n")
    pprint.pprint(human_decision_analysis)

    print("\n===================Critic Decisions Analysis:====================\n")
    pprint.pprint(critic_decision_analysis)

    print("\n===================Agent Rounds Analysis:====================\n")
    pprint.pprint(rounds_analysis)

    print("\n===================Run Times Analysis:====================\n")
    pprint.pprint(runtimes_analysis)

    print("\n===================Correlation and Confusion Matrix:====================\n")
    get_correlation_and_confusion_matrix()

if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent

    human_decision_path = base_dir / "data/human_decision.jsonl"
    critic_decision_path = base_dir / "data/critic_agent_decision.jsonl"
    human_scores_path = base_dir / "data/human_scores.jsonl"
    critic_scores_path = base_dir / "data/critic_agent_scores.jsonl"

    number_of_rounds_path = base_dir / "data/number_of_rounds.jsonl"
    run_time_plan = base_dir / "data/run_time.jsonl"
    success_path = base_dir / "data/success.jsonl"

    human_scores_data = read_jsonl_file(human_scores_path)  
    critic_scores_data = read_jsonl_file(critic_scores_path)
    human_decisions_data = read_jsonl_file(human_decision_path) 
    critic_decisions_data = read_jsonl_file(critic_decision_path)
    rounds_data = list(read_jsonl_file(number_of_rounds_path)) 

    runtimes_data = read_jsonl_file(run_time_plan) 
    successes_data = read_jsonl_file(success_path) 

    # rounds_cases = split_by_separator(rounds)
    human_scores = split_by_separator(human_scores_data)
    human_scores_analysis = analyze_scores(human_scores)
    # print(human_scores)
    # pprint.pprint(human_scores_analysis)

    critic_scores = split_by_separator(critic_scores_data)
    critic_scores_analysis = analyze_scores(critic_scores)
    # print(critic_scores)
    # pprint.pprint(critic_scores_analysis)

    human_decisions = split_by_separator(human_decisions_data)
    # pprint.pprint(human_decisions)
    human_decision_analysis = analyze_decisions(human_decisions)
    # pprint.pprint(human_decision_analysis)

    critic_decisions = split_by_separator(critic_decisions_data)
    # pprint.pprint(critic_decisions)
    critic_decision_analysis = analyze_decisions(critic_decisions)
    # pprint.pprint(critic_decision_analysis)

    rounds = split_by_separator(rounds_data)
    rounds_analysis = analyze_agent_rounds(rounds)
    # pprint.pprint(rounds_analysis)

    runtimes = split_by_separator(runtimes_data)
    total_runtime_per_agent = calculate_total_runtime_per_agent(runtimes)
    # pprint.pprint("Total Runtime Per Agent:")
    # pprint.pprint(total_runtime_per_agent)
    runtimes_analysis = analyze_run_times(runtimes)

    display_analysis(
        human_scores_analysis, 
        critic_scores_analysis,
        human_decision_analysis, 
        critic_decision_analysis,
        rounds_analysis, 
        runtimes_analysis
    )

# python -m autogen.evaluation.analysis.analysis