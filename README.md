# Event Aggregator — UTS Pub-Sub System

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker)](https://docker.com)
[![Tests](https://img.shields.io/badge/tests-15%20passed-brightgreen)](tests/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

A high-performance **event aggregation service** built with Python and FastAPI. It receives events via HTTP, performs **idempotent deduplication** using a persistent SQLite store, and exposes queryable endpoints for processed events and real-time statistics. Designed for **at-least-once delivery** with crash tolerance.

---

## Table of Contents

- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Local Development](#local-development)
  - [Docker (Required)](#docker-required)
  - [Docker Compose (Bonus)](#docker-compose-bonus)
- [API Reference](#api-reference)
  - [POST /publish](#post-publish)
  - [GET /events](#get-events)
  - [GET /stats](#get-stats)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Performance](#performance)
- [Design Decisions](#design-decisions)
- [Video Demo](#video-demo)
- [License](#license)

---

## Architecture

```
┌─────────────┐     POST /publish    ┌──────────────────┐
│  Publisher  │ ──────────────────►  │   FastAPI App    │
│ (curl/test) │                      │   (HTTP Server)  │
└─────────────┘                      └────────┬─────────┘
                                              │
                                       asyncio.Queue
                                              │
                                      ┌───────▼────────┐
                                      │   Consumer     │
                                      │  (background)  │
                                      └───┬─────────┬──┘
                                          │         │
                                   INSERT OR IGNORE │
                                          │         │
                                    ┌─────▼──┐  ┌──▼──────────┐
                                    │ SQLite │  │ Stats       │
                                    │ (dedup)│  │ (in-memory) │
                                    └────────┘  └─────────────┘
```

**Flow:**
1. **Publisher** sends event(s) to `POST /publish` (single or batch)
2. **FastAPI** validates the event schema via Pydantic models
3. Event is enqueued into an **asyncio.Queue** (in-memory FIFO)
4. **Consumer** (background task) dequeues and attempts to store in SQLite
5. **SQLite** `INSERT OR IGNORE` with `PRIMARY KEY (topic, event_id)` ensures deduplication
6. **Stats** counters are updated atomically (received, unique, duplicates dropped)

---

## Features

- ✅ **Idempotent Deduplication** — Events with the same `(topic, event_id)` are processed exactly once
- ✅ **Persistent Storage** — SQLite with WAL mode survives container restarts
- ✅ **Batch & Single Ingestion** — Accepts one event or an array of events per request
- ✅ **At-Least-Once Delivery** — Consumer tolerates duplicate submissions gracefully
- ✅ **Real-Time Statistics** — Query received count, unique processed, duplicates, topics, and uptime
- ✅ **Schema Validation** — Automatic 422 responses for malformed events
- ✅ **Crash Tolerance** — Dedup state persists across restarts via file-based SQLite
- ✅ **Non-Blocking** — Fully asynchronous with asyncio for high throughput

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Framework** | [FastAPI](https://fastapi.tiangolo.com) 0.104+ |
| **Runtime** | Python 3.11+ with asyncio |
| **Dedup Store** | SQLite 3 (WAL mode, `INSERT OR IGNORE`) |
| **Validation** | Pydantic v2 |
| **Server** | Uvicorn (ASGI) |
| **Testing** | pytest + pytest-asyncio + TestClient |
| **Container** | Docker (python:3.11-slim) |

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed on your machine
- (Optional) Python 3.11+ for local development

### Docker Compose (Direkomendasikan)

Menjalankan dua service sekaligus: aggregator dan publisher yang secara otomatis mengirim 6.000 events.

```bash
docker compose up --build
```

Setelah berjalan, akses endpoint berikut di terminal lain:

```bash
curl http://localhost:8080/stats
curl http://localhost:8080/events
curl http://localhost:8080/events?topic=orders
```

Untuk menghentikan:

```bash
docker compose down
```

---

### Docker (Aggregator Saja)

```bash
docker build -t uts-aggregator .
docker run -p 8080:8080 uts-aggregator
```

Kirim event secara manual setelah server berjalan:

```bash
curl -X POST http://localhost:8080/publish \
  -H "Content-Type: application/json" \
  -d '{"topic":"orders","event_id":"ord-001","timestamp":"2024-01-01T00:00:00Z","source":"order-svc","payload":{}}'
```

---

### Lokal (Tanpa Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8080
```

Server akan berjalan di `http://localhost:8080`.

---

## API Reference

### POST /publish

Ingest one or more events into the system.

**Endpoint:** `POST /publish`

**Request Body** (single event):

```json
{
  "topic": "orders",
  "event_id": "ord-001",
  "timestamp": "2024-01-01T00:00:00Z",
  "source": "order-service",
  "payload": {
    "order_id": 123,
    "amount": 49.99
  }
}
```

**Request Body** (batch array):

```json
[
  {
    "topic": "orders",
    "event_id": "ord-001",
    "timestamp": "2024-01-01T00:00:00Z",
    "source": "order-service",
    "payload": {}
  },
  {
    "topic": "payments",
    "event_id": "pay-001",
    "timestamp": "2024-01-01T00:00:01Z",
    "source": "payment-service",
    "payload": {}
  }
]
```

**Response** `200 OK`:

```json
{
  "received": 2,
  "status": "ok"
}
```

**Response** `422 Unprocessable Entity` (invalid schema):

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "topic"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

**Schema:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `topic` | string | ✅ | Event category (e.g., "orders", "payments") |
| `event_id` | string | ✅ | Unique identifier within the topic |
| `timestamp` | string (ISO 8601) | ✅ | Time of event occurrence |
| `source` | string | ✅ | Originating service name |
| `payload` | object | ❌ | Arbitrary event data (default: `{}`) |

> **Note:** Duplicate events (same `topic` + `event_id`) are silently accepted at the API level but **deduplicated** by the consumer. Only the first occurrence is persisted.

### GET /events

Retrieve deduplicated events, optionally filtered by topic.

**Endpoint:** `GET /events?topic={topic}`

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `topic` | string | ❌ | Filter events by topic. Omit to retrieve all events. |

**Response** `200 OK`:

```json
[
  {
    "topic": "orders",
    "event_id": "ord-001",
    "timestamp": "2024-01-01T00:00:00Z",
    "source": "order-service",
    "payload": {}
  }
]
```

### GET /stats

Retrieve real-time statistics about the system.

**Endpoint:** `GET /stats`

**Response** `200 OK`:

```json
{
  "received": 6000,
  "unique_processed": 5000,
  "duplicate_dropped": 1000,
  "topics": ["orders", "payments", "logs", "analytics", "notifications"],
  "uptime": 12.34
}
```

| Field | Type | Description |
|-------|------|-------------|
| `received` | integer | Total events received (including duplicates) |
| `unique_processed` | integer | Events successfully stored (unique) |
| `duplicate_dropped` | integer | Duplicate events detected and dropped |
| `topics` | array[string] | Distinct topics seen so far |
| `uptime` | float | Seconds since service started |

---

## Project Structure

```
uts-aggregator/
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI application, routes, lifespan
│   ├── models.py            # Pydantic models (Event, PublishResponse, StatsResponse)
│   ├── dedup_store.py       # SQLite-based persistent deduplication store
│   ├── stats.py             # Thread-safe in-memory statistics tracker
│   ├── consumer.py          # Background consumer with asyncio.Queue
│   └── publisher.py         # Stress-test script for load simulation
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # pytest fixtures (DedupStore, Stats, TestClient)
│   ├── test_dedup.py        # Deduplication validation & persistence tests
│   ├── test_schema.py       # Event schema validation tests
│   ├── test_api.py          # API endpoint & statistics consistency tests
│   └── test_stress.py       # Performance stress test (5,000+ events)
├── data/                    # Runtime SQLite database (gitignored)
├── requirements.txt         # Python dependencies
├── Dockerfile               # Docker image definition
├── docker-compose.yml       # Multi-service orchestration (bonus)
├── README.md                # This file
└── report.md                # Design report with citations
```

---

## Testing

Proyek ini memiliki **15 unit tests** yang mencakup semua area fungsional.

```bash
# Lokal
source .venv/bin/activate
python3 -m pytest tests/ -v

# Docker
docker run --rm uts-aggregator python3 -m pytest tests/ -v
```

| File | Tests | Cakupan |
|------|-------|---------|
| `test_dedup.py` | 4 | Deduplication, persistence, consumer integration |
| `test_schema.py` | 6 | Validasi skema event, missing fields, batch |
| `test_api.py` | 4 | Endpoint `/events` dan `/stats` |
| `test_stress.py` | 1 | 5.000 event unik + 1.000 duplikat < 30 detik |

---

## Performance

Benchmark results from the stress test (5,000 unique + 1,000 duplicate events):

| Metric | Value |
|--------|-------|
| Total events submitted | 6,000 (5,000 unique + 1,000 duplicates) |
| Average execution time | ~0.87 seconds |
| Throughput | ~6,900 events/second |
| Deduplication accuracy | 100% (no false positives) |
| Memory usage | Minimal (in-memory counters only) |

---

## Design Decisions

### Idempotency & Dedup Strategy

- **Mechanism**: `INSERT OR IGNORE` with `PRIMARY KEY (topic, event_id)` guarantees atomic deduplication without race conditions.
- **Persistence**: SQLite with **WAL mode** (`PRAGMA journal_mode=WAL`) balances write performance with crash safety.
- **Why not Redis?** The specification requires a local-only store that survives restarts. SQLite satisfies this without external dependencies.

### Ordering

**Total ordering is not required.** Each event is independent — there are no causal dependencies between events. The aggregator's role is simply to collect and store unique events. Partial ordering is provided by the single FIFO consumer from `asyncio.Queue`.

### At-Least-Once Delivery

The `POST /publish` endpoint never rejects events. Duplicates are accepted at the API layer and deduplicated by the consumer. This satisfies at-least-once semantics without requiring complex acknowledgment protocols.

### Why FastAPI?

- **Native asyncio support** for non-blocking I/O
- **Automatic schema validation** via Pydantic (reduces boilerplate)
- **Auto-generated OpenAPI docs** at `/docs`
- **High performance** comparable to Node.js and Go

---

## Video Demo

[![YouTube Demo](https://img.shields.io/badge/YouTube-Watch-red?logo=youtube)]()

<!-- TODO: Replace with actual YouTube link -->
*A 5–8 minute demonstration of the system, including:*

- Building and running with Docker
- Publishing events (single and batch)
- Verifying deduplication with duplicate submissions
- Checking statistics via `/stats`
- Querying events via `/events`
- Running unit tests
- Performance stress test

---

## License

This project is developed as part of a university assignment (UTS). All rights reserved.

