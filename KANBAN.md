# ViralCutter Agentic Kanban Board

## Board Rules

- Every work item must reference a Goal ID from `GOAL.md`.
- An agent may own no more than one P0/P1 implementation item at a time.
- A task cannot move to **Done** until its acceptance criteria and tests pass.
- Blocked tasks must state a concrete blocker and the goal or decision required to unblock them.
- Agents must avoid editing the same high-conflict file in parallel unless ownership is coordinated.
- `webui/app.py`, `main_improved.py`, and project schema files are high-conflict areas.

## Status Legend

| Status | Meaning |
|---|---|
| Done | Implemented, tested, documented, and accepted |
| In Progress | Actively owned by an agent |
| Review | Implementation finished and awaiting review or smoke test |
| Ready | Well-defined and unblocked |
| Backlog | Planned but not ready to start |
| Blocked | Cannot proceed until a dependency or decision is resolved |

## Priority Legend

| Priority | Meaning |
|---|---|
| P0 | Critical reliability, security, or regression prevention |
| P1 | Major product capability |
| P2 | Important quality, UX, or maintainability improvement |
| P3 | Experimental or ecosystem expansion |

## Completed Baseline

| ID | Capability | Status | Evidence / Expected Result |
|---|---|---|---|
| BASE-001 | WhisperX language selector | Done | Auto detection and forced language selection are available |
| BASE-002 | Editable AI prompt template | Done | WebUI can load, edit, and save prompt templates |
| BASE-003 | Runtime Doctor | Done | Python, CUDA, GPU, WhisperX stack, FFmpeg, and media checks are available |
| BASE-004 | Transcription presets | Done | Fast Test, Balanced, Accurate, and Custom presets are available |
| BASE-005 | Pipeline progress display | Done | Stage index, percentage, and elapsed time are displayed |
| BASE-006 | Configurable watermark | Done | Watermark can be enabled and positioned by the user |
| BASE-007 | Sentence-aware timing refinement | Done | Pre-roll, post-roll, overlap handling, and sentence snapping are available |
| BASE-008 | Face mode None | Done | Source framing can be preserved without face reframing |
| BASE-009 | Compilation and ordering | Done | Clips can be reordered and compiled |
| BASE-010 | Comprehensive WebUI logs | Done | Project logs contain configuration, stages, command, and process output |

## Active Roadmap Board

| Card | Goal | Work Item | Priority | Status | Suggested Agent | Dependencies | Primary Deliverable | Acceptance Summary |
|---|---|---|---|---|---|---|---|---|
| VC-001 | G-001 | Document the canonical pipeline contract and project directory schema | P0 | Ready | Architect | None | `docs/PIPELINE_CONTRACT.md` | CLI, WebUI, files, and stages have one documented contract |
| VC-002 | G-001 | Add WebUI-to-function-to-CLI contract tests | P0 | Ready | QA | VC-001 | Callback contract test suite | Positional input/output mismatches fail in tests |
| VC-003 | G-001 | Rename ambiguous AI and Whisper chunk-size fields internally | P1 | Backlog | Developer | VC-001 | Clear configuration names | No shared or ambiguous `chunk_size` meaning |
| VC-004 | G-013 | Centralize command and secret redaction | P0 | Ready | Security Reviewer | None | Redaction utility | API keys and tokens never appear in logs |
| VC-005 | G-013 | Add project-root path containment and filename validation | P0 | Ready | Developer | VC-001 | Safe path utility | Project paths cannot escape `VIRALS_DIR` |
| VC-006 | G-014 | Establish core test layout and CI smoke checks | P0 | Ready | QA | None | `tests/` and CI workflow | Syntax, unit tests, and callback contracts gate merges |
| VC-007 | G-002 | Define versioned `project_state.json` schema | P1 | Ready | Architect | VC-001 | State schema | All stages and transitions are represented |
| VC-008 | G-002 | Implement atomic state read/write and transition validation | P1 | Backlog | Developer | VC-007 | `scripts/pipeline_state.py` | Interrupted writes cannot corrupt project state |
| VC-009 | G-002 | Add resume and retry controls to Library | P1 | Backlog | Frontend Developer | VC-008 | Resume UI | User can continue from the last valid stage |
| VC-010 | G-002 | Add dependency-based downstream invalidation | P1 | Backlog | Developer | VC-008 | Invalidation engine | Editing a stage invalidates only required downstream work |
| VC-011 | G-009 | Move prompt and subtitle config to project `.runtime/` | P1 | Ready | Developer | VC-005 | Project-scoped runtime files | Projects cannot overwrite shared temporary files |
| VC-012 | G-009 | Replace global process state with project job registry | P1 | Backlog | Backend Developer | VC-008, VC-011 | `webui/jobs.py` | Jobs can be inspected and stopped per project |
| VC-013 | G-009 | Add stale PID and abandoned-job recovery | P1 | Backlog | Backend Developer | VC-012 | Recovery logic | Restarted Colab sessions recover stale states safely |
| VC-014 | G-010 | Define structured JSON pipeline event schema | P2 | Backlog | Architect | VC-001, VC-007 | Event schema | Progress no longer depends on translated log text |
| VC-015 | G-010 | Emit structured events from all major pipeline stages | P2 | Backlog | Developer | VC-014 | Event emitters | Every stage reports start, progress, completion, and failure |
| VC-016 | G-010 | Add stage ETA based on runtime history | P2 | Backlog | Data/Backend Agent | VC-015 | ETA service | ETA is displayed as an estimate and improves over time |
| VC-017 | G-003 | Define candidate and approved-segment schemas | P1 | Backlog | Architect | VC-007 | JSON schemas | Raw candidates and approved segments are separated |
| VC-018 | G-003 | Implement candidate manager validation and persistence | P1 | Backlog | Developer | VC-017 | `scripts/candidate_manager.py` | Candidate edits, selection, and order are validated |
| VC-019 | G-003 | Build Segment Review table and edit controls | P1 | Backlog | Frontend Developer | VC-018 | `webui/review.py` | User can approve, reject, edit, and reorder candidates |
| VC-020 | G-003 | Add lightweight per-candidate preview rendering | P1 | Backlog | Media Developer | VC-018 | Preview generator | Candidate can be reviewed before final rendering |
| VC-021 | G-003 | Add Approve and Continue workflow transition | P1 | Backlog | Backend Developer | VC-009, VC-019 | Review gate | Rendering starts only from approved segments |
| VC-022 | G-004 | Add candidate multiplier controls | P2 | Backlog | Developer | VC-018 | Candidate expansion | Requested final count can generate a larger candidate pool |
| VC-023 | G-004 | Add explainable score breakdown | P2 | Backlog | AI Developer | VC-018 | Scoring module | Every candidate includes deterministic scoring components |
| VC-024 | G-004 | Add speech density, silence, duration, face, and motion signals | P2 | Backlog | AI/Media Agent | VC-023 | Signal extractors | Candidate ranking uses multiple measurable signals |
| VC-025 | G-005 | Add cached scene detection stage | P2 | Backlog | Media Developer | VC-007 | `scripts/scene_analysis.py` | Scene boundaries are reusable and project-scoped |
| VC-026 | G-005 | Implement Smart Hybrid boundary resolver | P2 | Backlog | Algorithm Developer | VC-018, VC-025 | Boundary resolver | Sentence, scene, duration, and overlap constraints are respected |
| VC-027 | G-005 | Add boundary comparison and restore controls | P2 | Backlog | Frontend Developer | VC-019, VC-026 | Review timing UI | Original and refined timing can be compared and restored |
| VC-028 | G-006 | Audit and harden existing watermark implementation | P1 | Ready | Reviewer | BASE-006, VC-006 | Watermark regression tests | Position, scale, opacity, and safe-area behavior are reliable |
| VC-029 | G-006 | Define reusable brand preset schema | P1 | Ready | Architect | VC-001 | Brand preset schema | Watermark and outro configuration can be reused |
| VC-030 | G-006 | Add watermark safe-area preview | P1 | Backlog | Frontend Developer | VC-028, VC-029 | Branding preview | User sees likely platform UI overlap before rendering |
| VC-031 | G-006 | Implement image, video, and generated-card outro | P1 | Ready | Media Developer | VC-029 | `scripts/append_outro.py` | Outro sources are normalized and appended safely |
| VC-032 | G-006 | Add per-clip and compilation-only outro modes | P1 | Backlog | Developer | VC-031 | Outro workflow controls | Outro placement matches selected mode exactly |
| VC-033 | G-006 | Add branding invalidation rules to project state | P1 | Backlog | Backend Developer | VC-010, VC-029 | State integration | Branding edits rerun only branding and downstream outputs |
| VC-034 | G-007 | Define platform export preset schema | P1 | Ready | Architect | VC-029 | `scripts/platform_presets.py` | TikTok, Reels, Shorts, and Generic presets are versioned |
| VC-035 | G-007 | Implement media validation report | P1 | Backlog | Media Developer | VC-034 | `scripts/validate_publish_media.py` | Blocking errors and recommendations are distinguished |
| VC-036 | G-007 | Add platform safe-area overlays | P2 | Backlog | Frontend Developer | VC-030, VC-034 | Preview overlays | Users can preview title, caption, and button collision zones |
| VC-037 | G-008 | Implement project ZIP allowlist exporter | P1 | Ready | Developer | VC-004, VC-005 | `webui/project_export.py` | Missing optional files are skipped and secrets are excluded |
| VC-038 | G-008 | Add export manifest and missing-item report | P1 | Backlog | Developer | VC-037 | `export_manifest.json` | Every ZIP describes what was included or absent |
| VC-039 | G-008 | Add Download Project ZIP action to Library | P1 | Ready | Frontend Developer | VC-037 | Library export control | Selected project can be downloaded from WebUI |
| VC-040 | G-011 | Define publishing adapter interface and history schema | P2 | Backlog | Architect | VC-034, VC-004 | Base publishing contract | Platform adapters share lifecycle and status handling |
| VC-041 | G-011 | Implement YouTube account connection | P2 | Backlog | Integration Developer | VC-040, VC-013 | OAuth connection | Account identity and token lifecycle are handled safely |
| VC-042 | G-011 | Implement resumable YouTube upload and status tracking | P2 | Backlog | Integration Developer | VC-035, VC-041 | YouTube publisher | Upload can resume or retry without rerendering |
| VC-043 | G-012 | Implement TikTok publishing adapter | P3 | Backlog | Integration Developer | VC-040, VC-042 | TikTok adapter | User-confirmed posting and status tracking work |
| VC-044 | G-012 | Implement Instagram publishing adapter | P3 | Backlog | Integration Developer | VC-040, VC-042 | Instagram adapter | Hosted-media workflow and processing status are handled |
| VC-045 | G-015 | Split `webui/app.py` into focused feature modules | P2 | Backlog | Refactor Agent | VC-006 | Modular WebUI | Features have clear ownership and lower merge conflicts |
| VC-046 | G-015 | Reorganize Create New into progressive sections | P2 | Backlog | UX Developer | VC-045 | Improved information architecture | Default workflow is simple; advanced controls remain available |
| VC-047 | G-015 | Add accessibility and responsive-layout checks | P2 | Backlog | QA/UX Agent | VC-046 | Accessibility checklist | Keyboard, labels, contrast, and narrow layouts are tested |
| VC-048 | G-016 | Update installation and Colab documentation | P2 | Ready | Documentation Agent | None | Installation guide | Clean runtime installation is reproducible |
| VC-049 | G-016 | Document project state, candidates, branding, export, and publishing | P2 | Backlog | Documentation Agent | Related feature goals | Feature documentation | Schemas and workflows are understandable to users and agents |
| VC-050 | G-016 | Add changelog and release checklist | P2 | Ready | Release Agent | VC-006 | `CHANGELOG.md` and release guide | Releases consistently report changes and test status |

## Recommended Next Sprint

### Sprint Objective

Create the foundation for larger multi-agent development while delivering a visible branding/export improvement.

| Order | Card | Reason |
|---:|---|---|
| 1 | VC-006 | Prevent new agent work from silently breaking existing features |
| 2 | VC-001 | Establish one stable pipeline and project contract |
| 3 | VC-004 | Protect logs and future publishing credentials |
| 4 | VC-011 | Remove shared temporary-file conflicts |
| 5 | VC-029 | Define reusable branding data before adding outro behavior |
| 6 | VC-031 | Deliver the next visible feature: configurable outro |
| 7 | VC-037 | Make project backup safe and deterministic |
| 8 | VC-039 | Expose ZIP export in the Library UI |

## Suggested Agent Ownership

| Agent | Primary Responsibilities | Avoid Parallel Ownership With |
|---|---|---|
| Orchestrator | Dependencies, task assignment, branch strategy, acceptance tracking | None |
| Architect | Schemas, contracts, state transitions, module boundaries | Another architect editing the same schema |
| Developer | Backend implementation and file operations | Another developer in the same module |
| Media Developer | FFmpeg, scene detection, outro, validation, preview rendering | Other media work touching the same render stage |
| Frontend Developer | Gradio components, state binding, callback contracts | Refactor agent editing `webui/app.py` |
| AI Developer | Candidate generation, ranking, scoring signals | Prompt/schema changes without architect coordination |
| Integration Developer | OAuth, platform publishing, upload status | Security-sensitive work without security review |
| QA | Unit, integration, smoke, regression, and callback tests | None; QA may review all cards |
| Security Reviewer | Secrets, path safety, exports, OAuth storage | None; security review is cross-cutting |
| Documentation Agent | User guides, schema docs, migration notes, changelog | None |
| Reviewer | Code review, scope control, regression detection | Must not approve own implementation alone |

## Definition of Ready

A card may move from **Backlog** to **Ready** when:

- Goal and expected outcome are clear.
- Dependencies are complete or explicitly mocked.
- Files likely to change are identified.
- Acceptance criteria are testable.
- Security and migration impact are understood.
- Ownership does not conflict with another active card.

## Definition of Done

A card may move to **Done** when:

- Implementation is complete.
- Acceptance criteria pass.
- Automated tests pass.
- Colab smoke test is documented when relevant.
- No credentials or private data are exposed.
- Documentation is updated.
- Reviewer approval is recorded.
- `GOAL.md` and `KANBAN.md` remain consistent with the delivered behavior.
