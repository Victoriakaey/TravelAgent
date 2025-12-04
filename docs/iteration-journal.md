# Iteration Journal (Apr 2025 - Oct 2025)

- [Iteration 0 (Apr 2025) – Implementing the Base Structure and Multi-Agent Framework](#iteration-0-apr-2025--implementing-the-base-structure-and-multi-agent-framework)
- [Iteration 1 (Apr to May 2025) – Developing the Initial ContentAgent Module](#iteration-1-apr-to-may-2025--developing-the-initial-contentagent-module)
- [Iteration 2 (May 2025) – Introducing the LLM-Based Filter](#iteration-2-may-2025--introducing-the-llm-based-filter)
- [Iteration 3 (June–July 2025) – Replacing the LLM Filter with an NLP Rule-Based Filter](#iteration-3-junejuly-2025--replacing-the-llm-filter-with-an-nlp-rule-based-filter)
- [Iteration 4 (July 2025) – Introducing and Refining the CriticAgent](#iteration-4-july-2025--introducing-and-refining-the-criticagent)
- [Iteration 5 (Aug–Sep 2025) – Integrating CriticAgent with SearchAgent and TransactionAgent](#iteration-5-augsep-2025--integrating-criticagent-with-searchagent-and-transactionagent)
- [Iteration 5.5 (Sep 2025) – SelectorGroupChat and UserProxyAgent Integration](#iteration-55-sep-2025--selectorgroupchat-and-userproxyagent-integration)
- [Iteration 6 (Oct 2025) – System Refinement and Evaluation](#iteration-6-oct-2025--system-refinement-and-evaluation)


## Iteration 0 (Apr 2025) – Implementing the Base Structure and Multi-Agent Framework

The project began in April 2025 with the development of the base multi-agent framework, composed of six agents working collaboratively to generate a complete travel package: the Orchestrator, SearchAgent, DealAgent, ContentAgent, RecommendationAgent, and TransactionAgent. This framework was implemented using the **AutoGen Framework with MagneticOne** to enable modular communication and coordination among agents.

As the team lead of a six-member group, I was responsible for setting up the initial AutoGen architecture so that each team member could later implement their own agent within a shared and consistent structure. During this stage, I also created dummy agent templates that the team used as placeholders for early testing, ensuring that the overall system communication and orchestration logic functioned correctly before deeper module-level development.

In addition, I built and configured the **Redis Storage Service**, which handled the persistence of agent states and the exchange of information between agents, allowing the system to maintain shared memory across turns. This initial setup produced a functional multi-agent skeleton capable of structured message passing and persistent state storage, providing the essential technical foundation for all subsequent iterations of the Travel Agent system.

## Iteration 1 (Apr to May 2025) – Developing the Initial ContentAgent Module

Following the completion of the base multi-agent framework, the first major functional milestone was the implementation of the **ContentAgent**, the component under my responsibility. In this stage, the goal was to **build a working end-to-end prototype that could autonomously collect travel information from open domains and generate preliminary travel plans without human input**. 

The ContentAgent performed three core tasks: 
- Web scraping relevant travel content such as blogs, guides, and itineraries from open-domain sources
- Cleaning and parsing the retrieved text into structured segments
- Synthesizing a simple travel plan from the gathered material

The generated plan and its associated metadata were then saved to the **Redis Storage Service**, enabling other agents to retrieve and reuse the information in later stages of the workflow.

At this point, the system contained no filtering, validation, or critique modules; the emphasis was solely on achieving a functional content pipeline capable of producing coherent itineraries directly from open-domain data. While the resulting plans were often unrefined and inconsistent in quality, this iteration demonstrated the feasibility of autonomous data-to-plan generation and established the baseline upon which later improvements in safety, factual accuracy, and reasoning were built.

## Iteration 2 (May 2025) – Introducing the LLM-Based Filter

### **Before**

The *Travel Agent* prototype at this point consisted of a simple two-stage pipeline:
**WebScraperAgent → ContentGenerationAgent.**
The system scraped travel-related webpages, cleaned them with Trafilatura, segmented them into textual chunks, and passed these directly to the generator to compose itineraries.
While functional, this baseline lacked any form of quality control—the generator relied entirely on unverified open-domain text.

### **Motivation**

During early testing, several deficiencies became apparent:

1. **Outdated Information.** Many scraped guides referenced attractions that had closed or events that no longer existed.
2. **Factual Inaccuracy.** Some content contained exaggerated or incorrect claims (e.g., inflated prices, misleading locations).
3. **Safety and Relevance Issues.** Open-domain material occasionally included risky or irrelevant recommendations that contradicted user constraints.
4. **Lack of Transparency.** When poor material entered the generator, it was difficult to trace which input chunk caused the error.

These issues motivated the addition of a **quality-gate mechanism** between scraping and generation to ensure that only accurate, safe, and up-to-date information would propagate downstream.

### **Change**

A new **LLM-as-Filter** module was inserted between the scraper and generator, producing the pipeline:
**WebScraperAgent → LLM Filter → ContentGenerationAgent.**

**Implementation Details**

* **Input:** Each content chunk contained its URL, timestamp, and textual excerpt.
* **Evaluation Dimensions:** Recency, factual accuracy, safety, and relevance to user preferences and constraints.
* **Prompt Contract:**

  ```xml
  <filter>
    <label>KEEP | DROP</label>
    <reasons>bullet-point justification per criterion</reasons>
    <evidence>short quote or metadata reference</evidence>
  </filter>
  ```
* **Decision Logic:** Any single violation (e.g., outdated or unsafe) triggered `DROP`; borderline cases required explicit justification.
* **Engineering Steps:** Batch processing (8–16 chunks per call), URL-based deduplication, cached verdicts, and structured logs for all decisions.

### **Impact**

**Positive Effects**

* **Improved Plan Quality.** The rate of factual and temporal errors in generated itineraries decreased substantially in qualitative reviews.
* **Higher User Alignment.** Irrelevant or low-value content was largely eliminated, yielding plans more consistent with stated preferences.
* **Traceability.** Each inclusion or exclusion carried an explicit rationale, simplifying later debugging.

**Limitations**

* **Severe Latency.** Total runtime increased from roughly 6–8 minutes to 25–40 minutes per run.
* **Inconsistent Judgments.** The same chunk occasionally received different verdicts across runs.
* **Scalability Concerns.** Local inference on an M1 Mac Pro was computationally expensive.


## Iteration 3 (June–July 2025) – Replacing the LLM Filter with an NLP Rule-Based Filter

### **Before**

By June 2025, my *Travel Agent* pipeline still relied on an **LLM-based filter** between the WebScraper and ContentGeneration stages.
Although this setup improved factual reliability, it was computationally heavy and unpredictable.
Running locally through **Ollama** on my M1 Mac Pro, each full pipeline took **25–40 minutes**, and borderline chunks sometimes produced inconsistent “KEEP” or “DROP” labels.
Because the filter itself was probabilistic, two identical runs could yield slightly different results—an unacceptable property for a system that needed repeatable evaluation.

### **Motivation**

I wanted a filtering mechanism that was:

1. **Deterministic and reproducible** — identical input should always produce identical output.
2. **Lightweight and fast** — so I could iterate on downstream modules many times per day.
3. **Transparent and explainable** — so every decision could be traced and debugged.

After profiling the LLM filter, I confirmed that most delay came from local inference and token generation, not network latency.
That insight led me to build a fully local, explainable **rule-based NLP filter** that combined keyword heuristics with semantic relevance scoring.

### **Process and Troubleshooting**

1. **Designing deterministic rules**
   I began by identifying the minimum gating criteria—accuracy, safety, recency, relevance, and preference match—and formalized a policy:

   > KEEP ⇐ ACCURACY_OK ∧ SAFETY_OK ∧ RECENCY_OK ∧ RELEVANCE_OK ∧ PREFERENCE_SUFFICIENT
   > This structure became the foundation for the new `NLPFilterTool` class.
2. **Choosing a similarity model**
   I selected `all-MiniLM-L6-v2` for compact embeddings and reasonable speed.
   To represent user intent, I fused the **user query** with **profile keywords**, cached its embedding once per run, and measured cosine similarity for each chunk.
3. **Adding dynamic intent anchors**
   To capture entity-level relevance without hard-coded locations, I introduced a **dynamic anchor boost**: capitalized multi-word spans (e.g., *Blue Lagoon*) and salient tokens that appear in both intent and chunk receive a small, capped score increase.
   This improved recall for meaningful matches like landmarks or cuisines.
4. **Building explicit rule checks**
   Each content chunk was evaluated against explicit functions:

   * **Factual Suspicion:** look for words like *fake*, *scam*, *hoax*.
   * **Safety:** scan for blacklisted or sensitive terms.
   * **Recency:** extract dates via `dateparser` and require year ≥ ACCEPTED_YEAR (default 2022) with evergreen overrides.
   * **Preference Match:** count overlapping profile keywords; allow relevance bypass if semantic similarity ≥ 0.56.
   * **Relevance:** cosine ≥ 0.45 after anchor adjustment.
     Each rule produced a structured record in `decision_trace` with `id`, `value`, `threshold`, and `because`, stored in Redis for later audit.
5. **Debugging and calibration**
   Early runs dropped valid content due to over-strict date patterns (“open year-round” flagged as outdated).
   I relaxed regex logic and introduced a fallback when no explicit year was found but relevance was high.
   I also refined thresholds empirically by comparing results from both filters side-by-side on several destinations until the new filter preserved all obviously valuable material while running far faster.

### **Change**

The updated pipeline became:
**WebScraperAgent → NLP Rule-Based Filter → ContentGenerationAgent.**

All intermediate decisions—scores, matched anchors, rule outcomes—were logged in structured JSON form in Redis.
Average filter time fell to **under one minute** per run.

### **Impact**

**Positive Effects**

* **Runtime Reduction:** End-to-end latency dropped from ~30 minutes to 4–6 minutes.
* **Determinism:** Repeated runs now produced identical outputs.
* **Explainability:** Each “KEEP” or “DROP” carried a full scorecard and textual justification.
* **Faster Iteration:** Lightweight, local execution enabled frequent testing and debugging.

**Limitations and Lessons Learned**

* Rule heuristics sometimes missed nuanced semantic errors that an LLM might catch.
* Threshold tuning and pattern maintenance required manual oversight as data sources evolved.
* This iteration taught me that **engineering reliability and transparency often matter more than raw model sophistication** in a multi-agent pipeline.

## Iteration 4 (July 2025) – Introducing and Refining the CriticAgent

### **Before**

By July 2025, my pipeline — **WebScraperAgent → NLP Filter → ContentGenerationAgent** — had become fast and reliable.
However, the system still lacked an internal standard for what constituted a “good” travel plan.
Some itineraries were well-structured, but others were incomplete, repetitive, or poorly aligned with user preferences.
At this point, the workflow was purely feed-forward: once the ContentGenerationAgent produced an itinerary, the process ended.
If the output was weak, I had to diagnose and rerun modules manually.

### **Motivation**

I wanted the system to **assess its own outputs** and decide whether regeneration was necessary — essentially, to think like an internal reviewer.
My objectives were to:

1. Introduce a reasoning layer that could evaluate factuality, completeness, and alignment.
2. Enable the system to decide between *rewrite*, *rescrape*, or *accept*.
3. Record structured reasoning so that later modules — and I, as developer — could understand *why* a decision was made.

The idea was to evolve *Travel Agent* from a linear generator into a **self-monitoring system** capable of iterative improvement.

### **Process and Troubleshooting**

1. **Defining evaluation criteria**
    Initially, I drafted five axes — factual accuracy, completeness, structure, user alignment, and safety — but found them overlapping and unstable in practice.
    After reviewing logs from hundreds of generations, I distilled them into three robust categories: **factuality**, **completeness**, and **user alignment**.
2. **Designing structured outputs**
    My first few attempts asked the LLM for free-form feedback, but the responses were inconsistent and hard to parse programmatically.
    I introduced a strict XML-style schema for the CriticAgent’s output:
    `xml
    <decision>RE-WRITE | RE-SCRAPE | RE-SEARCH | ACCEPT</decision>
    <reasoning>step-by-step justification</reasoning>
    `
    This change alone made orchestration control far more stable and debuggable.
3. **Early loop failures**
    In initial runs, the critic often returned endless **RE-WRITE** labels, even for minor stylistic issues.
    After inspecting reasoning logs, I realized the model lacked a clear termination condition.
    I introduced a **bounded feedback policy**: if three consecutive rewrites improved completeness or keyword coverage by less than 5 %, the plan would be automatically accepted.
    This stopped infinite loops without weakening judgment quality.
4. **Cross-checking decisions**
    To verify that critic feedback was actually helping, I tracked plan metrics (day-coverage, preference coverage, and length balance) across rewrite cycles.
    The metrics confirmed steady improvement and better internal consistency after each critique.
5. **Integrating logging for transparency**
    Each decision — label, reasoning text, and plan snapshot — was written to Redis.
    This gave me a full audit trail for every generation and made it easy to analyze failure cases later.

### **Change**

The pipeline became:
**WebScraperAgent → NLP Filter → ContentGenerationAgent → CriticAgent.**

The CriticAgent applied the schema above, returning one of four decisions:

* `RE-WRITE` → `ContentGenerationAgent` will be called by the `PlanningAgent` to regenerate the plan using the same filtered material;
* `RE-SCRAPE` → `WebScraperAgent` will be called by the `PlanningAgent` to rescrape travel informations;
* `RE-SEARCH` → `SearchAgent` will be called by the `PlanningAgent` to research flight/hotel/place/tour informations via structured API calls;
* `ACCEPT` → finalize and store the plan.

All reasoning text and control signals were persisted to Redis for analysis and traceability.

### **Impact**

**Positive Effects**

* **Closed feedback loop** — the system could now judge and refine its own outputs automatically.
* **Improved quality** — average itinerary completeness and user-preference satisfaction improved visibly across iterations.
* **Transparency** — structured reasoning made decisions interpretable and debuggable.

**Limitations and Lessons Learned**

* Runtime increased by roughly 1–2 minutes per additional critique cycle.
* LLM judgments remained somewhat subjective, occasionally over-penalizing stylistic issues.
* Through this process I learned that **bounded reasoning and clear success criteria** are essential to prevent oscillation in self-evaluating systems.


## Iteration 5 (Aug–Sep 2025) – Integrating CriticAgent with SearchAgent and TransactionAgent

### **Before**

After establishing the self-evaluation loop, *Travel Agent* could reliably generate and assess itineraries.
However, the system still operated in isolation: even when the *CriticAgent* requested a “re-search” or “transaction” action, there was no mechanism to connect those decisions to real service modules.
The *SearchAgent* (developed earlier by Shuran Sun) and the *TransactionAgent* existed separately but were not orchestrated through the reasoning pipeline.
As a result, feedback loops ended prematurely — plans could be judged “incomplete” without triggering a corrective action such as refreshing flight or hotel results.

### **Motivation**

I aimed to unify generation, judgment, and execution within a single orchestrated loop so that:

1. **Critic decisions** could directly influence agent routing.
2. The system could perform **targeted corrections** — e.g., re-invoke *SearchAgent* only when flight or lodging data was stale.
3. State information could persist across cycles through **Redis**, enabling the critic’s reasoning to access both prior results and newly fetched data.

This would transform *Travel Agent* from a modular pipeline into a **coordinated multi-agent ecosystem** with dynamic decision flow.

### **Process and Troubleshooting**

1. **Extending the CriticAgent’s schema**
    I expanded the critic’s XML output to include fine-grained control signals such as:
    `xml
    <action>RE-SEARCH-FLIGHT | RE-SEARCH-HOTEL | RE-GENERATE | ACCEPT</action>
    <context>brief justification</context>
    `
    This allowed selective re-activation of the *SearchAgent* rather than full re-scraping.

2. **Building routing logic in the orchestrator**
    I modified the orchestration layer so that it listened for the critic’s structured signals and delegated tasks accordingly.
    Each branch triggered specific agents in sequence while preserving shared state keys in Redis (`session_id`, `plan_id`, `critic_round`).
    For example:
    - `RE-SEARCH-FLIGHT` → invoke *SearchAgent* (flight mode) → update plan context.
    - `RE-GENERATE` → re-call *ContentGenerationAgent* with updated chunks.
    - `ACCEPT` → store final plan and trigger *TransactionAgent*.

3. **Redis state synchronization**
    I rewrote state handlers to support dynamic session-level updates.
    Instead of fixed initialization, each agent now retrieved and updated only the sub-keys it owned, allowing multiple agents to work on the same session concurrently without overwriting each other’s data.

4. **Failure debugging**
    During early integration, recursive critic calls sometimes produced conflicting writes in Redis (especially when multiple re-searches were triggered simultaneously).
    To fix this, I introduced a **session-lock mechanism** that serialized critic-initiated updates and ensured that only one sub-pipeline could modify a given plan at a time.

5. **Testing end-to-end flows**
    I ran controlled simulations with various user profiles and destinations to ensure that the critic’s routing led to consistent end states.
    Logs confirmed stable transitions such as:
    `FILTER → GENERATE → CRITIC (RE-SEARCH-FLIGHT) → SEARCH → RE-GENERATE → CRITIC (ACCEPT)`.

### **Change**

The system architecture evolved from a simple sequential flow into a **conditional orchestration loop**:

**WebScraperAgent → NLP Filter → ContentGenerationAgent → CriticAgent → (conditional branch)**
→ SearchAgent / TransactionAgent / Termination

All intermediate states and control messages were logged and versioned in Redis.
The orchestrator now handled multi-round interactions gracefully, with automatic termination once the critic returned `ACCEPT`.

### **Impact**

**Positive Effects**

* **End-to-end autonomy:** The system could now search, plan, evaluate, and finalize bookings without manual intervention.
* **Consistency:** All agents shared a unified state structure, ensuring continuity across iterations.
* **Traceability:** Every route taken by the critic was recorded, enabling clear replay and performance analysis.

**Limitations and Insights**

* Added complexity to state management required strict locking and careful Redis key design.
* Each additional branch introduced potential race conditions, which I mitigated through session synchronization.
* This iteration taught me that **multi-agent coordination is as much an engineering problem as it is a reasoning one** — robust state design matters as much as model choice.

## Iteration 5.5 (Sep 2025) – SelectorGroupChat and UserProxyAgent Integration

### **Before**

After integrating the *CriticAgent* with *SearchAgent* and *TransactionAgent*, I noticed persistent instability during error-handling scenarios.
When *SearchAgent* encountered invalid user input — such as impossible travel dates, outdated destinations, or missing city codes — it failed silently.
Attempts to recover through the critic often led to dead ends because no agent in the pipeline could communicate with the user directly.
At the same time, the original AutoGen `Orchestrator` structure proved rigid and prone to message routing confusion during multi-turn correction loops.

### **Motivation**

I needed a more flexible orchestration layer and a human-facing recovery path:

1. **Flexible Routing:** Replace the fixed Orchestrator with a structure that allowed dynamic agent selection and conditional branching.
2. **User Mediation:** Introduce a `UserProxyAgent` to resolve ambiguous or invalid inputs interactively.
3. **Context Continuity:** Ensure that the system could recover gracefully without losing conversation or state.

### **Process and Troubleshooting**

1. **Building SelectorGroupChat**
    I implemented `SelectorGroupChat`, a custom orchestration layer supporting:
    - Conditional routing based on message type (`critic_feedback`, `error`, `info_request`),
    - Multi-agent context persistence,
    - Dual termination rules (`MaxMessageTermination` or `TextMentionTermination`),
    - Optional repeated speaker turns for iterative refinements.
    This architecture replaced the static turn-taking of AutoGen’s Orchestrator with a selective, event-driven model.
2. **Introducing UserProxyAgent**
    The new *UserProxyAgent* acted as an interactive failsafe.
    When *SearchAgent* reported invalid data (e.g., date before today, empty result, invalid city/accommodation code), the *PlanningAgent* rerouted control to *UserProxyAgent*, which prompted the user for clarification.
    Once corrected, it returned validated data back into the loop — preventing total pipeline collapse.
3. **Enhancing Temporal Awareness**
    I added a date utility to the *PlanningAgent* that automatically injects the current system date into prompts, enabling agents to reject past-dated trips or expired deals.
4. **Debugging and Validation**
    During testing, I confirmed successful recovery for multiple input error cases.
    For example: when an invalid departure date was detected, *UserProxyAgent* engaged the user and re-ran *SearchAgent* with corrected parameters, resolving issues without restarting the session.

### **Change**

System orchestration evolved into a **Selector-based and user-aware architecture**:

**UserProxyAgent → PlanningAgent (SelectorGroupChat) → WebScraperAgent / SearchAgent / ContentGenerationAgent / CriticAgent / TransactionAgent**

Each component now communicated asynchronously through Redis state memory, coordinated by dynamic routing rather than linear sequencing.

### **Impact**

* **Error Recovery:** The system could now self-correct invalid inputs interactively.
* **Stability:** Flexible routing eliminated orchestration deadlocks.
* **Usability:** Improved user experience — errors no longer crashed the planning flow.

## Iteration 6 (Oct 2025) – System Refinement and Evaluation

### **Before**

By early October 2025, *Travel Agent* had matured into a coordinated multi-agent ecosystem that could scrape, filter, generate, critique, and re-search autonomously.
While functionally complete, the system still lacked systematic **instrumentation** for performance measurement and transparency.
I could observe behavior qualitatively through logs, but not quantify runtime distribution, loop frequency, or content-quality outcomes across agents.

### **Motivation**

The goals for this iteration were to:

1. **Stabilize orchestration** by ensuring that every possible critic-driven branch terminated cleanly.
2. **Add full observability**—timing, logs, and decision tracing—for every agent.
3. **Establish reproducible evaluation protocols** that could support an ablation study and quantitative assessment of the system’s reliability and efficiency.

This phase marked a transition from *development* to *evaluation readiness*.

### **Process and Troubleshooting**

1. **Introducing TimeTracker and runtime profiling**
    I built a lightweight `TimeTracker` module that wrapped each agent call and recorded total and per-submodule execution time.
    This revealed that, on average, the *NLP Filter* consumed ~18 % of runtime, *ContentGenerationAgent* ~40 %, and *CriticAgent* ~25 %.
    These numbers guided later optimization decisions.

2. **Structured logging with Python Logging and Redis**
    I replaced ad-hoc print debugging with a unified `logging` configuration writing to both console and Redis.
    Every run now persisted a structured record containing:
    - timestamps for agent start/finish,
    - critic labels and reasoning text,
    - number of retries per agent,
    - total loop count.
    This data enabled post-hoc analysis and regression testing.

3. **Eliminating residual loops**
    Despite earlier fixes, edge cases occasionally produced endless `RE-WRITE` cycles when critics oscillated between minor textual preferences.
    I implemented a **loop-limit safeguard** (max N retries) with automatic `ACCEPT` on convergence and annotated every termination cause in logs for auditing.

4. **Preference and constraint coverage metrics**
    I augmented the *ContentGenerationAgent* to compute and report:
    - how many user preferences and constraints were covered in each plan,
    - which remained unfulfilled.
    These numbers provided interpretable metrics of alignment and helped visualize improvement after critic feedback.

5. **Dataset and Ablation Preparation**
    To evaluate reasoning effectiveness, I organized four ablation settings:
    (1) no Critic, (2) Critic-only, (3) Fallback-only, and (4) Critic + Fallback.
    Each configuration reused the same user profiles and destinations for comparability, allowing me to measure loop frequency, latency, and qualitative alignment across conditions.

6. **Final stability and qualitative review**
    Across dozens of test sessions, the system completed every run without deadlock, maintaining consistent behavior under repeated execution.
    Qualitatively, generated itineraries became more coherent, detailed, and context-aware compared with early iterations.

### **Change**

At this stage, the architecture solidified into its final, stable form:
**WebScraperAgent → NLP Filter → ContentGenerationAgent → CriticAgent → (SearchAgent / TransactionAgent / Termination)**.
A unified logging and timing infrastructure now wrapped the entire pipeline, and evaluation hooks were embedded for both quantitative and qualitative studies.

### **Impact**

**Positive Effects**

* **Full Observability:** Every agent’s performance, reasoning, and decision path could be reproduced and analyzed.
* **Reliability:** No infinite loops or orphaned sessions after extensive stress tests.
* **Benchmark Readiness:** The framework now supported consistent ablation runs and metric tracking.

**Limitations and Lessons Learned**

* Comprehensive logging slightly increased runtime overhead (~10 %), a trade-off I accepted for transparency.
* Interpretation of critic reasoning still required manual reading—future versions could benefit from structured reasoning parsers.
* This iteration taught me the value of **engineering evaluation discipline**—instrumentation and traceability are the backbone of any trustworthy agentic system.
