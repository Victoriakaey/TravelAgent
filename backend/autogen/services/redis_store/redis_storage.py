import json
from redis import asyncio as aioredis

REDIS_URL = "redis://localhost:6379"

class RedisStorage:
    def __init__(self, redis_url=REDIS_URL):
        self.redis = aioredis.from_url(redis_url)

    def clean_for_json(self, obj):
        if hasattr(obj, "model_dump"):
            return self.clean_for_json(obj.model_dump())  # recursively clean model_dump output
        elif isinstance(obj, dict):
            return {str(k): self.clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.clean_for_json(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self.clean_for_json(item) for item in obj)
        elif hasattr(obj, "__dict__"):
            return self.clean_for_json(vars(obj))  # handle unexpected class objects
        elif isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj # assumed to be a primitive (str, int, float, bool, None)
        else:
            # If it's not a simple type, return a placeholder
            return f"<<non-serializable: {type(obj).__name__}>>"

    async def save_agent_state(self, agent_type: str, agent_name: str, state_data: dict):
        cleaned_state = self.clean_for_json(state_data)
        await self.redis.set(f"{agent_type}:{agent_name}:latest", json.dumps(cleaned_state))

    async def get_agent_state(self, agent_type: str, agent_name: str) -> dict | None:
        raw = await self.redis.get(f"{agent_type}:{agent_name}:latest")
        return json.loads(raw) if raw else None

    async def save_agent_session(self, agent_type: str, agent_name: str, session_id: str, state_data: dict):
        session_key = f"{agent_type}:{agent_name}:sessions:{session_id}"
        cleaned_state = self.clean_for_json(state_data)
        await self.redis.set(session_key, json.dumps(cleaned_state))
        await self.redis.set(f"{agent_type}:{agent_name}:latest_session", session_id)

    async def get_latest_session_id(self, agent_type: str,  agent_name: str) -> str | None:
        raw = await self.redis.get(f"{agent_type}:{agent_name}:latest_session")
        # return raw.decode() if raw else None
        return raw if raw else None

    async def get_session(self, agent_type: str, agent_name: str, session_id: str) -> dict | None:
        session_key = f"{agent_type}:{agent_name}:sessions:{session_id}"
        raw = await self.redis.get(session_key)
        return json.loads(raw) if raw else None

    async def aclose(self):
        await self.redis.aclose()


# make session data expire after xxx days?
# await self.redis.set(session_key, json.dumps(cleaned_state), ex=86400 * 7)  # expire after 7 days