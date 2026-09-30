# GOAL: AI Controls Parity, Whisper Tuning & Prompt Template Injection

> **Target**:
> 1. **AI Chunk Size Control**: Menambahkan kontrol UI untuk AI Chunk Size dengan penyesuaian nilai default otomatis per AI backend (`custom`: 40.000, `gemini`: 70.000, `g4f`: 70.000, `local`: 30.000, default: 15.000), serta meneruskannya ke CLI backend (`--chunk-size`).
> 2. **Whisper Performance Tuning**: Menambahkan kontrol UI untuk **Whisper Batch Size** (`--whisper-batch-size`, default: 8) dan **Whisper Chunk Size** (`--whisper-chunk-size`, default: 10) pada seksi Transcription Settings agar user dapat mengoptimalkan throughput VRAM GPU (Tesla T4 / RTX).
> 3. **AI Prompt Template Pre-injection & Reset**: Menginjeksi konten asli dari `prompt.txt` secara otomatis ke dalam editor prompt template saat pertama kali dimuat atau saat ditekan tombol "Reset to Default", dengan tetap memberi kebebasan penuh kepada user untuk mengedit dan menyimpannya.
> 4. **Custom AI API Resilience & Token Guard**: Memasang batas token eksplisit (`max_tokens: 4096`) pada `call_custom_api` dan deteksi error pemotongan reasoning (`finish_reason == "length"`), serta meneruskan argumen prompt & chunk size saat fallback Smart-Clipping.
>
> **Stakeholders**: Orchestrator (milestone & decomposition), Developer (UI components, backend endpoints & pipeline arguments), Reviewer (audit payload validation & memory safety), Nara (QA verification & end-to-end testing).  
> **Status**: READY FOR ORCHESTRATION  

---

## 1. Latar Belakang & Problem Statement

### A. AI Chunk Size & Token Bottleneck
* **Masalah**: Pada WebUI Gradio lama, saat user memilih backend `custom`, Gradio otomatis mengisi `chunk_size = 40000` sehingga transkrip panjang diproses efisien dalam 1-2 panggilan API. Pada WebUI baru (FastAPI + React), kontrol `chunk_size` belum ada di form GeneratorTab, menyebabkan CLI selalu jatuh ke default 15.000 (transkrip dipecah jadi banyak potongan kecil).
* **Solusi**: Sediakan input number "AI Chunk Size" di UI Generator Controls (seksi AI Backend) dengan auto-suggest default sesuai backend terpilih, dan teruskan nilainya ke CLI `--chunk-size`.

### B. Whisper Batch Size & Whisper Chunk Size
* **Masalah**: Backend `JobRunRequest` dan CLI `main_improved.py` sudah mendukung `--whisper-batch-size` dan `--whisper-chunk-size`, namun kontrol tersebut belum diekspos di UI React `GeneratorTab.tsx`. User di Colab tidak dapat menaikkan batch size (misal ke 16 atau 32) untuk mempercepat proses transkripsi WhisperX saat VRAM GPU mencukupi.
* **Solusi**: Tambahkan input tuning Whisper di accordion Transcription Settings:
  * `Whisper Batch Size`: input number (1 - 64, default 8).
  * `Whisper Chunk Size`: input number (5 - 60 detik, default 10).

### C. Prompt Template Kosong & Rusaknya Placeholder
* **Masalah**: State `promptTemplate` di frontend saat ini diinisialisasi dengan string kosong (`''`). Jika user mengisi instruksi kustom pendek (misal: "Buatkan 10 klip viral..."), teks tersebut dikirim mentah sebagai `--prompt-file` tanpa membawa transkrip video atau format JSON karena kehilangan placeholder `{transcript_chunk}` dan `{json_template}`.
* **Solusi**:
  1. Buat endpoint backend `GET /api/v1/system/prompt-template` yang membaca isi file fisik `prompt.txt` dari root project.
  2. Saat komponen `GeneratorTab` dimuat pertama kali (atau jika `prompt_template` belum tersimpan di `localStorage`), frontend otomatis mengambil template default dari endpoint tersebut dan mengisinya ke textarea.
  3. Tombol "Reset to Default" memanggil ulang endpoint ini untuk mengembalikan prompt ke kondisi default `prompt.txt`.

### D. Custom API Limit & Reasoning Model Failure
* **Masalah**: Pemanggilan Custom API di `scripts/create_viral_segments.py` tidak menyertakan parameter `max_tokens`. Gateway pihak ketiga (seperti Sumopod/LiteLLM/vLLM) menerapkan default 1024 token. Pada model reasoning (`deepseek-v4.1-flash:netra` / DeepSeek R1), seluruh 1024 token habis terkuras di fase thinking (`reasoning_content`), sehingga `content` kembali kosong (`null`) dan pipeline gagal tanpa pesan kesalahan yang jelas.
* **Solusi**:
  1. Pasang `max_tokens: 4096` secara default pada payload `call_custom_api`.
  2. Tambahkan pengecekan: jika `finish_reason == "length"` dan `content` kosong, berikan pesan log peringatan informatif bahwa kuota token habis di fase reasoning.
  3. Di `scripts/smart_clipping.py`, pastikan saat fallback ke `create_viral_segments.create()` meneruskan parameter `prompt_file_arg` dan `chunk_size_arg`.

---

## 2. Arsitektur & Alur Data

```
[Frontend: GeneratorTab.tsx]
   │
   ├── 1. Inisialisasi: Fetch GET /api/v1/system/prompt-template (isi default prompt.txt)
   ├── 2. Auto Chunk Size: Ganti backend -> auto-set chunk size (custom=40k, gemini=70k, local=30k)
   ├── 3. Whisper Controls: Batch size (8) & Chunk size (10)
   ▼
[API Request: POST /api/v1/jobs/run]
   │
   ├── payload: {
   │      "chunk_size": 40000,
   │      "whisper_batch_size": 8,
   │      "whisper_chunk_size": 10,
   │      "prompt_template": "You are a World-Class Viral Video Editor...\n{transcript_chunk}...",
   │      ...
   │   }
   ▼
[Backend: webui/backend/schemas/jobs.py -> to_cli_args()]
   │
   ├── CLI Args:
   │      --chunk-size 40000
   │      --whisper-batch-size 8
   │      --whisper-chunk-size 10
   │      --prompt-file /tmp/tmp_prompt_xxxx.txt
   ▼
[Pipeline Execution: main_improved.py & scripts/create_viral_segments.py]
   │
   ├── Transcribe: whisperx with batch_size=8, chunk_size=10
   ├── AI Analysis: create_viral_segments with chunk_size=40000, max_tokens=4096
   └── Subtitle & Cut: output klip viral lengkap
```

---

## 3. Pembagian Tugas Tim (Orchestration Breakdown)

```
[Orchestrator]
      │
      ├──> [Developer]
      │       ├── Task 1: Backend Endpoint GET /api/v1/system/prompt-template
      │       ├── Task 2: Backend Job Schema & CLI Tuning (whisper & chunk args passthrough)
      │       ├── Task 3: Pipeline AI Fix (max_tokens 4096, token truncation warning & smart-clipping fallback args)
      │       ├── Task 4: Frontend Whisper Controls (batch size & chunk size inputs)
      │       ├── Task 5: Frontend Chunk Size Input & Backend Auto-suggest Default
      │       └── Task 6: Frontend Prompt Template Pre-injection & Reset to Default Logic
      │
      ├──> [Reviewer]
      │       └── Task 7: Review Payload Validation, Range Limits, Memory Bounds & Error Handling
      │
      └──> [Nara]
              └── Task 8: QA Verification (Prompt Injection Test, Custom API Token Test & Whisper Settings Test)
```

### Task 1: Backend Endpoint Prompt Template (`@developer`)
* **File**: `webui/backend/api/v1/system.py`
  * Tambahkan endpoint:
    * `GET /api/v1/system/prompt-template`: Membaca isi file `prompt.txt` di root repository dan mengembalikan `{ "template": "..." }`.
    * Fallback jika file `prompt.txt` tidak ditemukan: kembalikan string prompt default sistem.

### Task 2: Backend Schema & Argument Verification (`@developer`)
* **File**: `webui/backend/schemas/jobs.py`
  * Pastikan field `chunk_size`, `whisper_batch_size`, dan `whisper_chunk_size` memiliki validasi integer positif rasional:
    * `chunk_size`: Optional[int] (1000 - 200000)
    * `whisper_batch_size`: Optional[int] (1 - 64)
    * `whisper_chunk_size`: Optional[int] (5 - 60)
  * Pastikan argumen `--chunk-size`, `--whisper-batch-size`, dan `--whisper-chunk-size` selalu diteruskan ke command CLI saat nilainya diatur.

### Task 3: Pipeline AI Robustness Fix (`@developer`)
* **File**: `scripts/create_viral_segments.py`
  * Di `call_custom_api()`:
    * Tambahkan `"max_tokens": 4096` pada payload API chat completion.
    * Periksa jika `finish_reason == "length"` dan `content` kosong/null: cetak peringatan jelas:
      `[WARN] Custom API response was truncated due to token limit (finish_reason=length). Consider using a direct instruct model or increasing token limit.`
* **File**: `scripts/smart_clipping.py`
  * Di `run_smart_clipping_pipeline()`:
    * Saat memanggil fallback `create_viral_segments.create()` (baris ~508), pastikan meneruskan parameter yang konsisten dengan input pengguna: `chunk_size_arg`, `prompt_file_arg`.

### Task 4: Frontend Whisper Controls (`@developer`)
* **File**: `webui/frontend/src/components/GeneratorTab.tsx`
  * Pada accordion/card **Transcription Settings (Whisper)**:
    * Tambahkan input number `Whisper Batch Size` (default: 8, min: 1, max: 64).
    * Tambahkan input number `Whisper Chunk Size` (default: 10, min: 5, max: 60).
    * Pasang hook `usePersistedState` untuk mempertahankan nilai saat berpindah tab.

### Task 5: Frontend Chunk Size Input & Auto-suggest (`@developer`)
* **File**: `webui/frontend/src/components/GeneratorTab.tsx`
  * Pada accordion/card **AI Backend Settings**:
    * Tambahkan input number `AI Chunk Size (characters)` (min: 1000, max: 150000).
    * Pasang listener: saat `aiBackend` berubah:
      * `custom` -> suggest default 40000
      * `gemini` -> suggest default 70000
      * `g4f` -> suggest default 70000
      * `local` -> suggest default 30000
    * Izinkan user mengedit nilai chunk size secara bebas dan simpan ke `localStorage`.

### Task 6: Frontend Prompt Template Pre-injection & Reset (`@developer`)
* **File**: `webui/frontend/src/components/GeneratorTab.tsx`
  * Buat helper API call ke `GET /api/v1/system/prompt-template`.
  * Saat `GeneratorTab` pertama kali di-mount dan `promptTemplate` masih kosong: otomatis isi dengan template default dari server.
  * Pada tombol **Reset to Default**: fetch ulang template default dari server dan timpa state `promptTemplate`.
  * Berikan indikator visual jika template saat ini identik dengan default atau sedang menggunakan versi modifikasi kustom.

### Task 7: Review Code & Security Validation (`@reviewer`)
* Audit bahwa input template tidak memungkinkan arbitrary file write di luar folder temporary.
* Audit batas maksimum dan minimum pada input number `chunk_size` dan `whisper_batch_size` untuk mencegah OOM GPU atau memory crash.
* Verifikasi tidak ada secret/API key yang tersimpan ke dalam file template prompt.

### Task 8: QA Verification & Testing (`@nara`)
* **Test Case 1 (Prompt Pre-injection)**: Buka tab Generator untuk pertama kali (atau setelah clear storage), verifikasi editor prompt template langsung terisi teks utuh `prompt.txt` dengan seluruh placeholder `{transcript_chunk}`, `{json_template}`, dll.
* **Test Case 2 (Prompt Edit & Reset)**: Edit teks prompt template, simpan, reload halaman untuk memastikan persistensi, lalu klik "Reset to Default" dan pastikan template kembali ke teks asli `prompt.txt`.
* **Test Case 3 (AI Chunk Size Auto-suggest)**: Pilih backend `Custom API`, pastikan chunk size terisi 40000. Pilih `Gemini`, pastikan berubah ke 70000. Coba ubah manual ke 50000 dan verifikasi nilainya terkirim di payload `POST /api/v1/jobs/run`.
* **Test Case 4 (Whisper Tuning CLI Passthrough)**: Jalankan job dengan Whisper Batch Size = 16 dan Chunk Size = 20, verifikasi command process memuat `--whisper-batch-size 16 --whisper-chunk-size 20`.
* **Test Case 5 (Custom API Token Limit Test)**: Uji pemanggilan custom API dengan model besar dan verifikasi payload `max_tokens: 4096` terkirim serta error handling berjalan aman jika terjadi truncation.

---

## 4. Kriteria Keberhasilan (Acceptance Criteria)

1. [ ] **Prompt Template Pre-injected**: Textarea AI Prompt Template otomatis terisi teks default `prompt.txt` tanpa mengharuskan user copy-paste manual.
2. [ ] **Prompt Template Reset**: Tombol "Reset to Default" berhasil mengembalikan teks template ke konten asli `prompt.txt` dari server.
3. [ ] **Configurable AI Chunk Size**: Tersedia input Chunk Size di UI yang otomatis menyarankan default cerdas sesuai backend dan nilainya diteruskan ke CLI `--chunk-size`.
4. [ ] **Configurable Whisper Tuning**: Tersedia input Whisper Batch Size dan Chunk Size di UI yang diteruskan ke CLI `--whisper-batch-size` dan `--whisper-chunk-size`.
5. [ ] **State Persistence**: Seluruh nilai pengaturan baru (chunk size, whisper batch/chunk, prompt template) tersimpan di `localStorage` dan tidak reset saat berpindah tab.
6. [ ] **Custom API Resilience**: `call_custom_api` mengirim parameter `max_tokens: 4096` dan menampilkan log peringatan yang jelas jika terjadi pemotongan token pada model reasoning.
7. [ ] **Automated Tests**: Unit test backend (pytest) dan unit test frontend (vitest) lulus 100%.
