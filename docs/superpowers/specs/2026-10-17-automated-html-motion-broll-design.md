# Automated HTML Motion B-Roll Design Specification

## Overview
Fitur **Automated HTML Motion B-Roll** (Hyperframes-style) menyisipkan animasi motion graphic modern (seperti counter statistik, kartu kutipan pembicara, dan daftar poin argumen) secara kontekstual di atas video podcast 9:16. Animasi dibuat menggunakan template HTML/CSS/JS mandiri berlatar belakang transparan, dirender secara deterministik frame-by-frame via headless Chromium (Playwright) tanpa membebani GPU/VRAM Colab, kemudian di-overlay menggunakan FFmpeg sebelum proses burning subtitle.

---

## 1. Arsitektur Komponen

```
[ Transcript with Timestamps ]
             │
             ▼
[ LLM Extraction Pipeline ] ──► Deteksi Momen Kunci (Statistik, Kutipan, Poin)
             │                 menghasilkan broll_items metadata
             ▼
[ HTML Template Engine ]   ──► Jinja2 / String Param Injection (1080x1920, transparent)
             │                 (stat_counter.html, quote_card.html, point_highlight.html)
             ▼
[ Headless Playwright Renderer ] ──► Evaluasi window.renderSeek(progress) per frame (30 FPS)
             │                     Pipe PNG frames via stdin ke FFmpeg (CPU-only)
             ▼
[ Transparent WebM Assets ] ──► Codec libvpx-vp9, pix_fmt yuva420p
             │
             ▼
[ FFmpeg Video Overlay ] ──► Layer 0: Video 9:16
                             Layer 1: B-Roll WebM (enable='between(...)')
                             Layer 2: Watermark Branding
                             Layer 3: ASS Subtitles
```

---

## 2. Kontrak Data (Metadata Schema)

### 2.1 Skema B-Roll per Klip
Metadata B-Roll disematkan di dalam masing-masing item klip pada `viral_segments`:
```json
{
  "title": "Rahasia Retensi Video Pendek",
  "start_time": 10.0,
  "end_time": 45.0,
  "duration": 35.0,
  "score": 94,
  "broll_items": [
    {
      "start_offset": 3.0,
      "duration": 3.5,
      "template_id": "stat_counter",
      "data": {
        "target_number": "87",
        "suffix": "%",
        "prefix": "+",
        "label": "Lonjakan Retensi 3 Detik Pertama",
        "accent_color": "#FF3B30"
      }
    },
    {
      "start_offset": 18.0,
      "duration": 4.0,
      "template_id": "quote_card",
      "data": {
        "quote": "Bila pembukaan video tidak memikat dalam 2 detik, penonton pergi selamanya.",
        "author": "Dr. Sarah Adams",
        "title": "Media Psychologist"
      }
    }
  ]
}
```

### 2.2 Template Catalog & Parameter Schema
1. **`stat_counter`**:
   - `target_number` (string/number): Angka tujuan animasi counter.
   - `prefix` (string): Karakter awalan opsional (misal: `$`, `+`).
   - `suffix` (string): Karakter akhiran opsional (misal: `%`, `M`, `X`).
   - `label` (string): Teks deskriptif di bawah angka.
   - `accent_color` (string hex): Warna aksen angka.
2. **`quote_card`**:
   - `quote` (string): Pernyataan / punchline penting.
   - `author` (string): Nama pembicara atau narasumber.
   - `title` (string): Peran / gelar / konteks pembicara.
3. **`point_highlight`**:
   - `headline` (string): Judul kartu ringkasan.
   - `points` (array of strings): 2 hingga 3 butir poin kunci yang muncul bergantian (*staggered pop-in*).

---

## 3. HTML Template Engine (`scripts/broll_templates/`)

Setiap template dibuat sebagai dokumen HTML5 mandiri:
- **Ukuran Kanvas:** Viewport tetap 1080 x 1920 px.
- **Background:** `background: transparent;` pada `<html>` dan `<body>`.
- **Desain & Gaya:** Tipografi bold modern (Inter / Roboto / System sans-serif), drop shadow tajam untuk kontras di atas video apapun, glassmorphism gelap bergradien lembut (`background: rgba(18, 18, 18, 0.75)` dengan border tipis `rgba(255, 255, 255, 0.1)`).
- **Kontrak Animasi Deterministik:**
  Template tidak menggunakan `setInterval` atau `requestAnimationFrame` otomatis untuk animasi render. Template mengekspos fungsi sinkron:
  ```javascript
  window.renderSeek = function(progress) {
    // progress: float antara 0.0 s/d 1.0
    // Menghitung status animasi elemen secara matematis (misal cubic bezier easing)
  };
  ```
  - `progress` 0.0 – 0.15: Animasi masuk (*slide up / pop-in + opacity 0 to 1*).
  - `progress` 0.15 – 0.85: Tampilan diam stabil (*idle / subtle floating glow*).
  - `progress` 0.85 – 1.0: Animasi keluar (*fade out / slide down*).

---

## 4. Headless Deterministic Renderer (`scripts/broll_renderer.py`)

### 4.1 Spesifikasi Eksekusi
- Modul Python mengeksekusi Playwright Chromium headless dengan flag hemat memori:
  `--disable-gpu`, `--no-sandbox`, `--disable-setuid-sandbox`, `--disable-dev-shm-usage`.
- Viewport diatur tepat `{'width': 1080, 'height': 1920}`.
- Frame rate output: **30 FPS**.
- Total frame dihitung: $\text{total\_frames} = \text{round}(\text{duration} \times 30)$.

### 4.2 Pipeline Pipe ke FFmpeg
Daripada menyimpan ribuan file PNG sementara ke disk (yang memakan I/O SSD di Colab), frame langsung di-stream via pipe stdin:
```python
ffmpeg_cmd = [
    "ffmpeg", "-y", "-loglevel", "error",
    "-f", "image2pipe",
    "-vcodec", "png",
    "-r", "30",
    "-i", "-",
    "-c:v", "libvpx-vp9",
    "-pix_fmt", "yuva420p",
    "-b:v", "2M",
    "-auto-alt-ref", "0",
    output_webm_path
]
```
Untuk setiap frame dari 0 sampai $\text{total\_frames} - 1$:
1. `page.evaluate(f"window.renderSeek({frame / (total_frames - 1)})")`
2. `frame_bytes = page.screenshot(type="png", omit_background=True)`
3. `proc.stdin.write(frame_bytes)`

Hasil akhir berupa file `.webm` dengan alpha channel murni, berdurasi tepat sesuai metadata.

---

## 5. Integrasi FFmpeg & Pipeline Video

### 5.1 Urutan Filter Graph pada `scripts/burn_subtitles.py`
Ketika fitur B-Roll aktif dan klip memiliki item B-Roll:
1. File `.webm` dirender ke direktori proyek sementara (`project_folder/broll_cache/`).
2. Masukkan file WebM sebagai input tambahan pada FFmpeg:
   ```bash
   ffmpeg -y -i input_video.mp4 -i broll_0.webm -i watermark.png \
     -filter_complex "\
       [0:v][1:v]overlay=x=0:y=0:enable='between(t, 3.0, 6.5)':eof_action=pass[with_broll];\
       [with_broll][2:v]overlay=x='main_w-overlay_w-40':y=40:eof_action=pass[watermarked];\
       [watermarked]ass=subtitles.ass[video_out]\
     " \
     -map "[video_out]" -map 0:a? -c:a copy ...
   ```
3. Jika terdapat lebih dari 1 B-roll, rangkaian overlay dirangkai secara bersambung (`[0:v][1:v]overlay...[b1]; [b1][2:v]overlay...[b2]`).

### 5.2 CLI Flag di `main_improved.py`
- Tambahkan argument: `--enable-html-broll` (action: `store_true`, default: `False`).
- Integrasikan eksekusi B-Roll setelah pemotongan video selesai dan sebelum atau saat subtitle diburn.

---

## 6. Frontend WebUI & REST API

### 6.1 Navbar Update (`Navbar.tsx`)
Tambahkan tab `B-Roll` di antara `Watermark` dan `Subtitle Editor`:
- ID: `'broll'`
- Label: `'B-Roll'`
- Icon: Lucide `Sparkles` / `Layers`

### 6.2 Komponen Halaman `BrollTab.tsx`
- **Katalog Template:** Kartu visual untuk masing-masing template (`stat_counter`, `quote_card`, `point_highlight`).
- **Form Kustomisasi Data Uji:** Form input dinamis sesuai skema template terpilih.
- **Tombol Test Render:** Memanggil endpoint backend `/api/v1/broll/preview`, menampilkan progress spinner, dan menampilkan video pratinjau vertikal (9:16 player) loop setelah selesai.
- **Status Integrasi:** Badge informasi kesiapan Playwright Chromium di server.

### 6.3 Kontrol di `GeneratorTab.tsx`
- Tambahkan panel section **Automated Motion B-Roll** (Section 7, tepat setelah Watermark Branding).
- Checkbox persistensi: `enable_html_broll`.
- Tautan navigasi cepat: *"Customize & Preview Templates in B-Roll Tab →"*.

### 6.4 Backend API Endpoint (`webui/backend/api/v1/broll.py`)
- `GET /api/v1/broll/templates`: Daftar metadata template, nama, deskripsi, dan contoh payload JSON.
- `POST /api/v1/broll/preview`: Menerima `{ template_id: str, data: dict, duration: float }`, merender klip pendek via `broll_renderer.py`, menyimpannya di `static/previews/` dan mengembalikan URL video.

---

## 7. Rencana Pengujian (Testing Strategy)

1. **Unit Test Template & Renderer (`tests/test_broll_renderer.py`):**
   - Render klip sintetis 2 detik untuk masing-masing dari 3 template HTML.
   - Validasi bahwa output `.webm` terbentuk, memiliki durasi $\approx 2.0$ detik, dan format piksel mengandung alpha (`yuva420p`).
2. **FFmpeg Overlay Integration Test (`tests/test_broll_overlay.py`):**
   - Overlay video WebM transparan di atas video sintetis 10 detik.
   - Verifikasi durasi video utama tidak terpotong dan audio tetap tersinkronisasi.
3. **Frontend Integration Test (`tabs.test.tsx`):**
   - Verifikasi tab B-Roll muncul di Navbar di posisi yang benar.
   - Verifikasi form render preview dan toggle B-Roll di GeneratorTab berfungsi.
4. **End-to-End CLI Smoke Test:**
   - Eksekusi `main_improved.py --enable-html-broll --skip-prompts` pada video sampel.
