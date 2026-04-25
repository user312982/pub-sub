import aiohttp
import uuid
import datetime
import asyncio
import os
import sys

API_URL = os.getenv("API_URL", "http://localhost:8080")


async def push_normal_event():
    async with aiohttp.ClientSession() as session:
        print("\n--- Pushing Normal Event ---")
        event_1_id = str(uuid.uuid4())
        event_1 = {
            "topic": "user_activity",
            "event_id": event_1_id,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "source": "web_dashboard",
            "payload": {"action": "logout", "user_id": 999},
        }
        async with session.post(f"{API_URL}/publish", json=event_1) as resp:
            data = await resp.json()
            print("Dispatched Event:", data)


async def push_redundant_event():
    async with aiohttp.ClientSession() as session:
        print("\n--- Pushing Redundant Event (Simulating At-Least-Once) ---")
        event_id = "demo-id-777"
        event = {
            "topic": "demo",
            "event_id": event_id,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "source": "ios_app",
            "payload": {"action": "click", "element": "buy_button"},
        }
        async with session.post(f"{API_URL}/publish", json=event) as resp:
            data = await resp.json()
            print("Dispatched First Attempt:", data)
        async with session.post(f"{API_URL}/publish", json=event) as resp2:
            data2 = await resp2.json()
            print("Dispatched Second Attempt (Duplicate):", data2)


async def push_event_batch():
    async with aiohttp.ClientSession() as session:
        print("\n--- Pushing Event Batch ---")
        batch = [
            {
                "topic": "server_health",
                "event_id": str(uuid.uuid4()),
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "source": "monitor",
                "payload": {"cpu_temp": 45, "disk_usage": "60%"},
            },
            {
                "topic": "server_health",
                "event_id": str(uuid.uuid4()),
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "source": "monitor",
                "payload": {"cpu_temp": 50, "disk_usage": "61%"},
            },
        ]
        async with session.post(f"{API_URL}/publish", json=batch) as resp:
            data = await resp.json()
            print("Dispatched Batch:", data)


async def run_performance_benchmark():
    # aiohttp does not set timeout globally the same way, we define a ClientTimeout
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        print("\n--- Executing Performance Benchmark (5000 events, 1000 duplicates) ---")
        total_unique = 4000
        num_duplicates = 1000
        total_events = total_unique + num_duplicates
        
        events = []
        for i in range(total_unique):
            events.append(
                {
                    "topic": "benchmark_topic",
                    "event_id": f"bench-{i}",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "source": "stress-tester",
                    "payload": {},
                }
            )

        for i in range(num_duplicates):
            events.append(
                {
                    "topic": "benchmark_topic",
                    "event_id": f"bench-{i}",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "source": "stress-tester",
                    "payload": {},
                }
            )

        import random
        random.shuffle(events)
        
        batch_size = 1000
        import time
        start = time.time()
        for i in range(0, total_events, batch_size):
            batch = events[i : i + batch_size]
            async with session.post(f"{API_URL}/publish", json=batch) as resp:
                print(f"Sent chunk {i} to {i + len(batch)}, code: {resp.status}")
            
        elapsed = time.time() - start
        print(f"Completed {total_events} events in {elapsed:.2f}s ({total_events/elapsed:.0f} ev/sec)")


async def check_stats():
    async with aiohttp.ClientSession() as session:
        print("\n--- Global System Metrics ---")
        async with session.get(f"{API_URL}/stats") as resp:
            data = await resp.json()
            print(data)


async def check_events():
    async with aiohttp.ClientSession() as session:
        print("\n--- Querying Events by topic 'demo' ---")
        async with session.get(f"{API_URL}/events?topic=demo") as resp:
            data = await resp.json()
            print(data)


async def main():
    pass


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        func = globals().get(command)
        if callable(func) and asyncio.iscoroutinefunction(func):
            asyncio.run(func())
        else:
            print(f"Unrecognized command: {command}")
    else:
        asyncio.run(main())
