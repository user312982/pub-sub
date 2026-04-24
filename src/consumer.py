import asyncio
import logging

from src.models import Event
from src.dedup_store import DedupStore
from src.stats import Stats

logger = logging.getLogger(__name__)


class Consumer:
    def __init__(self, dedup_store: DedupStore, stats: Stats, maxsize: int = 10000):
        self.queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)
        self.dedup_store = dedup_store
        self.stats = stats
        self._task: asyncio.Task | None = None

    def start(self):
        self._task = asyncio.create_task(self._consumer_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def publish(self, event: Event):
        await self.queue.put(event)
        await self.stats.increment_received()

    async def _consumer_loop(self):
        while True:
            try:
                event = await self.queue.get()
                is_new = await self.dedup_store.store_event(event)
                if is_new:
                    logger.info(
                        "Processed event: topic=%s event_id=%s",
                        event.topic, event.event_id,
                    )
                else:
                    logger.warning(
                        "Duplicate event dropped: topic=%s event_id=%s source=%s",
                        event.topic, event.event_id, event.source,
                    )
                    await self.stats.increment_duplicate()
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Consumer error: %s", e)
                self.queue.task_done()
