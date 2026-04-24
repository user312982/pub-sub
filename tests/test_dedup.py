import tempfile
import os
from datetime import datetime

import pytest

from src.dedup_store import DedupStore
from src.models import Event
from src.stats import Stats
from src.consumer import Consumer


@pytest.mark.asyncio
async def test_dedup_rejects_duplicate():
    tmp = tempfile.mktemp(suffix=".db")
    store = DedupStore(tmp)
    try:
        event = Event(
            topic="test",
            event_id="dup-001",
            timestamp=datetime.utcnow(),
            source="svc",
            payload={"data": 1},
        )
        assert await store.store_event(event) is True
        assert await store.store_event(event) is False
        assert await store.count_unique_processed() == 1
    finally:
        store.close()
        os.unlink(tmp)


@pytest.mark.asyncio
async def test_same_event_id_different_topics():
    tmp = tempfile.mktemp(suffix=".db")
    store = DedupStore(tmp)
    try:
        event_a = Event(
            topic="orders", event_id="same-id",
            timestamp=datetime.utcnow(), source="svc", payload={},
        )
        event_b = Event(
            topic="payments", event_id="same-id",
            timestamp=datetime.utcnow(), source="svc", payload={},
        )
        assert await store.store_event(event_a) is True
        assert await store.store_event(event_b) is True
        assert await store.count_unique_processed() == 2
    finally:
        store.close()
        os.unlink(tmp)


@pytest.mark.asyncio
async def test_dedup_persistence_across_restart():
    tmp = tempfile.mktemp(suffix=".db")
    try:
        store1 = DedupStore(tmp)
        event = Event(
            topic="test", event_id="persist-001",
            timestamp=datetime.utcnow(), source="svc",
            payload={"msg": "hello"},
        )
        assert await store1.store_event(event) is True
        assert await store1.store_event(event) is False
        assert await store1.count_unique_processed() == 1
        store1.close()

        store2 = DedupStore(tmp)
        assert await store2.store_event(event) is False
        assert await store2.count_unique_processed() == 1
        store2.close()
    finally:
        os.unlink(tmp)


@pytest.mark.asyncio
async def test_consumer_dedup_integration():
    tmp = tempfile.mktemp(suffix=".db")
    store = DedupStore(tmp)
    st = Stats()
    consumer = Consumer(store, st)
    consumer.start()
    try:
        event = Event(
            topic="test", event_id="int-001",
            timestamp=datetime.utcnow(), source="svc", payload={},
        )
        await consumer.publish(event)
        await consumer.publish(event)
        await consumer.queue.join()

        assert await store.count_unique_processed() == 1
        assert await st.get_received() == 2
        assert await st.get_duplicate() == 1
    finally:
        await consumer.stop()
        store.close()
        os.unlink(tmp)
