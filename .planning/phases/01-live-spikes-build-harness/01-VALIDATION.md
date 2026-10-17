---
phase: "1"
slug: "live-spikes-build-harness"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-17"
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` (stdlib) for builder/tools; the compile gate's own `--self-test` for VER-01 |
| **Config file** | none (`tools/tests/__init__.py` required — Wave 0 creates it) |
| **Quick run command** | `python -I tools/compile_check.py --self-test` |
| **Full suite command** | `python -I tools/compile_check.py && python -I -m unittest discover -s tools/tests -t tools && python -I tools/build_sb.py build spike --check && python -I tools/check_findings.py docs/live-spikes/FINDINGS.md` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -I tools/compile_check.py --self-test` (plus the unit suite once it exists)
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green; live items stay `not verified` unless the user confirmed them
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

Filled by the planner (2026-10-17). Executors update Status.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-T1 | 01-01 | 1 | VER-01 | T-01-01 | Stub has no credential-bearing members | tracer (gate on good.cs) | `python -I tools/compile_check.py --files tools/fixtures/compile/good.cs` | ❌ W0 | ⬜ pending |
| 01-01-T2 | 01-01 | 1 | VER-01 | T-01-02 | README states what an offline pass cannot prove | self-test | `python -I tools/compile_check.py --self-test` | ❌ W0 | ⬜ pending |
| 01-01-T3 | 01-01 | 1 | VER-01 | T-01-03 | Reflection-only metadata, no data/ access | script | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/verify-stub.ps1 -StreamerBotDir "D:/Users/qu1ck1y/Documents/tw/StreamerBot" -Facts` | ❌ W0 | ⬜ pending |
| 01-02-T1 | 01-02 | 1 | PKG-04 | T-01-06 | Strict codec, json.loads only | tracer + unit | `python -I -m unittest discover -s tools/tests -t tools -p "test_build_sb.py"` | ❌ W0 | ⬜ pending |
| 01-02-T2 | 01-02 | 1 | PKG-04 | T-01-05 | Bounded decode; cap, trailing data, truncation rejected | unit | `python -I -m unittest discover -s tools/tests -t tools -p "test_build_sb.py"` | ❌ W0 | ⬜ pending |
| 01-02-T3 | 01-02 | 1 | PKG-04 | T-01-07, T-01-08 | Audit masks secrets, flags patterns and structure | unit | `python -I -m unittest discover -s tools/tests -t tools -p "test_build_sb.py"` | ❌ W0 | ⬜ pending |
| 01-03-T1 | 01-03 | 2 | PKG-04, VER-03 | T-01-11 | Recipe keeps backups outside the repo | tracer (gate on GoldenRuntime.cs) | `python -I tools/compile_check.py --files tools/golden/GoldenRuntime.cs` | ❌ W0 | ⬜ pending |
| 01-03-T2 | 01-03 | 2 | PKG-04 | T-01-09, T-01-10 | Golden has no secrets (audit exit 0) | human-action + audit | `python -I tools/build_sb.py audit tools/golden/golden-1.0.7.sb` | ❌ W0 (needs user export) | ⬜ pending |
| 01-03-T3 | 01-03 | 2 | PKG-04 | T-01-09 | Human approval before commit (blocking-human) | decision | (manual: user chooses commit / re-export) | n/a | ⬜ pending |
| 01-04-T1 | 01-04 | 2 | VER-03 | T-01-14 | No account name, credential members or exception messages logged | tracer (gate on spike) | `python -I tools/compile_check.py --files spike/DaSpikeA.cs spike/DaSpikeB.cs` | ❌ W0 | ⬜ pending |
| 01-04-T2 | 01-04 | 2 | VER-03 | T-01-13, T-01-15 | Loopback-only listeners; repro isolated from Dispose | gate + source checks | `python -I tools/compile_check.py --files spike/DaSpikeA.cs spike/DaSpikeB.cs` | ❌ W0 | ⬜ pending |
| 01-05-T1 | 01-05 | 3 | PKG-04 | T-01-17 | Sources only from the manifest inside the repo | tracer (build + check) | `python -I tools/build_sb.py build spike --check` | ❌ W0 | ⬜ pending |
| 01-05-T2 | 01-05 | 3 | PKG-04 | T-01-20 | No invented keys; no dangling refs | check + audit | `python -I tools/build_sb.py build spike --check` / `python -I tools/build_sb.py audit dist/spike.sb` | ❌ W0 | ⬜ pending |
| 01-05-T3 | 01-05 | 3 | PKG-04 | T-01-20 | Mutations detected; golden fidelity | unit | `python -I -m unittest discover -s tools/tests -t tools -p "test_build_sb.py"` | ❌ W0 | ⬜ pending |
| 01-06-T1 | 01-06 | 3 | VER-03 | T-01-22 | Live statuses need evidence + user confirmation | tracer + script | `python -I tools/check_findings.py docs/live-spikes/FINDINGS.md` | ❌ W0 | ⬜ pending |
| 01-06-T2 | 01-06 | 3 | VER-03 | T-01-21 | Evidence prints masked markers only; never opens data/ | unit | `python -I -m unittest discover -s tools/tests -t tools -p "test_live_tools.py"` | ❌ W0 | ⬜ pending |
| 01-07-T1 | 01-07 | 4 | VER-03, PKG-04 | T-01-25 | Pre-flight: package identity pinned | tracer (full pipeline) | `python -I tools/build_sb.py build spike --check` | ❌ W0 | ⬜ pending |
| 01-07-T2 | 01-07 | 4 | VER-03 | T-01-24, T-01-26, T-01-27 | User does not paste logs; S6 last; re-export stays in dist/ | human-action (live) | (manual: RUNSHEET S0-S7, E3, F6) | n/a | ⬜ pending |
| 01-07-T3 | 01-07 | 4 | VER-03 | T-01-25 | Findings honesty gate passes | script | `python -I tools/check_findings.py docs/live-spikes/FINDINGS.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tools/compile_check.py`, `tools/compile-check/CompileCheck.csproj`, `tools/compile-check/Stub/CphStub.cs`, `tools/fixtures/compile/{good,bad_syntax,net48_gap}.cs`
- [ ] `tools/build_sb.py`, `tools/packages/spike.json`, `tools/tests/__init__.py`, `tools/tests/test_build_sb.py`
- [ ] `tools/golden/{RECIPE.md,GoldenRuntime.cs}`, then the user's `golden-1.0.7.sb`
- [ ] `spike/DaSpikeA.cs`, `spike/DaSpikeB.cs`
- [ ] `tools/live_evidence.py`, `tools/check_findings.py`, `docs/live-spikes/{RUNSHEET.md,FINDINGS.md}`
- [ ] `.gitignore` additions, `.gitattributes`
- Framework install: none beyond the one-time `dotnet restore`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Golden `.sb` exported from Streamer.bot 1.0.7 | PKG-04 | Only the user's live Streamer.bot can export it | Follow `tools/golden/RECIPE.md`, export, then run `build_sb.py audit` and review |
| Spike `.sb` imports and compiles without errors; custom trigger and Execute C# Method bind and run (SC3) | VER-03 | Requires live Streamer.bot 1.0.7 | `docs/live-spikes/RUNSHEET.md` steps S1–S3; user confirms |
| Clean exit with cancel-on-Dispose (SC4) | VER-03 | Requires closing live Streamer.bot | RUNSHEET S4; `python -I tools/live_evidence.py --sb-dir <dir> --after-close`; user confirms no `Streamer.bot.exe` remains |
| Deliberate old shutdown-hang repro (SC4) | VER-03 | Requires live Streamer.bot | RUNSHEET S6 (last); same helper; user confirms |
| Findings F1–F9 marked `verified live` | VER-03 | Live-only outcomes | Each live status needs evidence + "user YYYY-MM-DD" confirmation |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
