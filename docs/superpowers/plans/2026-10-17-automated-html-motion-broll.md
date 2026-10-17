# Automated HTML Motion B-Roll Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and integrate an automated contextual HTML motion graphic B-Roll generator (Hyperframes-style) into ViralCutter using Playwright headless Chromium, transparent WebM VP9 rendering, FFmpeg alpha overlay, and React WebUI tab.

**Architecture:** Momen kunci (statistik, kutipan, poin argumen) diekstrak oleh LLM ke dalam metadata `broll_items`. Template HTML/CSS/JS mandiri (1080x1920, transparan) di-inject data lalu dirender secara deterministik frame-by-frame (30 FPS) oleh Playwright Chromium (CPU-only) dan di-pipe ke FFmpeg menjadi file `.webm` (`libvpx-vp9`, `yuva420p`). Video WebM transparan kemudian di-overlay di atas video 9:16 menggunakan filter `overlay` FFmpeg sebelum burning subtitle.

**Tech Stack:** Python 3.10+, Playwright, FFmpeg (`libvpx-vp9`), React, TypeScript, Tailwind CSS, Vite.

**Spec:** `docs/superpowers/specs/2026-10-17-automated-html-motion-broll-design.md`

## Global Constraints
- Canvas resolusi: 1080x1920 (9:16 vertikal), `background: transparent`.
- Codec video B-roll transparan: `libvpx-vp9`, pixel format `yuva420p`, container `.webm`.
- Rendering harus CPU-only (tidak membebani VRAM GPU Colab).
- Animasi harus deterministik via sinkronisasi `window.renderSeek(progress)` ($0.0 \dots 1.0$).
- Urutan visual layer: Video Dasar (Layer 0) -> B-Roll WebM (Layer 1) -> Watermark (Layer 2) -> ASS Subtitles (Layer 3).
- Branch kerja: `feat/html-motion-broll`.

---

### Task 1: HTML Templates & Template Engine

**Files:**
- Create: `scripts/broll_templates/stat_counter.html`
- Create: `scripts/broll_templates/quote_card.html`
- Create: `scripts/broll_templates/point_highlight.html`
- Create: `scripts/broll_engine.py`
- Test: `tests/test_broll_templates.py`

**Interfaces:**
- Produces:
  - `broll_engine.get_template_path(template_id: str) -> str`
  - `broll_engine.render_html_content(template_id: str, data: dict) -> str`
  - `broll_engine.list_templates() -> List[Dict[str, Any]]`

- [ ] **Step 1: Write failing test for template loading and content injection**

```python
# tests/test_broll_templates.py
import pytest
from scripts import broll_engine

def test_list_templates_returns_catalog():
    templates = broll_engine.list_templates()
    ids = [t["id"] for t in templates]
    assert "stat_counter" in ids
    assert "quote_card" in ids
    assert "point_highlight" in ids

def test_render_stat_counter_html():
    data = {
        "target_number": "87",
        "prefix": "+",
        "suffix": "%",
        "label": "Tingkat Retensi",
        "accent_color": "#FF3B30"
    }
    html = broll_engine.render_html_content("stat_counter", data)
    assert "87" in html
    assert "Tingkat Retensi" in html
    assert "window.renderSeek" in html
    assert "background: transparent" in html or "background:transparent" in html

def test_render_quote_card_html():
    data = {
        "quote": "Konten hebat butuh hook cepat",
        "author": "Budi Santoso",
        "title": "Kreator Konten"
    }
    html = broll_engine.render_html_content("quote_card", data)
    assert "Konten hebat butuh hook cepat" in html
    assert "Budi Santoso" in html
    assert "window.renderSeek" in html

def test_render_point_highlight_html():
    data = {
        "headline": "3 Kunci Viral",
        "points": ["Hook 3 detik", "Pacing dinamis", "Punchline jelas"]
    }
    html = broll_engine.render_html_content("point_highlight", data)
    assert "3 Kunci Viral" in html
    assert "Hook 3 detik" in html
    assert "window.renderSeek" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_broll_templates.py -v`
Expected: FAIL with ModuleNotFoundError or FileNotFoundError.

- [ ] **Step 3: Create template files and broll_engine.py**

Create `scripts/broll_templates/stat_counter.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    width: 1080px; height: 1920px;
    background: transparent;
    overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  .container {
    width: 100%; height: 100%;
    display: flex; align-items: center; justify-content: center;
    padding: 80px;
  }
  .card {
    background: rgba(18, 18, 20, 0.88);
    border: 2px solid rgba(255, 255, 255, 0.12);
    border-radius: 40px;
    padding: 60px 80px;
    text-align: center;
    box-shadow: 0 30px 60px rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(20px);
    max-width: 900px;
    transform-origin: center center;
    opacity: 0;
    transform: translateY(60px) scale(0.92);
  }
  .number-box {
    font-size: 130px;
    font-weight: 900;
    line-height: 1.1;
    color: {{ACCENT_COLOR}};
    text-shadow: 0 4px 24px rgba(0,0,0,0.6);
    letter-spacing: -2px;
  }
  .label {
    font-size: 38px;
    font-weight: 700;
    color: #F3F4F6;
    margin-top: 24px;
    line-height: 1.3;
    text-shadow: 0 2px 10px rgba(0,0,0,0.8);
  }
</style>
</head>
<body>
<div class="container">
  <div class="card" id="card">
    <div class="number-box" id="number">{{PREFIX}}0{{SUFFIX}}</div>
    <div class="label">{{LABEL}}</div>
  </div>
</div>
<script>
  const targetNum = parseFloat("{{TARGET_NUMBER}}") || 0;
  const prefix = "{{PREFIX}}";
  const suffix = "{{SUFFIX}}";
  const card = document.getElementById('card');
  const numEl = document.getElementById('number');

  function easeOutCubic(x) { return 1 - Math.pow(1 - x, 3); }
  function easeInCubic(x) { return x * x * x; }

  window.renderSeek = function(progress) {
    progress = Math.max(0, Math.min(1, progress));
    if (progress < 0.18) {
      const p = easeOutCubic(progress / 0.18);
      card.style.opacity = p;
      card.style.transform = `translateY(${60 * (1 - p)}px) scale(${0.92 + 0.08 * p})`;
      const current = Math.round(targetNum * p);
      numEl.textContent = `${prefix}${current}${suffix}`;
    } else if (progress <= 0.82) {
      card.style.opacity = 1;
      card.style.transform = 'translateY(0) scale(1)';
      numEl.textContent = `${prefix}${targetNum}${suffix}`;
    } else {
      const p = easeInCubic((progress - 0.82) / 0.18);
      card.style.opacity = 1 - p;
      card.style.transform = `translateY(${-40 * p}px) scale(${1 - 0.06 * p})`;
      numEl.textContent = `${prefix}${targetNum}${suffix}`;
    }
  };
  window.renderSeek(0);
</script>
</body>
</html>
```

Create `scripts/broll_templates/quote_card.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    width: 1080px; height: 1920px;
    background: transparent;
    overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  .container {
    width: 100%; height: 100%;
    display: flex; align-items: center; justify-content: center;
    padding: 80px;
  }
  .card {
    background: rgba(18, 18, 22, 0.90);
    border: 2px solid rgba(255, 255, 255, 0.14);
    border-radius: 36px;
    padding: 60px 70px;
    box-shadow: 0 30px 60px rgba(0, 0, 0, 0.75);
    backdrop-filter: blur(20px);
    max-width: 920px;
    opacity: 0;
    transform: translateY(70px);
  }
  .quote-icon {
    font-size: 80px;
    color: #F59E0B;
    line-height: 0.8;
    margin-bottom: 20px;
  }
  .quote-text {
    font-size: 42px;
    font-weight: 700;
    color: #FFFFFF;
    line-height: 1.4;
    font-style: italic;
    text-shadow: 0 2px 8px rgba(0,0,0,0.7);
  }
  .author-box {
    margin-top: 36px;
    display: flex;
    flex-direction: column;
    border-top: 2px solid rgba(255, 255, 255, 0.1);
    padding-top: 24px;
  }
  .author-name {
    font-size: 32px;
    font-weight: 800;
    color: #FBBF24;
  }
  .author-title {
    font-size: 24px;
    color: #9CA3AF;
    margin-top: 4px;
  }
</style>
</head>
<body>
<div class="container">
  <div class="card" id="card">
    <div class="quote-icon">“</div>
    <div class="quote-text">{{QUOTE}}</div>
    <div class="author-box">
      <div class="author-name">{{AUTHOR}}</div>
      <div class="author-title">{{TITLE}}</div>
    </div>
  </div>
</div>
<script>
  const card = document.getElementById('card');
  function easeOutCubic(x) { return 1 - Math.pow(1 - x, 3); }
  function easeInCubic(x) { return x * x * x; }

  window.renderSeek = function(progress) {
    progress = Math.max(0, Math.min(1, progress));
    if (progress < 0.18) {
      const p = easeOutCubic(progress / 0.18);
      card.style.opacity = p;
      card.style.transform = `translateY(${70 * (1 - p)}px)`;
    } else if (progress <= 0.82) {
      card.style.opacity = 1;
      card.style.transform = 'translateY(0)';
    } else {
      const p = easeInCubic((progress - 0.82) / 0.18);
      card.style.opacity = 1 - p;
      card.style.transform = `translateY(${-40 * p}px)`;
    }
  };
  window.renderSeek(0);
</script>
</body>
</html>
```

Create `scripts/broll_templates/point_highlight.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    width: 1080px; height: 1920px;
    background: transparent;
    overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  .container {
    width: 100%; height: 100%;
    display: flex; align-items: center; justify-content: center;
    padding: 80px;
  }
  .card {
    background: rgba(18, 18, 22, 0.90);
    border: 2px solid rgba(255, 255, 255, 0.14);
    border-radius: 36px;
    padding: 60px 70px;
    box-shadow: 0 30px 60px rgba(0, 0, 0, 0.75);
    backdrop-filter: blur(20px);
    width: 920px;
    opacity: 0;
    transform: translateY(60px);
  }
  .headline {
    font-size: 44px;
    font-weight: 800;
    color: #60A5FA;
    margin-bottom: 36px;
    border-bottom: 2px solid rgba(96, 165, 250, 0.3);
    padding-bottom: 16px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  .point-item {
    font-size: 34px;
    font-weight: 700;
    color: #F3F4F6;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    opacity: 0;
    transform: translateX(-30px);
  }
  .point-badge {
    background: #3B82F6;
    color: white;
    width: 48px; height: 48px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 24px; font-weight: 900;
    margin-right: 20px; flex-shrink: 0;
  }
</style>
</head>
<body>
<div class="container">
  <div class="card" id="card">
    <div class="headline">{{HEADLINE}}</div>
    <div id="points-container">
      {{POINTS_HTML}}
    </div>
  </div>
</div>
<script>
  const card = document.getElementById('card');
  const pointItems = document.querySelectorAll('.point-item');

  function easeOutCubic(x) { return 1 - Math.pow(1 - x, 3); }
  function easeInCubic(x) { return x * x * x; }

  window.renderSeek = function(progress) {
    progress = Math.max(0, Math.min(1, progress));
    if (progress < 0.15) {
      const p = easeOutCubic(progress / 0.15);
      card.style.opacity = p;
      card.style.transform = `translateY(${60 * (1 - p)}px)`;
    } else if (progress <= 0.85) {
      card.style.opacity = 1;
      card.style.transform = 'translateY(0)';
      const activeWindow = 0.85 - 0.15;
      pointItems.forEach((el, idx) => {
        const itemStart = 0.15 + (idx * 0.12);
        if (progress >= itemStart) {
          const itemP = Math.min(1, (progress - itemStart) / 0.10);
          el.style.opacity = itemP;
          el.style.transform = `translateX(${-30 * (1 - itemP)}px)`;
        } else {
          el.style.opacity = 0;
          el.style.transform = 'translateX(-30px)';
        }
      });
    } else {
      const p = easeInCubic((progress - 0.85) / 0.15);
      card.style.opacity = 1 - p;
      card.style.transform = `translateY(${-40 * p}px)`;
    }
  };
  window.renderSeek(0);
</script>
</body>
</html>
```

Create `scripts/broll_engine.py`:
```python
import html
import os
from typing import Any, Dict, List

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "broll_templates")

CATALOG: List[Dict[str, Any]] = [
    {
        "id": "stat_counter",
        "name": "Stat Counter",
        "description": "Animated numerical metric with label and customizable accent color",
        "default_duration": 3.5,
        "sample_data": {
            "target_number": "87",
            "prefix": "+",
            "suffix": "%",
            "label": "Tingkat Retensi 3 Detik Pertama",
            "accent_color": "#FF3B30",
        },
    },
    {
        "id": "quote_card",
        "name": "Quote Card",
        "description": "Highlight memorable punchline or statement with speaker attribution",
        "default_duration": 4.0,
        "sample_data": {
            "quote": "Bila pembukaan video tidak memikat dalam 2 detik, penonton pergi selamanya.",
            "author": "Dr. Sarah Adams",
            "title": "Media Psychologist",
        },
    },
    {
        "id": "point_highlight",
        "name": "Point Highlight",
        "description": "Staggered bullet points highlighting core arguments or steps",
        "default_duration": 4.5,
        "sample_data": {
            "headline": "3 Kunci Viral",
            "points": ["Hook 3 detik pertama", "Pacing tanpa dead-air", "Punchline memuaskan"],
        },
    },
]


def list_templates() -> List[Dict[str, Any]]:
    return list(CATALOG)


def get_template_path(template_id: str) -> str:
    path = os.path.join(TEMPLATES_DIR, f"{template_id}.html")
    if not os.path.exists(path):
        raise FileNotFoundError(f"B-roll template '{template_id}' not found at {path}")
    return path


def render_html_content(template_id: str, data: Dict[str, Any]) -> str:
    path = get_template_path(template_id)
    with open(path, "r", encoding="utf-8") as f:
        template_str = f.read()

    data = data or {}

    if template_id == "stat_counter":
        target_num = html.escape(str(data.get("target_number", "100")))
        prefix = html.escape(str(data.get("prefix", "")))
        suffix = html.escape(str(data.get("suffix", "%")))
        label = html.escape(str(data.get("label", "Key Statistic")))
        accent = html.escape(str(data.get("accent_color", "#FF3B30")))

        rendered = template_str.replace("{{TARGET_NUMBER}}", target_num)
        rendered = rendered.replace("{{PREFIX}}", prefix)
        rendered = rendered.replace("{{SUFFIX}}", suffix)
        rendered = rendered.replace("{{LABEL}}", label)
        rendered = rendered.replace("{{ACCENT_COLOR}}", accent)
        return rendered

    elif template_id == "quote_card":
        quote = html.escape(str(data.get("quote", "")))
        author = html.escape(str(data.get("author", "Speaker")))
        title = html.escape(str(data.get("title", "")))

        rendered = template_str.replace("{{QUOTE}}", quote)
        rendered = rendered.replace("{{AUTHOR}}", author)
        rendered = rendered.replace("{{TITLE}}", title)
        return rendered

    elif template_id == "point_highlight":
        headline = html.escape(str(data.get("headline", "Summary")))
        raw_points = data.get("points") or ["Key Point 1", "Key Point 2"]
        points_html_parts = []
        for idx, pt in enumerate(raw_points, start=1):
            esc_pt = html.escape(str(pt))
            points_html_parts.append(
                f'<div class="point-item"><div class="point-badge">{idx}</div><span>{esc_pt}</span></div>'
            )
        points_html = "\n".join(points_html_parts)

        rendered = template_str.replace("{{HEADLINE}}", headline)
        rendered = rendered.replace("{{POINTS_HTML}}", points_html)
        return rendered

    raise ValueError(f"Unsupported template_id: {template_id}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_broll_templates.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/broll_templates/ scripts/broll_engine.py tests/test_broll_templates.py
git commit -m "feat(broll): create HTML template engine and 3 motion graphics templates"
```

---

### Task 2: Deterministic Headless Renderer (Playwright -> FFmpeg Pipe WebM)

**Files:**
- Create: `scripts/broll_renderer.py`
- Test: `tests/test_broll_renderer.py`

**Interfaces:**
- Consumes: `broll_engine.render_html_content(template_id, data)`
- Produces: `broll_renderer.render_broll_clip(template_id: str, data: dict, duration: float, output_path: str, fps: int = 30) -> str`

- [ ] **Step 1: Write test for headless WebM rendering**

```python
# tests/test_broll_renderer.py
import os
import subprocess
import tempfile
import pytest
from scripts import broll_renderer

def test_render_broll_clip_generates_valid_alpha_webm():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_webm = os.path.join(tmpdir, "test_stat.webm")
        data = {
            "target_number": "99",
            "prefix": "",
            "suffix": "%",
            "label": "Test Retensi",
            "accent_color": "#10B981"
        }
        res_path = broll_renderer.render_broll_clip(
            template_id="stat_counter",
            data=data,
            duration=1.0,
            output_path=output_webm,
            fps=30
        )
        assert os.path.exists(res_path)
        assert os.path.getsize(res_path) > 1000

        # Check format and alpha channel via ffprobe
        probe = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,pix_fmt,duration",
                "-of", "default=noprint_wrappers=1",
                output_webm
            ],
            capture_output=True, text=True, check=True
        )
        stdout = probe.stdout
        assert "codec_name=vp9" in stdout
        assert "pix_fmt=yuva420p" in stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_broll_renderer.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement scripts/broll_renderer.py**

```python
import os
import subprocess
import tempfile
from typing import Any, Dict
from playwright.sync_api import sync_playwright
from scripts import broll_engine


def render_broll_clip(
    template_id: str,
    data: Dict[str, Any],
    duration: float,
    output_path: str,
    fps: int = 30,
) -> str:
    """
    Renders an HTML motion template to a transparent WebM video (VP9 / yuva420p)
    frame-by-frame via Playwright headless Chromium and FFmpeg stdin pipe (CPU-only).
    """
    duration = max(1.0, float(duration or 3.0))
    total_frames = max(1, int(round(duration * fps)))
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    html_content = broll_engine.render_html_content(template_id, data)

    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "-r",
        str(fps),
        "-i",
        "-",
        "-c:v",
        "libvpx-vp9",
        "-pix_fmt",
        "yuva420p",
        "-b:v",
        "2M",
        "-auto-alt-ref",
        "0",
        output_path,
    ]

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tf:
        tf.write(html_content)
        temp_html_path = tf.name

    proc = None
    try:
        proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(viewport={"width": 1080, "height": 1920})
            page = context.new_page()
            page.goto(f"file://{os.path.abspath(temp_html_path)}")

            denominator = max(1, total_frames - 1)
            for frame_idx in range(total_frames):
                progress = frame_idx / denominator
                page.evaluate(f"window.renderSeek({progress})")
                frame_bytes = page.screenshot(type="png", omit_background=True)
                proc.stdin.write(frame_bytes)

            browser.close()

        proc.stdin.close()
        proc.wait()
    finally:
        if proc and proc.poll() is None:
            proc.kill()
        if os.path.exists(temp_html_path):
            try:
                os.remove(temp_html_path)
            except Exception:
                pass

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError(f"B-roll render failed: Output file missing or empty: {output_path}")

    return output_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_broll_renderer.py -v`
Expected: PASS in ~2–4s.

- [ ] **Step 5: Commit**

```bash
git add scripts/broll_renderer.py tests/test_broll_renderer.py
git commit -m "feat(broll): implement deterministic headless Playwright renderer to transparent WebM"
```

---

### Task 3: LLM Prompt & Metadata Extraction

**Files:**
- Modify: `scripts/create_viral_segments.py:926-940`
- Modify: `scripts/smart_clipping.py:155-195,680-700`
- Test: `tests/test_broll_llm_parser.py`

**Interfaces:**
- Produces: `broll_items` list inside viral segment dicts:
  `{"start_offset": float, "duration": float, "template_id": str, "data": dict}`

- [ ] **Step 1: Write test for broll_items extraction and parsing**

```python
# tests/test_broll_llm_parser.py
from scripts import smart_clipping

def test_parse_llm_topics_with_broll():
    sample_llm = """
    {
      "topics": [
        {
          "title": "Rahasia Cuan 100M",
          "rationale": "High retention statistic",
          "score": 92,
          "segments": {
            "hook": {"start_time": 2.0, "end_time": 6.0, "text": "Kalian tahu tidak?"},
            "core": {"start_time": 8.0, "end_time": 25.0, "text": "Bisnis ini melonjak 85% dalam 1 bulan."},
            "payoff": {"start_time": 30.0, "end_time": 40.0, "text": "Itulah kuncinya."}
          },
          "broll_items": [
            {
              "start_offset": 8.5,
              "duration": 3.5,
              "template_id": "stat_counter",
              "data": {
                "target_number": "85",
                "suffix": "%",
                "label": "Lonjakan Bisnis 1 Bulan"
              }
            }
          ]
        }
      ]
    }
    """
    topics = smart_clipping.parse_llm_topics(sample_llm)
    assert len(topics) == 1
    topic = topics[0]
    assert "broll_items" in topic
    assert len(topic["broll_items"]) == 1
    assert topic["broll_items"][0]["template_id"] == "stat_counter"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_broll_llm_parser.py -v`
Expected: FAIL (`broll_items` not preserved).

- [ ] **Step 3: Update LLM json_template and parse_llm_topics**

In `scripts/smart_clipping.py`, update `build_narrative_prompt` to include `broll_items` in the example format:
```python
      "broll_items": [
        {
          "start_offset": 5.0,
          "duration": 3.5,
          "template_id": "stat_counter",
          "data": {
            "target_number": "85",
            "suffix": "%",
            "label": "Lonjakan Bisnis"
          }
        }
      ]
```
And in `parse_llm_topics(llm_response)`:
Extract and normalize `broll_items` if present in topic dict; validate `template_id` in `{"stat_counter", "quote_card", "point_highlight"}` and ensure valid `start_offset` and `duration`.

In `scripts/create_viral_segments.py:926`, update `json_template` to optionally describe `broll_items`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_broll_llm_parser.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/create_viral_segments.py scripts/smart_clipping.py tests/test_broll_llm_parser.py
git commit -m "feat(broll): add broll_items metadata schema and LLM extraction parser"
```

---

### Task 4: FFmpeg Alpha Overlay & Pipeline Integration

**Files:**
- Modify: `scripts/burn_subtitles.py:120-225`
- Modify: `main_improved.py` (CLI flag `--enable-html-broll`)
- Test: `tests/test_broll_overlay.py`

**Interfaces:**
- Consumes: `broll_renderer.render_broll_clip()`
- Produces: `burn_video_file(..., broll_items=None)` overlaying transparent WebM before subtitles.

- [ ] **Step 1: Write integration test for broll overlay burning**

```python
# tests/test_broll_overlay.py
import os
import subprocess
import tempfile
import pytest
from scripts import burn_subtitles, broll_renderer

def test_burn_video_file_with_broll_overlay():
    with tempfile.TemporaryDirectory() as tmpdir:
        video_in = os.path.join(tmpdir, "test_input.mp4")
        sub_ass = os.path.join(tmpdir, "test_sub.ass")
        output_mp4 = os.path.join(tmpdir, "test_out.mp4")
        broll_webm = os.path.join(tmpdir, "broll.webm")

        # Create 5s synthetic video
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=5:size=320x180:rate=30",
            "-f", "lavfi", "-i", "sine=duration=5",
            "-c:v", "libx264", "-c:a", "aac",
            video_in
        ], check=True)

        # Create 2s WebM broll
        broll_renderer.render_broll_clip(
            "stat_counter",
            {"target_number": "50", "suffix": "%", "label": "Uji B-Roll"},
            duration=2.0,
            output_path=broll_webm,
            fps=30
        )

        with open(sub_ass, "w") as f:
            f.write("[Script Info]\nScriptType: v4.00+\n[Events]\nFormat: Layer, Start, End, Style, Text\nDialogue: 0,0:00:01.00,0:00:03.00,Default,Test\n")

        broll_items = [
            {
                "start_offset": 1.0,
                "duration": 2.0,
                "video_path": broll_webm
            }
        ]

        burn_subtitles.burn_video_file(
            video_path=video_in,
            subtitle_path=sub_ass,
            output_path=output_mp4,
            broll_items=broll_items
        )

        assert os.path.exists(output_mp4)
        assert os.path.getsize(output_mp4) > 1000

        # Verify video duration matches 5s
        res = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            output_mp4
        ], capture_output=True, text=True, check=True)
        dur = float(res.stdout.strip())
        assert abs(dur - 5.0) < 0.2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_broll_overlay.py -v`
Expected: FAIL (argument `broll_items` not accepted).

- [ ] **Step 3: Implement broll overlay filter graph in burn_subtitles.py and CLI in main_improved.py**

In `scripts/burn_subtitles.py`:
- Add `broll_items=None` to `burn_video_file` signature.
- If `broll_items`:
  - Add each WebM file as an input (`-i path_to_webm`).
  - Chain overlay filter:
    `[prev_video][broll_in]overlay=x=0:y=0:enable='between(t,{start},{end})':eof_action=pass[next_video]`
  - Pass resulting stream to watermark and subtitles filter graph.

In `main_improved.py`:
- Add argument:
  `parser.add_argument("--enable-html-broll", action="store_true", help="Enable contextual HTML motion graphic B-roll overlays")`
- In workflow step, if `args.enable_html_broll`:
  Render each clip's `broll_items` to temporary project folder `project_folder/broll_cache/` before invoking `burn_subtitles.burn()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_broll_overlay.py -v`
Expected: PASS in ~6–8s.

- [ ] **Step 5: Commit**

```bash
git add scripts/burn_subtitles.py main_improved.py tests/test_broll_overlay.py
git commit -m "feat(broll): integrate WebM alpha overlay filter graph into burn pipeline and CLI"
```

---

### Task 5: Backend API Endpoints & Job Schema

**Files:**
- Create: `webui/backend/api/v1/broll.py`
- Modify: `webui/backend/main.py:15-30,55-65`
- Modify: `webui/backend/schemas/jobs.py`
- Test: `tests/test_backend_broll.py`

**Interfaces:**
- Endpoints:
  - `GET /api/v1/broll/templates` -> `List[BrollTemplateResponse]`
  - `POST /api/v1/broll/preview` -> `BrollPreviewResponse` (`preview_url`)
- Schema: `enable_html_broll: bool = False` in `JobRunRequest` and in `to_cli_args()`.

- [ ] **Step 1: Write tests for backend B-Roll endpoints**

```python
# tests/test_backend_broll.py
import pytest
from fastapi.testclient import TestClient
from webui.backend.main import app

client = TestClient(app)

def test_get_broll_templates():
    response = client.get("/api/v1/broll/templates")
    assert response.status_code == 200
    templates = response.json()
    assert len(templates) >= 3
    ids = [t["id"] for t in templates]
    assert "stat_counter" in ids

def test_preview_broll_template():
    payload = {
        "template_id": "stat_counter",
        "duration": 1.0,
        "data": {
            "target_number": "100",
            "suffix": "%",
            "label": "Test Label"
        }
    }
    response = client.post("/api/v1/broll/preview", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "preview_url" in data
    assert data["preview_url"].endswith(".webm")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_backend_broll.py -v`
Expected: FAIL 404 Not Found.

- [ ] **Step 3: Implement webui/backend/api/v1/broll.py and mount in main.py**

Create `webui/backend/api/v1/broll.py`:
- Use `broll_engine.list_templates()`.
- Implement preview endpoint creating video in `PREVIEWS_DIR` and returning `/preview/stream?path=...`.
Update `webui/backend/main.py` with `app.include_router(broll.router, prefix="/api/v1/broll", tags=["broll"])`.
Update `webui/backend/schemas/jobs.py` with `enable_html_broll: bool = Field(default=False)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_backend_broll.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add webui/backend/api/v1/broll.py webui/backend/main.py webui/backend/schemas/jobs.py tests/test_backend_broll.py
git commit -m "feat(broll): create backend templates & preview API endpoints and job schema flag"
```

---

### Task 6: Frontend UI (Navbar Tab, BrollTab, GeneratorTab Integration)

**Files:**
- Modify: `webui/frontend/src/api/types.ts`
- Modify: `webui/frontend/src/api/client.ts`
- Modify: `webui/frontend/src/components/Navbar.tsx`
- Create: `webui/frontend/src/components/BrollTab.tsx`
- Modify: `webui/frontend/src/components/GeneratorTab.tsx`
- Modify: `webui/frontend/src/App.tsx`
- Modify: `webui/frontend/src/test/tabs.test.tsx`

**Interfaces:**
- `Navbar`: Add `{ id: 'broll', label: 'B-Roll', icon: Sparkles }` right after `watermark`.
- `BrollTab`: Catalog selector, form fields for template data, Test Render Preview button, and 9:16 video player preview.
- `GeneratorTab`: Section 7 "Automated Motion B-Roll" toggle `enable_html_broll`.

- [ ] **Step 1: Write frontend test for BrollTab and Navbar integration**

Add tests to `webui/frontend/src/test/tabs.test.tsx`:
- Verify 'B-Roll' is in Navbar tabs right after 'Watermark'.
- Verify clicking 'B-Roll' tab renders template options (`Stat Counter`, `Quote Card`, `Point Highlight`).
- Verify GeneratorTab renders 'Motion B-Roll' section and toggle.

- [ ] **Step 2: Run frontend test to verify it fails**

Run: `cd webui/frontend && npm test`
Expected: FAIL.

- [ ] **Step 3: Implement frontend components**

1. Update `api/types.ts` with `BrollTemplate`, `BrollPreviewRequest`, `BrollPreviewResponse`, and `enable_html_broll` in `JobRunRequest`.
2. Update `api/client.ts` with `brollApi.getTemplates()` and `brollApi.preview()`.
3. In `Navbar.tsx`: Insert `{ id: 'broll' as TabType, label: 'B-Roll', icon: Sparkles }` right after `watermark`.
4. Create `webui/frontend/src/components/BrollTab.tsx`:
   - Template selection card list.
   - Dynamic inputs for selected template data.
   - Duration slider (1.5s to 6.0s).
   - "Test Render Motion B-Roll" button with spinner.
   - 9:16 Video player displaying rendered WebM preview with transparent grid background.
5. In `GeneratorTab.tsx`:
   - Add persisted state `const [enableHtmlBroll, setEnableHtmlBroll] = usePersistedState<boolean>('enable_html_broll', false);`.
   - Add Section 7 UI card with toggle and shortcut button to navigate to B-Roll tab.
   - Include `enable_html_broll: enableHtmlBroll` in `handleRunJob()` payload.
6. In `App.tsx`:
   - Import `BrollTab` and render it when `currentTab === 'broll'`.

- [ ] **Step 4: Run frontend test and build**

Run: `cd webui/frontend && npm test && npm run build`
Expected: 58+ passed, build succeeds with zero errors.

- [ ] **Step 5: Commit**

```bash
git add webui/frontend/
git commit -m "feat(ui): add B-Roll tab to navbar, template preview playground, and generator toggle"
```

---

### Task 7: Full System Verification & Regression Run

**Files:**
- Test: All tests in `tests/` and `webui/frontend/src/test/`

- [ ] **Step 1: Run complete backend pytest suite**

Run: `PYTHONPATH=. pytest tests/ -v`
Expected: 195+ passed, 0 failures.

- [ ] **Step 2: Run complete frontend vitest suite and compilation**

Run: `cd webui/frontend && npm test && npm run build`
Expected: All tests pass, build output clean.

- [ ] **Step 3: End-to-End CLI Smoke Run**

Run short smoke test:
```bash
python3 -c "from scripts import broll_engine, broll_renderer; print('Templates:', len(broll_engine.list_templates()))"
```
Expected: `Templates: 3`.

- [ ] **Step 4: Final commit and summary report**

```bash
git status
```
Ensure working tree is clean.
