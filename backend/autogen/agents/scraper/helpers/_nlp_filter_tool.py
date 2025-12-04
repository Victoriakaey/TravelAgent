import re
from typing import Dict, Any, List, Optional, Tuple
from sentence_transformers import SentenceTransformer, util
from dateparser.search import search_dates

# -------- thresholds / policy --------
ACCEPTED_YEAR = 2022
PREFERENCE_THRESHOLD = 1
RELEVANCE_THRESHOLD = 0.45
RECENCY_RELEVANCE_OVERRIDE = 0.56   # if no dates, allow relevance ≥ this to satisfy recency
PREF_BYPASS_RELEVANCE = 0.56        # allow KEEP with high relevance even if prefs=0

# Dynamic anchor boost (no hardcoded locations)
ANCHOR_BOOST_PER_MATCH = 0.02       # small bump per matched intent anchor
MAX_ANCHOR_BOOST = 0.06             # cap total anchor boost
MAX_INTENT_ANCHORS = 12             # limit to reduce noise

SUSPICIOUS_PATTERNS = ["fake", "scam", "hoax", "misleading", "false info", "clickbait"]
BLACKLISTED_WORDS = ["violence", "scam", "adult-only", "nudity", "political", "hate", "terror", "religious extremism"]

# simple stopwords for anchor extraction (kept tiny on purpose)
_STOPWORDS = {
    "the","a","an","and","or","for","to","of","in","on","at","with","by","from",
    "best","top","guide","trip","tour","tours","travel","itinerary","day","days",
    "this","that","these","those","is","are","was","were","be","been","being",
    "you","your","yours","our","ours","their","theirs"
}

class NLPFilterTool:
    """
    Explainable filter with dynamic anchor boosting (no hardcoded locations).
    Policy:
      KEEP requires ACCURACY_OK ∧ SAFETY_OK ∧ RECENCY_OK ∧ RELEVANCE_OK ∧ PREFERENCE_SUFFICIENT,
      where PREFERENCE_SUFFICIENT := (preference_score ≥ 1) OR (relevance ≥ PREF_BYPASS_RELEVANCE).
    """
    def __init__(self, user_profile: dict):
        self.similarity_model = "all-MiniLM-L6-v2"
        self.similarity_metric = "cosine_similarity"
        self.embedder = SentenceTransformer(self.similarity_model)
        self.user_profile_keywords = self.extract_keywords_from_profile(user_profile)
        self.user_profile = user_profile
        # cache intent anchors built from query+profile per call; not stored globally

    # ----------------- feature extraction -----------------

    def extract_keywords_from_profile(self, profile):
        keywords = []
        for section in profile.values():
            if isinstance(section, str):
                keywords.extend(section.lower().split())
            elif isinstance(section, list):
                for item in section:
                    if isinstance(item, str):
                        keywords.extend(item.lower().split())
        # drop numeric-only tokens; dedupe preserving order
        keywords = [kw for kw in keywords if not kw.isdigit()]
        return list(dict.fromkeys(keywords))

    def _compact_profile_text(self) -> str:
        # compact the profile keyword list to avoid ballooning the fused query
        return " ".join(self.user_profile_keywords[:50])

    def is_factually_suspicious(self, chunk):
        chunk_lc = chunk.lower()
        hits = [t for t in SUSPICIOUS_PATTERNS if t in chunk_lc]
        return len(hits) > 0, hits

    def is_up_to_date(self, chunk, metadata=None):
        years_found = []
        try:
            found = search_dates(chunk)
            if found:
                for _, date in found:
                    years_found.append(date.year)
        except Exception:
            pass

        meta_year = None
        if metadata and "last_updated" in metadata:
            try:
                meta_year = int(str(metadata["last_updated"])[:4])
            except Exception:
                meta_year = None

        up_to_date_text = any(y >= ACCEPTED_YEAR for y in years_found)
        up_to_date_meta = (meta_year is not None and meta_year >= ACCEPTED_YEAR)
        return (up_to_date_text or up_to_date_meta), {
            "years_found": sorted(set(y for y in years_found if y is not None)),
            "meta_last_updated_year": meta_year
        }

    # ----------------- relevance & anchors -----------------

    def _fused_intent_text(self, user_query: str) -> str:
        profile_text = self._compact_profile_text()
        return f"{user_query} | profile: {profile_text}" if profile_text else user_query

    def semantic_relevance(self, chunk: str, user_query: str) -> float:
        """
        Cosine similarity between chunk and fused intent (query + profile keywords).
        """
        fused_query = self._fused_intent_text(user_query)
        chunk_embedding = self.embedder.encode(chunk, convert_to_tensor=True)
        query_embedding = self.embedder.encode(fused_query, convert_to_tensor=True)
        return float(util.cos_sim(query_embedding, chunk_embedding)[0][0])

    def _extract_anchors(self, text: str) -> List[str]:
        """
        Extract dynamic anchors from text:
          - multi-word proper-like spans (Capitalized sequences)
          - salient non-stopword tokens (>3 chars)
        Lowercased for matching.
        """
        anchors: List[str] = []

        # multi-word capitalized spans (e.g., "Blue Lagoon", "Eiffel Tower")
        for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text):
            anchors.append(m.group(1).lower())

        # single tokens (letters/numbers/hyphen), length>3 and not stopword
        for tok in re.findall(r"[A-Za-z][A-Za-z0-9\-]+", text):
            t = tok.lower()
            if len(t) <= 3: 
                continue
            if t in _STOPWORDS:
                continue
            anchors.append(t)

        # dedupe while preserving order, truncate to cap noise
        seen = set()
        ordered = []
        for a in anchors:
            if a not in seen:
                seen.add(a)
                ordered.append(a)
        return ordered[:MAX_INTENT_ANCHORS]

    def _apply_dynamic_anchor_boost(self, relevance: float, chunk_text: str, intent_text: str) -> Tuple[float, Dict[str, Any]]:
        """
        Add a small, capped boost per intent anchor found in the chunk.
        No penalties, no hardcoded locations.
        """
        chunk_lc = chunk_text.lower()
        intent_anchors = self._extract_anchors(intent_text)
        matches = [a for a in intent_anchors if a in chunk_lc]
        boost = min(len(matches) * ANCHOR_BOOST_PER_MATCH, MAX_ANCHOR_BOOST)
        adjusted = max(-1.0, min(1.0, relevance + boost))
        info = {
            "intent_anchors": intent_anchors,
            "matched_anchors": matches,
            "anchor_boost": round(boost, 4),
            "relevance_before": round(relevance, 4),
            "relevance_after": round(adjusted, 4),
        }
        return adjusted, info

    # ----------------- safety & prefs -----------------

    def preference_match_score(self, chunk):
        chunk_lc = chunk.lower()
        hits = []
        for kw in self.user_profile_keywords:
            if re.search(rf"\b{re.escape(kw)}\b", chunk_lc):
                hits.append(kw)
        return len(hits), hits

    def is_contextually_safe(self, chunk):
        chunk_lc = chunk.lower()
        hits = [t for t in BLACKLISTED_WORDS if t in chunk_lc]
        return len(hits) == 0, hits

    # ----------------- explainability helpers -----------------

    def _rule(self, id: str, passed: bool, value: Any = None, threshold: Any = None, because: str = ""):
        return {"id": id, "passed": bool(passed), "value": value, "threshold": threshold, "because": because}

    def _summary(self, decision: str, scorecard: Dict[str, Any]) -> str:
        if decision == "KEEP":
            return (
                f"KEEP: relevance={scorecard['relevance']['value']:.2f} "
                f"(> {scorecard['relevance']['threshold']}), "
                f"pref_sufficient={scorecard['preference_sufficient']['passed']}, "
                f"up_to_date_ok={scorecard['recency']['passed']}."
            )
        failed = [r for r in scorecard["decision_trace"] if not r["passed"] and r["id"] in scorecard["required_rules"]]
        return "DROP: " + "; ".join(r["because"] for r in failed if r["because"])


    def failed_required_rules(scorecard):
        """Return failed gating rules with reasons."""
        req = scorecard.get("required_rules", set())
        trace = scorecard.get("decision_trace", [])
        return [
            {"id": r["id"], "because": r.get("because", ""), "value": r.get("value"), "threshold": r.get("threshold")}
            for r in trace if r.get("id") in req and not r.get("passed", False)
        ]

    def score_margins(scorecard):
        """Give useful 'margins' for tuning (value - threshold) when numeric."""
        rel = scorecard.get("relevance", {})
        pref = scorecard.get("preferences", {})
        rec = scorecard.get("recency", {})
        return {
            "relevance_margin": (rel.get("value") or 0) - (rel.get("threshold") or 0),
            "pref_value": pref.get("value"), "pref_threshold": pref.get("threshold"),
            "recency_passed": rec.get("passed"), "recency_override": rec.get("override_applied"),
        }


    # ----------------- main -----------------

    def filter_chunk(self, chunk, user_query, metadata: Optional[Dict[str, Any]] = None):
        # base signals
        suspicious, suspicious_hits = self.is_factually_suspicious(chunk)
        accuracy_ok = not suspicious

        up_to_date, date_ev = self.is_up_to_date(chunk, metadata)

        # fused relevance + dynamic anchor boost
        intent_text = self._fused_intent_text(user_query)
        relevance_raw = self.semantic_relevance(chunk, user_query)
        relevance_score, anchor_info = self._apply_dynamic_anchor_boost(relevance_raw, chunk, intent_text)

        preference_score, pref_hits = self.preference_match_score(chunk)
        is_safe, unsafe_hits = self.is_contextually_safe(chunk)

        preference_ok = (preference_score >= PREFERENCE_THRESHOLD)

        no_dates_found = (not date_ev["years_found"]) and (date_ev["meta_last_updated_year"] is None)
        up_to_date_ok = (
            up_to_date
            or (preference_ok and relevance_score > 0.50)                         # original-style override
            or (no_dates_found and relevance_score >= RECENCY_RELEVANCE_OVERRIDE) # evergreen fallback
        )

        relevance_ok = (relevance_score > RELEVANCE_THRESHOLD)

        # preference sufficiency: either match OR strong relevance
        preference_sufficient = preference_ok or (relevance_score >= PREF_BYPASS_RELEVANCE)
        pref_bypass_applied = (not preference_ok) and (relevance_score >= PREF_BYPASS_RELEVANCE)

        decision_trace = [
            self._rule("ACCURACY_OK", accuracy_ok, suspicious_hits or "", "no suspicious terms",
                       "no suspicious terms detected" if accuracy_ok else f"suspicious terms: {', '.join(suspicious_hits)}"),
            self._rule("SAFETY_OK", is_safe, unsafe_hits or "", "no unsafe terms",
                       "no unsafe terms detected" if is_safe else f"unsafe terms: {', '.join(unsafe_hits)}"),
            self._rule("RECENCY_OK", up_to_date_ok,
                       {"years_found": date_ev["years_found"], "meta_last_updated_year": date_ev["meta_last_updated_year"]},
                       f"year >= {ACCEPTED_YEAR} or override",
                       "recent enough" if up_to_date_ok else f"outdated (years={date_ev['years_found'] or ['none']}, meta={date_ev['meta_last_updated_year'] or 'none'}) with no override"),
            self._rule("RELEVANCE_OK", relevance_ok, round(relevance_score, 4), RELEVANCE_THRESHOLD,
                       "relevance above threshold" if relevance_ok else f"relevance {relevance_score:.2f} ≤ {RELEVANCE_THRESHOLD}"),
            self._rule("PREFERENCE_MATCH_OK", preference_ok, preference_score, PREFERENCE_THRESHOLD,
                       "preference matches present" if preference_ok else f"preference score {preference_score} < {PREFERENCE_THRESHOLD}"),
            self._rule("PREFERENCE_SUFFICIENT", preference_sufficient,
                       {"preference_score": preference_score, "relevance_score": round(relevance_score, 4)},
                       f"pref >= {PREFERENCE_THRESHOLD} OR relevance >= {PREF_BYPASS_RELEVANCE}",
                       "preferences matched or high relevance bypass"
                       if preference_sufficient else f"insufficient: prefs < {PREFERENCE_THRESHOLD} and relevance < {PREF_BYPASS_RELEVANCE}"),
        ]

        required_rules = {"ACCURACY_OK", "SAFETY_OK", "RECENCY_OK", "RELEVANCE_OK", "PREFERENCE_SUFFICIENT"}
        decision = "KEEP" if all(r["passed"] for r in decision_trace if r["id"] in required_rules) else "DROP"

        evidence = {
            # "similarity_model": self.similarity_model,
            # "similarity_metric": self.similarity_metric,
            "accuracy_ok": accuracy_ok,
            "suspicious_hits": suspicious_hits,
            "is_safe": is_safe,
            "unsafe_hits": unsafe_hits,
            "up_to_date": up_to_date,
            "date_years_found": date_ev["years_found"],
            "meta_last_updated_year": date_ev["meta_last_updated_year"],
            "up_to_date_ok": up_to_date_ok,
            "relevance_score": relevance_score,
            "relevance_ok": relevance_ok,
            "relevance_raw": relevance_raw,
            "anchor_boost_info": anchor_info,
            "preference_score": preference_score,
            "preference_ok": preference_ok,
            "preference_sufficient": preference_sufficient,
            "preference_bypass_applied": pref_bypass_applied,
            "matched_preferences": pref_hits[:20],
        }

        scorecard = {
            # "similarity": {"model": self.similarity_model, "metric": self.similarity_metric},
            "relevance": {"value": relevance_score, "threshold": RELEVANCE_THRESHOLD},
            "relevance_components": anchor_info,  # shows anchors and boost details
            "preferences": {"value": preference_score, "threshold": PREFERENCE_THRESHOLD, "matched": pref_hits[:20], "ok": preference_ok},
            "preference_sufficient": {"passed": preference_sufficient, "bypass_applied": pref_bypass_applied,
                                      "threshold": {"pref_at_least": PREFERENCE_THRESHOLD, "relevance_at_least": PREF_BYPASS_RELEVANCE}},
            "recency": {"passed": up_to_date_ok, "accepted_year": ACCEPTED_YEAR,
                        "years_found": date_ev["years_found"], "meta_last_updated_year": date_ev["meta_last_updated_year"],
                        "override_applied": (not up_to_date) and up_to_date_ok},
            "accuracy": {"passed": accuracy_ok, "suspicious_hits": suspicious_hits},
            "safety": {"passed": is_safe, "unsafe_hits": unsafe_hits},
            "decision_trace": decision_trace,
            "required_rules": required_rules,
        }

        reason = [r["because"] for r in decision_trace if (r["id"] in required_rules and not r["passed"] and r["because"])]

        return {
            "final_decision": decision,
            "reason": reason,
            "summary": self._summary(decision, scorecard),
            "accuracy": accuracy_ok,
            "up_to_date": up_to_date,
            "relevance_score": relevance_score,
            "preference_score": preference_score,
            "is_safe": is_safe,
            "evidence": evidence,
            "scorecard": scorecard,
        }


'''
Check for the following criteria:
    1. Accuracy: Evaluate whether the information is factually correct. 
    2. Up-to-date: Determine whether the information appears current or outdated. 
    3. Relevance: 
        A. Understand the user’s travel preferences and constraints by examining their user profile.
        B. Carefully read the content chunk to determine what it’s about.
        C. Decide whether the chunk meaningfully addresses the user's travel preferences and constraints.
    4. Safety: 
        A. Thoroughly analyze the user’s profile (preferences, constraints, travel duration, companions, accommodation).
        B. Review the chunk to identify any content that may be offensive, misleading, violent, political, religious, or promoting deceptive offers.
        C. Decide whether it is contextually safe for the user.
'''