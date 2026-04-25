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

## Panduan Penggunaan (Tutor Demo)

Setelah container di atas berjalan, Anda dapat berinteraksi dan mencoba sistem seperti skrip demo melalui perintah berikut:

### 1. Pengiriman Event Biasa
```bash
# Kirim event normal tunggal
docker compose exec publisher python3 src/publisher.py push_normal_event

# Kirim batch event sekaligus
docker compose exec publisher python3 src/publisher.py push_event_batch
```

### 2. Pengecekan Sistem
```bash
# Lihat ringkasan metrik (received, processed, dropped)
docker compose exec publisher python3 src/publisher.py check_stats

# Lihat daftar rekap event unik yang tersimpan (Topic: demo)
docker compose exec publisher python3 src/publisher.py check_events
```

### 3. Simulasi Deduplikasi (Idempotency)
```bash
# Kirim event dengan ID "demo-id-777" sebanyak 2x secepat mungkin
docker compose exec publisher python3 src/publisher.py push_redundant_event

# Cek stats lagi: angka duplicate_dropped pasti bertambah 1!
docker compose exec publisher python3 src/publisher.py check_stats
```

### 4. Skala Produksi (Stress Test)
```bash
# Bom server dengan 5000 event (4000 unik + 1000 duplikat) dalam batch 1000
docker compose exec publisher python3 src/publisher.py run_performance_benchmark
```

---

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

## Testing

Jalankan 15 unit tests (semua lulus/PASSED) secara terisolasi via Docker:
```bash
docker run --rm uts-aggregator python3 -m pytest tests/ -v
```

**Cakupan Pengujian:**
1. **Test API (`test_api.py`)**: Validasi respons konsisten dari `/stats` dan `/events`.
2. **Test Deduplikasi (`test_dedup.py`)**: Menguji keberhasilan pencegahan data ganda (idempotency) dan ketahanan persistensi data setelah sistem dimatikan (restart).
3. **Test Skema (`test_schema.py`)**: Memastikan sistem otomatis menolak payload rusak (tanpa `topic`/`event_id`, tipe tanggal salah) dengan HTTP 422.
4. **Test Stress (`test_stress.py`)**: Menguji kemampuan pemrosesan di atas 5.000 event (dengan >=20% duplikat) dalam satu tarikan.

---

##  Video Demo
[https://youtu.be/X4D96qp1PNc?si=wUcfuQ_pepuwjiYy]

---

##  Project Structure
- `src/`: Kode aplikasi (API, Consumer, Store).
- `tests/`: Unit tests (Pytest).
- `docker-compose.yml`: Orkestrasi aggregator & publisher.
- `report.md`: Penjelasan desain detail (Bab 1-7).
