import json
import logging
from collections import defaultdict
from .redis_store.redis_storage import RedisStorage

logger = logging.getLogger(__name__)

class LocalStateService:

    # Basic Methods
    def __init__(self, redis_store: RedisStorage):
        self.redis_store = redis_store
        # In-memory per-session cache so the selector can read synchronously
        self._flag_cache: dict[str, dict[str, bool]] = defaultdict(dict)

    # ---------- Async setters/getters (persist + cache) ----------

    async def aset_flag(self, session_id: str, name: str, value: bool) -> None:
        """
        Persist a boolean milestone flag and update the in-memory cache.
        """
        # Serialize boolean to a compact string
        v = "1" if value else "0"
        key = f"flags:{session_id}:{name}"
        # Adjust to your redis client API if needed
        await self.redis_store.redis.set(key, v)
        self._flag_cache[session_id][name] = value

    async def aget_flag(self, session_id: str, name: str) -> bool:
        """
        Read a boolean milestone flag from cache if present; otherwise from Redis.
        Also refreshes the cache.
        """
        # Serve from cache if available
        if name in self._flag_cache.get(session_id, {}):
            return bool(self._flag_cache[session_id][name])

        key = f"flags:{session_id}:{name}"
        # Adjust to your redis client API if needed
        raw = await self.redis_store.redis.get(key)
        if raw is None:
            # Default to False if never set
            self._flag_cache[session_id][name] = False
            return False

        val = True if raw in (b"1", "1", 1, True) else False
        self._flag_cache[session_id][name] = val
        return val

    # ---------- Synchronous cache reads for selector_func ----------

    def get_cached_flag(self, session_id: str, name: str) -> bool:
        """
        Synchronous, cache-only read (no awaits). Selector should use this.
        Returns False if the flag is absent.
        """
        return bool(self._flag_cache.get(session_id, {}).get(name, False))

    def set_cached_flag(self, session_id: str, name: str, value: bool) -> None:
        """
        Optional: in case you want to prime or override the cache without I/O.
        """
        self._flag_cache[session_id][name] = bool(value)

    def _make_key(self, agent_name: str, session_id: str, artifact_name: str) -> str:
        return f"{agent_name}:sessions:{session_id}:{artifact_name}"
    
    def _make_latest_key(self, agent_name: str) -> str:
        return f"{agent_name}:latest"
    
    def _make_latest_session_key(self, agent_name: str) -> str:
        return f"{agent_name}:latest_session"
    
    def _clean(self, data):
        return self.redis_store.clean_for_json(data)
    
    async def _list_keys(self, agent_name: str, session_id: str) -> list:
        pattern = f"{agent_name}:sessions:{session_id}:*"
        return await self.redis_store.redis.keys(pattern)

    async def _delete_key(self, agent_name: str, session_id: str, artifact_name: str):
        key = self._make_key(agent_name, session_id, artifact_name)
        await self.redis_store.redis.delete(key)

    async def _clear_session(self, agent_name: str, session_id: str):
        keys = await self._list_keys(agent_name, session_id)
        if keys:
            await self.redis_store.redis.delete(*keys)

    # Methods for User Profile and Travel Details
    async def set_user_profile(self, agent_name: str, session_id: str, user_profile: dict):
        key = self._make_key(agent_name, session_id, "user_profile")
        latest_key = self._make_latest_key(agent_name)
        latest_session_key = self._make_latest_session_key(agent_name)
        cleaned_profile = self._clean(user_profile)
        await self.redis_store.redis.set(key, json.dumps(cleaned_profile))
        await self.redis_store.redis.set(latest_key, json.dumps(cleaned_profile))
        await self.redis_store.redis.set(latest_session_key, session_id)

    async def get_user_profile(self, agent_name: str, session_id: str) -> dict:
        key = self._make_key(agent_name, session_id, "user_profile")
        raw = await self.redis_store.redis.get(key)
        return json.loads(raw) if raw else {}
    
    async def get_latest_user_profile(self, agent_name: str) -> dict:
        latest_key = self._make_latest_key(agent_name)
        raw = await self.redis_store.redis.get(latest_key)
        return json.loads(raw) if raw else {}

    async def set_user_travel_details(self, agent_name: str, session_id: str, travel_details: dict):
        key = self._make_key(agent_name, session_id, "user_travel_details")
        latest_key = self._make_latest_key(agent_name)
        latest_session_key = self._make_latest_session_key(agent_name)
        cleaned_details = self._clean(travel_details)
        await self.redis_store.redis.set(key, json.dumps(cleaned_details))
        await self.redis_store.redis.set(latest_key, json.dumps(cleaned_details))
        await self.redis_store.redis.set(latest_session_key, session_id)

    async def get_user_travel_details(self, agent_name: str, session_id: str) -> dict:
        key = self._make_key(agent_name, session_id, "user_travel_details")
        raw = await self.redis_store.redis.get(key)
        return json.loads(raw) if raw else {}
    
    async def get_latest_user_travel_details(self, agent_name: str) -> dict:
        latest_key = self._make_latest_key(agent_name)
        raw = await self.redis_store.redis.get(latest_key)
        return json.loads(raw) if raw else {}

    # Methods for Web Scraper Agent

    async def set_scraped_content(self, agent_name: str, session_id: str, content: dict):
        key = self._make_key(agent_name, session_id, "scraped_content")
        latest_key = self._make_latest_key(agent_name)
        latest_session_key = self._make_latest_session_key(agent_name)
        cleaned = self._clean(content)
        await self.redis_store.redis.set(key, json.dumps(cleaned))
        await self.redis_store.redis.set(f"{latest_key}:scraped_content", json.dumps(cleaned))
        await self.redis_store.redis.set(f"{latest_session_key}:scraped_content", session_id)

    async def get_scraped_content(self, agent_name: str, session_id: str) -> dict:
        key = self._make_key(agent_name, session_id, "scraped_content")
        raw = await self.redis_store.redis.get(key)
        return json.loads(raw) if raw else {}
    
    async def get_latest_scraped_content(self, agent_name: str) -> dict:
        latest_key = self._make_latest_key(agent_name)
        raw = await self.redis_store.redis.get(f"{latest_key}:scraped_content")
        return json.loads(raw) if raw else {}

    async def set_filtered_chunks(self, agent_name: str, session_id: str, chunks: list):
        key = self._make_key(agent_name, session_id, "filtered_chunks")
        latest_key = self._make_latest_key(agent_name)
        latest_session_key = self._make_latest_session_key(agent_name)
        cleaned = self._clean(chunks)
        await self.redis_store.redis.set(key, json.dumps(cleaned))
        await self.redis_store.redis.set(f"{latest_key}:filtered_chunks", json.dumps(cleaned))
        await self.redis_store.redis.set(f"{latest_session_key}:filtered_chunks", session_id)

    async def get_filtered_chunks(self, agent_name: str, session_id: str) -> dict:
        key = self._make_key(agent_name, session_id, "filtered_chunks")
        raw = await self.redis_store.redis.get(key)
        return json.loads(raw) if raw else {}
    
    async def get_latest_filtered_chunks(self, agent_name: str) -> dict:
        latest_key = self._make_latest_key(agent_name)
        raw = await self.redis_store.redis.get(f"{latest_key}:filtered_chunks")
        return json.loads(raw) if raw else {}

    # Methods for Search Agent

    async def store_search_results(self, agent_name: str, session_id: str, search_type: str, results: list):
        if not isinstance(results, list):
            raise ValueError("[LocalStateService - Search - Results]Expected list for search results")
        key = self._make_key(agent_name, session_id, f"search_results:{search_type}")
        latest_key = self._make_latest_key(agent_name)
        latest_session_key = self._make_latest_session_key(agent_name)
        cleaned_results = self._clean(results)
        await self.redis_store.redis.set(key, json.dumps(cleaned_results))
        await self.redis_store.redis.set(f"{latest_key}:search_results:{search_type}", json.dumps(cleaned_results))
        await self.redis_store.redis.set(f"{latest_session_key}:search_results:{search_type}", session_id)

    async def get_search_results(self, agent_name: str, session_id: str, search_type: str) -> list:
        key = self._make_key(agent_name, session_id, f"search_results:{search_type}")
        raw = await self.redis_store.redis.get(key)
        return json.loads(raw) if raw else []

    async def get_latest_search_results(self, agent_name: str, search_type: str) -> list:
        latest_key = self._make_latest_key(agent_name)
        raw = await self.redis_store.redis.get(f"{latest_key}:search_results:{search_type}")
        return json.loads(raw) if raw else []

    # TODO: might need to add latest/latest session methods later
    async def set_selected_item(self, agent_name: str, session_id: str, item_type: str, item: dict):
        key = self._make_key(agent_name, session_id, f"selected:{item_type}")
        cleaned_item = self._clean(item)
        await self.redis_store.redis.set(key, json.dumps(cleaned_item))

    # TODO: might need to add latest/latest session methods later
    async def get_selected_item(self, agent_name: str, session_id: str, item_type: str) -> dict:
        key = self._make_key(agent_name, session_id, f"selected:{item_type}")
        raw = await self.redis_store.redis.get(key)
        return json.loads(raw) if raw else {}
    
    # Methods for Travelers
    async def set_travelers(self, agent_name: str, session_id: str, travelers: list[dict]):
        """Store the list of traveler profiles for a session."""
        key = self._make_key(agent_name, session_id, "travelers")
        latest_key = self._make_latest_key(agent_name)
        latest_session_key = self._make_latest_session_key(agent_name)
        cleaned = self._clean(travelers)
        await self.redis_store.redis.set(key, json.dumps(cleaned))
        await self.redis_store.redis.set(f"{latest_key}:travelers", json.dumps(cleaned))
        await self.redis_store.redis.set(f"{latest_session_key}:travelers", session_id)

    async def get_travelers(self, agent_name: str, session_id: str) -> list[dict]:
        """Retrieve all traveler profiles for a session."""
        key = self._make_key(agent_name, session_id, "travelers")
        raw = await self.redis_store.redis.get(key)
        return json.loads(raw) if raw else []
    
    async def get_latest_travelers(self, agent_name: str) -> list[dict]:
        """Retrieve the most recent traveler profiles for an agent."""
        latest_key = self._make_latest_key(agent_name)
        raw = await self.redis_store.redis.get(f"{latest_key}:travelers")
        return json.loads(raw) if raw else []

    async def add_place(self, agent_name: str, session_id: str, place: dict):
        key = self._make_key(agent_name, session_id, "search_results:places")
        latest_key = self._make_latest_key(agent_name)
        latest_session_key = self._make_latest_session_key(agent_name)
        existing = await self.get_places(agent_name, session_id)
        if not isinstance(existing, list):
            logger.warning(f"[LocalStateService - Search - Add Place] Existing 'places' is not a list. Overwriting.")
            existing = []
        existing.append(self._clean(place))
        await self.redis_store.redis.set(key, json.dumps(existing))
        await self.redis_store.redis.set(f"{latest_key}:search_results:places", json.dumps(existing))
        await self.redis_store.redis.set(f"{latest_session_key}:search_results:places", session_id)

    async def get_places(self, agent_name: str, session_id: str) -> list:
        key = self._make_key(agent_name, session_id, "search_results:places")
        raw = await self.redis_store.redis.get(key)
        return json.loads(raw) if raw else []
    
    async def get_latest_places(self, agent_name: str) -> list:
        latest_key = self._make_latest_key(agent_name)
        raw = await self.redis_store.redis.get(f"{latest_key}:search_results:places")
        return json.loads(raw) if raw else []
    
    # Method for Content Generation Agent
    async def store_generated_plan(self, agent_name: str, session_id: str, plan: str):
        key = self._make_key(agent_name, session_id, "generated_plan")
        latest_key = self._make_latest_key(agent_name)
        latest_session_key = self._make_latest_session_key(agent_name)
        logger.info(f"[DEBUG] Writing generated plan to Redis at key: {key}")
        await self.redis_store.redis.set(key, plan)
        logger.info(f"[DEBUG] Successfully saved generated plan to Redis.")
        await self.redis_store.redis.set(f"{latest_key}:generated_plan", plan)
        await self.redis_store.redis.set(f"{latest_session_key}:generated_plan", session_id)

    async def get_generated_plan(self, agent_name: str, session_id: str) -> str | None:
        key = self._make_key(agent_name, session_id, "generated_plan")
        result = await self.redis_store.redis.get(key)
        return result.decode("utf-8") if result else None

    async def get_latest_generated_plan(self, agent_name: str) -> str | None:
        latest_key = self._make_latest_key(agent_name)
        result = await self.redis_store.redis.get(f"{latest_key}:generated_plan")
        return result.decode("utf-8") if result else None

    # Method for Critic Agent
    async def store_critic_reasoning(self, agent_name: str, session_id: str, reasoning: str):
        latest_key = self._make_latest_key(agent_name)
        latest_session_key = self._make_latest_session_key(agent_name)
        key = self._make_key(agent_name, session_id, "critic_reasoning")
        await self.redis_store.redis.set(key, reasoning)
        await self.redis_store.redis.set(f"{latest_key}:critic_reasoning", reasoning)
        await self.redis_store.redis.set(f"{latest_session_key}:critic_reasoning", session_id)

    async def get_critic_reasoning(self, agent_name: str, session_id: str) -> str | None:
        key = self._make_key(agent_name, session_id, "critic_reasoning")
        result = await self.redis_store.redis.get(key)
        return result.decode("utf-8") if result else None
    
    async def get_latest_critic_reasoning(self, agent_name: str) -> str | None:
        latest_key = self._make_latest_key(agent_name)
        result = await self.redis_store.redis.get(f"{latest_key}:critic_reasoning")
        return result.decode("utf-8") if result else None
    
    async def store_critic_checklist(self, agent_name: str, session_id: str, checklist: str):
        key = self._make_key(agent_name, session_id, "critic_checklist")
        latest_key = self._make_latest_key(agent_name)
        latest_session_key = self._make_latest_session_key(agent_name)
        await self.redis_store.redis.set(key, checklist)
        await self.redis_store.redis.set(f"{latest_key}:critic_checklist", checklist)
        await self.redis_store.redis.set(f"{latest_session_key}:critic_checklist", session_id)

    async def get_critic_checklist(self, agent_name: str, session_id: str) -> str | None:
        key = self._make_key(agent_name, session_id, "critic_checklist")
        result = await self.redis_store.redis.get(key)
        return result.decode("utf-8") if result else None
    
    async def get_latest_critic_checklist(self, agent_name: str) -> str | None:
        latest_key = self._make_latest_key(agent_name)
        result = await self.redis_store.redis.get(f"{latest_key}:critic_checklist")
        return result.decode("utf-8") if result else None

    async def store_critic_scores(self, agent_name: str, session_id: str, scores: str):
        key = self._make_key(agent_name, session_id, "critic_scores")
        latest_key = self._make_latest_key(agent_name)
        latest_session_key = self._make_latest_session_key(agent_name)
        await self.redis_store.redis.set(key, scores)
        await self.redis_store.redis.set(f"{latest_key}:critic_scores", scores)
        await self.redis_store.redis.set(f"{latest_session_key}:critic_scores", session_id)

    async def get_critic_scores(self, agent_name: str, session_id: str) -> str | None:
        key = self._make_key(agent_name, session_id, "critic_scores")
        result = await self.redis_store.redis.get(key)
        return result.decode("utf-8") if result else None
    
    async def get_latest_critic_scores(self, agent_name: str) -> str | None:
        latest_key = self._make_latest_key(agent_name)
        result = await self.redis_store.redis.get(f"{latest_key}:critic_scores")
        return result.decode("utf-8") if result else None
    
    async def store_critic_suggestions(self, agent_name: str, session_id: str, suggestions: str):
        key = self._make_key(agent_name, session_id, "critic_suggestions")
        latest_key = self._make_latest_key(agent_name)
        latest_session_key = self._make_latest_session_key(agent_name)
        await self.redis_store.redis.set(key, suggestions)
        await self.redis_store.redis.set(f"{latest_key}:critic_suggestions", suggestions)
        await self.redis_store.redis.set(f"{latest_session_key}:critic_suggestions", session_id)

    async def get_critic_suggestions(self, agent_name: str, session_id: str) -> str | None:
        key = self._make_key(agent_name, session_id, "critic_suggestions")
        result = await self.redis_store.redis.get(key)
        return result.decode("utf-8") if result else None
    
    async def get_latest_critic_suggestions(self, agent_name: str) -> str | None:
        latest_key = self._make_latest_key(agent_name)
        result = await self.redis_store.redis.get(f"{latest_key}:critic_suggestions")
        return result.decode("utf-8") if result else None

    async def store_critic_decision(self, agent_name: str, session_id: str, decision: str):
        key = self._make_key(agent_name, session_id, "critic_decision")
        latest_key = self._make_latest_key(agent_name)
        latest_session_key = self._make_latest_session_key(agent_name)
        await self.redis_store.redis.set(key, decision)
        await self.redis_store.redis.set(f"{latest_key}:critic_decision", decision)
        await self.redis_store.redis.set(f"{latest_session_key}:critic_decision", session_id)

    async def get_critic_decision(self, agent_name: str, session_id: str) -> str | None:
        key = self._make_key(agent_name, session_id, "critic_decision")
        result = await self.redis_store.redis.get(key)
        return result.decode("utf-8") if result else None
    
    async def get_latest_critic_decision(self, agent_name: str) -> str | None:
        latest_key = self._make_latest_key(agent_name)
        result = await self.redis_store.redis.get(f"{latest_key}:critic_decision")
        return result.decode("utf-8") if result else None
    
    async def store_critic_preference_constraint_counts(self, agent_name: str, session_id: str, preference_constraint_counts: str):
        latest_key = self._make_latest_key(agent_name)
        latest_session_key = self._make_latest_session_key(agent_name)
        key = self._make_key(agent_name, session_id, "critic_preference_constraint_counts")
        await self.redis_store.redis.set(key, preference_constraint_counts)
        await self.redis_store.redis.set(f"{latest_key}:critic_preference_constraint_counts", preference_constraint_counts)
        await self.redis_store.redis.set(f"{latest_session_key}:critic_preference_constraint_counts", session_id)

    async def get_critic_preference_constraint_counts(self, agent_name: str, session_id: str) -> str | None:
        key = self._make_key(agent_name, session_id, "critic_preference_constraint_counts")
        result = await self.redis_store.redis.get(key)
        return result.decode("utf-8") if result else None
    
    async def get_latest_critic_preference_constraint_counts(self, agent_name: str) -> str | None:
        latest_key = self._make_latest_key(agent_name)
        result = await self.redis_store.redis.get(f"{latest_key}:critic_preference_constraint_counts")
        return result.decode("utf-8") if result else None
    
    async def store_critic_raw_response(self, agent_name: str, session_id: str, raw_response: str):
        latest_key = self._make_latest_key(agent_name)
        latest_session_key = self._make_latest_session_key(agent_name)
        key = self._make_key(agent_name, session_id, "critic_raw_response")
        await self.redis_store.redis.set(key, raw_response)
        await self.redis_store.redis.set(f"{latest_key}:critic_raw_response", raw_response)
        await self.redis_store.redis.set(f"{latest_session_key}:critic_raw_response", session_id)

    async def get_critic_raw_response(self, agent_name: str, session_id: str) -> str | None:
        key = self._make_key(agent_name, session_id, "critic_raw_response")
        result = await self.redis_store.redis.get(key)
        return result.decode("utf-8") if result else None
    
    async def get_latest_critic_raw_response(self, agent_name: str) -> str | None:
        latest_key = self._make_latest_key(agent_name)
        result = await self.redis_store.redis.get(f"{latest_key}:critic_raw_response")
        return result.decode("utf-8") if result else None