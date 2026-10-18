---
phase: 01-live-spikes-build-harness
plan: 01
subsystem: testing
tags: [dotnet, net48, roslyn, csharp, python, compile-gate, cph-stub, powershell]

requires:
  - phase: none
    provides: first plan of the first phase
provides:
  - "One-command offline compile gate: python -I tools/compile_check.py (--self-test, --files, --lang)"
  - "net48 SDK-style CompileCheck.csproj parametrized by CcSource and CcLangVersion, define EXTERNAL_EDITOR"
  - "Dev-only CPH stub (IInlineInvokeProxy subset, [Serializable] CPHInlineBase) without credential-bearing members"
  - "Three self-test fixtures (good, bad_syntax CS1002, net48_gap CS0246)"
  - "tools/verify-stub.ps1 optional drift check and offline facts script (written, NOT executed)"
affects: [01-02, 01-03, 01-04, 01-05, 01-06, 01-07, phase-2, phase-3]

actuals:
  tokens: 7000
  tasks: 3
  commits: 4

tech-stack:
  added: ["Microsoft.NETFramework.ReferenceAssemblies.net48 1.0.3 (dev-time only)", "Newtonsoft.Json 13.0.3 (dev-time reference only)"]
  patterns: ["one .cs = one compilation in a private temp copy of the project", "verdict from dotnet exit code plus CS/NU/MSB codes, never message text", "#if EXTERNAL_EDITOR conditional base class header"]

key-files:
  created:
    - tools/compile_check.py
    - tools/compile-check/CompileCheck.csproj
    - tools/compile-check/Stub/CphStub.cs
    - tools/fixtures/compile/good.cs
    - tools/fixtures/compile/bad_syntax.cs
    - tools/fixtures/compile/net48_gap.cs
    - tools/verify-stub.ps1
    - tools/README.md
  modified:
    - .gitignore

key-decisions:
  - "Gate build runs in a per-run temp copy of the csproj and stub, so the repo never gets obj/ or bin/ and parallel runs do not collide"
  - "Diagnostic lines shown to the user are made repo-relative and stripped of the temp project suffix, so local absolute paths are not echoed"
  - "verify-stub.ps1 matches stub members by name, arity and CLR parameter type names, not by arity alone"

patterns-established:
  - "Offline gate verdicts are locale-independent: exit code plus CSnnnn/NUnnnn/MSBnnnn"
  - "Offline pass is documented as 'compiles against net48 refs plus stub', never as live proof"

requirements-completed: [VER-01]

duration: 35min
completed: 2026-10-18
status: complete
plan_head_before: af80be78751b5d67adc37da6b0fd383cded0a83c
plan_head_after: a6e12388aa47e947ac1bc51b7af25285d090642b
commits: 4

coverage:
  - id: D1
    description: "python -I tools/compile_check.py --self-test passes good, fails bad_syntax with CS1002 and net48_gap with CS0246 (OFFLINE result only)"
    requirement: VER-01
    verification:
      - kind: integration
        ref: "python -I tools/compile_check.py --self-test"
        status: pass
    human_judgment: false
  - id: D2
    description: "Default inputs come only from tools/packages/*.json codes[].source and tools/golden/*.cs; empty set exits 2 with 'no sources found'; bad manifest and missing source exit 2"
    requirement: VER-01
    verification:
      - kind: integration
        ref: "python -I tools/compile_check.py (wave-1 state, plus temporary manifests removed afterwards)"
        status: pass
    human_judgment: false
  - id: D3
    description: "tools/verify-stub.ps1 reports StreamerbotExiting = 707 from the 1.0.7 install and finds no stub drift"
    requirement: VER-01
    verification: []
    human_judgment: true
    rationale: "The script was written but could not be executed here: the worktree sandbox refused powershell.exe. Must be run once from the main checkout; until then it is unverified."
---

# Phase 1 Plan 01: Offline compile gate Summary

**Python-driven offline compile gate (net48 reference assemblies + Newtonsoft.Json 13.0.3 + hand-written CPH stub) that passes clean code and fails a missing semicolon with CS1002, plus an optional reflection-based stub drift script that is written but not yet run.**

## Performance

- **Duration:** about 35 min
- **Tasks:** 3 (tracer, TDD, auto)
- **Files created/modified:** 9
- **Commits:** 4 (feat, test, feat, feat)
- **Observed self-test runtime:** 3 s wall clock (start 1792318971, end 1792318974 epoch seconds) with restore and three builds, packages already in `~/.nuget/packages`; a single-file run measured 3.7 s earlier. Acceptance limit was 60 s.

## Accomplishments

- `python -I tools/compile_check.py --files tools/fixtures/compile/good.cs` prints `OK ...` and `compile_check: 1 passed, 0 failed`, exit 0, and leaves no `obj/` or `bin/` in the repo (offline result).
- `--self-test` prints `PASS self-test:good`, `PASS self-test:bad_syntax`, `PASS self-test:net48_gap` and exits 0. `--files tools/fixtures/compile/bad_syntax.cs` exits 1 and names CS1002; `net48_gap.cs` names CS0246 (offline results).
- Default inputs: no `tools/packages/*.json` and no `tools/golden/*.cs` gives `compile_check: no sources found (...)` and exit 2. Temporary manifests were used to check de-duplication, `bad manifest <path>` (exit 2) and `not found: <path>` (exit 2), then removed.
- `tools/README.md` documents the command, exit codes, locale-independent verdicts, why `-I`, source rules, inputs and a section "What an offline pass does NOT prove".

## Task Commits

1. **Task 1: tracer, good.cs compiles offline** - `95eccbe` (feat)
2. **Task 2: self-test fixtures, default inputs, README (TDD)** - RED `6427a60` (test), GREEN `9854768` (feat)
3. **Task 3: optional stub drift check and facts script** - `a6e1238` (feat)

**Plan metadata:** committed separately with this SUMMARY (docs).

## Tracer feedback gate

Mode: not auto, `human_verify_mode` = end-of-phase, tracer `<verify>` is automated-only, so the task's verify was re-run after the commit: `python -I tools/compile_check.py --files tools/fixtures/compile/good.cs` passed (exit 0, `OK ...`, no repo build output). Tracer verified end-to-end, expansion continued.

## TDD notes (Task 2)

- RED (`6427a60`): fixtures added; `python -I tools/compile_check.py --self-test` exited 2 with `unrecognized arguments: --self-test`, and the no-argument run printed `no sources given (use --files)` instead of `no sources found`. Semantic assessment: this is a command-line gate, not a unit-test runner, so no supported report format exists for `gsd_run check tdd-red-evidence`, and that classifier was NOT run. The failure is a usage error caused by the missing capability under test, which is the planned reason, but it is weaker evidence than an assertion failure. `workflow.tdd_mode` is not enabled in this project's config, so the gate classifier is not mandatory.
- GREEN (`9854768`): `--self-test` and default inputs implemented; the self-test and all Task 2 acceptance commands pass.
- No REFACTOR commit.

## Files Created/Modified

- `tools/compile_check.py` - gate driver: temp project copy, one restore, one build per source, locale-independent verdicts
- `tools/compile-check/CompileCheck.csproj` - net48 SDK-style project, LangVersion 7.3 by default, EXTERNAL_EDITOR defined
- `tools/compile-check/Stub/CphStub.cs` - dev-only `IInlineInvokeProxy` subset and `[Serializable] CPHInlineBase`; contains no credential-bearing members
- `tools/fixtures/compile/{good,bad_syntax,net48_gap}.cs` - self-test inputs
- `tools/verify-stub.ps1` - optional drift check and `-Facts`
- `tools/README.md` - documentation
- `.gitignore` - added `tools/compile-check/obj/`, `tools/compile-check/bin/`, `__pycache__/`

## Decisions Made

- Build output goes only to a per-run temp directory; the `.gitignore` entries are a safety net.
- Diagnostic lines are rewritten to repo-relative paths and lose the temp `.csproj` suffix (keeps output short and avoids echoing local absolute paths).
- `verify-stub.ps1` compares CLR parameter type names in addition to name and arity, so an overload with a changed parameter type is reported as DRIFT. This is stricter than the plan text and is untested against the real DLL (see Issues).

## Deviations from Plan

### Auto-fixed / additions

**1. [Rule 2 - Missing critical] Cleaner, safer diagnostics**
- **Found during:** Task 2 (RED run)
- **Issue:** raw MSBuild lines contained absolute local paths (including the user profile folder) and the temp project path.
- **Fix:** `diagnostic_lines` replaces the source path with its repo-relative form and strips the trailing `[...csproj]`.
- **Files modified:** tools/compile_check.py
- **Committed in:** 9854768

**2. [Plan deviation] Task 3 verification not executed**
- **Found during:** Task 3
- **Issue:** both the plan's `<automated>` command and the acceptance check run `powershell.exe`, which the worktree sandbox refused ("runs powershell in a plain command ... cannot be shown not to run git"). The same command was refused twice. I did not work around the refusal by wrapping it in another process.
- **Fix:** none possible here. The script is committed as written; only static checks were run (`! grep -qi twitch tools/verify-stub.ps1`, `grep -q verify-stub.ps1 tools/README.md`, no trailing whitespace).
- **Impact:** acceptance criteria "output contains StreamerbotExiting = 707 / StreamerbotStarted = 706 / CustomCodeEvent = 18002 / an OK line with RegisterCustomTrigger / no DRIFT line" are UNVERIFIED. The script has not been syntax-checked by PowerShell either.

**Total deviations:** 1 auto-added (Rule 2), 1 unverified task (environment restriction).
**Impact on plan:** gate (VER-01 core) is complete and verified offline; the optional drift script needs one run by a human or the orchestrator.

## Issues Encountered

- `-Facts` output lines (enum values and file versions) required by the plan's SUMMARY spec are NOT available, because the script could not run here. Do not copy any value into FINDINGS.md until it has been produced by a real run. To close this gap, run from the repo root of the merged checkout: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/verify-stub.ps1 -StreamerBotDir "D:/Users/qu1ck1y/Documents/tw/StreamerBot" -Facts`.
- If that run prints a `DRIFT ... parameter types differ` line, first suspect the script's type-name normalization (generic arity, `out T`, arrays), not the stub; the stub was written to match the member list in RESEARCH Pattern 3 exactly.

## Known Stubs

None. (`CphStub.cs` is a deliberate dev-only stub; its getters return null by design and it is never shipped.)

## Threat Flags

None beyond the plan's threat model. T-01-01 mitigated and checked (`! grep -qi twitch` on the stub); T-01-02 mitigated (README section "What an offline pass does NOT prove"); T-01-03 mitigated by design in the script but not exercised; T-01-SC: packages restored from the existing local NuGet cache at the pinned versions, no new install was performed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plans 01-03 to 01-07 can call `python -I tools/compile_check.py` once they add `tools/packages/*.json` or `tools/golden/*.cs`.
- Open item for the orchestrator: run `tools/verify-stub.ps1 -Facts` once in the merged checkout and confirm no DRIFT.
- Language version stays 7.3 until live finding F6.

## Self-Check: PASSED

All nine listed files exist, the four commits (`95eccbe`, `6427a60`, `9854768`, `a6e1238`) are ancestors of HEAD, and `git status --short` was clean after the last task commit. This check covers the committed files and the offline gate only; Task 3's runtime behavior is explicitly unverified, as stated above.

---
*Phase: 01-live-spikes-build-harness*
*Completed: 2026-10-18*
