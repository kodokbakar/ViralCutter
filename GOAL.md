# ViralCutter Agentic Development Goals

## 1. Mission

Transform ViralCutter from a linear video-processing script into a reliable, reviewable, resumable, and publish-ready short-form video production system.

The system should help a creator move from a long video to multiple high-quality vertical clips while preserving control over segment selection, branding, subtitles, rendering, export, and publishing.

## 2. Product Vision

ViralCutter should become a lightweight, open-source **AI-assisted short-form editing studio** with the following workflow:

```text
Import video
→ Validate runtime
→ Transcribe
→ Generate candidate clips
→ Review and approve clips
→ Refine boundaries
→ Render video
→ Apply branding and subtitles
→ Validate platform compatibility
→ Export or publish
```

The AI should propose and automate, but the user must retain final editorial control.

## 3. Current Baseline

The following capabilities are treated as the current baseline and should not be regressed:

- Multiple input sources, including URL, upload, existing project, and Google Drive.
- WhisperX transcription with selectable language.
- WhisperX Fast Test, Balanced, Accurate, and Custom presets.
- Runtime Doctor for Python, GPU, CUDA, WhisperX, CTranslate2, faster-whisper, FFmpeg, and media validation.
- Editable AI prompt template.
- AI-assisted viral segment generation.
- Sentence-aware boundary refinement with pre-roll and post-roll.
- Face processing and source-framing preservation.
- Subtitle styling, preview, editing, rendering, and burn-in.
- Compilation and clip ordering.
- Pipeline progress and elapsed-time reporting.
- Project-level logs and processing configuration.
- Configurable watermark support.

## 4. Agent Operating Principles

Every agent working on this roadmap must follow these rules:

1. Preserve existing behavior unless a goal explicitly changes it.
2. Prefer project-scoped files over shared global temporary files.
3. Keep CLI and WebUI behavior compatible whenever practical.
4. Every new feature must include validation, failure handling, and user-readable errors.
5. Long-running stages must be resumable or safely repeatable.
6. Never store credentials, access tokens, or secrets in project exports, logs, Git, or processing configuration.
7. Avoid adding abstractions without a concrete use case.
8. Add automated tests for state transitions, file operations, and data validation.
9. Keep stage outputs deterministic enough for retries and debugging.
10. Update `GOAL.md`, `KANBAN.md`, and user documentation when behavior changes.

## 5. Priority Model

| Priority | Meaning | Expected Treatment |
|---|---|---|
| P0 | Blocks normal use, risks data loss, or breaks the pipeline | Fix immediately |
| P1 | Major product capability or reliability improvement | Implement before secondary features |
| P2 | Important usability, quality, or maintainability improvement | Schedule after P1 foundations |
| P3 | Experimental, optional, or ecosystem expansion | Implement only after core stability |

## 6. Strategic Goals

---

## G-001 — Stabilize the Pipeline Contract

**Priority:** P0  
**Status Target:** First milestone

### Outcome

Define a stable contract between WebUI controls, CLI arguments, environment variables, stage outputs, and project files.

### Scope

- Audit positional Gradio inputs and outputs.
- Validate all CLI arguments before processing starts.
- Separate AI chunk size from WhisperX chunk size in names and configuration.
- Remove ambiguous or duplicated configuration paths.
- Define canonical project folder names and output files.
- Standardize structured stage messages.

### Deliverables

- `docs/PIPELINE_CONTRACT.md`
- Canonical CLI argument table.
- Canonical project directory schema.
- Input and output validation helpers.
- Regression tests for WebUI-to-CLI argument mapping.

### Acceptance Criteria

- Every WebUI input maps to the intended function parameter and CLI argument.
- Invalid batch size, chunk size, duration, or project path fails before launching the subprocess.
- The same configuration produces equivalent behavior from CLI and WebUI.
- No generator callback returns the wrong number of Gradio outputs.

### Dependencies

None.

---

## G-002 — Persistent Project State and Resumable Processing

**Priority:** P1  
**Status Target:** Core architecture milestone

### Outcome

Allow interrupted or failed projects to resume from the last valid stage without rerunning completed expensive work.

### Scope

- Add `project_state.json` with versioned schema.
- Record stage status: pending, running, waiting, completed, failed, skipped, and invalidated.
- Record start time, end time, duration, input fingerprint, output files, and error summary.
- Add stage dependency validation.
- Add resume, retry, and invalidate operations.
- Detect stale `running` states after a process or Colab runtime disappears.

### Deliverables

- `scripts/pipeline_state.py`
- State schema and migration strategy.
- Resume controls in WebUI.
- Retry controls for failed stages.
- Tests for state transitions and recovery.

### Acceptance Criteria

- A project interrupted after transcription can continue without transcribing again.
- Changing subtitle style invalidates subtitle rendering but not transcription or cutting.
- Changing segment timing invalidates cutting and all downstream stages.
- A failed stage records an actionable error and can be retried independently.
- State writes are atomic and cannot leave malformed JSON after interruption.

### Dependencies

G-001.

---

## G-003 — Interactive Candidate Review Studio

**Priority:** P1  
**Status Target:** Major product milestone

### Outcome

Pause the pipeline after AI candidate generation and let the user review, edit, preview, approve, reject, and reorder clips before rendering.

### Scope

- Separate raw candidates from approved segments.
- Add `viral_candidates.json`.
- Keep `viral_segments.txt` as the approved render source.
- Add candidate table with selection, order, title, hook, reasoning, score, start, end, and duration.
- Add lightweight preview generation.
- Allow manual candidate creation.
- Validate overlaps and duration constraints.

### Deliverables

- `webui/review.py`
- `scripts/candidate_manager.py`
- Segment Review tab.
- Approve and Continue action.
- Candidate and approved-segment schemas.

### Acceptance Criteria

- AI candidates are not rendered until approved.
- Users can edit start and end times without editing JSON manually.
- Rejected candidates are never rendered.
- Approved order is preserved in individual exports and compilations.
- Regenerating candidates does not overwrite approved segments without confirmation.

### Dependencies

G-001, G-002.

---

## G-004 — Candidate Expansion and Multi-Signal Virality Scoring

**Priority:** P2

### Outcome

Generate more candidates than the requested final clip count and rank them using explainable multi-signal scoring.

### Scope

- Add candidate multiplier: 1x, 2x, 3x, and 5x.
- Preserve the AI score and reasoning.
- Add duration suitability score.
- Add transcript hook score.
- Add speech density and silence penalty.
- Add visual activity and face-presence signals where available.
- Store a score breakdown instead of one opaque number.

### Deliverables

- Versioned scoring schema.
- Ranking and normalization module.
- Score breakdown in Segment Review.
- Tests using fixed candidate fixtures.

### Acceptance Criteria

- Requesting three final clips with a 3x multiplier creates up to nine candidates.
- Every score contains an explainable breakdown.
- Ranking is deterministic for identical input data.
- Users can sort candidates by overall score or individual signals.

### Dependencies

G-003.

---

## G-005 — Scene-Aware Boundary Refinement

**Priority:** P2

### Outcome

Combine transcript boundaries and visual scene boundaries to produce cleaner clip starts and endings.

### Scope

- Add scene detection as an optional stage.
- Store detected scene boundaries.
- Add boundary modes: Transcript Only, Scene Only, Smart Hybrid, and Disabled.
- Respect minimum and maximum clip duration.
- Prevent excessive overlap between approved clips.
- Display original and refined timing in review metadata.

### Deliverables

- `scripts/scene_analysis.py`
- Scene cache file inside the project.
- Smart Hybrid boundary resolver.
- Boundary diagnostics in logs and review UI.

### Acceptance Criteria

- Smart Hybrid never produces a clip outside configured duration limits.
- Refined boundaries are explainable and stored with the segment.
- Scene analysis is cached and reusable.
- Users can restore the original AI timing.

### Dependencies

G-002, G-003.

---

## G-006 — Branding Studio: Watermark Hardening and Outro Builder

**Priority:** P1

### Outcome

Provide reusable brand presets that can apply a watermark and an optional outro consistently across individual clips and compilations.

### Scope

- Preserve the existing configurable watermark implementation.
- Add brand preset save/load.
- Add watermark safe-area preview.
- Add text, image, and video outro modes.
- Add per-clip outro and compilation-only outro.
- Add duration, transition, audio, volume, and call-to-action controls.
- Normalize media formats before concatenation.

### Deliverables

- `webui/branding.py`
- `scripts/append_outro.py`
- `brand_presets/` schema.
- Brand preview and validation.
- Processing configuration integration.

### Acceptance Criteria

- Brand presets can be reused across projects.
- Outro media with a different resolution, frame rate, or audio format is normalized safely.
- Watermark and subtitles do not unintentionally cover each other.
- Per-clip and compilation-only outro modes produce the expected number of outros.
- Branding changes invalidate only branding and downstream outputs.

### Dependencies

G-001, G-002.

---

## G-007 — Platform Export Presets and Media Validation

**Priority:** P1

### Outcome

Render and validate clips for TikTok, Instagram Reels, YouTube Shorts, and generic vertical export.

### Scope

- Add platform presets.
- Validate aspect ratio, resolution, codec, frame rate, audio, duration, and file size.
- Add safe-area overlays for captions, buttons, and branding.
- Produce warnings without silently changing editorial content.
- Store validation reports per output.

### Deliverables

- `scripts/platform_presets.py`
- `scripts/validate_publish_media.py`
- Platform selector in WebUI.
- Validation report UI.
- Export preset documentation.

### Acceptance Criteria

- Users can validate a clip before export or publishing.
- Validation errors distinguish blocking failures from recommendations.
- Platform presets are versioned and testable.
- The generic vertical preset remains available without platform-specific assumptions.

### Dependencies

G-006.

---

## G-008 — Project ZIP Export and Backup

**Priority:** P1

### Outcome

Allow users to download a self-contained project export before a Colab runtime or temporary environment disappears.

### Scope

Include available files from:

```text
cuts/
final/
burned_sub/
compiled/
viral_segments.txt
viral_candidates.json
prompt.txt
webui_run.log
process_config.json
project_state.json
publish_history.json
compilation.mp4
compilation.srt
```

### Deliverables

- `webui/project_export.py`
- Download Project ZIP action.
- Export manifest with included and missing items.
- ZIP exclusion rules for secrets, caches, temporary files, and nested ZIP files.

### Acceptance Criteria

- Missing optional folders do not fail the export.
- The ZIP never includes credentials or token files.
- The ZIP contains a manifest with creation time and source project name.
- Repeated exports do not recursively include earlier ZIP files.

### Dependencies

G-001.

---

## G-009 — Project-Scoped Runtime Files and Job Isolation

**Priority:** P1

### Outcome

Remove shared temporary files and make every processing job isolated by project.

### Scope

Move temporary runtime files to:

```text
VIRALS/<project>/.runtime/
```

Include:

```text
prompt.txt
subtitle_config.json
command.json
process.pid
current_stage.json
stdout.log
stderr.log
```

Replace the single global process variable with a project-aware job registry.

### Deliverables

- `webui/jobs.py`
- Project-scoped runtime directory.
- Job start, stop, inspect, and stale-process cleanup.
- Single-GPU scheduling policy.

### Acceptance Criteria

- Two projects cannot overwrite each other's prompt or subtitle configuration.
- Stop affects only the selected job.
- Stale PID files are detected safely.
- The scheduler prevents accidental concurrent GPU-heavy transcription jobs unless explicitly enabled.

### Dependencies

G-002.

---

## G-010 — Reliable Progress, ETA, and Structured Events

**Priority:** P2

### Outcome

Replace fragile progress detection based only on human-readable log text with structured pipeline events.

### Scope

- Emit machine-readable JSON events from every stage.
- Track stage index, item progress, elapsed time, and estimated remaining time.
- Continue producing readable logs.
- Support indeterminate progress when total work is unknown.
- Record stage metrics for future ETA estimation.

### Deliverables

- Event schema.
- Event emitter and parser.
- Progress UI with current stage, item count, elapsed time, and ETA.
- Historical duration data per preset and hardware profile.

### Acceptance Criteria

- Changing a translated log message does not break progress tracking.
- Long stages update progress even when subprocess output is sparse.
- ETA is marked as estimated and never blocks processing.
- Completion always reaches 100 percent only after a successful exit code.

### Dependencies

G-001, G-002.

---

## G-011 — YouTube Publishing Integration

**Priority:** P2

### Outcome

Allow authenticated users to publish an exported clip to YouTube through a controlled, resumable publishing workflow.

### Scope

- OAuth connection flow.
- Channel selection.
- Title, description, tags, category, privacy, and scheduling fields where supported.
- Resumable upload.
- Upload progress, retry, and result history.
- Explicit confirmation before publishing.

### Deliverables

- `scripts/publish/youtube.py`
- `webui/publishing.py`
- Credential configuration guide.
- `publish_history.json` schema.

### Acceptance Criteria

- Tokens are never written to project exports or logs.
- Interrupted uploads can resume or retry safely.
- The UI clearly shows selected account, file, metadata, and privacy before publishing.
- Publishing failures do not invalidate rendered media.

### Dependencies

G-007, G-009, G-013.

---

## G-012 — TikTok and Instagram Publishing Adapters

**Priority:** P3

### Outcome

Add optional publishing adapters for TikTok and Instagram after the platform export and YouTube publishing foundations are stable.

### Scope

- Shared publishing interface.
- Platform-specific OAuth and permissions.
- Account and creator capability checks.
- Metadata and privacy controls.
- Upload or hosted-media handoff as required by the platform.
- Processing-status polling and failure reporting.
- Platform approval and configuration documentation.

### Deliverables

- `scripts/publish/base.py`
- `scripts/publish/tiktok.py`
- `scripts/publish/instagram.py`
- Shared publish queue.
- Platform-specific validation and user consent screens.

### Acceptance Criteria

- Unsupported account or app states produce actionable messages.
- No silent publishing occurs.
- The user confirms platform, account, media, caption, and privacy.
- Platform adapters do not change the core rendering pipeline.

### Dependencies

G-007, G-009, G-011, G-013.

---

## G-013 — Security, Secrets, and Privacy Hardening

**Priority:** P0

### Outcome

Prevent credentials, private media paths, and sensitive user data from leaking through logs, exports, source control, or error messages.

### Scope

- Central secret redaction.
- Environment-based secret configuration.
- Token storage abstraction.
- Export allowlist instead of broad folder archiving.
- File path validation and project-root containment.
- Safe handling of user-supplied filenames.
- Dependency and vulnerability checks.

### Deliverables

- Security checklist.
- Secret redaction utility.
- Export security tests.
- Path traversal tests.
- `.gitignore` hardening.

### Acceptance Criteria

- API keys and tokens are redacted from commands and logs.
- Project export uses an explicit allowlist.
- A project name cannot escape `VIRALS_DIR`.
- Secret-bearing files are excluded from all downloads.
- Security tests run in CI.

### Dependencies

G-001.

---

## G-014 — Automated Testing and Continuous Integration

**Priority:** P0

### Outcome

Make feature development safe enough for multiple agents to work in parallel without silently breaking the pipeline.

### Scope

- Unit tests for pure helpers.
- Integration tests for CLI configuration and project state.
- Fixture-based tests for candidate data.
- Small generated media fixtures for FFmpeg tests.
- Gradio callback contract tests.
- Static analysis and formatting.
- CI matrix for supported Python versions and operating systems where practical.

### Deliverables

- `tests/` structure.
- CI workflow.
- Coverage report.
- Smoke-test command.
- Agent pre-commit checklist.

### Acceptance Criteria

- Every P0 and P1 goal includes automated tests.
- CI blocks merges on syntax errors, callback mismatches, state corruption, or failed unit tests.
- Tests do not require a production API key.
- GPU-dependent tests have explicit skip markers and CPU-safe alternatives.

### Dependencies

None; begin immediately and expand with every goal.

---

## G-015 — WebUI Information Architecture and Accessibility

**Priority:** P2

### Outcome

Reduce the size and complexity of the Create New page while making the workflow understandable on desktop and Colab share links.

### Scope

- Group controls by Import, AI, Transcription, Review, Branding, Subtitles, Export, and Publish.
- Hide advanced controls until needed.
- Add preset summaries and validation messages.
- Add keyboard navigation and meaningful labels.
- Improve responsive layout.
- Add reduced-motion behavior.
- Split large `webui/app.py` responsibilities into focused modules.

### Deliverables

- WebUI component map.
- Modular tab/component files.
- Accessibility checklist.
- Responsive smoke tests.

### Acceptance Criteria

- A first-time user can complete a Fast Test run without opening advanced settings.
- Custom controls remain available without cluttering the default workflow.
- All interactive components have clear labels and error states.
- Refactoring does not change CLI behavior.

### Dependencies

G-001; coordinate with all UI-facing goals.

---

## G-016 — Documentation, Migration, and Release Packaging

**Priority:** P2

### Outcome

Make ViralCutter installable, understandable, and upgradeable for users and agentic contributors.

### Scope

- Installation documentation for Colab, Linux, and Windows.
- Feature guides.
- Project schema documentation.
- State and configuration migration notes.
- Troubleshooting matrix.
- Release checklist and changelog.
- Example presets and sample project.

### Deliverables

- `README.md` refresh.
- `docs/` documentation set.
- `CHANGELOG.md`.
- Versioned configuration schema.
- Release automation.

### Acceptance Criteria

- A clean Colab runtime can install and launch using documented steps.
- Breaking schema changes include migration instructions.
- Every release lists added, changed, fixed, and known issues.
- Agent contributors can identify the correct module and test command for each goal.

### Dependencies

Continuous; finalize after each milestone.

## 7. Recommended Milestones

| Milestone | Goals | Product Result |
|---|---|---|
| M1 — Reliable Foundation | G-001, G-013, initial G-014 | Stable configuration, safer files, regression protection |
| M2 — Resumable Projects | G-002, G-009, G-010 | Recoverable jobs with real project state |
| M3 — Editorial Control | G-003, G-004, G-005 | Candidate review and smarter clip selection |
| M4 — Brand and Export | G-006, G-007, G-008 | Branded, validated, downloadable outputs |
| M5 — Publishing | G-011, G-012 | Optional direct platform publishing |
| M6 — Product Maturity | G-015, G-016, expanded G-014 | Maintainable UI, documentation, and release process |

## 8. Global Definition of Done

A goal is complete only when all applicable conditions are satisfied:

- Implementation is merged without unrelated changes.
- Existing supported workflows still function.
- Acceptance criteria are demonstrably met.
- Automated tests are added and passing.
- Errors are actionable and do not expose secrets.
- New files and configuration are documented.
- Project state and exports remain backward-compatible or include migration handling.
- `KANBAN.md` status is updated.
- The feature has a manual Colab smoke-test procedure.
- The final commit message clearly describes the behavior delivered.

## 9. Agent Handoff Template

Every agent must leave a handoff containing:

```text
Goal ID:
Branch:
Commits:
Files changed:
Behavior implemented:
Tests executed:
Known limitations:
Open risks:
Recommended next task:
```

## 10. Non-Goals for the Near Term

The following should not be prioritized before the P0 and P1 foundations are stable:

- Fully autonomous publishing without explicit user confirmation.
- Multi-user cloud hosting with billing and account management.
- Distributed GPU workers.
- Training a proprietary virality model from scratch.
- Replacing FFmpeg with a custom media engine.
- Supporting every social network before the shared publishing interface is stable.
