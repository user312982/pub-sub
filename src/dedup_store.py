import json
import os
import sqlite3
import asyncio
from datetime import datetime, timezone
from typing import Optional

from src.models import Event


class DedupStore:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.lock = asyncio.Lock()
        self._init_db()

    def _init_db(self):
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                topic TEXT NOT NULL,
                event_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                payload TEXT DEFAULT '{}',
                processed_at TEXT NOT NULL,
                PRIMARY KEY (topic, event_id)
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_topic
            ON events(topic)
        """)
        self.conn.commit()

    async def store_event(self, event: Event) -> bool:
        async with self.lock:
            cursor = self.conn.execute(
                """INSERT OR IGNORE INTO events
                   (topic, event_id, timestamp, source, payload, processed_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    event.topic,
                    event.event_id,
                    event.timestamp.isoformat(),
                    event.source,
                    json.dumps(event.payload),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self.conn.commit()
            return cursor.rowcount > 0

    async def count_unique_processed(self) -> int:
        async with self.lock:
            cursor = self.conn.execute("SELECT COUNT(*) FROM events")
            return cursor.fetchone()[0]

    async def get_topics(self) -> list[str]:
        async with self.lock:
            cursor = self.conn.execute("SELECT DISTINCT topic FROM events")
            return [row[0] for row in cursor.fetchall()]

    async def get_events(self, topic: Optional[str] = None) -> list[Event]:
        async with self.lock:
            if topic:
                cursor = self.conn.execute(
                    "SELECT topic, event_id, timestamp, source, payload FROM events WHERE topic=? ORDER BY processed_at",
                    (topic,),
                )
            else:
                cursor = self.conn.execute(
                    "SELECT topic, event_id, timestamp, source, payload FROM events ORDER BY processed_at"
                )
            events = []
            for row in cursor.fetchall():
                events.append(Event(
                    topic=row[0],
                    event_id=row[1],
                    timestamp=datetime.fromisoformat(row[2]),
                    source=row[3],
                    payload=json.loads(row[4]),
                ))
            return events

    async def clear(self):
        async with self.lock:
            self.conn.execute("DELETE FROM events")
            self.conn.commit()

    def close(self):
        self.conn.close()
