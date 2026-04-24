import asyncio
import time


class Stats:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._received = 0
        self._duplicate_dropped = 0
        self._start_time = time.time()

    async def increment_received(self, count: int = 1):
        async with self._lock:
            self._received += count

    async def increment_duplicate(self, count: int = 1):
        async with self._lock:
            self._duplicate_dropped += count

    async def get_received(self) -> int:
        async with self._lock:
            return self._received

    async def get_duplicate(self) -> int:
        async with self._lock:
            return self._duplicate_dropped

    async def get_uptime(self) -> float:
        return time.time() - self._start_time

    async def reset(self):
        async with self._lock:
            self._received = 0
            self._duplicate_dropped = 0
            self._start_time = time.time()
