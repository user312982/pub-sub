import logging
from contextlib import asynccontextmanager
from typing import Optional, Union

from fastapi import FastAPI

from src.models import Event, PublishResponse, StatsResponse
from src.dedup_store import DedupStore
from src.stats import Stats
from src.consumer import Consumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app(
    dedup_store: Optional[DedupStore] = None,
    stats: Optional[Stats] = None,
    consumer: Optional[Consumer] = None,
):
    if dedup_store is None:
        dedup_store = DedupStore("data/dedup.db")
    if stats is None:
        stats = Stats()
    if consumer is None:
        consumer = Consumer(dedup_store, stats)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        consumer.start()
        logger.info("Aggregator started")
        yield
        await consumer.stop()
        dedup_store.close()
        logger.info("Aggregator stopped")

    app = FastAPI(title="Event Aggregator", lifespan=lifespan)

    @app.post("/publish", response_model=PublishResponse)
    async def publish(events: Union[list[Event], Event]):
        if not isinstance(events, list):
            events = [events]
        for event in events:
            await consumer.publish(event)
        return PublishResponse(received=len(events))

    @app.get("/events")
    async def get_events(topic: Optional[str] = None):
        return await dedup_store.get_events(topic)

    @app.get("/stats", response_model=StatsResponse)
    async def get_stats():
        received = await stats.get_received()
        dup_dropped = await stats.get_duplicate()
        unique = await dedup_store.count_unique_processed()
        topics = await dedup_store.get_topics()
        uptime = await stats.get_uptime()
        return StatsResponse(
            received=received,
            unique_processed=unique,
            duplicate_dropped=dup_dropped,
            topics=topics,
            uptime=uptime,
        )

    return app


app = create_app()
