# run this to check if redis is working or not
import asyncio
import json
from redis import asyncio as aioredis

async def main():
    try:
        # Connect to Redis (default host/port)
        redis = aioredis.from_url("redis://localhost:6379")

        print(type(redis)) # get type of redis

        # 1. Set a simple string key
        await redis.set("my_name", "Victoria")
        print("Saved 'my_name'")

        # 2. Get and print it
        name = await redis.get("my_name")
        print("Fetched from Redis:", name.decode())

        # 3. Save a Python dictionary as JSON
        user_profile = {
            "id": "u123",
            "name": "Victoria",
            "interests": ["food", "cats"],
            "logged_in": True,
        }
        
        await redis.set("user:u123:profile", json.dumps(user_profile))
        print("Saved user profile")

        # 4. Read it back
        raw_data = await redis.get("user:u123:profile")
        parsed = json.loads(raw_data)
        print("User Profile from Redis:", parsed)

        # 5. Update the value and re-save it
        parsed["logged_in"] = False
        await redis.set("user:u123:profile", json.dumps(parsed))
        print("Updated and re-saved profile")

        # 6. Clean up (optional)
        # await redis.delete("my_name", "user:u123:profile")
        # print("🧹 Cleaned up test keys")

        # Close connection
        await redis.aclose()

    except Exception as e:
        print("Redis error:", e)

asyncio.run(main())


# from redis import asyncio as aioredis
# import asyncio

# async def test_redis_connection():
#     try:
#         redis = aioredis.from_url("redis://localhost:6379")
#         await redis.set("test_key", "value")
#         result = await redis.get("test_key")
#         print("Connected! Result:", result.decode())
#         await redis.aclose()
#     except Exception as e:
#         print("❌ Failed to connect to Redis:", e)

# asyncio.run(test_redis_connection())
