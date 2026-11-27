# PROJECT LEDGER — ViralCutter

## Context
- **Goal**: Open-source AI tool to turn long videos into viral shorts (TikTok/Reels/Shorts) with dynamic captions, face tracking, and smart clipping.
- **Current Objective**: Resolve execution log streaming & process concurrency bugs (`AUDIT-LOGSTREAM-BACKEND`), maintain robust Google Drive & Colab integration, and optimize end-to-end rendering pipelines.
- **Constraints**:
  - Strict worktree isolation (max 3 concurrent pipelines; single writer per worktree).
  - Forbidden git commands: `stash`, `reset`, force-push, history rewrite.
  - Protected paths: `models/`, `credentials.json`, `token_drive.json`, `webui/PREVIEW/`, `VIRALS/`, `.worktrees/`, `webui/frontend/dist/`.
  - Cross-platform support (Linux, Windows, macOS).

## Tasks

| ID / Ref | Task | Owner | Branch / Worktree | Status | Evidence / Next |
| --- | --- | --- | --- | --- | --- |
| `issue-8` | Unify 16kHz audio extraction cache for Whisper & detector | developer | `feat/issue-8` | `DONE` | Commits `a622305`, `54ed543`, merged `6cd5ae6` |
| `issue-9` | Merge gaming split & subtitles into single-pass filtergraph | developer | `feat/issue-9` | `DONE` | Commits `0779f61`, `bb75b30`, merged `3f1096b` |
| `issue-6` | Parallelize clip layout rendering and subtitle burning | developer | `feat/issue-6` | `DONE` | Commits `b533c6a`, `7e20aab`, merged `373b4d9` |
| `issue-10` | Zero-copy symbolic link import to eliminate Cloudflare 524 timeouts | developer | `feat/issue-10` | `DONE` | Commits `a47ebc6`, `ca8ad49`, `90d4116`; Tester PASS & Reviewer APPROVE; PR #14 merged |
| `issue-11` | Missing auto-scroll, SSE reconnection, and DOM thrashing in GeneratorTab | developer | `fix/issue-11` | `DONE` | Commits `c915d9a`, `d6e7e62`, `889aa7f`; Tester PASS & Reviewer APPROVE; PR #15 merged |
| `issue-12` | Pipe reader UnicodeDecodeError, cancellation race, orphaned GPU processes | developer | `fix/issue-12` | `DONE` | Commits `409e8d8`, `b4a8c2b`, `4341d37`; Tester PASS & Reviewer APPROVE; PR #16 merged |
| `issue-13` | Readline blocks on \r progress bars, stdout flush, SSE cursor resume | developer | `fix/issue-13` | `DONE` | Commits `fb2e3b7`, `a19ebba`; Tester PASS & Reviewer APPROVE; PR #17 merged |

Status: `TODO` · `WIP` · `BLOCKED` · `DONE`

## Decisions

| Ref | Decision / Reason |
| --- | --- |
| `DEC-001` | **FastAPI SSE Log Streaming**: Transitioned from Gradio WebSockets to FastAPI SSE (`/api/v1/jobs/{id}/logs/stream`) for modularity and decoupled UI. |
| `DEC-002` | **Single-Pass Filtergraph (`issue-9`)**: Merged gaming split framing and subtitle burning into a single FFmpeg command to eliminate intermediate disk I/O and re-encoding latency. |
| `DEC-003` | **Unified Audio Extraction (`issue-8`)**: Shared a single 16kHz mono WAV extraction between Whisper transcription and moment detection. |
| `DEC-004` | **Parallel Clip Layout Rendering (`issue-6`)**: Parallelized independent clip exports across multiprocessing workers. |
| `DEC-005` | **Symlink-First Video Import**: Prefer `os.symlink` over `shutil.copy2` for Google Drive and local source files to prevent duplicate disk storage and reduce setup latency. |
| `DEC-006` | **Worktree Isolation & Antigravity V2**: Enforce strict isolated worktrees per feature/fix, with move-only task verification before dispatching agent writes. |

## Rules
- Read this ledger before starting or resuming work.
- Claim a unique task before work; parallel tasks use isolated branches/worktrees when editing code.
- Orchestrator is the sole writer; agents report changes and evidence via task ID in handoff reports.
- Update only on claim (`WIP`), blocker (`BLOCKED`), handoff, or completion (`DONE`). Keep entries short and factual.
- Mark `DONE` only when acceptance criteria are met and checks are verified; cite test/commit/PR evidence. Record blockers with next action.
- Keep shared decisions only. No transcripts, duplicate docs, secrets, or verbose logs.
- Archive completed rows when no longer needed; retain durable references in git history or project specs.
