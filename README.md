# Event Aggregator — UTS Pub-Sub System

Layanan agregasi event berbasis FastAPI yang mendukung **Idempotent Deduplication** dan **Persistent Storage** menggunakan SQLite.

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
