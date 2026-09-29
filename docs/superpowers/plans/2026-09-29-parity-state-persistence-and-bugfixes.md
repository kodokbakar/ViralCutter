# GOAL: Paritas Penuh Fitur, State Persistence, dan Bugfix WebUI ViralCutter

> **Target**: Menyelesaikan 9 temuan regresi & integrasi pada arsitektur FastAPI + React WebUI di branch `feat/migrate-web`.  
> **Stakeholders**: Orchestrator (dispatch & tracking), Developer (implementasi kode), Reviewer (audit & quality gate), Nara (verifikasi QA E2E & reproduksi).  
> **Status**: READY FOR ORCHESTRATION  

---

## 1. Latar Belakang & Daftar Masalah (9 Temuan Kritis)

1. **State Persistence Antar Tab**: Berpindah tab mereset form input ke default/kosong karena `GeneratorTab` unmount total pada `App.tsx`.
2. **AI Backend Connection Test**: Tidak ada tombol uji koneksi dan status latensi sebelum eksekusi pipeline.
3. **Face Processing Controls**: Pengaturan framing, deteksi wajah, mode fallback, threshold, dan active speaker belum tersedia di UI generator.
4. **Execution Log Stream**: Container log memanjang tanpa batas (unbounded height) dan layout rusak saat streaming log panjang.
5. **Toggle Subtitle Workflow**: Pengguna tidak dapat memilih apakah video akhir ingin dibakar subtitle atau hanya dipotong ("Cut Only").
6. **Bug Subtitle Default & Video Preview**: Subtitle default tidak muncul/terbakar pada video hasil render, serta belum ada fitur visual video preview cuplikan 3 detik dengan teks uji coba (*"The quick brown fox jumps over the lazy dog"*).
7. **Isolasi Colab vs Google Drive**: Folder kerja proyek secara keliru tersimpan di Google Drive (`/content/drive/MyDrive/ViralCutter/VIRALS`), menyebabkan latensi FUSE tinggi dan mengotori Google Drive. Proyek harus terisolasi di disk lokal Colab (`/content/ViralCutter/VIRALS`), dan Google Drive hanya menjadi sumber import video serta tujuan ekspor manual via tombol.
8. **Generated Video Preview di Generator**: Setelah proses selesai, tidak ada pemutar video hasil klip di bagian bawah tab Generator.
9. **Kelengkapan Kontrol Generator**: Durasi min/max, pre-roll/post-roll, segment count, viral mode toggle, prompt template editor, dan kontrol Smart-Clipping belum ada di UI Generator.

---

## 2. Rincian Teknis & Solusi Tiap Item

### Item 1: State Persistence & DOM Retention
* **Frontend (`App.tsx`)**:
  * Ubah render tab dari conditional unmount `{currentTab === 'x' && <Tab />}` menjadi persistence container `<div className={currentTab === 'x' ? 'block' : 'hidden'}><Tab /></div>`.
  * Pertahankan instansiasi DOM, posisi scroll, dan state in-memory saat berpindah tab.
* **Storage Sync (`useLocalStorage`)**:
  * Simpan field sensitif/konfigurasi ke `localStorage`:
    * `ai_backend`, `api_key`, `ai_base_url`, `ai_model_name`, `custom_model_name`
    * `face_mode`, `face_model`, `no_face_mode`
    * `font_name`, `font_size`, `font_color`, `highlight_color`, `outline_color`
  * Form memuat ulang konfigurasi dari `localStorage` saat browser direfresh.

### Item 2: AI Backend Test Connection
* **Backend Endpoint**:
  * `POST /api/v1/system/test-ai`
  * Request Body:
    ```json
    {
      "backend": "gemini | g4f | local | custom",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-...",
      "model_name": "gpt-4o-mini"
    }
    ```
  * Handler: Panggil fungsi `scripts.create_viral_segments.verify_ai_connection`.
  * Response: `{ "success": true, "message": "Connected to gpt-4o-mini! (142ms)", "latency_ms": 142 }`.
* **Frontend (`GeneratorTab.tsx`)**:
  * Tombol **"Test Connection"** dengan status loading spinner di sebelah selector AI backend.
  * Status alert badge: Hijau (Sukses + ms latensi), Merah (Gagal + detail error HTTP/koneksi).

### Item 3: Face Processing Settings Panel
* **Frontend (`GeneratorTab.tsx`)**:
  * Tambahkan card section: **Face & Framing Settings**.
  * Input Kontrol:
    * `face_mode`: Dropdown (`auto`, `1` [Single Speaker], `2` [Split Screen], `none` [Preserve Original]).
    * `face_model`: Dropdown (`insightface`, `mediapipe`).
    * `no_face_mode`: Dropdown (`padding`, `zoom`).
    * `face_preset`: Dropdown (`Default (Balanced)`, `Stable (Focus Main)`, `Sensitive (Catch All)`, `High Precision`).
    * Presets auto-fill: `face_filter_threshold`, `face_two_threshold`, `face_confidence_threshold`, `face_dead_zone`.
    * Collapsible Advanced Active Speaker:
      * Checkbox `focus_active_speaker`
      * Sliders: `active_speaker_mar` (0.01 - 0.10), `active_speaker_score_diff` (0.5 - 3.0), `active_speaker_decay` (0.5 - 5.0).
      * Checkbox `include_motion`, slider `motion_threshold`, `motion_sensitivity`.

### Item 4: Execution Log Stream Container
* **Frontend (`GeneratorTab.tsx`)**:
  * Kontainer log dengan batas ukuran tegas: `h-72 max-h-80 w-full overflow-y-auto font-mono text-xs bg-zinc-950 p-4 rounded-lg border border-zinc-800`.
  * Sticky Header: Status badge job, toggle **Auto-scroll** (ON/OFF), tombol **Copy Logs**, dan tombol **Clear**.
  * Smart Auto-scroll: Hanya scroll otomatis ke bawah jika scrollbar user berada di posisi paling bawah (`scrollHeight - scrollTop <= clientHeight + 50`). Jika user scroll ke atas untuk investigasi, jangan paksa scroll.

### Item 5: Toggle Subtitle Processing & Custom Styling Flag
* **Frontend (`GeneratorTab.tsx`)**:
  * Tambahkan toggle switch: **Burn Subtitles** (default: `true`).
  * Jika dinonaktifkan (`false`), kirim payload `workflow = "2"` ("Cut Only") ke API `/api/v1/jobs/run`.
  * Tambahkan checkbox: **Use Custom Subtitles** (default: `false` / ikuti konfigurasi tab Subtitles).
  * Jika aktif, sertakan payload `subtitle_config` lengkap yang diambil dari state Subtitles/localStorage.

### Item 6: Perbaikan Subtitle Default & Fitur Subtitle Video Preview
* **Akar Masalah Bug Subtitle**:
  1. `main_improved.py`: `outline_transparency = "FF"` membuat garis tepi 100% transparan (hilang). Nilai harus `"00"` (opaque).
  2. `main_improved.py`: `border_style = 2` tidak valid pada format standar ASS (hanya 1 untuk outline/shadow, 3 untuk box). Nilai default harus `1`.
  3. `scripts/adjust_subtitles.py`: Jika segment Whisper tidak memiliki kata terpisah (`words: []`), ASS menghasilkan 0 baris dialog. Wajib ada fallback menggunakan `segment['text']` dengan durasi segmen.
* **Fitur Subtitle Video Preview**:
  * Backend Endpoint: `POST /api/v1/preview/subtitle-video`
    * Request Body:
      ```json
      {
        "video_path": "/path/to/video.mp4",
        "subtitle_config": { ... },
        "sample_text": "The quick brown fox jumps over the lazy dog",
        "timestamp": 3.0,
        "duration": 3.0
      }
      ```
    * Eksekusi: Potong 3 detik video via FFmpeg, buat file `.ass` sementara berisi teks sampel, bakar subtitle menggunakan `libx264 ultrafast`, simpan ke `webui/PREVIEW/sub_preview_<hash>.mp4`.
    * Response: `{ "preview_url": "/api/v1/preview/stream?path=...", "file_path": "..." }`.
  * Frontend (`SubtitlesTab.tsx`):
    * Tombol **"Preview on Video"** di atas visual canvas.
    * Tampilkan video player 9:16 yang memutar looping klip 3 detik dengan rendering subtitle aktual.

### Item 7: Isolasi Runtime Colab & Export ke Google Drive
* **Isolasi Folder Kerja**:
  * `ViralCutter.ipynb`: Kembalikan `VIRALCUTTER_OUTPUT_DIR` ke disk lokal Colab `/content/ViralCutter/VIRALS`.
  * `/content/drive/MyDrive` murni berfungsi sebagai sumber pembacaan file input video.
* **Tombol Ekspor ke Google Drive**:
  * Pada `GeneratorTab.tsx` (setelah proses selesai) dan `LibraryTab.tsx`:
    * Tambahkan tombol **"Export to Google Drive"**.
    * Memanggil endpoint `POST /api/v1/gdrive/export`:
      ```json
      {
        "project_name": "project_123",
        "destination_folder": "/content/drive/MyDrive/ViralCutter_Exports"
      }
      ```
    * Menyalin artefak video hasil / file ZIP ke Google Drive dengan progress feedback.

### Item 8: Video Preview Card di GeneratorTab
* **Frontend (`GeneratorTab.tsx`)**:
  * Tambahkan section: **Generated Clips & Output Preview** di bawah Log Console.
  * Trigger: Saat status job `completed`, fetch daftar aset video dari `/api/v1/library/projects/{projectName}`.
  * Tampilkan:
    * Grid cuplikan video hasil (rasio 9:16).
    * HTML5 Video player dengan tombol fullscreen.
    * Tombol **Download MP4**.
    * Tombol **Open in Subtitle Editor**.
    * Tombol **Export to Google Drive**.

### Item 9: Paritas Kontrol Generator Lengkap
* **Parameter Segmentasi & Durasi**:
  * `segments`: Number input (default 3, min 1, max 20).
  * `viral`: Toggle switch (default true).
  * `themes`: Text input (aktif jika `viral` false).
  * `min_duration`: Number input (detik, default 15).
  * `max_duration`: Number input (detik, default 90).
  * `pre_roll`: Number input (detik, default 1.25).
  * `post_roll`: Number input (detik, default 0.75).
* **Smart-Clipping Controls**:
  * Toggle: **Automated Smart-Clipping** (`smart_clipping`).
  * Dropdown: `smart_clipping_mode` (`splice` [Hook + Core + Payoff] vs `continuous` [Single Topic]).
  * Number: `smart_snap_margin` (detik, default 0.05).
  * Toggle: **Remove Dead Air** (`smart_remove_dead_air`).
  * Number: `smart_silence_threshold` (detik, default 0.6).
* **AI Prompt Template Editor**:
  * Collapsible card: **AI Prompt Template**.
  * Textarea dengan tombol **Reset to Default** dan **Save Template**.
  * Kirim nilai teks prompt ke backend melalui field `prompt_template` pada `JobRunRequest`.

---

## 3. Rencana Pembagian Tugas Agen (Orchestration Plan)

```
[Orchestrator]
      │
      ├──> [Developer]
      │       ├── Task 1: Backend fixes & endpoints (Test AI, Subtitle Preview Video, Adjust Subtitles Fallback, Default ASS fix)
      │       ├── Task 2: Colab isolation & GDrive export logic
      │       └── Task 3: Frontend state persistence, controls parity, video preview card, log container
      │
      ├──> [Reviewer]
      │       ├── Task 4: Code review (Diff quality, security validation, type safety, regression check)
      │
      └──> [Nara]
              ├── Task 5: QA Verification (Automated test suites, API endpoint tests, UI E2E, mock runs)
```

### Task 1: Backend Fixes & Endpoint Extensions (`@developer`)
1. **File**: `main_improved.py`
   * Perbaiki default `outline_transparency` dari `"FF"` menjadi `"00"`.
   * Perbaiki `border_style` dari `2` menjadi `1`.
2. **File**: `scripts/adjust_subtitles.py`
   * Tambahkan fallback jika `segment.get('words')` kosong agar dialog tetap terbuat dari `segment['text']` dengan start dan end time segmen.
3. **File**: `webui/backend/api/v1/system.py`
   * Tambahkan endpoint `POST /api/v1/system/test-ai` yang memanggil `verify_ai_connection`.
4. **File**: `webui/backend/api/v1/preview.py`
   * Tambahkan endpoint `POST /api/v1/preview/subtitle-video` untuk cuplikan preview 3 detik dengan teks uji coba.
5. **File**: `webui/backend/schemas/system.py` & `schemas/preview.py`
   * Tambahkan Pydantic models yang sesuai untuk request dan response baru.

### Task 2: Colab Notebook & Runtime Isolation (`@developer`)
1. **File**: `ViralCutter.ipynb`
   * Set `VIRALCUTTER_OUTPUT_DIR` default ke direktori lokal Colab (`/content/ViralCutter/VIRALS` atau `./VIRALS`).
   * Pastikan folder Google Drive tidak menjadi working directory output, melainkan hanya di-mount untuk input video dan ekspor akhir.

### Task 3: Frontend State, UI Parity & Player Integration (`@developer`)
1. **File**: `webui/frontend/src/App.tsx`
   * Render semua tab secara persistent dengan toggle container class CSS `block` vs `hidden`.
2. **File**: `webui/frontend/src/components/GeneratorTab.tsx`
   * Tambahkan persistensi `localStorage` untuk form state generator.
   * Tambahkan panel kontrol Face & Framing lengkap.
   * Tambahkan kontrol durasi, segmentasi, smart-clipping, dan prompt template editor.
   * Tambahkan tombol "Test Connection" untuk AI Backend.
   * Tambahkan toggle "Burn Subtitles" (`workflow`).
   * Rapikan Execution Log Stream dengan kontainer fixed-height (`h-72 max-h-80`) dan smart auto-scroll.
   * Tambahkan section "Generated Clips & Results Preview" dengan pemutar video dan tombol "Export to Google Drive".
3. **File**: `webui/frontend/src/components/SubtitlesTab.tsx`
   * Tambahkan tombol "Preview Subtitles on Video" yang memanggil endpoint `subtitle-video`.
   * Tampilkan pemutar video preview cuplikan 3 detik 9:16.
4. **File**: `webui/frontend/src/api/client.ts` & `src/api/types.ts`
   * Tambahkan method client untuk `testAiConnection` dan `getSubtitleVideoPreview`.

### Task 4: Audit & Security Review (`@reviewer`)
1. Pastikan tidak ada path traversal vulnerability pada endpoint preview video dan ekspor GDrive.
2. Periksa kompatibilitas backward CLI args pada `main_improved.py`.
3. Verifikasi konsistensi type TypeScript dan validasi schema Pydantic.
4. Pastikan tidak ada memory leak pada SSE event listeners dan video preview objects.

### Task 5: QA Testing & Verifikasi Hasil (`@nara`)
1. **API Integration Tests**:
   * Test `POST /api/v1/system/test-ai` dengan mock dan provider aktif.
   * Test `POST /api/v1/preview/subtitle-video` memastikan file video 3 detik berhasil di-generate dan stream HTTP 206 berfungsi.
   * Test `POST /api/v1/jobs/run` dengan flag `workflow="2"` memastikan subtitle burning di-skip.
2. **Subtitle Burning Test**:
   * Jalankan pembuatan ASS subtitle dengan konfigurasi default dan pastikan baris dialog serta style outline valid (tidak transparan).
3. **Frontend UI Tests**:
   * Verifikasi tab switching tidak menghilangkan input yang sudah diisi.
   * Verifikasi log console memiliki scroll bar tetap dan tidak memanjang ke bawah.
   * Verifikasi preview video muncul setelah job status `completed`.

---

## 4. Kriteria Keberhasilan (Acceptance Criteria)

1. [ ] **State Preservation**: Input teks, dropdown, dan slider pada tab Generator tidak hilang ketika berpindah ke Subtitles/Library lalu kembali lagi, serta bertahan setelah page refresh.
2. [ ] **AI Connection Check**: Tombol "Test Connection" menampilkan latensi waktu respons dalam milidetik atau pesan error yang akurat.
3. [ ] **Full Face Controls**: Pengguna dapat memilih model wajah, mode auto/1/2/none, mode fallback padding/zoom, serta threshold presets langsung dari UI.
4. [ ] **Stable Log UI**: Execution Log Stream memiliki tinggi tetap (`h-72 max-h-80`), scrollable, dan tidak merusak layout saat menerima ratusan baris log.
5. [ ] **Selective Subtitles**: Pengguna dapat mematikan subtitle sebelum generate, dan pipeline video berjalan tanpa tahap pembakaran subtitle.
6. [ ] **Rendered Subtitle Visible**: Subtitle yang dibakar dengan setting default terlihat jelas pada video output (outline hitam solid, font jelas), dan tombol "Preview on Video" di SubtitlesTab memutar video sampel 3 detik yang valid.
7. [ ] **Colab Isolation**: Video hasil dan file temporary tersimpan di disk lokal Colab; Google Drive hanya bertambah file jika tombol "Export to Google Drive" ditekan.
8. [ ] **Immediate Output Preview**: Video klip hasil pemrosesan langsung dapat diputar dan diunduh di bagian bawah tab Generator saat proses selesai.
9. [ ] **Complete Parameter Controls**: Durasi, segmen, smart-clipping, dan prompt template dapat diatur langsung di antarmuka tanpa menyentuh CLI.
