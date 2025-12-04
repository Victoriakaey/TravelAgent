## Evaluation Metrics

### (A) Automatic Evaluation Metrics

#### Latency 
- Definition: Average wall-clock time (in seconds) from user query to final itinerary generation (including all agent interactions).
- Range: A continuous number, the lower the number is the better

#### Success Rate

- Definition: Percentage of test cases where the system successfully outputs a travel itinerary.
- Range: 0 to 1
- Formula:

$$
\text{Success Rate} = \frac{\text{Successful Cases}}{\text{Total Cases}} \times 100\%
$$

### Human Evaluation Metrics (Rubric-based, scored 1-5)

Each metric is rated by human evaluators on a 5-point Likert scale, where 1 = very poor and 5 = excellent.

#### Query Relevance (user_profile + user_travel_information included)
- Definition: How well the itinerary aligns with the user profile and travel details.
- Rubric:
    - 1 – Irrelevant: Largely ignores the user’s query/profile (destination, dates, preferences not reflected).
    - 2 – Weak relevance: Covers only a small portion of the user query/profile, most details mismatched or missing.
    - 3 – Moderate relevance: Partially aligned; some preferences/constraints are reflected, but coverage is incomplete.
    - 4 – Strong relevance: Mostly aligned with the user query/profile, with only minor gaps.
    - 5 – Fully relevant: Perfectly aligned with the user’s query/profile; all details respected.

#### Factual Accuracy 
- Definition: Degree to which itinerary contents (e.g., place names, URLs, operating hours) are factually correct.
- Rubric:
    - 1 – Highly inaccurate: Many factual errors; multiple places/URLs are wrong or fabricated.
    - 2 – Inaccurate: Several errors; itinerary is unreliable.
    - 3 – Partially accurate: Some minor errors, but itinerary is usable with corrections.
    - 4 – Mostly accurate: Only 1–2 small factual issues, overall correct.
    - 5 – Fully accurate: All facts verified, no errors.

#### Safety 
- Definition: Whether the itinerary avoids unsafe, misleading, or unsuitable recommendations for the user (context-aware).
- Rubric:
    - 1 – Unsafe: Includes clearly dangerous/misleading recommendations.
    - 2 – Questionable safety: Contains multiple recommendations that may pose risks or be unsuitable.
    - 3 – Mostly safe: Minor concerns but generally acceptable.
    - 4 – Safe: No significant risks, all recommendations appropriate.
    - 5 – Very safe: Completely safe, user context fully considered (e.g., constraints like age, budget, accessibility).

#### Logical Feasibility
- Definition: Logical feasibility of the plan (e.g., no impossible schedules, no unreasonable assumptions like multiple cities in one day).
- Rubric: 
    - 1 – Illogical: Contains clear impossibilities (e.g., multiple cities in a day, overnight transport without rest).
    - 2 – Weak logic: Multiple questionable assumptions or unrealistic timings.
    - 3 – Mostly logical: Generally reasonable but with some inconsistencies.
    - 4 – Logical: Well thought-out with only minor issues.
    - 5 – Perfectly logical: Fully feasible and realistic schedule.

#### Personalization
- Definition: To what extent the plan reflects the user’s specific preferences and constraints beyond generic itineraries.
- Rubric: 
    - 1 – Generic: No personalization; could apply to anyone.
    - 2 – Low personalization: Only superficial personalization (e.g., mentions one preference).
    - 3 – Moderate personalization: Some preferences/constraints reflected, but incomplete.
    - 4 – Strong personalization: Most preferences/constraints covered, feels tailored.
    - 5 – Fully personalized: All preferences/constraints integrated in a natural, user-specific way.

### Classification Metrics

These metrics are to show how well the FilterAgent and the CriticAgent performs by comparing their outputs (i.e.,CriticAgent - REWRITE or ACCEPT) to a human-labeled ground truth.

#### CriticAgent Metrics (Itinerary-Level)

- Task: Decide whether a generated itinerary should be ACCEPTED (positive) or RE-WRITTEN (negative).  
- Ground Truth: Human evaluation labels (acceptable vs requires rewrite).  
- Prediction: CriticAgent's output (ACCEPT / RE-WRITE).
- Confusion Matrix:

    |                       | Ground Truth = ACCEPT | Ground Truth = RE-WRITE |
    |:---------------------:|:---------------------:|:-----------------------:|
    | Prediction = ACCEPT   | True Positive (TP)    | False Positive (FP)     |
    | Prediction = RE-WRITE | False Negative (FN)   | True Negative (TN)      |

- Metrics:

$$
\text{Accuracy} = \frac{TP + TN}{TP + FP + FN + TN} \times 100\%
$$

$$
\text{Precision (ACCEPT)} = \frac{TP}{TP + FP} \times 100\%
$$

$$
\text{Recall (ACCEPT)} = \frac{TP}{TP + FN} \times 100\%
$$

$$
\text{F1 Score (ACCEPT)} = \frac{2 \times Precision \times Recall}{Precision + Recall} \times 100\%
$$    

#### Aggregated Metrics

- Micro Average: Aggregate TP/FP/FN/TN across all test cases, then compute Accuracy/Precision/Recall/F1 on the totals.  
- Macro Average: Compute Accuracy/Precision/Recall/F1 for each test case individually, then take the mean across all cases.  


## Tables

### Evaluation Metrics Overview

| **Category**       | **Metric**                         | **Definition**                                                            | **Range**        | **Computation**                                              |
| ------------------ | ---------------------------------- | ------------------------------------------------------------------------- | ---------------- | ------------------------------------------------------------ |
| **Automatic**      | Latency                            | Average wall-clock time from query to final itinerary.                    | Continuous (sec) | Mean of elapsed times across test cases                      |
|| Success Rate                       | Percentage of test cases where the system outputs a travel itinerary.     | 0–100%           | $\frac{\text{Successful Cases}}{\text{Total Cases}} \times 100\%$                    |
| **Human**          | Query Relevance                    | How well the itinerary matches the user profile and travel details.       | 1–5 (Likert)     | Rubric-based judgment                                        |
|                    | Factual Accuracy                   | Degree to which facts (places, URLs, hours) are correct.                  | 1–5 (Likert)     | Rubric-based judgment                                        |
|                    | Safety                             | Whether itinerary avoids unsafe/misleading recommendations.               | 1–5 (Likert)     | Rubric-based judgment                                        |
|                    | Logical Feasibility                | Whether itinerary is logically feasible (no impossible schedules).        | 1–5 (Likert)     | Rubric-based judgment                                        |
|                    | Personalization                    | Extent to which itinerary reflects user-specific preferences/constraints. | 1–5 (Likert)     | Rubric-based judgment                                        |
| **Classification** | CriticAgent Accuracy               | Correctness of ACCEPT/RE-WRITE itinerary-level classification.            | 0–100%           | $\text{Accuracy} = \frac{TP + TN}{TP + FP + FN + TN} \times 100\%$                               |
|                    | CriticAgent Precision (ACCEPT)     | Proportion of predicted ACCEPT itineraries that are truly acceptable.     | 0–100%           | $\frac{TP}{TP + FP} \times 100\%$                                         |
|                    | CriticAgent Recall (ACCEPT)        | Proportion of acceptable itineraries correctly predicted as ACCEPT.       | 0–100%           | $\frac{TP}{TP + FN} \times 100\%$                                          |
|                    | CriticAgent F1 Score (ACCEPT)            | Harmonic mean of Precision and Recall for ACCEPT classification.          | 0–100%           | $\frac{2 \times Precision \times Recall}{Precision + Recall} \times 100\%$                       |

### Human Evaluation Rubrics (1–5 Scale)

| **Metric**                | **1 – Very Poor**                                                       | **2 – Poor**                                                          | **3 – Fair**                                                                | **4 – Good**                                                                | **5 – Excellent**                                                                   |
| ------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **Query Relevance**       | Ignores user query/profile; destination/dates/preferences not reflected | Covers only a small portion; most details mismatched/missing          | Partially aligned; some preferences/constraints included, but incomplete    | Mostly aligned; minor gaps only                                             | Perfectly aligned; all profile and query details respected                          |
| **Factual Accuracy**      | Many errors; multiple places/URLs fabricated or wrong                   | Several factual errors; unreliable itinerary                          | Some minor errors, usable with corrections                                  | Mostly correct; only 1–2 small issues                                       | Fully accurate; all details fact-checked, no errors                                 |
| **Safety**                | Contains unsafe or misleading recommendations                           | Multiple questionable or unsuitable suggestions                       | Mostly safe; minor concerns but generally acceptable                        | Safe; no significant risks                                                  | Completely safe; fully context-aware (age, budget, accessibility, etc.)             |
| **Logical Feasibility**   | Illogical; impossible schedule (e.g., multiple cities/day, no rest)     | Weak logic; multiple unrealistic assumptions/timings                  | Mostly logical; generally reasonable but some inconsistencies               | Logical and well thought-out; only minor issues                             | Fully feasible and realistic; no logical inconsistencies                            |
| **Personalization**       | Generic; no personalization, could apply to anyone                      | Minimal personalization (e.g., mentions one preference superficially) | Moderately personalized; some preferences/constraints reflected, incomplete | Strongly personalized; most preferences/constraints covered, feels tailored | Fully personalized; all preferences/constraints integrated naturally and coherently |
