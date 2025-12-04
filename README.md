# TravelAgent System

A dynamic conversational travel system built on a multi-agent architecture. It orchestrates open-domain web scraping, structured API search, personalized itinerary generation, and self-critique–driven refinement, enabling users to plan and book complete trips through an intelligent end-to-end workflow.

## Table of Content

- [Overview](#overview)
- [Required Services](#required-services)
- [How to Setup](#how-to-setup)
    - [Create Conda Virtual Environment](#1-create-conda-virtual-environment)
    - [Setup Docker](#2-setup-docker)
    - [Setup Redis](#3-setup-redis)
    - [Setup SearXNG](#4-setup-searxng)
    - [Setup Ollama](#5-setup-ollama)
    - [Setup Perplexica](#6-setup-perplexica)
    - [Setup SearchAgent](#7-setup-searchagent)
- [How to Run](#how-to-run)
    - [Running the End-to-End Pipeline](#running-the-end-to-end-pipeline)
    - [Running Sub-agents Individually](#running-sub-agents-individually)
- [Analysis of the System](#analysis-of-the-system)
    - [Evaluation Datasets Curation](#evaluation-datasets-curation)
        - [User Cases and Queries (requests) Datasets](#a-user-cases-and-queries-requests-datasets)
        - [System Analysis Datasets](#b-system-analysis-datasets)
        - [`CriticAgent` Analysis Datasets](#c-criticagent-analysis-datasets)
    - [Evaluation Scripts](#evaluation-scripts)

## Overview

TravelAgent is built on [Microsoft’s AutoGen framework](https://github.com/microsoft/autogen), the system uses a centrally orchestrated [`SelectorGroupChat`](https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/selector-group-chat.html) architecture in which a `PlanningAgent` delegates work to a coordinated set of specialized agents:


| Agent                    | Core Function                                                                                                        | Model(s) Used                                                |
|:------------------------:|:----------------------------------------------------------------------------------------------------------------------:|:------------------------------------------------------------:|
| **PlanningAgent**        | Central orchestrator; decomposes tasks and delegates to specialized agents                                            | [`qwen2.5:7b`](https://ollama.com/library/qwen2.5)                                                 |
| **SelectorGroupChat**    | Routing layer that dynamically selects which agent should act next                                                     | [`qwen2.5:7b`](https://ollama.com/library/qwen2.5)                                                 |
| **UserProxyAgent**       | Interfaces with the user via `input()` and requests clarification whenever the input is missing, ambiguous, or internally inconsistent      | /                 |
| **WebScraperAgent**      | Retrieves and filters open-domain travel content using `Perplexica` + `SearXNG`, followed by multi-stage NLP filtering to ensure factuality, safety, relevance, and preference alignment         | [`qwen2.5:7b`](https://ollama.com/library/qwen2.5) (text generation) <br> [`snowflake-arctic-embed:335m`](https://ollama.com/library/snowflake-arctic-embed) (embeddings) |
| **SearchAgent**          | Performs agentic API calls to query structured travel data (flights, hotels, routes, POIs) from the `Amadeus` and `Google Maps` APIs                           | [`qwen2.5:7b`](https://ollama.com/library/qwen2.5)                                                 |
| **ContentGenerationAgent** | Generate the final itinerary in Markdown using the `filtered_content` from the WebScraperAgent and the `searched_results` from the `SearchAgent`                                  | [`gemma2:9b`](https://ollama.com/library/gemma2)                                                  |
| **CriticAgent**          | Evaluates itinerary for factuality, feasibility, safety, and hard-constraint compliance; returns `ACCEPT` / `RE-WRITE` | [`deepseek-r1:8b`](https://ollama.com/library/deepseek-r1)                                             |
| **TransactionAgent**     | Provides a lightweight placeholder booking confirmation to complete the end-to-end flow (triggered only after an `ACCEPT` decision from the CriticAgent)                                          | [`qwen2.5:7b`](https://ollama.com/library/qwen2.5)                                                 |

To improve reliability, TravelAgent combines **agent-level fallback mechanisms** with **a system-level self-critique loop**.

The **agent-level fallback mechanisms** maintain data quality by:

- Triggering a re-scrape in the `WebScraperAgent` when **fewer than five chunks are marked `KEEP`**, and

- Escalating `SearchAgent` API call failures (e.g., user-requested travel dates earlier than today, mismatched amenity codes, invalid parameters, etc) to a **human-in-the-loop** path coordinated by the `PlanningAgent`. 

    - In this path, the `UserProxyAgent` requests any missing information from the user or assists the user in troubleshooting using the error message returned by the `SearchAgent`.

The **system-level self-critique loop** ensures the final itinerary satisfies the user’s travel needs by:

- Having the `CriticAgent` evaluate each draft itinerary for information accuracy, logical feasibility, factual grounding, and explicit hard constraints. The critic outputs a structured raw_response containing:

    - a checklist of criteria met,

    - six evaluation scores (confidence, relevance, accuracy, safety, feasibility, personalization, each on a 0–5 scale),
    - a binary decision (ACCEPT or RE-WRITE),
    - a rationale explaining the decision, and
    - a targeted suggestion for how the plan should be revised.

- Routing any `RE-WRITE` decision through the `PlanningAgent`, which forwards the critic’s full `raw_response` to the `ContentGenerationAgent` for targeted regeneration conditioned on the critic’s guidance and the current evidence base (`filtered_content` and `search_results`).

A more detailed [project report](./docs/TravelAgent_An_End_to_End_Multi_Agent_System_with_Critic_Driven_Self_Improvement_for_Personalized_Travel_Planning.pdf) — which includes the system architecture, design decisions, and evaluation results — along with the accompanying [iteration journal](./docs/iteration-journal.md) documenting the full development process, are available in the [`docs`](./docs/) folder.


## Required Services

TravelAgent requires the following services to be running:

| Service                                                                 | Role                                           | Port  | How it Runs | Description |
|:-----------------------------------------------------------------------:|:--------------------------------------------:|:-----:|:-----------:|:-----------:|
| [**Redis**](https://github.com/redis/redis)                             | State cache / intermediate artifact store      | 6379  | Docker      | Stores agent states, scraped content, filtered chunks, and runtime artifacts to enable cross-agent coordination. |
| [**SearXNG**](https://github.com/searxng/searxng)                       | Local meta-search engine                       | 8080  | Docker      | Provides privacy-preserving meta-search results that Perplexica consumes before ranking and scraping. |
| [**Perplexica**](https://github.com/ItzCrazyKns/Perplexica)             | Open-domain web search + agentic RAG           | 3000  | Terminal    | Performs agentic search using LLMs + embeddings; returns ranked URLs, extracted snippets, and content for scraping. |
| [**Ollama**](https://ollama.com/)                                       | Local open-source LLM runtime                  | 11434 | Terminal    | Runs lightweight local inference for text generation, embeddings, and filtering across `WebScraperAgent` and `CriticAgent`. |


## How to Setup

The following instructions describe how to set up all core services required to run TravelAgent-Omega, including Python environments, Redis, SearXNG, Perplexica, Ollama, and API credentials for the SearchAgent.

### 1. Create Conda Virtual Environment

Set up the Python backend environment from the repository root.

```bash
conda create -n travelagent python=3.10 -y
conda activate travelagent
pip install -r backend/requirements.txt
```

---

### 2. Setup Docker

Docker is required to run services such as `Redis` and `SearXNG`.

After installing [Docker Desktop](https://docs.docker.com/get-started/get-docker/), verify that Docker is running:
```bash
docker --version
```

You should see output similar to:
```bash
Docker version 25.x.x, build xxxx
```

If you prefer to test that containers can run correctly:
```bash
docker run hello-world
```

This should print a confirmation message indicating that Docker is installed and functioning properly.

---

### 3. Setup Redis

Redis is used as the system-wide state cache and intermediate artifact store.
```bash
# First-time setup (creates a new Redis container)
docker run -d --name redis -p 6379:6379 redis:7 

# Optional: test connectivity, should return PONG 
docker exec -it redis redis-cli ping  

# Starting Redis on subsequent runs
docker start redis
```
You may also install [Redis Insight](https://redis.io/insight/) for a GUI view of stored data.

---

### 4. Setup SearXNG

SearXNG provides the meta-search backend used by Perplexica. 

Navigate to the directory containing docker-compose.yml:

```bash
cd backend/agents/source/searxng
docker compose up -d
```

Check service availability:

```
http://localhost:8080
```

For manual installation instructions, refer to the [SearXNG official documentation](https://docs.searxng.org/admin/installation-searxng.html#installation-basic).

---

### 5. Setup Ollama

Ollama serves as the local LLM runtime, hosting all models used by the TravelAgent system.

After installing [Ollama](https://ollama.com/download), start the local LLM runtime:

```bash
ollama serve
```

Download all required models: 

```bash       
ollama pull gemma2:9b
ollama pull qwen2.5:7b
ollama pull deepseek-r1:8b
ollama pull snowflake-arctic-embed:latest
```

Verify model availability:

```bash
curl http://localhost:11434/api/tags
```

---

### 6. Setup Perplexica 

Perplexica performs open-domain web search + agentic RAG for the `WebScraperAgent`.

Navigate to the source directory (Note this project is using the `travel-agent` branch of this repo):
```bash
cd backend/autogen/agents/source
```

Clone the Travel-Agent version of the repo (only if not already present):

```bash
# Clone the Perplexica repository 
git clone git@github.com:Victoriakaey/Perplexica.git 

cd Perplexica

# Navigate to the travel-agent branch
git checkout travel-agent
```

Create a `config.toml` file in the Perplexica directory:

```toml
[GENERAL]
SIMILARITY_MEASURE = "cosine"
KEEP_ALIVE = "5m"

[MODELS.OPENAI]
API_KEY = ""

[MODELS.GROQ]
API_KEY = ""

[MODELS.ANTHROPIC]
API_KEY = ""

[MODELS.GEMINI]
API_KEY = ""

[MODELS.CUSTOM_OPENAI]
API_KEY = ""
API_URL = ""
MODEL_NAME = ""

[MODELS.OLLAMA]
API_URL = "http://localhost:11434"

[MODELS.DEEPSEEK]
API_KEY = ""

[MODELS.LM_STUDIO]
API_URL = ""

[API_ENDPOINTS]
SEARXNG = "http://localhost:8080"
```

Install and run Perplexica:
```bash
npm install
npm run build
npm run start
```

Verify (In another terminal):
```
http://localhost:3000
```

---

### 7. Setup SearchAgent

The SearchAgent integrates `Amadeus` (flights/hotels) and `Google Maps` (places, photos, routing).

You must create a `.env` file with the following keys.

```env
AMADEUS_CLIENT_ID=
AMADEUS_CLIENT_SECRET=
GOOGLE_MAPS_API_KEY=
```

To Obtain the API keys, follow the instructions below:

#### Amadeus API Key

1. Visit: https://developers.amadeus.com
2. Create a free developer account.
3. After login, go to: Dashboard → My Apps → Create New App
4. Enable: Self-Service APIs (Flight Offers Search, Flight Inspiration Search, Hotel Search, etc.)
5. Once the app is created, Amadeus will provide two keys:
    - `AMADEUS_CLIENT_ID`
    - `AMADEUS_CLIENT_SECRET`

6. Copy them into your `.env` file.

Note: The SearchAgent uses the Self-Service Test Environment, so no paid account is required.

#### Google Maps API Key

1. Visit: https://developers.google.com/maps
2. Create or select a Google Cloud Project.
3. Enable the following APIs:
    - Places API
    - Places API (New)
    - Geocoding API
    - Directions API
    - Maps Routes API (if using routing)
4. Go to: APIs & Services → Credentials → Create API Key
5. Copy them into your `.env` file.
6. (Recommended) Restrict the key to:

    - HTTP referrers or IP addresses
    - Only the required APIs

Google setup docs: https://developers.google.com/maps/documentation/places/web-service/cloud-setup

#### Troubleshooting

If your `SearchAgent` fails to authenticate with Amadeus or Google Maps, refer to the following official guides:

- **Amadeus – Quick Start Guide (how to create app, obtain keys, environment setup):**  
  https://developers.amadeus.com/self-service/apis-docs/guides/developer-guides/quick-start/

- **Google Maps Platform – Get Started (create project, enable billing, enable APIs, create API key):**  
  https://developers.google.com/maps/get-started

Common issues to check:
- Make sure `.env` is placed in `backend/` and loaded correctly.
- Ensure “Self-Service APIs” are enabled in your Amadeus app.
- On Google Cloud, verify you have enabled:
  - Places API (New)
  - Geocoding API
  - Directions API / Routes API (if routing is used)
- Ensure your Google Maps API key is **not restricted** in a way that blocks your backend usage.

## How to Run 

### Running the End-to-End Pipeline

The TravelAgent system requires several background services to be running. You must have all services are running before launching the main process ([`main.py`](./backend/autogen/main.py)).

Here's a recommended order of operations running one by one:

1. Start Redis via Docker

    ```bash
    docker start redis     
    ```

2. Start SearXNG via Docker

    ```bash
    docker start searxng      
    ```

3. Start Ollama **in one terminal** (make sure all required models are already pulled)

    ```bash
    ollama serve
    ```

4. Start Perplexica **in second terminal**

    ```bash
    cd backend/agents/source/Perplexica # navigate to the Perplexica folder
    npm run start
    ```

5. Run TravelAgent in **a third terminal**

    ```bash
    conda activate travelagent # activate conda environment
    cd backend # navigate to the backend folder
    python -m autogen.main --case_num <case-num>
    ```
    Different `case-num`: 1 (baseline), 2 (with fallback), 3 (with critic), or 4 (full system)

---

### Running Sub-agents Individually

To run each sub-agent, modify the [`test_agents.py`](./backend/autogen/test/test_agents.py) accordingly and run

```bash
python -m autogen.test.test_agents --test <test-mode>
```

Different `test-mode`:
    "webscraper", "webscraper_fallback", "nlp_filter", "llm_filter", "search", "search_fallback", "content", "critic"， "transaction"

## Analysis of the System

### Evaluation Datasets Curation

#### A. User Cases and Queries (requests) Datasets

Data are curated using the selected [10 user cases](./data/user_cases_ablation_study.json) from [an original 53 user cases](./data/user_cases_complete.json) and [the queries (request)](./data/user_query_requests.jsonl) are curated using the [`generate_user_query`](./backend/autogen/agents/source/_user_query_generation.py). 

#### B. System Analysis Datasets

The 40 sets of [plans](./backend/autogen/evaluation/analysis/data/plans.jsonl), [run time](./backend/autogen/evaluation/analysis/data/run_time.jsonl), [number of rounds](./backend/autogen/evaluation/analysis/data/number_of_rounds.jsonl), [search mode](./backend/autogen/evaluation/analysis/data/search_mode.jsonl), [total kept and dropped content count](./backend/autogen/evaluation/analysis/data/total_kept_dropped_content.jsonl) are curated by [running the end-to-end system via `main.py` script](#running-the-end-to-end-pipeline). Logs of [the end-to-end system ran](./backend/autogen/evaluation/logs/picked_10_user_cases_end_to_end/) could be found in the [logs](./backend/autogen/evaluation/logs/) folder.

```bash
python -m autogen.main --case_num <case-num>
```
Different `case-num`: 1 (baseline), 2 (with fallback), 3 (with critic), or 4 (full system)

#### C. `CriticAgent` Analysis Datasets

The 40 sets of critic agent's [scores (confidence, relevance, accuracy, safety, feasibility, and personalization)](./backend/autogen/evaluation/analysis/data/critic_agent_scores.jsonl) and [decisions (`ACCEPT` or `RE-WRITE`)](./backend/autogen/evaluation/analysis/data/critic_agent_decision.jsonl) are curated by running the [`critic_agent_evaluation.py`](./backend/autogen/evaluation/ground_truth_curation/critic_agent_evaluation.py) script. Logs of [the critic agent evaluation process](./backend/autogen/evaluation/logs/critic_agent_evaluation/) could be found in the [logs](./backend/autogen/evaluation/logs/) folder.

```bash
python -m autogen.evaluation.ground_truth_curation.critic_agent_evaluation
```

The 40 sets of ground truth, i.e., [human decisions (`ACCEPT` or `RE-WRITE`)](./backend/autogen/evaluation/analysis/data/human_decision.jsonl) and [human scores (relevance, accuracy, safety, feasibility, and personalization)](./backend/autogen/evaluation/analysis/data/human_scores.jsonl) are curated by 1 human annotator by running the [`human_evaluation.py`](./backend/autogen/evaluation/ground_truth_curation/human_evaluation.py) script. Logs of [the human evaluation process](./backend/autogen/evaluation/logs/human_evaluation/) could be found in the [logs](./backend/autogen/evaluation/logs/) folder.

```bash
python -m autogen.evaluation.ground_truth_curation.human_evaluation
```

---

### Evaluation Scripts

Based on the [metrics](./backend/autogen/evaluation/README.md), analysis scripts were written to test the efficiency of the system and each sub-agents.

To display analysis including: (1) [human scores](./backend/autogen/evaluation/analysis/data/human_scores.jsonl), (2) [critic agent scores](./backend/autogen/evaluation/analysis/data/critic_agent_scores.jsonl), (3) [human decisions](./backend/autogen/evaluation/analysis/data/human_decision.jsonl), (4) [critic agent decisions](./backend/autogen/evaluation/analysis/data/critic_agent_decision.jsonl), (5) [number of rounds each agents were ran](./backend/autogen/evaluation/analysis/data/number_of_rounds.jsonl), (6) [runtimes](./backend/autogen/evaluation/analysis/data/run_time.jsonl), and (7) [correlation and confunsion matrix](./backend/autogen/evaluation/analysis/correlation_confusion_matrix.py) based on analysis of human and critic agent's scores and decisions; run the following command to run the [`analysis.py`](./backend/autogen/evaluation/analysis/analysis.py) script:

```bash
python -m autogen.evaluation.analysis.analysis
```

To run the [correlation and confunsion matrix](./backend/autogen/evaluation/analysis/correlation_confusion_matrix.py) alone, by running the [`correlation_confusion_matrix.py`](./backend/autogen/evaluation/analysis/correlation_confusion_matrix.py) script:
```bash
python -m autogen.evaluation.analysis.correlation_confusion_matrix
```

To run analysis on the `WebScraperAgent` and the `SearchAgent` based on: [the total dropped and kept content from the filter mechanism from the WebScraperAgent](./backend/autogen/evaluation/analysis/data/total_kept_dropped_content.jsonl) and [different search mode conducted](./backend/autogen/evaluation/analysis/data/search_mode.jsonl) by running the [`web_search_scraper_analysis.py`](./backend/autogen/evaluation/analysis/web_search_scraper_analysis.py) script:
```bash
python -m autogen.evaluation.analysis.web_search_scraper_analysis
```

Note that the output should be outputed in the [`web_search_analysis_output`](./backend/autogen/evaluation/analysis/web_search_analysis_output/)

