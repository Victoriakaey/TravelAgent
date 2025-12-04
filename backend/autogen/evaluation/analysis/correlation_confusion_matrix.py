import json
import pandas as pd
import numpy as np
from pathlib import Path

# ---------------------------------------------------
# Config: data folder (same directory as this script)
# ---------------------------------------------------
BASE = Path(__file__).parent / "data"

# =========================
# Helpers to load the data
# =========================

def load_jsonl_dicts(path: Path):
    """Load jsonl where each valid line is a JSON object (used for scores)."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            # skip manual separators
            if line == '"#"' or line == "#":
                continue

            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                print(f"[WARN] Skip invalid JSON line {i} in {path.name}: {line!r}")
                continue

            # sometimes it's a JSON string that itself is a JSON dict
            if isinstance(value, str):
                v_strip = value.strip()
                if v_strip == "#":
                    continue
                if v_strip.startswith("{") and v_strip.endswith("}"):
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        pass

            if not isinstance(value, dict):
                print(f"[WARN] Skip non-dict record on line {i} in {path.name}: {value!r}")
                continue

            records.append(value)
    return records


def load_decisions(path: Path):
    """
    Load decisions where each line is `"ACCEPT"` or `"RE-WRITE"` (JSON string),
    or just raw ACCEPT / RE-WRITE.
    """
    decisions = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            if line == '"#"' or line == "#":
                continue

            # Usually JSON string like `"ACCEPT"`
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                value = line  # fallback: raw string

            # also support dict format like {"decision": "..."} if ever used
            if isinstance(value, dict):
                if "decision" in value:
                    d_str = str(value["decision"]).strip().upper()
                    if d_str in ("ACCEPT", "RE-WRITE"):
                        decisions.append(d_str)
                    else:
                        print(f"[WARN] Unknown decision value in dict on line {i} in {path.name}: {value!r}")
                else:
                    print(f"[WARN] Unexpected dict in decisions file {path.name} line {i}: {value!r}")
                continue

            if isinstance(value, str):
                v = value.strip().upper()
                if v in ("ACCEPT", "RE-WRITE"):
                    decisions.append(v)
                else:
                    print(f"[WARN] Skip unknown decision value in {path.name} line {i}: {value!r}")
                continue

            print(f"[WARN] Skip non-string decision in {path.name} line {i}: {value!r}")
    return decisions


def parse_critic_scores(rec):
    """
    rec can be:
    - string: "confidence=5; relevance=4; ..."
    - list: ["confidence=5; relevance=4; ..."]
    - dict: {"confidence": "5", "relevance": "4", ...}
            or {"scores": "confidence=5; ..."}
    Return: dict{"confidence":5.0, "relevance":4.0, ...}
    """
    # Case 1: already a dict with individual keys
    if isinstance(rec, dict):
        keys = ["confidence", "relevance", "accuracy",
                "safety", "feasibility", "personalization"]

        if any(k in rec for k in keys):
            out = {}
            for k in keys:
                if k in rec:
                    try:
                        out[k] = float(rec[k])
                    except Exception:
                        pass
            return out

        # maybe {"scores": "confidence=5; ..."}
        if "scores" in rec:
            rec = rec["scores"]
        # or a single-key dict whose value is the string
        elif len(rec) == 1:
            rec = next(iter(rec.values()))
        else:
            return {}

    # Case 2: list, just take first element
    if isinstance(rec, list):
        if not rec:
            return {}
        rec = rec[0]

    # Case 3: must be string to parse "a=b; c=d"
    if not isinstance(rec, str):
        return {}

    s = rec
    result = {}
    parts = [p.strip() for p in s.split(";") if p.strip()]
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            k = k.strip()
            v = v.strip()
            try:
                result[k] = float(v)
            except Exception:
                pass
    return result


def decision_to_int(d):
    """
    Map decision string to int:
    ACCEPT   -> 1 (positive)
    RE-WRITE -> 0 (negative)
    """
    if isinstance(d, str):
        d = d.strip().upper()
        if d == "ACCEPT":
            return 1
        if d == "RE-WRITE":
            return 0
    return -1


# =====================
# Load all input files
# =====================

def get_correlation_and_confusion_matrix():

    human_scores = load_jsonl_dicts(BASE / "human_scores.jsonl")
    critic_scores = load_jsonl_dicts(BASE / "critic_agent_scores.jsonl")
    human_decisions_raw = load_decisions(BASE / "human_decision.jsonl")
    critic_decisions_raw = load_decisions(BASE / "critic_agent_decision.jsonl")

    assert len(human_scores) == len(critic_scores), \
        f"score lengths mismatch: human={len(human_scores)}, critic={len(critic_scores)}"
    assert len(human_decisions_raw) == len(critic_decisions_raw) == len(human_scores), \
        f"decision lengths mismatch: human_dec={len(human_decisions_raw)}, " \
        f"critic_dec={len(critic_decisions_raw)}, scores={len(human_scores)}"

    rows = []

    for i in range(len(human_scores)):
        h = human_scores[i]
        c = parse_critic_scores(critic_scores[i])
        hd = decision_to_int(human_decisions_raw[i])
        cd = decision_to_int(critic_decisions_raw[i])

        rows.append({
            "case_id": i,

            # human scores
            "human_relevance": float(h["relevance"]),
            "human_accuracy": float(h["accuracy"]),
            "human_safety": float(h["safety"]),
            "human_feasibility": float(h["feasibility"]),
            "human_personalization": float(h["personalization"]),

            # critic scores
            "critic_confidence": c.get("confidence", np.nan),
            "critic_relevance": c.get("relevance", np.nan),
            "critic_accuracy": c.get("accuracy", np.nan),
            "critic_safety": c.get("safety", np.nan),
            "critic_feasibility": c.get("feasibility", np.nan),
            "critic_personalization": c.get("personalization", np.nan),

            # decisions
            "human_decision": hd,
            "critic_decision": cd,
        })

    df = pd.DataFrame(rows)

    # ======================================
    # 1. Dimension-wise score correlations
    # ======================================

    pairs = [
        ("human_relevance", "critic_relevance"),
        ("human_accuracy", "critic_accuracy"),
        ("human_safety", "critic_safety"),
        ("human_feasibility", "critic_feasibility"),
        ("human_personalization", "critic_personalization"),
    ]

    print("===== DIMENSION-WISE CORRELATIONS =====")
    for h_col, c_col in pairs:
        sub = df[[h_col, c_col]].dropna()
        pearson = sub[h_col].corr(sub[c_col], method="pearson")
        spearman = sub[h_col].corr(sub[c_col], method="spearman")
        print(f"{h_col} vs {c_col}:  Pearson={pearson:.3f},  Spearman={spearman:.3f}")

    # ======================================
    # 2. Overall score correlation
    # ======================================

    df["human_overall"] = df[[
        "human_relevance", "human_accuracy", "human_safety",
        "human_feasibility", "human_personalization"
    ]].mean(axis=1)

    df["critic_overall"] = df[[
        "critic_relevance", "critic_accuracy", "critic_safety",
        "critic_feasibility", "critic_personalization"
    ]].mean(axis=1)

    sub = df[["human_overall", "critic_overall"]].dropna()
    pearson_overall = sub["human_overall"].corr(sub["critic_overall"], method="pearson")
    spearman_overall = sub["human_overall"].corr(sub["critic_overall"], method="spearman")

    print("\n===== OVERALL SCORE CORRELATION =====")
    print(f"Overall: Pearson={pearson_overall:.3f}, Spearman={spearman_overall:.3f}")

    # ======================================
    # 3. Decision-level performance metrics
    # ======================================

    valid = df[(df["human_decision"] >= 0) & (df["critic_decision"] >= 0)]

    y_true = valid["human_decision"].values
    y_pred = valid["critic_decision"].values

    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())

    print("\n===== CONFUSION MATRIX =====")
    print("                Critic=ACCEPT   Critic=RE-WRITE")
    print(f"Human=ACCEPT         {tp:3d}             {fn:3d}")
    print(f"Human=RE-WRITE       {fp:3d}             {tn:3d}")

    # Accuracy
    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total > 0 else 0.0

    # Precision / Recall / F1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    # Specificity (True Negative Rate)
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    # Balanced Accuracy
    balanced_accuracy = (recall + specificity) / 2.0

    # MCC (Matthews Correlation Coefficient)
    denom = (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
    if denom > 0:
        mcc = (tp * tn - fp * fn) / np.sqrt(denom)
    else:
        mcc = 0.0

    print("\n===== DECISION METRICS =====")
    print(f"True Positives (TP):      {tp:.3f}")
    print(f"True Negatives (TN):      {tn:.3f}")
    print(f"False Positives (FP):     {fp:.3f}")
    print(f"False Negatives (FN):     {fn:.3f}")
    print(f"Accuracy:           {accuracy:.3f}")
    print(f"Precision:          {precision:.3f}")
    print(f"Recall (Sensitivity): {recall:.3f}")
    print(f"F1:                 {f1:.3f}")
    print(f"Specificity (TNR):  {specificity:.3f}")
    print(f"Balanced Accuracy:  {balanced_accuracy:.3f}")
    print(f"MCC:                {mcc:.3f}")


if __name__ == "__main__":
    get_correlation_and_confusion_matrix()


# python -m autogen.evaluation.analysis.correlation_confusion_matrix