from datetime import datetime, timezone


class TestAPI:
    def test_events_endpoint_returns_processed_events(self, client):
        event = {
            "topic": "orders",
            "event_id": "ord-001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "svc",
            "payload": {"order": 1},
        }
        client.post("/publish", json=event)
        client.post("/publish", json=event)

        resp = client.get("/events?topic=orders")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["event_id"] == "ord-001"

    def test_events_endpoint_all_topics(self, client):
        for i in range(5):
            client.post("/publish", json={
                "topic": f"topic-{i}",
                "event_id": f"evt-{i:03d}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "svc",
                "payload": {"i": i},
            })
        resp = client.get("/events")
        assert resp.status_code == 200
        assert len(resp.json()) == 5

    def test_stats_consistency_after_publish(self, client):
        events = [
            {"topic": "t1", "event_id": "e1", "timestamp": datetime.now(timezone.utc).isoformat(), "source": "s", "payload": {}},
            {"topic": "t1", "event_id": "e2", "timestamp": datetime.now(timezone.utc).isoformat(), "source": "s", "payload": {}},
            {"topic": "t2", "event_id": "e3", "timestamp": datetime.now(timezone.utc).isoformat(), "source": "s", "payload": {}},
        ]
        for ev in events:
            client.post("/publish", json=ev)
            client.post("/publish", json=ev)

        resp = client.get("/stats")
        data = resp.json()
        assert data["received"] == 6
        assert data["unique_processed"] == 3
        assert data["duplicate_dropped"] == 3
        assert "t1" in data["topics"]
        assert "t2" in data["topics"]
        assert data["uptime"] > 0

    def test_stats_empty_initial(self, client):
        resp = client.get("/stats")
        data = resp.json()
        assert data["received"] == 0
        assert data["unique_processed"] == 0
        assert data["duplicate_dropped"] == 0
        assert data["topics"] == []
        assert data["uptime"] > 0
