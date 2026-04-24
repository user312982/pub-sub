#!/usr/bin/env python3
import asyncio
import random
import sys
import time
import uuid
from datetime import datetime

import aiohttp

TOPICS = ["orders", "payments", "notifications", "analytics", "logs"]
SOURCES = [f"service-{i}" for i in range(1, 6)]


def generate_event(seq: int) -> dict:
    return {
        "topic": random.choice(TOPICS),
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "source": random.choice(SOURCES),
        "payload": {"seq": seq, "data": f"payload-{seq}"},
    }


async def send_event(session: aiohttp.ClientSession, url: str, event: dict):
    async with session.post(f"{url}/publish", json=event) as resp:
        return await resp.json()


async def main():
    target_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    total_unique = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    duplicate_pct = float(sys.argv[3]) if len(sys.argv) > 3 else 0.20

    total_duplicates = int(total_unique * duplicate_pct)
    total_events = total_unique + total_duplicates

    print(f"Target: {target_url}")
    print(f"Generating {total_events} events ({total_unique} unique + {total_duplicates} duplicates)...")

    all_events = []
    for i in range(total_unique):
        all_events.append(generate_event(i))

    for _ in range(total_duplicates):
        dup = random.choice(all_events).copy()
        all_events.append(dup)

    random.shuffle(all_events)

    print(f"Sending {len(all_events)} events...")
    start = time.time()

    async with aiohttp.ClientSession() as session:
        for i, event in enumerate(all_events):
            await send_event(session, target_url, event)
            if (i + 1) % 1000 == 0:
                elapsed = time.time() - start
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                print(f"  {i+1}/{len(all_events)} events ({rate:.0f}/s)")

    elapsed = time.time() - start
    print(f"\nSent {len(all_events)} events in {elapsed:.2f}s ({total_events/elapsed:.0f} events/s)")

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{target_url}/stats") as resp:
            stats_data = await resp.json()
            print(f"\nStats: {stats_data}")

        async with session.get(f"{target_url}/events") as resp:
            events = await resp.json()
            print(f"Unique events stored: {len(events)}")


if __name__ == "__main__":
    asyncio.run(main())
