# GOAL: AI Hook Title Overlay & Generator Output Preview Relocation

> **Target**: 
> 1. Mengimplementasikan fitur **AI Hook Title Overlay (Stop-the-Scroll Header)**: banner kotak teks tebal di bagian atas video (misal: "RAHASIA CUAN DARI AI?!") yang digenerate otomatis oleh LLM berdasarkan hook transkrip paling memikat untuk memaksimalkan retensi 3 detik pertama penonton.
> 2. Mendesain ulang tata letak **Generator Preview** di WebUI: memindahkan tampilan hasil preview video ke bagian bawah form & console agar area preview lebih luas (full-width), serta memastikan area ini murni hanya menampilkan klip hasil generator tanpa elemen input video.  
>
> **Stakeholders**: Orchestrator (milestone & dispatch), Developer (pipeline backend & layout frontend), Reviewer (audit safe-area & visual parity), Nara (QA visual render & UI responsive test).  
> **Status**: COMPLETED & ARCHIVED  

---

## 1. Latar Belakang & Spesifikasi Kebutuhan

### A. AI Hook Title Overlay (Stop-the-Scroll Header)
Pada format video pendek (TikTok, Instagram Reels, YouTube Shorts), 2-3 detik pertama sangat menentukan apakah audiens akan lanjut menonton atau langsung swipe.
- **Top Header Banner**: Banner teks tebal di atas frame (alignment top-center) dengan background box kontras tinggi (misal: teks kuning/putih dengan box hitam semi-transparan atau solid) yang langsung terbaca seketika.
- **LLM-Driven Hook Title**: Judul bukan sekadar ringkasan topik umum, melainkan kalimat "punchy" (maksimal 4-7 kata, huruf kapital/bold, memicu rasa penasaran/FOMO) yang diekstraksi dan dirangkum oleh model AI dari transkrip segmen viral.
- **Burn-in Rendering**: Terintegrasi ke pipeline subtitle ASS (`scripts/adjust_subtitles.py`) atau FFmpeg filter (`scripts/burn_subtitles.py`) sehingga permanen melekat pada klip final, namun tetap dapat diedit di Subtitle Editor sebelum di-burn.

### B. Relokasi & Isolasi Generator Output Preview
Saat ini di `webui/frontend/src/components/GeneratorTab.tsx`, panel "Generated Clips & Output Preview" berada di kolom kanan (`lg:col-span-6`) tepat di bawah Execution Log Stream.
- **Keterbatasan Layout Lama**: Area preview sempit, rasio 9:16 tertekan tinggi vertikal log, dan user harus bolak-balik scroll ke bawah log untuk melihat klip.
- **Target Desain Baru**:
  1. Pindahkan seluruh seksi hasil generator ke bawah grid utama (full-width span 12).
  2. Berikan tata letak grid dan player yang lapang (side-by-side player 9:16 dan list klip).
  3. **Isolasi Hasil**: Hanya menampilkan klip video yang dihasilkan oleh pipeline generator. Menghilangkan segala komponen preview input video atau form file input dari seksi ini.

---

## 2. Arsitektur Teknis & Perubahan Modul

```
[LLM Transcript Analysis: scripts/create_viral_segments.py]
      │  ✨ Prompt menghasilkan field "hook_title" (punchy, uppercase, 4-7 kata)
      ▼
[Segment Metadata: final/XXX_timeline.json]
      │  Simpan hook_title per segmen bersama start/end timestamps
      ▼
[ASS Subtitle Styler: scripts/adjust_subtitles.py]
      │  Tambahkan Style 'HookHeader' (Alignment=8, BorderStyle=3, MarginV=35)
      │  Inject Dialogue event statis dari t=0.0s hingga t=clip_duration
      ▼
[FFmpeg Burning: scripts/burn_subtitles.py]
      │  Bake subtitle + hook header langsung ke klip 9:16
      ▼
[WebUI GeneratorTab: webui/frontend/src/components/GeneratorTab.tsx]
      │  1. Kontrol Hook Header (Toggle On/Off, font size, banner style)
      │  2. Preview Section dipindah ke bawah grid controls & logs (Full Width)
      │  3. Murni isolated output player (tanpa input video preview)
```

### 1. Backend: Prompting & Segment Schema
* **File**: `prompt.txt`, `scripts/create_viral_segments.py`
  * Tambahkan instruksi khusus pada prompt LLM:
    * `hook_title`: "High-converting, curiosity-inducing hook headline in ALL CAPS (4-7 words, e.g., 'RAHASIA CUAN DARI AI?!', 'JANGAN LAKUKAN HAL INI!')."
  * Pastikan fallback parser di `create_viral_segments.py` mengembalikan field `hook_title` (fallback ke `title` jika LLM tidak menyediakan).

### 2. Subtitle Engine: ASS Header Styler
* **File**: `scripts/adjust_subtitles.py`
  * Definisi V4+ Style baru: `Style: HookHeader`
    * `Alignment`: 8 (Top Center)
    * `BorderStyle`: 3 (Opaque bounding box)
    * `Fontsize`: 20-24 (sesuai PlayRes 360x640)
    * `MarginV`: 35-45 (berada di bawah status bar smartphone, di atas konten video utama)
    * `PrimaryColour`: Kuning (`&H0000FFFF`) atau Putih (`&H00FFFFFF`)
    * `BackColour`: Hitam pekat (`&H00000000`) atau semi-transparan (`&H80000000`)
  * Inject event ASS sepanjang durasi klip untuk menampilkan `hook_title`.

### 3. Backend Job Schema & CLI Arguments
* **File**: `webui/backend/schemas/jobs.py` & `main_improved.py`
  * Parameter baru: `--enable_hook_header` (boolean, default: True)
  * Parameter styling opsional: `--hook_header_style` (misal: "yellow_box", "white_box", "neon")

### 4. Frontend: GeneratorTab Layout Reorganization
* **File**: `webui/frontend/src/components/GeneratorTab.tsx`
  * Ubah grid layout:
    * Baris Atas (2 Kolom): Generator Controls (`lg:col-span-6`) dan Execution Log Stream (`lg:col-span-6`).
    * Baris Bawah (Full Width / Span 12): "Generated Clips & Output Preview" ditempatkan di bawah.
  * Tampilan Preview Baru:
    * Area pemutar 9:16 lebih besar dan responsif.
    * Grid thumbnail/daftar klip tertata rapi di sebelah kanan atau bawah player.
    * Tidak ada elemen/komponen video input sama sekali di seksi preview ini.
  * Tambahkan opsi "Hook Title Overlay" pada tab/accordion Subtitles di Generator Controls.

---

## 3. Pembagian Tugas Tim (Orchestration Breakdown)

```
[Orchestrator]
      │
      ├──> [Developer]
      │       ├── Task 1: Prompt & LLM Hook Title Extraction (prompt.txt & create_viral_segments.py)
      │       ├── Task 2: ASS Hook Header Styler & Duration Span (adjust_subtitles.py)
      │       ├── Task 3: Backend Schema & CLI Args for Hook Header (schemas/jobs.py & main_improved.py)
      │       ├── Task 4: Frontend GeneratorTab Layout Refactor (Relocate Preview to Bottom Full-Width)
      │       └── Task 5: Frontend Hook Header Controls & Subtitle Editor Support
      │
      ├──> [Reviewer]
      │       └── Task 6: Audit Safe-Area (Header vs TikTok/Reels UI), Code & Subtitle Collision Review
      │
      └──> [Nara]
              └── Task 7: QA Verification (9:16 Render Test, Hook Banner Readability & Responsive UI Test)
```

### Task 1: Prompt & LLM Hook Title Extraction (`@developer`)
* Perbarui `prompt.txt` dan `json_template` di `scripts/create_viral_segments.py`.
* Wajibkan output `hook_title` dengan aturan stop-the-scroll:
  * Singkat (4-7 kata).
  * ALL CAPS, provokatif, memancing rasa ingin tahu.
  * Bahasa sama dengan bahasa transkrip video.
* Simpan `hook_title` ke dalam `timeline.json` dan metadata segmen.

### Task 2: ASS Hook Header Styler (`@developer`)
* Di `scripts/adjust_subtitles.py`:
  * Tambahkan style ASS `HookHeader` dengan `Alignment: 8` dan background box tebal (`BorderStyle: 3`).
  * Tulis Dialogue baris pertama yang memuat teks hook header sepanjang total durasi klip.
  * Berikan konfigurasi margin atas (`MarginV: 35-45`) agar tidak tertutup header TikTok/Reels.

### Task 3: Backend Job Schema & CLI Passthrough (`@developer`)
* Di `webui/backend/schemas/jobs.py`:
  * Tambahkan field `enable_hook_header: bool = True` dan `hook_header_style: str = "yellow_box"`.
  * Teruskan argumen ke `to_cli_args()`.
* Di `main_improved.py`:
  * Terima flag `--enable_hook_header` dan teruskan ke pipeline subtitle.

### Task 4: Frontend Preview Section Relocation & Isolation (`@developer`)
* Di `webui/frontend/src/components/GeneratorTab.tsx`:
  * Pindahkan `Generated Clips & Output Preview` keluar dari kolom kanan `lg:col-span-6`.
  * Tempatkan sebagai container full-width (`w-full mt-6` atau `lg:col-span-12`) di bawah kontrol generator dan execution log stream.
  * Pastikan seksi preview ini murni hanya menampilkan klip hasil generate (`outputClips`, player klip, download/export buttons).
  * Hilangkan atau pastikan tidak ada player input video di area output preview.

### Task 5: Frontend Hook Header Options & Subtitle Editor (`@developer`)
* Di `GeneratorTab.tsx`:
  * Tambahkan toggle switch "AI Hook Title Header" (default checked).
* Di `SubtitleEditor.tsx`:
  * Tampilkan field editable "Hook Title" di panel atas agar user dapat mengubah teks judul sebelum re-burn.

### Task 6: Audit Safe-Area & Collision Review (`@reviewer`)
* Verifikasi posisi header berada di zona aman (TikTok/Instagram Reels Top Safe Zone: ~100-150px dari tepi atas).
* Pastikan style `HookHeader` tidak bertabrakan dengan subtitle dinamis di tengah/bawah layar.
* Audit responsivitas UI layout baru di resolusi desktop (1920x1080), laptop (1366x768), dan tablet/mobile.

### Task 7: QA Verification & Visual Test (`@nara`)
* **Test Case 1 (Hook Title Generation)**: Jalankan generate pada klip sampel, verifikasi LLM menghasilkan judul hook yang menarik dan tersimpan di metadata.
* **Test Case 2 (Video Burn Render)**: Verifikasi video hasil render menampilkan banner kotak tebal di bagian atas dengan font terbaca jelas.
* **Test Case 3 (Layout Generator Preview)**: Buka WebUI, pastikan output preview berada di bagian bawah dengan lebar penuh, tidak terdistorsi, dan tidak memuat input video.
* **Test Case 4 (Toggle Disable)**: Matikan toggle hook header, verifikasi video ter-render bersih tanpa banner atas.

---

## 4. Kriteria Keberhasilan (Acceptance Criteria)

1. [x] **AI Hook Title Generation**: LLM menghasilkan teks hook pendek (4-7 kata, ALL CAPS, memikat) untuk setiap klip viral.
2. [x] **Top Header Overlay Render**: Video output memiliki banner/kotak teks tebal di bagian atas layar dengan kontras tinggi yang jelas terbaca.
3. [x] **Safe-Area Compliance**: Banner tidak terpotong atau tertutup elemen interface platform video pendek (username, status bar, navigation bar).
4. [x] **Preview Relocation**: Seksi preview klip hasil generator berpindah ke bagian bawah form & console, memiliki area tampilan luas (full-width).
5. [x] **Isolated Output Preview**: Seksi preview murni menampilkan klip hasil generator dan aksinya (download, edit, export), bebas dari elemen input video.
6. [x] **Configurable & Editable**: User dapat menyalakan/mematikan banner via toggle di WebUI dan mengedit teks judulnya di Subtitle Editor.
