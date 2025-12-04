"""
Analyze:
  1) search_mode.jsonl  (SearchAgent telemetry)
  2) total_kept_dropped_content.jsonl  (WebScraperAgent keep/drop)

Outputs console summaries and saves CSV/JSON under --outdir.
No dependencies on ChatGPT-specific tools.
"""

from __future__ import annotations
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Any

import pandas as pd


# --------------------
# IO helpers
# --------------------
def read_jsonl(path: Path) -> List[Any]:
    """
    Load a .jsonl file into a list.
    Skips lines that are literal "#" separators.
    Keeps other unparseable lines as dicts with '_parse_error'.
    """
    rows: List[Any] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue

            # ---- NEW: skip case separators ----
            # These appear in your file as the JSON string "#"  (e.g., "#" or "\"#\"")
            if s == "#" or s == '"#"':
                continue

            try:
                obj = json.loads(s)
                rows.append(obj)
            except Exception as e:
                rows.append({"_parse_error": str(e), "_raw": s})

    return rows

# --------------------
# Search mode analysis
# --------------------
def analyze_search_modes(rows: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    modes_all = ["flight", "hotel", "tour", "place"]
    total_records = len(rows)

    mode_use = Counter()
    co_occurrence: Dict[str, Counter] = defaultdict(Counter)
    errors_per_mode = Counter()
    error_messages: Dict[str, Counter] = defaultdict(Counter)

    sum_len_all = Counter()
    sum_len_success_only = Counter()
    count_len_all = Counter()
    count_len_success_only = Counter()
    success_count = Counter()

    for row in rows:
        # which modes were attempted in this request
        modes = row.get("searched_mode", [])
        if not isinstance(modes, list):
            modes = [modes] if modes else []
        for m in modes:
            mode_use[m] += 1

        # co-occurrence counts
        for i in range(len(modes)):
            for j in range(i + 1, len(modes)):
                a, b = sorted([modes[i], modes[j]])
                co_occurrence[a][b] += 1

        # error harvesting
        errs = row.get("error", [])
        if isinstance(errs, dict):
            errs = [errs]
        for e in errs:
            m = e.get("mode")
            if not m:
                continue
            errors_per_mode[m] += 1
            payload = e.get("errors") or e.get("error")
            if isinstance(payload, dict):
                arr = payload.get("errors") or payload.get("error") or []
                if isinstance(arr, list):
                    for item in arr:
                        title = item.get("title") or item.get("code") or "UNKNOWN"
                        detail = item.get("detail")
                        msg = title if not detail else f"{title}::{detail}"
                        error_messages[m][msg] += 1
            else:
                error_messages[m][str(e)] += 1

        # content lengths per mode
        lens = row.get("searched_content_len", {})
        if isinstance(lens, dict):
            for m in modes_all:
                val = lens.get(m, 0)
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    sum_len_all[m] += val
                    count_len_all[m] += 1
                    if val > 0:
                        success_count[m] += 1
                        sum_len_success_only[m] += val
                        count_len_success_only[m] += 1

    # summary per mode
    summary_rows = []
    for m in modes_all:
        recs_with_len = count_len_all[m]
        successes = success_count[m]
        errors = errors_per_mode[m]
        avg_all = (sum_len_all[m] / recs_with_len) if recs_with_len else 0
        avg_success = (sum_len_success_only[m] / count_len_success_only[m]) if count_len_success_only[m] else 0
        success_rate = (successes / recs_with_len) * 100 if recs_with_len else 0
        error_rate = (errors / total_records) * 100 if total_records else 0
        summary_rows.append(
            {
                "mode": m,
                "records": total_records,
                "times_requested": mode_use[m],
                "records_with_len_field": recs_with_len,
                "success_count(>0 items)": successes,
                "success_rate_%": round(success_rate, 2),
                "error_count": errors,
                "error_rate_overall_%": round(error_rate, 2),
                "avg_items_all_records": round(avg_all, 2),
                "avg_items_success_only": round(avg_success, 2),
            }
        )

    df_summary = pd.DataFrame(summary_rows).sort_values("mode")

    # co-occurrence upper triangle
    cooc_rows = []
    for a in modes_all:
        for b in modes_all:
            if a >= b:
                continue
            cooc_rows.append({"mode_a": a, "mode_b": b, "count_same_request": co_occurrence[a][b]})
    df_cooc = pd.DataFrame(cooc_rows)

    # top error messages
    err_rows = []
    for m in modes_all:
        for msg, cnt in error_messages[m].most_common(10):
            err_rows.append({"mode": m, "message": msg, "count": cnt})
    df_errors = pd.DataFrame(err_rows)

    return df_summary, df_cooc, df_errors


# --------------------
# WebScraper keep/drop
# --------------------
def normalize_scraper_row(row: Any) -> Tuple[int, int, int]:
    """
    Returns (length, kept, dropped) from shapes like:
      - {"length_of_scraped_items": N, "total_kept_items": A, "total_dropped_items": B}
      - {"length": N, "kept": A, "dropped": B}
      - [length, kept, dropped]
      - [{"length": N}, {"kept": A}, {"dropped": B}]
    """
    if isinstance(row, dict):
        length = row.get("length_of_scraped_items") or row.get("length") or row.get("scraped_len") or 0
        kept = row.get("total_kept_items") or row.get("kept") or 0
        dropped = row.get("total_dropped_items") or row.get("dropped") or 0
        return int_safe(length), int_safe(kept), int_safe(dropped)

    if isinstance(row, list):
        # numeric triple
        if len(row) == 3 and all(isinstance(x, (int, float)) for x in row):
            return int(row[0]), int(row[1]), int(row[2])
        # list of dicts
        if all(isinstance(x, dict) for x in row):
            length = kept = dropped = 0
            for d in row:
                if "length_of_scraped_items" in d:
                    length = d["length_of_scraped_items"]
                if "length" in d:
                    length = d["length"]
                if "scraped_len" in d:
                    length = d["scraped_len"]
                if "total_kept_items" in d:
                    kept = d["total_kept_items"]
                if "kept" in d:
                    kept = d["kept"]
                if "total_dropped_items" in d:
                    dropped = d["total_dropped_items"]
                if "dropped" in d:
                    dropped = d["dropped"]
            return int_safe(length), int_safe(kept), int_safe(dropped)

    return 0, 0, 0


def int_safe(x: Any) -> int:
    try:
        return int(x)
    except Exception:
        return 0


def analyze_scraper(rows: List[Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    per_run = []
    sum_length = sum_kept = sum_dropped = 0

    for row in rows:
        if isinstance(row, dict) and "_parse_error" in row:
            continue
        length, kept, dropped = normalize_scraper_row(row)
        keep_rate = (kept / length) * 100 if length else 0.0
        drop_rate = (dropped / length) * 100 if length else 0.0
        per_run.append(
            {
                "length_of_scraped_items": length,
                "total_kept_items": kept,
                "total_dropped_items": dropped,
                "keep_rate_%": round(keep_rate, 2),
                "drop_rate_%": round(drop_rate, 2),
            }
        )
        sum_length += length
        sum_kept += kept
        sum_dropped += dropped

    df_runs = pd.DataFrame(per_run)
    overall = {
        "records": len(df_runs),
        "total_scraped_items": int(sum_length),
        "total_kept_items": int(sum_kept),
        "total_dropped_items": int(sum_dropped),
        "overall_keep_rate_%": round((sum_kept / sum_length) * 100, 2) if sum_length else 0.0,
        "overall_drop_rate_%": round((sum_dropped / sum_length) * 100, 2) if sum_length else 0.0,
    }
    return df_runs, overall


# --------------------
# CLI / Main
# --------------------
SEARCH_PATH = "data/search_mode.jsonl"
SCRAPER_PATH = "data/total_kept_dropped_content.jsonl"
OUTDIR = "autogen/evaluation/result/web_search_analysis_output"

def main():
    outdir = Path(OUTDIR)
    outdir.mkdir(parents=True, exist_ok=True)

    base_dir = Path(__file__).resolve().parent
    search_path = base_dir / SEARCH_PATH
    scraper_path = base_dir / SCRAPER_PATH

    search_rows = read_jsonl(search_path)
    scraper_rows = read_jsonl(scraper_path)

    # Analyze search
    df_search_summary, df_cooc, df_errors = analyze_search_modes(search_rows)
    df_search_summary.to_csv(outdir / "search_summary.csv", index=False)
    df_cooc.to_csv(outdir / "search_cooccurrence.csv", index=False)
    df_errors.to_csv(outdir / "search_top_errors.csv", index=False)

    print("\n=== Search Summary ===")
    print(df_search_summary)
    print("\n=== Search Co-occurrence ===")
    print(df_cooc)
    print("\n=== Search Top Errors ===")
    print(df_errors)

    # Analyze scraper
    df_runs, overall = analyze_scraper(scraper_rows)
    df_runs.to_csv(outdir / "scraper_runs.csv", index=False)
    with (outdir / "scraper_overall.json").open("w") as f:
        json.dump(overall, f, indent=2)

    print("\n=== Scraper Runs ===")
    print(df_runs)
    print("\n=== Scraper Overall ===")
    print(json.dumps(overall, indent=2))

    print(f"\nAll outputs saved to: {outdir.resolve()}")

if __name__ == "__main__":
    main()

# python -m autogen.evaluation.result.web_search_scraper_analysis