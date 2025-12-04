import json
import statistics
from typing import List

def read_jsonl_file(path):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON line: {line}") from e
            data.append(value)
    return data

def split_by_separator(data: List, separator: str = "#") -> dict:
    cases = {}
    current_case_index = 1
    cases[f"case_{current_case_index}"] = []

    for item in data:
        if item == separator:
            # Start a new case
            current_case_index += 1
            cases[f"case_{current_case_index}"] = []
        else:
            cases[f"case_{current_case_index}"].append(item)

    return cases

def compute_mean(datas: List[int]) -> float:
    return round(statistics.mean(datas), 2) if datas else 0.0

def compute_median(datas: List[int]) -> float:
    return round(statistics.median(datas), 2) if datas else 0.0

def compute_stddev(datas: List[int]) -> float:
    return round(statistics.stdev(datas), 2) if len(datas) > 1 else 0.0

def compute_variance(datas: List[int]) -> float:
    return round(statistics.variance(datas), 2) if len(datas) > 1 else 0.0

def compute_percentage_above_threshold(datas: List[int], threshold: int = 4) -> float:
    if not datas:
        return 0.0
    count_above = sum(1 for data in datas if data >= threshold)
    return (count_above / len(datas)) * 100
