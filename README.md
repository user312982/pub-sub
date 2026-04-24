# Event Aggregator — UTS Pub-Sub System

Layanan aggregator event berbasis Python (FastAPI) dengan deduplication idempoten, SQLite persistent store, dan dukungan Docker.

## Arsitektur

```
Publisher ──POST /publish──► FastAPI ──asyncio.Queue──► Consumer ──► SQLite Dedup Store
                                                              │
                                                         ┌────┴────┐
                                                         │  Unique  │  → Store & log
                                                         │ Duplicate│  → Drop & log
                                                         └─────────┘
```

- **FastAPI** — async HTTP server
- **asyncio.Queue** — pipeline in-process publisher → consumer
- **Consumer** — background task, single worker (FIFO)
- **SQLite** — persistent dedup store (WAL mode, `INSERT OR IGNORE`)

## Build & Run

### Docker (Wajib)

```bash
docker build -t uts-aggregator .
docker run -p 8080:8080 uts-aggregator
```

### Docker Compose (Bonus)

```bash
docker compose up --build
```

Publisher akan otomatis mengirim 5000 event + 20% duplikat ke aggregator.

### Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8080
```

### Run Tests

```bash
source .venv/bin/activate
python3 -m pytest tests/ -v
```

## Endpoints

| Method | Path | Deskripsi |
|--------|------|-----------|
| POST | `/publish` | Menerima single event atau batch array |
| GET | `/events?topic=` | Mengembalikan daftar event unik yang telah diproses |
| GET | `/stats` | Statistik: received, unique_processed, duplicate_dropped, topics, uptime |

### Contoh Request

```bash
# Single event
curl -X POST http://localhost:8080/publish \
  -H "Content-Type: application/json" \
  -d '{"topic":"orders","event_id":"ord-001","timestamp":"2024-01-01T00:00:00Z","source":"order-svc","payload":{"order_id":123}}'

# Batch events
curl -X POST http://localhost:8080/publish \
  -H "Content-Type: application/json" \
  -d '[{"topic":"orders","event_id":"ord-001",...}, {...}]'

# Get events by topic
curl http://localhost:8080/events?topic=orders

# Get stats
curl http://localhost:8080/stats
```

## Asumsi & Keputusan Desain

1. **Idempotency**: dedup berdasarkan `(topic, event_id)` — event dengan kombinasi yang sama hanya diproses sekali.
2. **Persistensi**: SQLite dengan WAL mode, file disimpan di `/app/data/dedup.db` — tahan restart container.
3. **Ordering**: Total ordering tidak diperlukan. Aggregator hanya mengumpulkan event unik, tidak ada dependensi antar event.
4. **At-Least-Once**: Endpoint tidak menolak duplikat; consumer melakukan dedup. Publisher bisa kirim event sama berkali-kali.
5. **Deduplication log**: Setiap duplikasi tercatat di log dengan level `WARNING`.

## Struktur Proyek

```
├── src/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, routes, lifespan
│   ├── models.py        # Pydantic models (Event, PublishResponse, StatsResponse)
│   ├── dedup_store.py   # SQLite persistent dedup store
│   ├── stats.py         # Stats tracker (async thread-safe)
│   ├── consumer.py      # Async consumer with internal queue
│   └── publisher.py     # Stress test script
├── tests/
│   ├── conftest.py
│   ├── test_dedup.py    # Dedup validation & persistence
│   ├── test_schema.py   # Event schema validation
│   ├── test_api.py      # API consistency tests
│   └── test_stress.py   # 5000+ events performance test
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── README.md
└── report.md
```

## Video Demo

[Link YouTube — menyusul]
