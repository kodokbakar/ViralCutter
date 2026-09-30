# GOAL: Real-Time Stream Log Parity (FastAPI SSE vs Gradio)

> **Target**: Memperbaiki masalah buffering pada Execution Log Stream WebUI ViralCutter sehingga log proses tertulis secara instan baris-demi-baris (real-time) layaknya antarmuka Gradio asli, tanpa menunggu hingga seluruh pekerjaan selesai.  
> **Stakeholders**: Orchestrator (dispatch & milestone tracking), Developer (implementasi engine subprocess & SSE flusher), Reviewer (audit streaming & lock concurrency), Nara (QA verification & latency benchmark).  
> **Status**: READY FOR ORCHESTRATION  

---

## 1. Root Cause Analysis (Mengapa Log Tertahan Sampai Selesai?)

Pada versi Gradio lama (`webui/app.py`), generator function mengeksekusi `subprocess.Popen` di dalam loop lokal dan langsung me-`yield` output setiap `0.2` detik melalui koneksi WebSocket interaktif Gradio.

Pada arsitektur baru (FastAPI + SSE + React), terdapat 5 titik hambatan (bottlenecks) yang menyebabkan log tertahan dalam buffer dan baru muncul sekaligus saat proses selesai:

```
[Python Subprocess: main_improved.py]
      │  ❌ Bottleneck 1: Stdio block-buffering (4KB-8KB) tanpa flag '-u'
      ▼
[JobManager: iter(proc.stdout.readline)]
      │  ❌ Bottleneck 2: Subprocess child prints tanpa explicit flush=True
      ▼
[FastAPI StreamingResponse: job.event_generator()]
      │  ❌ Bottleneck 3: Tidak ada SSE keep-alive/heartbeat ping (idle drop)
      ▼
[Proxy / Cloudflare Tunnel / Uvicorn]
      │  ❌ Bottleneck 4: Response buffering karena header proxy kurang (no-transform)
      ▼
[Browser EventSource & React GeneratorTab]
      │  ❌ Bottleneck 5: requestAnimationFrame terhenti saat tab background/iframe
      ▼
[Execution Log UI Screen]
```

### Rincian 5 Akar Masalah:
1. **Python Subprocess Block-Buffering**:
   * CLI dijalankan melalui `cmd = [python_exec, script_path, ...]` tanpa flag `-u` (`unbuffered`).
   * Saat Python mendeteksi `stdout` diarahkan ke `subprocess.PIPE` (non-TTY), runtime C/Python secara otomatis beralih dari mode *line-buffered* ke *block-buffered* (4.096 hingga 8.192 byte).
   * Sebagian besar log tahapan hanya berukuran puluhan byte, sehingga buffer tidak pernah terisi penuh dan tertahan sampai proses selesai/exit.
2. **Subprocess Script Tanpa Explicit Flush**:
   * Script pembantu seperti `scripts/cut_segments.py`, `scripts/edit_video.py`, dan `scripts/burn_subtitles.py` memanggil `subprocess.run(..., capture_output=True)` yang menelan seluruh stdout FFmpeg sampai command selesai.
3. **Ketiadaan SSE Heartbeat / Active Flush Signal**:
   * Generator `job.event_generator()` hanya yield saat ada item di `self.events`.
   * Pada tahap yang memakan waktu lama (seperti Whisper transcribing ~45s atau model loading), zero event dikirim. Reverse proxy (Cloudflare Tunnel) menganggap stream tidak aktif atau menunda flush chunk TCP.
4. **Header Anti-Buffering Reverse Proxy Kurang Lengkap**:
   * Header `StreamingResponse` saat ini:
     `{"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}`
   * Cloudflare Tunnel dan Nginx proxy memerlukan `Cache-Control: no-cache, no-transform` dan `Content-Encoding: identity` agar tidak menahan paket HTTP chunked transfer.
5. **Frontend Rendering Terblokir oleh `requestAnimationFrame`**:
   * `GeneratorTab.tsx` mengumpulkan log di `logBufferRef.current` dan hanya menampilkannya ke layar lewat `requestAnimationFrame(flushLogs)`.
   * Browser modern (Chrome/Firefox/Edge) **membekukan (freeze/pause)** `requestAnimationFrame` ketika tab berada di latar belakang (background tab), diminimalkan, atau saat user berpindah tab lain. Log baru tertumpah sekaligus ketika tab dibuka kembali.

---

## 2. Rencana Solusi Teknis & Arsitektur

### Solusi 1: Unbuffered Python Execution & Popen Pipe Handling
* **File**: `webui/backend/schemas/jobs.py` & `webui/backend/core/job_manager.py`
* **Implementasi**:
  1. Tambahkan flag `-u` pada saat menyusun argumen Python:
     ```python
     cmd = [python_exec, "-u", script_path]
     ```
  2. Pastikan environment process secara eksplisit mengeset:
     ```python
     env["PYTHONUNBUFFERED"] = "1"
     env["PYTHONIOENCODING"] = "utf-8"
     ```
  3. Konfigurasi `subprocess.Popen`:
     ```python
     proc = subprocess.Popen(
         cmd,
         cwd=work_dir,
         stdout=subprocess.PIPE,
         stderr=subprocess.STDOUT,
         text=True,
         bufsize=1,  # Line-buffered
         universal_newlines=True,
         start_new_session=True,
         env=env,
     )
     ```

### Solusi 2: Non-Blocking FFmpeg & Child Scripts Streaming
* **File**: `scripts/cut_segments.py`, `scripts/edit_video.py`, `scripts/burn_subtitles.py`, `main_improved.py`
* **Implementasi**:
  1. Hilangkan `capture_output=True` pada command-command FFmpeg yang berjalan lama. Gunakan pipe forwarding atau cetak progres langsung dengan `print(..., flush=True)`.
  2. Pastikan setiap `print()` indikator progres di `main_improved.py` menyertakan `flush=True`.

### Solusi 3: HTTP Anti-Buffering Headers & Keep-Alive Heartbeat di FastAPI
* **File**: `webui/backend/api/v1/jobs.py` & `webui/backend/core/job_manager.py`
* **Implementasi**:
  1. Perbarui header response SSE pada `stream_job_logs`:
     ```python
     headers = {
         "Cache-Control": "no-cache, no-transform",
         "Connection": "keep-alive",
         "X-Accel-Buffering": "no",
         "Content-Type": "text/event-stream; charset=utf-8",
     }
     ```
  2. Tambahkan keep-alive ping periodik di dalam `event_generator()`:
     * Jika tidak ada event log baru dalam waktu 1.0 detik, kirim komentar SSE:
       ```python
       yield ": ping\n\n"
       ```
     * Komentar SSE ini tidak memengaruhi parser klien, tetapi memaksa buffer proxy (Cloudflare/Nginx) melakukan TCP flush seketika ke browser.

### Solusi 4: Frontend High-Performance Timer-Based Flusher
* **File**: `webui/frontend/src/components/GeneratorTab.tsx`
* **Implementasi**:
  1. Ganti `requestAnimationFrame` dengan timer adaptif berbasis `setInterval(flushLogs, 100)` atau `setTimeout`.
  2. `setInterval` tetap dijalankan oleh browser di latar belakang (walaupun di-throttle ke interval 1 detik), sehingga log tetap mengalir dan tidak membeku saat user membuka tab lain.
  3. Saat event SSE masuk dari `jobsApi.streamLogs`, jika buffer kosong, langsung masukkan baris pertama ke state untuk respons instan (<16ms).
  4. Pisahkan dependensi `useEffect` SSE stream agar tidak re-mount/disconnect saat prop non-kritis (seperti `fetchCompletedClips` atau `selectedClip`) berubah.

---

## 3. Pembagian Tugas Tim (Orchestration Breakdown)

```
[Orchestrator]
      │
      ├──> [Developer]
      │       ├── Task 1: Backend unbuffered CLI ('-u', PYTHONUNBUFFERED=1, bufsize=1)
      │       ├── Task 2: FastAPI SSE headers (no-transform) & Keep-Alive heartbeat ping (: ping)
      │       ├── Task 3: Script explicit flush verification (main_improved.py & pipeline scripts)
      │       └── Task 4: Frontend streamLogs hook & timer flusher (replace requestAnimationFrame)
      │
      ├──> [Reviewer]
      │       └── Task 5: Code review (memory footprint, SSE connection leak, unbuffered I/O safety)
      │
      └──> [Nara]
              └── Task 6: QA Verification (real-time latency benchmark via curl & browser background test)
```

### Task 1: Backend Unbuffered Subprocess Execution (`@developer`)
* Modifikasi `webui/backend/schemas/jobs.py`:
  * Ubah `to_cli_args()` agar selalu menyisipkan `-u` tepat setelah `python_exec`.
* Modifikasi `webui/backend/core/job_manager.py`:
  * Pastikan `bufsize=1`, `universal_newlines=True`, dan `PYTHONUNBUFFERED="1"`.
  * Verifikasi `proc.stdout.readline` segera memancarkan event `"log"` ke queue `job.events`.

### Task 2: SSE Keep-Alive & Anti-Buffering Headers (`@developer`)
* Modifikasi `webui/backend/api/v1/jobs.py`:
  * Tambahkan header anti-buffering lengkap: `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`.
* Modifikasi `Job.event_generator()` di `job_manager.py`:
  * Catat timestamp aktivitas terakhir. Jika waktu idle > 1.0 detik, yield `: ping\n\n`.

### Task 3: Child Pipeline Explicit Flush (`@developer`)
* Audit script utama (`main_improved.py`, `scripts/cut_segments.py`, `scripts/burn_subtitles.py`):
  * Pastikan print status penting menggunakan `flush=True`.
  * Cegah blocking buffer pada subprocess FFmpeg.

### Task 4: Frontend Background-Resilient Log Ingestion (`@developer`)
* Modifikasi `webui/frontend/src/components/GeneratorTab.tsx`:
  * Hapus `requestAnimationFrame` untuk log buffering.
  * Gunakan timed batcher (`100ms`) atau direct append dengan cap ukuran (misal 1.500 baris).
  * Bersihkan dependensi `useEffect` SSE stream (`trackedJobId` murni).

### Task 5: Audit & Concurrency Review (`@reviewer`)
* Verifikasi tidak ada race condition saat multiple SSE clients terkoneksi ke satu `job_id`.
* Pastikan loop `event_generator` berhenti bersih saat client disconnect tanpa meninggalkan zombie coroutine.
* Pastikan flag `-u` tidak merusak encoding output pada platform Linux / Colab.

### Task 6: QA Streaming Verification & Benchmark (`@nara`)
* **Benchmark 1 (CLI / Curl Test)**:
  * Jalankan endpoint SSE via `curl -N http://localhost:7860/api/v1/jobs/{job_id}/stream`.
  * Verifikasi baris log muncul seketika secara bertahap saat script berjalan, bukan serentak di akhir.
* **Benchmark 2 (Background Tab Test)**:
  * Jalankan job di browser, pindah ke tab lain selama 20 detik, lalu kembali.
  * Verifikasi log sudah terisi sesuai progres waktu berjalan, bukan baru mulai rendering saat tab difokuskan.
* **Benchmark 3 (Cloudflare Tunnel Test)**:
  * Uji koneksi stream melalui tunnel dan pastikan tidak ada chunk delay melebihi 1 detik.

---

## 4. Kriteria Keberhasilan (Acceptance Criteria)

1. [ ] **Instant First Log**: Baris log pertama (`Starting job ...`) muncul di UI dalam waktu < 500ms setelah tombol "Run ViralCutter" ditekan.
2. [ ] **Step-by-Step Streaming**: Setiap tahapan (Download, Transcription, AI Selection, Cutting, Face, Subtitles) memancarkan log secara langsung saat eksekusi berlangsung, persis seperti perilaku di Gradio.
3. [ ] **No End-of-Job Dump**: Log tidak tertahan atau menumpuk untuk dimuntahkan sekaligus di akhir proses.
4. [ ] **Background Tab Continuity**: Log tetap ter-update saat user membuka tab browser lain atau meminimalkan jendela browser.
5. [ ] **Keep-Alive Resilience**: Koneksi SSE tidak timeout/disconnect meskipun proses Whisper atau download video memakan waktu lebih dari 60 detik tanpa output log baru.
