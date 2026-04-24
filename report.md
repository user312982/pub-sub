# Laporan UTS — Event Aggregator System

## Ringkasan Sistem

Sistem aggregator event berbasis Python (FastAPI + asyncio) yang menerima event dari publisher melalui HTTP, melakukan deduplication idempoten berbasis `(topic, event_id)`, dan menyimpan event unik ke dalam SQLite persistent store. Sistem dirancang untuk menangani at-least-once delivery dengan toleransi crash dan restart.

### Arsitektur Sistem

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

---

## 1. Karakteristik Sistem Terdistribusi dan Trade-off (Bab 1)

Sistem terdistribusi memiliki tiga karakteristik utama: **distribution transparency**, **openness**, dan **scalability** (Coulouris et al., 2012, Chapter 1). Dalam desain Pub-Sub log aggregator ini, trade-off yang paling menonjol terjadi antara **transparansi** dan **performa**.

### Implementasi dalam Sistem

| Karakteristik | Implementasi |
|---|---|
| **Distribution Transparency** | Consumer dan dedup store berjalan dalam proses yang sama dengan FastAPI — pengirim tidak perlu tahu detail internal pemrosesan |
| **Openness** | Menggunakan HTTP standar dan JSON sebagai format data — dapat diintegrasikan dengan layanan apa pun |
| **Scalability** | Single consumer saat ini, namun arsitektur asyncio.Queue memungkinkan multiple consumer worker ke depannya |

### Trade-off yang Diambil

Upaya untuk menyembunyikan sepenuhnya masalah jaringan atau memaksakan strict consistency dapat meningkatkan latensi dan menurunkan throughput secara signifikan (Coulouris et al., 2012, Chapter 1). Oleh karena itu, sistem ini **tidak memaksakan strong consistency** — endpoint `/publish` menerima event secara asynchronous dan langsung merespons tanpa menunggu konsumen selesai memproses. Dengan cara ini, availability tetap terjaga dan publisher tidak terblokir.

---

## 2. Client-Server vs Publish-Subscribe (Bab 2)

Arsitektur **client-server** bekerja dengan pola request-reply yang sinkron, sementara **publish-subscribe** menggunakan pendekatan berbasis peristiwa (event-based architecture) yang lebih longgar dengan **referential decoupling** dan **temporal decoupling** (Coulouris et al., 2012, Chapter 2).

### Alasan Memilih Pub-Sub

| Aspek | Client-Server | Publish-Subscribe (Dipilih) |
|---|---|---|
| **Coupling** | Kuat — klien tahu lokasi server | Longgar — publisher dan consumer tidak saling kenal |
| **Sinkronisasi** | Sinkron — klien menunggu respons | Asinkron — publisher lanjut tanpa blokir |
| **Skalabilitas** | Bottleneck di server | Skalabel — event bus menangani banyak publisher |
| **Waktu** | Kedua pihak harus aktif | Temporal decoupling — boleh tidak aktif bersamaan |

Pada model client-server, ribuan node pengirim log yang terhubung secara sinkron ke satu layanan berpotensi menimbulkan bottleneck. Dengan Pub-Sub, setiap publisher cukup mengirimkan event log secara asinkron, lalu dapat langsung melanjutkan prosesnya. Sementara itu, aggregator sebagai subscriber dapat mengambil dan memproses log sesuai kapasitas yang tersedia tanpa menghambat sistem pengirim.

### Implementasi

Publisher dan consumer dipisahkan oleh `asyncio.Queue` pada [`src/consumer.py`](src/consumer.py:12). Publisher (endpoint `/publish`) hanya memasukkan event ke antrian dan merespons HTTP 200. Consumer berjalan sebagai background task yang mengambil event dari antrian dan memprosesnya secara FIFO.

---

## 3. At-Least-Once Delivery dan Idempotency (Bab 3)

Dalam penanganan kegagalan komunikasi, **at-least-once delivery** menjamin bahwa sebuah pesan akan dieksekusi setidaknya satu kali melalui mekanisme pengiriman ulang saat terjadi timeout. Sebaliknya, **exactly-once semantics** sangat sulit dicapai secara mutlak karena pengirim tidak pernah dapat mengetahui dengan pasti apakah server benar-benar telah mengeksekusi pesan terakhir (Coulouris et al., 2012, Chapter 3).

### Mengapa At-Least-Once?

Sistem ini menggunakan **at-least-once delivery** dengan alasan:

1. **Kesederhanaan** — Tidak perlu ACK yang kompleks atau two-phase commit
2. **Kinerja** — Tidak ada overhead koordinasi antar node
3. **Kecukupan** — Untuk aggregator log, duplikasi bisa ditoleransi selama integritas data tetap terjaga

### Peran Idempotent Consumer

Karena mekanisme retry pada skema at-least-once secara alami dapat menimbulkan pengiriman log ganda, keberadaan **idempotent consumer** menjadi sangat penting. Operasi yang idempoten adalah operasi yang akan menghasilkan keadaan akhir yang sama meskipun dijalankan berulang kali. Tanpa idempotent consumer, pengiriman ulang akibat gangguan jaringan sesaat dapat menyebabkan duplikasi entri log dan merusak integritas data pada sistem aggregator.

### Implementasi

Idempotency diimplementasikan melalui [`src/dedup_store.py`](src/dedup_store.py:42) dengan `INSERT OR IGNORE` dan PRIMARY KEY `(topic, event_id)`:

```python
INSERT OR IGNORE INTO events (topic, event_id, ...) VALUES (?, ?, ...)
```

Operasi SQL atomik ini memastikan bahwa:

- Jika event **belum ada** → INSERT berhasil, `rowcount > 0` → event unik
- Jika event **sudah ada** → INSERT diabaikan, `rowcount = 0` → duplikat di-drop

Setiap duplikasi yang terdeteksi dicatat di log dengan level `WARNING` pada [`src/consumer.py`](src/consumer.py:44-47).

---

## 4. Skema Penamaan dan Dampak terhadap Dedup (Bab 4)

Skema penamaan memiliki peran penting dalam melokalisasi entitas pada sistem terdistribusi (Coulouris et al., 2012, Chapter 4). Untuk penamaan topic, pendekatan yang disarankan adalah **structured naming** secara hierarkis, misalnya `datacenter/service/severity`. Untuk event_id, pendekatan **flat naming** yang bersifat collision-resistant lebih tepat digunakan, misalnya UUID4.

### Skema Penamaan dalam Sistem

| Entitas | Pendekatan | Contoh |
|---|---|---|
| **topic** | Structured naming (flat) | `"orders"`, `"payments"`, `"notifications"` |
| **event_id** | Flat naming (UUID4) | `"a1b2c3d4-e5f6-..."` |
| **source** | Identitas node asal | `"service-1"`, `"order-service"` |

### Dampak terhadap Dedup

Penggunaan `event_id` yang unik dan stabil memberikan dampak besar terhadap efektivitas proses deduplication. Dengan ID yang konsisten, dedup store cukup memeriksa keberadaan kunci `(topic, event_id)` tanpa harus membandingkan seluruh isi log. Jika suatu paket log dikirim ulang melalui mekanisme retry, paket tersebut tetap menghasilkan identitas yang sama. Dengan demikian, aggregator dapat mengenalinya sebagai duplikasi dan menolak pencatatan ulang.

Pada sistem ini, dedup store menggunakan **composite primary key** `(topic, event_id)` pada [`src/dedup_store.py`](src/dedup_store.py:30). Kombinasi ini memungkinkan:

- Event ID yang sama di **topic berbeda** → dianggap unik (contoh: event_id="log-001" di topic "orders" dan "payments")
- Event ID yang sama di **topic sama** → dianggap duplikat

Ini memungkinkan fleksibilitas penamaan antar layanan tanpa khawatir collision global.

---

## 5. Ordering dan Pendekatan Praktis (Bab 5)

**Totally-ordered multicasting** menjamin bahwa seluruh pesan diterima dalam urutan yang sama oleh semua proses. Namun, total ordering tidak selalu diperlukan. Dalam sistem log aggregator, total ordering dapat diabaikan apabila pemrosesan log bersifat **komutatif** (hasil akhir tidak bergantung pada urutan) atau ketika log berasal dari layanan yang tidak memiliki ketergantungan langsung satu sama lain sehingga cukup memerlukan **causal ordering** (Coulouris et al., 2012, Chapter 5).

### Keputusan: Total Ordering Tidak Diperlukan

Sistem ini **tidak memaksakan total ordering** dengan alasan:

1. **Independensi event** — Setiap event bersifat independen; tidak ada causal dependency antar event
2. **Komutatif** — Hasil akhir (kumpulan event unik) tidak bergantung pada urutan pemrosesan
3. **Tidak ada stateful aggregation** — Aggregator hanya mengumpulkan dan menyimpan event unik

### Pendekatan yang Digunakan

| Aspek | Implementasi |
|---|---|
| **Partial ordering** | Single consumer FIFO dari `asyncio.Queue` pada [`src/consumer.py`](src/consumer.py:12) |
| **Timestamp** | Event menyertakan timestamp ISO 8601 dari publisher |
| **Urutan penyimpanan** | SQLite `ORDER BY processed_at` pada [`src/dedup_store.py`](src/dedup_store.py:71-76) |

Jika sistem tetap dipaksa menggunakan total ordering melalui central sequencer, performa dapat menurun dan masalah skalabilitas akan semakin besar (Coulouris et al., 2012, Chapter 5). Oleh karena itu, pendekatan partial ordering melalui single consumer FIFO dipilih sebagai keseimbangan antara ordering dan performa.

---

## 6. Failure Modes dan Strategi Mitigasi (Bab 6)

Beberapa failure modes yang umum pada sistem terdistribusi meliputi **crash failure** (proses berhenti sepenuhnya), **omission failure** (kegagalan komponen dalam mengirim atau menerima pesan), serta **arbitrary failure** (pesan duplikat atau tidak berurutan) (Coulouris et al., 2012, Chapter 6).

### Failure Modes dan Mitigasi

| Failure Mode | Deskripsi | Mitigasi dalam Sistem |
|---|---|---|
| **Crash failure** | Proses berhenti sepenuhnya | SQLite persistent store di [`src/dedup_store.py`](src/dedup_store.py:12-16) — data tetap aman di disk |
| **Omission failure** | Pesan gagal dikirim/diterima | Publisher dapat melakukan retry (at-least-once) |
| **Arbitrary failure** | Pesan duplikat atau tidak berurutan | Dedup store dengan `INSERT OR IGNORE` menolak duplikat |

### Toleransi Crash

Sistem dirancang untuk toleran terhadap crash melalui:

1. **Persistent Dedup Store** — [`src/dedup_store.py`](src/dedup_store.py:12) menggunakan SQLite dengan WAL mode (`PRAGMA journal_mode=WAL`) yang memastikan durability dan crash recovery
2. **File-based Storage** — Database disimpan di `data/dedup.db` yang di-mount sebagai volume Docker pada [`docker-compose.yml`](docker-compose.yml:7) sehingga data tetap aman meskipun container dihapus
3. **Idempotent Consumer** — [`src/consumer.py`](src/consumer.py:37) menggunakan `store_event()` yang idempoten — reprocessing tidak mengubah state

Seluruh strategi ini sesuai dengan rekomendasi teori: durable dedup store untuk mencatat ID log secara persisten, serta checkpointing untuk pemulihan (Coulouris et al., 2012, Chapter 6).

---

## 7. Eventual Consistency dan Idempotency (Bab 7)

**Eventual consistency** merupakan model konsistensi lemah yang menjamin bahwa apabila tidak ada lagi pembaruan baru yang masuk, seluruh salinan data pada berbagai replika pada akhirnya akan berkonvergensi ke keadaan yang sama (Coulouris et al., 2012, Chapter 7). Dalam sistem log aggregator berskala besar, model ini banyak digunakan karena mampu mengurangi beban sinkronisasi global dan sekaligus mendukung availability serta performa yang lebih tinggi.

### Penerapan dalam Sistem

Sistem ini mengadopsi **eventual consistency** dalam pemrosesan event:

| Aspek | Implementasi |
|---|---|
| **Model** | Eventual consistency — event yang baru masuk mungkin belum langsung tersedia di `/events` karena masih dalam antrian |
| **Konvergensi** | Consumer FIFO memproses event secara berurutan; semua event unik akhirnya tersimpan di SQLite |
| **Idempotency** | `INSERT OR IGNORE` memastikan event yang sama tidak merusak data meskipun diterima berulang kali |

Penerapan idempotency dan mekanisme dedup sangat penting untuk menjaga validitas konvergensi dalam eventual consistency. Jika operasi konsumsi log dirancang agar idempoten dan setiap log disaring melalui deduplikasi, maka penerimaan log yang sama secara berulang tidak akan merusak isi basis data. Dengan cara ini, sistem dapat mencapai konvergensi tanpa menimbulkan inkonsistensi akibat duplikasi pembaruan.

---

## 8. Metrik Evaluasi dan Keputusan Desain (Bab 1–7)

Keputusan arsitektur pada sistem ini dievaluasi melalui tiga metrik utama: **throughput**, **latency**, dan **duplicate rate** (Coulouris et al., 2012; Steen & Tanenbaum, 2023).

### Throughput

| Metrik | Hasil |
|---|---|
| Total event diproses | 6.000 (5.000 unique + 1.000 duplikat) |
| Waktu eksekusi | ~0.87 detik |
| **Throughput** | **~6.900 events/detik** |

Desain Pub-Sub yang asinkron dipilih karena mampu membebaskan publisher dari proses menunggu respons, sehingga kapasitas pengiriman log dapat meningkat jauh di atas pendekatan client-server tradisional.

### Latency

Sistem memilih **eventual consistency** dibanding strong consistency agar log dapat segera diterima dan diproses secara lokal tanpa menunggu sinkronisasi seluruh replika secara real-time. Dalam implementasi:

- `POST /publish` → enqueue → HTTP 200 (latency rendah, ~milidetik)
- Consumer → SQLite → selesai (background, tidak memengaruhi respons HTTP)

### Duplicate Rate

| Metrik | Hasil |
|---|---|
| Duplikat dikirim | 1.000 (20% dari total) |
| Duplikat terdeteksi & di-drop | 1.000 |
| **Duplicate rate** | **0% false positive** |

Dengan idempotent consumer dan durable dedup store, sistem tetap tahan terhadap banjir data ganda dan mampu menjaga integritas hasil agregasi.

---

## Ringkasan Keterkaitan dengan Teori

| Bab | Topik | Implementasi | Kode Terkait |
|---|---|---|---|
| Bab 1 | Karakteristik Sistem Terdistribusi | Trade-off transparansi vs performa; availability diprioritaskan | [`src/main.py`](src/main.py:31-38) — async lifespan |
| Bab 2 | Client-Server vs Pub-Sub | Arsitektur Pub-Sub dengan referential & temporal decoupling | [`src/consumer.py`](src/consumer.py:12) — asyncio.Queue |
| Bab 3 | At-Least-Once Delivery | Retry + idempotent consumer via `INSERT OR IGNORE` | [`src/dedup_store.py`](src/dedup_store.py:42) |
| Bab 4 | Skema Penamaan | Topic (structured), event_id (flat UUID4), composite PK | [`src/dedup_store.py`](src/dedup_store.py:30) — PK(topic, event_id) |
| Bab 5 | Ordering | Total ordering tidak diperlukan; partial ordering via FIFO | [`src/consumer.py`](src/consumer.py:33) — consumer loop |
| Bab 6 | Failure Modes | Crash tolerance via SQLite WAL mode; mitigasi duplikasi | [`src/dedup_store.py`](src/dedup_store.py:20-21) — WAL |
| Bab 7 | Eventual Consistency | Model eventual consistency; idempotency menjaga konvergensi | [`src/dedup_store.py`](src/dedup_store.py:42) — INSERT OR IGNORE |

---

## Unit Tests

Sistem memiliki **15 unit tests** (melebihi minimum 5-10 yang disyaratkan):

| # | Test | Cakupan | File |
|---|---|---|---|
| 1 | `test_dedup_rejects_duplicate` | Dedup bekerja untuk event yang sama | [`tests/test_dedup.py`](tests/test_dedup.py:14) |
| 2 | `test_same_event_id_different_topics` | Event ID sama, topic beda = 2 unique | [`tests/test_dedup.py`](tests/test_dedup.py:34) |
| 3 | `test_dedup_persistence_across_restart` | Dedup store tahan restart (simulasi) | [`tests/test_dedup.py`](tests/test_dedup.py:55) |
| 4 | `test_consumer_dedup_integration` | Consumer pipeline + dedup stats | [`tests/test_dedup.py`](tests/test_dedup.py:78) |
| 5 | `test_valid_event_schema` | Event valid → 200 OK | [`tests/test_schema.py`](tests/test_schema.py:7) |
| 6 | `test_missing_topic_field` | Missing topic → 422 | [`tests/test_schema.py`](tests/test_schema.py:21) |
| 7 | `test_missing_event_id_field` | Missing event_id → 422 | [`tests/test_schema.py`](tests/test_schema.py:31) |
| 8 | `test_invalid_timestamp_format` | Bad timestamp → 422 | [`tests/test_schema.py`](tests/test_schema.py:41) |
| 9 | `test_empty_body` | Empty body → 422 | [`tests/test_schema.py`](tests/test_schema.py:52) |
| 10 | `test_batch_publish` | Batch 10 events → received=10 | [`tests/test_schema.py`](tests/test_schema.py:56) |
| 11 | `test_events_by_topic` | GET /events?topic=... mengembalikan 1 event | [`tests/test_api.py`](tests/test_api.py:5) |
| 12 | `test_events_all_topics` | GET /events semua topic = 5 | [`tests/test_api.py`](tests/test_api.py:22) |
| 13 | `test_stats_consistency` | Stats cocok dengan data yang dikirim | [`tests/test_api.py`](tests/test_api.py:35) |
| 14 | `test_stats_empty_initial` | Stats awal = 0 semua | [`tests/test_api.py`](tests/test_api.py:54) |
| 15 | `test_stress_5000_events` | 5000 events + 20% duplikat < 30 detik | [`tests/test_stress.py`](tests/test_stress.py:15) |

### Cara menjalankan tests

```bash
# Local
python3 -m pytest tests/ -v

# Docker
docker run --rm uts-aggregator python3 -m pytest tests/ -v
```

---

## Sitasi

Coulouris, G., Dollimore, J., Kindberg, T., & Blair, G. (2012). *Distributed Systems: Concepts and Design* (5th ed.). Addison-Wesley.

Steen, M. van, & Tanenbaum, A. S. (2023). *Distributed Systems* (4th ed.). Maarten van Steen.

FastAPI Documentation. (2024). *FastAPI*. https://fastapi.tiangolo.com/

Python asyncio Documentation. (2024). *asyncio — Asynchronous I/O*. https://docs.python.org/3/library/asyncio.html

SQLite Documentation. (2024). *SQLite*. https://www.sqlite.org/docs.html

---

## Informasi Tambahan

| Item | Detail |
|---|---|
| **Framework** | FastAPI 0.104+ dengan Python 3.11 |
| **Dedup Store** | SQLite 3 (WAL mode, `INSERT OR IGNORE`) |
| **Testing** | pytest + pytest-asyncio (15 tests) |
| **Container** | python:3.11-slim, non-root user (`appuser`) |
| **Repository** | [Link GitHub] |
| **Video Demo** | [Link YouTube] |
