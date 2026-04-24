import asyncio
import os
import tempfile
import time
from datetime import datetime, timezone

import pytest

from src.dedup_store import DedupStore
from src.stats import Stats
from src.consumer import Consumer


@pytest.mark.asyncio
async def test_stress_5000_events_with_duplicates():
    tmp = tempfile.mktemp(suffix=".db")
    store = DedupStore(tmp)
    st = Stats()
    consumer = Consumer(store, st)
    consumer.start()
    try:
        total_unique = 5000
        duplicate_pct = 0.20
        total_duplicates = int(total_unique * duplicate_pct)

        events = []
        for i in range(total_unique):
            events.append({
                "topic": "stress",
                "event_id": f"str-{i:05d}",
                "timestamp": datetime.now(timezone.utc),
                "source": "stress-test",
                "payload": {"seq": i},
            })

        for _ in range(total_duplicates):
            events.append(events[0])

        import random
        random.shuffle(events)

        from src.models import Event as EventModel
        start = time.time()

        for raw in events:
            await consumer.publish(EventModel(**raw))

        await consumer.queue.join()
        elapsed = time.time() - start

        unique = await store.count_unique_processed()
        recv = await st.get_received()
        dup_count = await st.get_duplicate()

        assert unique == total_unique
        assert recv == total_unique + total_duplicates
        assert dup_count == total_duplicates
        assert elapsed < 30.0, f"Stress test took {elapsed:.2f}s"
    finally:
        await consumer.stop()
        store.close()
        os.unlink(tmp)
