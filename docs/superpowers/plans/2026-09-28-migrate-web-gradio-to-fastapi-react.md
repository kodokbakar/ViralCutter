# Archival Plan: Rewrite WebUI ViralCutter (Gradio ke FastAPI + React)

> **Status**: ARCHIVED / COMPLETED (Phase 1 - Phase 4)  
> **Date**: 2026-09-28  
> **Branch**: `feat/migrate-web`  
> **Original File**: `GOAL.md`  

---

## 1. Executive Summary & Visi Proyek
ViralCutter saat ini menggunakan antarmuka monolitik Gradio (`webui/app.py` ~2450 baris). Rewrite ini memisahkan arsitektur menjadi dua layer independen:
1. **Backend**: FastAPI (Python 3.10+) yang bertugas sebagai API engine, menjalankan pipeline video melalui non-blocking subprocess, menyediakan Server-Sent Events (SSE) untuk streaming log dan progres, mengelola library file, dan diagnostik sistem.
2. **Frontend**: React SPA modern (Vite + TypeScript + Tailwind CSS + Lucide Icons + Shadcn UI patterns) yang responsif, modular, memiliki timeline & segment editor untuk subtitle, dan tersinkronisasi dengan pemutar video.
3. **Colab & Remote First**: Tetap dapat dijalankan secara optimal di Google Colab menggunakan satu port tunggal (7860) dengan tunnel Cloudflare publik tanpa auth, sembari mempertahankan opsi fallback `--legacy-gradio`.

---

## 2. Keputusan Arsitektur & Spesifikasi Kunci

| Aspek | Keputusan Terpilih | Detail Implementasi |
| :--- | :--- | :--- |
| **Backend Framework** | FastAPI + Uvicorn | Routing modular `/api/v1/*`, Pydantic v2 schemas, ASGI streaming. |
| **Real-time Protocol** | Server-Sent Events (SSE) | HTTP text/event-stream (`/api/v1/jobs/{id}/stream`), auto-reconnect browser native. |
| **Frontend Framework** | React 18/19 + Vite + TypeScript | Dibangun di direktori `webui/frontend/`. |
| **Styling & Components** | Tailwind CSS + Lucide Icons + Shadcn UI | Desain gelap modern (Zinc/Slate theme), komponen modular headless. |
| **State & Settings Persistence** | Browser `localStorage` | Simpan API keys, prompt template, preferensi subtitle, preset face mode di client. |
| **Colab Build Strategy** | Opsi B (Build Runtime di Colab) | Source code di-commit ke Git. Setup cell Colab menjalankan `npm install && npm run build`. |
| **Concurrency / Job Lock** | Opsi A (Strict Single-Job Lock) | Mencegah GPU OOM pada Colab T4. Tolak request baru dengan HTTP 409 jika sedang running. |
| **Subtitle Editor UX** | Synchronized Segment Table + Video | Tabel segmen kata/kalimat tersinkronisasi klik dengan seekbar video player 9:16 + Re-burn button. |
| **Video Input Support** | 4-in-1 Hybrid Input | Tab YouTube URL, File Upload (multipart streaming), Google Drive, dan Server Path. |
| **Fallback Mode** | `--legacy-gradio` | Menjalankan launcher `webui/app.py` asli jika ada kebutuhan darurat. |
| **Bahasa UI** | English (default) | Antarmuka bersih, konsisten, standar internasional. |
| **Keamanan / Auth** | Publik Terbuka | Sesuai lingkungan Colab/personal workstation, tanpa proteksi password tambahan. |

---

## 3. Struktur Direktori Proyek

```
ViralCutter/
├── webui/
│   ├── app.py                     # Legacy Gradio launcher (fallback via --legacy-gradio)
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── main.py                # Entrypoint FastAPI, CORS, static mount frontend/dist
│   │   ├── config.py              # Environment vars, folder paths (OUTPUT_DIR, VIRALS, PREVIEWS)
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── job_manager.py     # Subprocess manager, single-job lock, SSE broadcaster
│   │   │   ├── tunnel.py          # Cloudflare tunnel wrapper (cloudflared)
│   │   │   └── doctor.py          # Pemeriksaan GPU VRAM, FFmpeg, CUDA, dependencies
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── jobs.py            # Pydantic schemas parameter generator/cutter
│   │   │   ├── preview.py         # Schema payload preview frame & ASS
│   │   │   ├── library.py         # Schema response daftar project & video
│   │   │   └── subtitles.py       # Schema model segmen subtitle editor
│   │   └── api/
│   │       ├── __init__.py
│   │       └── v1/
│   │           ├── __init__.py
│   │           ├── jobs.py        # POST /run, GET /{id}/stream, POST /{id}/cancel, GET /active
│   │           ├── upload.py      # POST /upload (streaming multipart video)
│   │           ├── preview.py     # POST /preview/frame, POST /preview/subtitle, POST /preview/watermark
│   │           ├── library.py     # GET /projects, GET /video/..., POST /export/...
│   │           ├── subtitles.py   # GET /{project}, PUT /{project}, POST /re-burn
│   │           ├── gdrive.py      # GET /status, GET /files
│   │           └── system.py      # GET /doctor, GET /models, GET /presets
│   └── frontend/
│       ├── package.json
│       ├── vite.config.ts
│       ├── tailwind.config.js
│       ├── tsconfig.json
│       ├── index.html
│       └── src/
│           ├── main.tsx
│           ├── App.tsx
│           ├── components/
│           │   ├── ui/            # Shadcn UI (Button, Input, Card, Tabs, Slider, Dialog, Badge, Table)
│           │   ├── layout/        # Navbar, TabNav, StatusHeader
│           │   ├── tabs/
│           │   │   ├── GeneratorTab.tsx       # Form input video, AI backend, face tracking, smart clipping
│           │   │   ├── SubtitlesTab.tsx       # Styling font, warna, outline, live snippet preview
│           │   │   ├── WatermarkTab.tsx       # Posisi watermark, opasitas, skala, frame preview
│           │   │   ├── SubtitleEditorTab.tsx  # Tabel segmen tersinkronisasi player, edit timestamp & teks
│           │   │   ├── LibraryTab.tsx         # Galeri klip video 9:16, download, ZIP export
│           │   │   ├── GDriveTab.tsx          # Google Drive visual browser & selector
│           │   │   └── DiagnosticsTab.tsx     # Status hardware GPU/CUDA & dependensi
│           │   ├── terminal/
│           │   │   └── LogConsole.tsx         # Console log real-time dengan autoscroll & stage progress
│           │   └── preview/
│           │       └── VideoPreviewCard.tsx   # Canvas simulasi rasio 9:16
│           ├── hooks/
│           │   ├── useSSE.ts                  # EventSource hook dengan auto-reconnect
│           │   ├── useLocalStorage.ts        # Sync form state ke browser localStorage
│           │   └── useJobs.ts                 # API call handler untuk eksekusi & cancel job
│           └── lib/
│               ├── api.ts                     # Fetch client wrapper
│               └── utils.ts                   # Classnames / tailwind-merge helpers
```

---

## 4. Rincian API Endpoints Backend (FastAPI v1)

### 4.1 Job Lifecycle & Real-time Stream
- `POST /api/v1/jobs/run`
  - Validasi body via Pydantic model (`JobRunRequest`).
  - Cek single-job lock: Jika `JobManager.is_running()`, return `409 Conflict` (`"A job is currently in progress"`).
  - Mulai background subprocess mengeksekusi `python scripts/main.py [args]`.
  - Return: `{ "status": "started", "job_id": "job_YYYYMMDD_HHMMSS" }`.
- `GET /api/v1/jobs/{job_id}/stream`
  - Protokol SSE (`text/event-stream`).
  - Stream events:
    - `progress`: `{ "stage": "TRANSCRIPTION", "percent": 40, "elapsed": "00:01:23" }`
    - `log`: `{ "level": "INFO", "timestamp": "14:20:10", "message": "Face tracking segment 1..." }`
    - `complete`: `{ "status": "completed", "output_dir": "output/virals/proj_123" }`
    - `error`: `{ "status": "failed", "error": "Traceback detail..." }`
- `POST /api/v1/jobs/{job_id}/cancel`
  - Mengirim sinyal `SIGTERM` ke process group; jika tidak berhenti dalam 5 detik, kirim `SIGKILL`.
  - Return: `{ "status": "cancelled", "job_id": job_id }`.
- `GET /api/v1/jobs/active`
  - Return status pekerjaan aktif saat ini, durasi berjalan, dan tahapan terkini.

### 4.2 Upload & File Handling
- `POST /api/v1/upload`
  - Menerima file multipart upload dari browser.
  - Streaming tulis ke disk (`output/uploads/{timestamp}_{filename}`) dengan buffer 64KB untuk mencegah lonjakan RAM.
  - Return: `{ "file_path": "/absolute/path/to/uploaded/video.mp4", "filename": "video.mp4" }`.

### 4.3 Interactive Previews
- `POST /api/v1/preview/frame`
  - Ekstraksi 1 frame video 9:16 menggunakan FFmpeg pada detik tertentu.
  - Return URL atau base64 data URI frame.
- `POST /api/v1/preview/subtitle`
  - Membuat format ASS sementara berdasarkan styling (font, color, outline, alignment) dan me-render sampel preview frame atau cuplikan 3 detik.
  - Return URL preview video/gambar.
- `POST /api/v1/preview/watermark`
  - Mengomposisikan logo watermark di atas frame cuplikan video untuk verifikasi posisi & transparansi.

### 4.4 Subtitle Editor API
- `GET /api/v1/subtitles/{project_name}`
  - Membaca file `final-outputXXX_processed.json`.
  - Return struktur data terurai: `[{ "id": 1, "start": 0.0, "end": 2.5, "text": "Kata pertama" }, ...]`.
- `PUT /api/v1/subtitles/{project_name}`
  - Menerima perubahan teks dan timestamp segmen, memvalidasi urutan waktu, dan menyimpan kembali ke file JSON.
- `POST /api/v1/subtitles/re-burn`
  - Menjalankan `scripts/burn_subtitles.py` untuk membakar ulang subtitle ke video tanpa perlu mengulang transkripsi Whisper atau pemotongan AI.

### 4.5 Library & Export
- `GET /api/v1/library/projects`
  - Memindai folder output (`VIRALCUTTER_OUTPUT_DIR` / `output/virals`).
  - Mengembalikan daftar proyek beserta video MP4 yang dihasilkan, thumbnail, dan metadata.
- `GET /api/v1/library/video/{project_name}/{filename}`
  - Menyajikan video MP4 dengan dukungan HTTP `Range` request (`206 Partial Content`) untuk scrubbing lancar di pemutar video HTML5.
- `POST /api/v1/library/export/{project_name}`
  - Menjalankan generator ZIP (`webui/project_export.py`) dan mengembalikan file ZIP untuk diunduh.

### 4.6 Google Drive & Diagnostics
- `GET /api/v1/gdrive/status`
  - Cek ketersediaan mount path Google Drive (`/content/drive/MyDrive`).
- `GET /api/v1/gdrive/files`
  - Memindai file video di Google Drive (ekstensi `.mp4`, `.mov`, `.mkv`, dll.) dengan caching in-memory 60 detik.
- `GET /api/v1/system/doctor`
  - Status runtime: VRAM GPU (NVIDIA CUDA), versi FFmpeg, status library Python.
- `GET /api/v1/system/models`
  - Daftar model Whisper lokal dan opsi backend AI (Gemini, Groq, Ollama, Custom).

---

## 5. Rencana Eksekusi Berfase (Execution Roadmap)

### Fase 1: Backend Foundation & Core Job Engine
- [x] Buat struktur direktori `webui/backend/` (core, schemas, api/v1).
- [x] Implementasikan `webui/backend/core/job_manager.py` (subprocess Popen, buffer log, single-job lock, SSE generator).
- [x] Buat Pydantic schemas `webui/backend/schemas/jobs.py` mencakup seluruh argumen `scripts/main.py`.
- [x] Implementasikan router `webui/backend/api/v1/jobs.py` (`/run`, `/{id}/stream`, `/{id}/cancel`, `/active`).
- [x] Uji coba trigger pipeline video via curl/mock script untuk memastikan SSE streaming log berjalan mulus.

### Fase 2: Implementasi Seluruh Endpoint Fitur Backend
- [x] Buat endpoint streaming upload `webui/backend/api/v1/upload.py`.
- [x] Porting dan refactor modul preview ke `webui/backend/api/v1/preview.py`.
- [x] Porting modul library & video streaming ke `webui/backend/api/v1/library.py`.
- [x] Porting subtitle editor & re-burn handler ke `webui/backend/api/v1/subtitles.py`.
- [x] Porting Google Drive scanner ke `webui/backend/api/v1/gdrive.py`.
- [x] Porting runtime doctor & model lister ke `webui/backend/api/v1/system.py`.

### Fase 3: Frontend Scaffold & Desain Komponen
- [x] Inisialisasi Vite + React + TypeScript di `webui/frontend/`.
- [x] Setup Tailwind CSS, Lucide React, dan instalasi komponen Shadcn UI primitives.
- [x] Bangun layout shell: Navbar atas, tab switcher horizontal, dan collapsible bottom log console.
- [x] Implementasikan `useSSE` hook untuk parsing event stream real-time.
- [x] Implementasikan `useLocalStorage` hook untuk sinkronisasi form state otomatis.

### Fase 4: Implementasi Halaman Frontend & Integrasi
- [x] Bangun `GeneratorTab.tsx`: 4 pilihan input (YouTube, Upload, Drive, Local), AI settings, Face tracking, Smart clipping.
- [x] Bangun `SubtitlesTab.tsx` & `WatermarkTab.tsx`: Kontrol styling dengan visual preview card 9:16.
- [x] Bangun `SubtitleEditorTab.tsx`: Tabel segmen tersinkronisasi pemutar video, tombol Split/Merge/Delete, dan trigger Re-burn.
- [x] Bangun `LibraryTab.tsx`: Grid hasil klip, pemutar video popup, tombol download, dan tombol Export ZIP.
- [x] Bangun `GDriveTab.tsx` (file explorer) dan `DiagnosticsTab.tsx` (status sistem).
- [x] Hubungkan tombol "Run ViralCutter" dengan validasi input, status busy lock, dan autoscroll log console.

### Fase 5: Integrasi Colab, Tunneling & Pengujian Menyeluruh
- [ ] Konfigurasi FastAPI untuk menyajikan file statis `webui/frontend/dist` pada root path `/`.
- [ ] Integrasikan `cloudflared` tunnel otomatis pada startup FastAPI saat flag `--colab` atau `--tunnel cloudflare` diaktifkan.
- [ ] Tambahkan flag `--legacy-gradio` pada entrypoint CLI agar user tetap dapat menjalankan Gradio lama jika diperlukan.
- [ ] Perbarui cell setup pada `ViralCutter.ipynb` untuk menjalankan `npm install && npm run build` dan mengeksekusi FastAPI server.
- [ ] Jalankan pengujian menyeluruh (E2E testing) dari submit video YouTube -> pemrosesan SSE -> editing subtitle -> download hasil video.

---

## 6. Kriteria Keberhasilan (Acceptance Criteria)
1. **Zero Feature Regression**: Seluruh kapabilitas pada Gradio lama (transkripsi, AI selection, face tracking, custom font ASS, watermark, editor subtitle, library, export ZIP) berfungsi sempurna di antarmuka baru.
2. **Real-time Log & Progress**: Log terminal dan persentase proses mengalir lancar via SSE tanpa jeda atau memory leak di browser.
3. **Pencegahan GPU Crash**: Sistem strict lock menolak pekerjaan baru dengan pesan informatif jika GPU sedang memproses video lain.
4. **Colab Operational**: Notebook `ViralCutter.ipynb` berhasil melakukan build frontend dan menyajikan WebUI melalui Cloudflare Tunnel pada port 7860.
5. **Transisi Aman**: Pengguna dapat beralih ke Gradio lama kapan saja melalui flag `--legacy-gradio`.
