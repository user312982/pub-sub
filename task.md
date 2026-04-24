Bangun layanan aggregator berbasis Python (disarankan FastAPI/Flask + asyncio) dengan spesifikasi berikut:

    a. Model Event & API
        Event JSON minimal: { "topic": "string", "event_id": "string-unik", "timestamp": "ISO8601", "source": "string", "payload": { ... } }
        Endpoint POST /publish menerima batch atau single event; validasi skema.
        Consumer (subscriber) memproses event dari internal queue (in-memory) dan melakukan dedup berdasarkan (topic, event_id).
        Endpoint GET /events?topic=... mengembalikan daftar event unik yang telah diproses.
        Endpoint GET /stats menampilkan: received, unique_processed, duplicate_dropped, topics, uptime.

    b. Idempotency & Deduplication
        Implementasikan dedup store yang tahan terhadap restart (contoh: SQLite atau file-based key-value) dan local-only.
        Idempotency: satu event dengan (topic, event_id) yang sama hanya diproses sekali meski diterima berkali-kali.
        Logging yang jelas untuk setiap duplikasi yang terdeteksi.

    c. Reliability & Ordering
        At-least-once delivery: simulasi duplicate delivery di publisher (mengirim beberapa event dengan event_id sama).
        Toleransi crash: setelah restart container, dedup store tetap mencegah reprocessing event yang sama.
        Ordering: jelaskan di laporan apakah total ordering dibutuhkan atau tidak dalam konteks aggregator Anda.

    d. Performa Minimum
        Skala uji: proses >= 5.000 event (dengan >= 20% duplikasi). Sistem harus tetap responsif.

    e. Docker
        Wajib: Dockerfile untuk membangun image yang menjalankan layanan.
        Rekomendasi (Python): base image python:3.11-slim, non-root user, dependency caching via requirements.txt.
        Contoh skeleton Dockerfile (sesuaikan):

        FROM python:3.11-slim
        WORKDIR /app
        RUN adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app
        USER appuser
        COPY requirements.txt ./
        RUN pip install --no-cache-dir -r requirements.txt
        COPY src/ ./src/
        EXPOSE 8080
        CMD ["python", "-m", "src.main"]

    f. Docker Compose (Opsional, +10%)
        Pisahkan publisher dan aggregator dalam dua service, jaringan internal default Compose.
        Tidak boleh menggunakan layanan eksternal publik.

    g. Unit Tests (Wajib, 5–10 tests)
        Gunakan pytest (atau test framework pilihan) dengan cakupan minimum:
            Validasi dedup: kirim duplikat, pastikan hanya sekali diproses.
            Persistensi dedup store: setelah restart (simulasi), dedup tetap efektif.
            Validasi skema event (topic, event_id, timestamp).
            GET /stats dan GET /events konsisten dengan data.
            Stress kecil: masukan batch event, ukur waktu eksekusi (assert dalam batas yang wajar).

Deliverables (GitHub + Laporan)

    Link repository GitHub (public atau akses disediakan) berisi:
        src/ kode aplikasi.
        tests/ unit tests.
        requirements.txt (atau pyproject.toml).
        Dockerfile (wajib), docker-compose.yml (opsional untuk bonus).
        README.md berisi cara build/run, asumsi, dan endpoint.
        report.md atau report.pdf berisi penjelasan desain (hubungkan ke Bab 1–7) dan sitasi.
        Link video demo YouTube publik (5–8 menit) yang mendemonstrasikan sistem.
    Sertakan instruksi run singkat:
        Build: docker build -t uts-aggregator .
        Run: docker run -p 8080:8080 uts-aggregator