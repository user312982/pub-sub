# Event Aggregator — UTS Pub-Sub System

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![Testing](https://img.shields.io/badge/Tests-15%20Passed-brightgreen.svg)](tests/)

Layanan aggregator event berkinerja tinggi yang dirancang untuk menangani beban ribuan event secara asinkron dengan fitur de-duplikasi otomatis (Idempotency).

### 🛠 Core Technologies
- **Backend:** Python 3.11 + FastAPI (Async IO)
- **Database:** SQLite 3 (WAL Mode) untuk persistensi lokal
- **Reliability:** At-least-once delivery dengan Intelligent Deduplication
- **Testing:** 15 Automated Unit Tests (Pytest)
- **Isolation:** Containerized via Docker & Docker Compose

---

## Quick Start

### Docker Compose (Rekomendasi)
```bash
docker compose up -d --build
```
*Service publisher otomatis mengirim 5000 event untuk pengujian.*

### Docker Manual
```bash
# Build image
docker build -t uts-aggregator .

# Run aggregator (default port 8080)
docker run -p 8080:8080 uts-aggregator
```

---

## 🛠 API Reference

### 1. `POST /publish`
Menerima satu atau banyak event (batch).
- **Body:** Single Object atau Array of Objects.
- **Payload:** `{ "topic": "string", "event_id": "string", "timestamp": "ISO8601", "source": "string", "payload": {} }`

### 2. `GET /events`
Mengambil daftar event unik yang telah diproses.
- **Query Param:** `topic` (optional) untuk filter.

### 3. `GET /stats`
Menampilkan metrik sistem: `received`, `unique_processed`, `duplicate_dropped`, `topics`, dan `uptime`.

---

##  Asumsi
1. **Deduplikasi:** Berdasarkan kombinasi unik `(topic, event_id)`.
2. **Durabilitas:** Data disimpan di `data/dedup.db` (SQLite) yang di-mount via volume Docker.
3. **Semantik:** Menggunakan *At-least-once delivery*; publisher dapat mengirim ulang jika gagal, sistem menangani duplikasi.
4. **Ordering:** Menggunakan *Partial Ordering* (FIFO) melalui `asyncio.Queue`.

---

##  Testing
Jalankan unit tests (15 Passed):
```bash
docker run --rm uts-aggregator python3 -m pytest tests/ -v
```

---

##  Video Demo
[https://youtu.be/X4D96qp1PNc?si=wUcfuQ_pepuwjiYy]

---

##  Project Structure
- `src/`: Kode aplikasi (API, Consumer, Store).
- `tests/`: Unit tests (Pytest).
- `docker-compose.yml`: Orkestrasi aggregator & publisher.
- `report.md`: Penjelasan desain detail (Bab 1-7).
