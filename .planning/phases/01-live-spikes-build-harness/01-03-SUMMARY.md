---
phase: 01-live-spikes-build-harness
plan: 03
subsystem: testing
tags: [streamer.bot, sb-format, golden-export, audit, csharp, russian-recipe]

requires:
  - phase: 01-live-spikes-build-harness
    provides: "01-01 compile gate (compile_check.py), 01-02 build_sb.py audit/check/decode"
provides:
  - "tools/golden/GoldenRuntime.cs: tiny runtime that registers Golden: Event and fires goldenEvent (offline compile gate passes)"
  - "tools/golden/RECIPE.md: Russian step list for the golden export"
  - "tools/golden/golden-1.0.7.sb: the user's real Streamer.bot 1.0.7 export (version 24), audited, user-approved, committed"
  - "First live observations: F1 (no Exiting trigger in picker), F5 (If/Else results, confounded), E8 (no action-level description key)"
affects: [01-04, 01-05, 01-06, 01-07, phase-6]

actuals:
  tokens: 3500
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Golden .sb is the only schema authority for the builder; committed alone, by explicit path, after audit exit 0 and a blocking-human look"

key-files:
  created:
    - tools/golden/GoldenRuntime.cs
    - tools/golden/RECIPE.md
    - tools/golden/golden-1.0.7.sb
  modified: []

key-decisions:
  - "User chose `commit` at the blocking-human checkpoint; the golden was committed alone"
  - "RECIPE.md corrected after the live session: Log is at Core > Misc > Log (level Information); optional step 7 flagged as unclear for the 1.0.7 UI"

requirements-completed: [PKG-04, VER-03]

plan_head_before: 0b0a1c29ba972cde1a2919aa0c27ace3197f32d3
plan_head_after: 6fe7d3fd0580500080061b16cf7ed53f5be9d220
commits: 3

coverage:
  - id: D1
    description: "GoldenRuntime.cs compiles offline against net48 refs plus the CPH stub (OFFLINE result only)"
    requirement: VER-03
    verification:
      - kind: integration
        ref: "python -I tools/compile_check.py --files tools/golden/GoldenRuntime.cs"
        status: pass
    human_judgment: false
  - id: D2
    description: "Golden export from the user's Streamer.bot 1.0.7 is stored in the repo after audit exit 0 and explicit user approval"
    requirement: PKG-04
    verification:
      - kind: integration
        ref: "python -I tools/build_sb.py audit tools/golden/golden-1.0.7.sb (exit 0, 0 hard); check (0 failed)"
        status: pass
    human_judgment: true
    rationale: "Absence of unwanted values was judged by the user at the blocking-human checkpoint; the audit regexes only reduce the risk"
  - id: D3
    description: "Live observations from the golden session (F1, F5, E8) recorded verbatim for 01-07"
    requirement: VER-03
    verification: []
    human_judgment: true
    rationale: "Observations come from the user's own Streamer.bot session and cannot be reproduced by automation here"

duration: not measured (spans two user round trips)
completed: 2026-10-18
status: complete
---

# Phase 1 Plan 03: Golden export Summary

**The user's real Streamer.bot 1.0.7 export (`golden-1.0.7.sb`, format version 24) is in the repo after a clean audit (0 hard) and an explicit `commit` decision, together with a compile-checked golden runtime, a Russian recipe, and the first live observations (no Exiting trigger in the picker, If/Else results confounded by input format, no action-level description key).**

## Performance

- **Tasks:** 3 (tracer, human-action, blocking-human decision)
- **Files created:** 3 (`GoldenRuntime.cs`, `RECIPE.md`, `golden-1.0.7.sb`)
- **Duration:** not measured; two user round trips took place between tasks

## Accomplishments

- `tools/golden/GoldenRuntime.cs` compiles with `python -I tools/compile_check.py --files tools/golden/GoldenRuntime.cs` (`OK`, exit 0). Offline result only. In the live session the user's pasted log shows `GOLDEN PING {"ping":1} http=HttpClient` and `GOLDEN FIRE`, so the code compiled and ran in Streamer.bot 1.0.7 (reported by the user).
- `tools/golden/RECIPE.md` (Russian) pins every action, queue, Log text and export metadata.
- `tools/golden/golden-1.0.7.sb` (3652 bytes) passes `audit` (exit 0) and `check`, was reviewed by the user, and is committed alone.
- The decoded `byteCode` of `GoldenRuntime` equals `tools/golden/GoldenRuntime.cs` after line-ending normalization (the export embeds CRLF).

## Task Commits

1. **Task 1: GoldenRuntime.cs + Russian recipe (tracer)** - `230d6c8` (feat)
   - Recipe fix after the live session (Log path, step 7 note) - `4647c26` (docs)
2. **Task 2: User exports the golden** (human-action) - no commit by design
3. **Task 3: User approves committing the golden** (blocking-human; user typed `commit`) - `6fe7d3f` (feat). `git ls-files tools/golden/golden-1.0.7.sb` prints the path and `git show --name-only --format= HEAD` listed only that file.

**Plan metadata:** committed separately with this SUMMARY (docs).

## Tracer feedback gate

Mode `end-of-phase`, tracer `<verify>` automated-only: re-ran `python -I tools/compile_check.py --files tools/golden/GoldenRuntime.cs` after the commit, it passed, and execution continued to the checkpoints.

## Audit and check results (golden-1.0.7.sb)

Audit INFO lines:

- `version=24 exportedFrom=1.0.7 minimumVersion=1.0.0-alpha.1`
- `meta.name=DA Golden`
- `actions=3 GOLDEN | Call; GOLDEN | Runtime; SPIKE | On event (dict)`
- `subActionTypes=120,1020,99901,99902,99998,99999`
- `triggerTypes=706,18002`

Audit REVIEW lines: `meta.author=streamer.bot-donationAlerts`, `queue=Golden Queue`, and 139 unknown-key notices (the builder's seed key sets cover only a few kinds). Unique unknown keys: queue `id, blocking, name`; trigger 706 `id, type, enabled, exclusions`; trigger 18002 `name, eventName` plus those four; sub-action 99998 `executeCodeId, method, runOnUiThread, saveResultToVariable, saveToVariable` plus base keys; sub-action 1020 `logLevel, message` plus base keys; sub-actions 99901/99902 `random, subActions` plus base keys. Final line: `audit: 0 hard, 141 review` (exit 0).

Check lines (exit 0):

- `PASS check:roundtrip`
- `PASS check:utf8-no-bom`
- `PASS check:ids-format`
- `PASS check:ids-unique`
- `PASS check:refs-resolve`
- `PASS check:bytecode-utf8`
- `check: 0 failed`

Structure read from the decoded JSON (outside the repo): commands, websocketServers, websocketClients and timers are empty; one queue `Golden Queue` (`blocking: true`); the `references` of the code sub-action are `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\mscorlib.dll`, `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\System.Net.Http.dll` and `.\Newtonsoft.Json.dll`; no user-profile paths, no Send Message, no Play Sound (step 7 was not done).

## Live observations (golden session)

User's step-9 report (facts as relayed by the coordinator; log lines verbatim):

1. Streamer.bot version shown in the app: 1.0.7.
2. Trigger "Streamer.bot Exiting" in the trigger list: NO. `GOLDEN | Call` has only the Started trigger (finding F1 data: the EventType enum has `StreamerbotExiting = 707` per offline reflection in RESEARCH, but the picker did not offer it).
3. Action Description field: the user's answer was ambiguous ("да/нет"). User answer ambiguous; decoded file shows no `description` key on any of the 3 actions (action keys are only `alwaysRun, collapsedGroups, concurrent, enabled, excludeFromHistory, excludeFromPending, group, id, name, queue, randomAction, subActions, triggers`). A `description` key appears only on the code sub-action (type 99999, value `golden runtime`). E8 input for 01-07: no action-level description in the 1.0.7 export.
4. Log pasted by the user (verbatim):

```text
[2026-10-18 13:51:23.677 INF] GOLDEN PING {"ping":1} http=HttpClient
[2026-10-18 13:51:23.678 DBG] InlineCode :: Running 'GoldenFire' entry point from instance 'e08e2a62-cbf7-44bf-86b6-8ebd941e8595'
[2026-10-18 13:51:23.686 DBG] ActionDispatcher :: Queueing 'SPIKE | On event (dict)' (1f1e1fde-6e2e-4cc5-b0ac-5f8c430ef5e5, CustomCodeEvent) to 'Golden Queue' (f1802ee5-fe9b-4d5f-881e-4057114f3306), with 14 arguments
[2026-10-18 13:51:23.686 DBG] ActionQueue :: 'Golden Queue' (f1802ee5-fe9b-4d5f-881e-4057114f3306) :: Enqueue action 1f1e1fde-6e2e-4cc5-b0ac-5f8c430ef5e5
[2026-10-18 13:51:23.687 DBG] ActionQueue :: 'Golden Queue' (f1802ee5-fe9b-4d5f-881e-4057114f3306) :: Handling queue
[2026-10-18 13:51:23.687 INF] GOLDEN FIRE
[2026-10-18 13:51:23.687 DBG] ActionQueue :: 'Golden Queue' (f1802ee5-fe9b-4d5f-881e-4057114f3306) :: Performing blocking 'SPIKE | On event (dict)' (1f1e1fde-6e2e-4cc5-b0ac-5f8c430ef5e5, 6f1918ea-77dc-4073-be3d-899de7b92dc9)
[2026-10-18 13:51:23.701 INF] SPIKE ARGS amount=22,5 count=7 flag=True text=x
[2026-10-18 13:51:23.707 INF] SPIKE IF-GT PASS
[2026-10-18 13:51:23.707 INF] SPIKE IF-EQ FAIL
[2026-10-18 13:51:23.707 INF] SPIKE IF-BOOL FAIL
```

5. Step 7 (`GOLDEN | Examples`): NOT done. The user found it unclear: no "Comment" sub-action visible in the picker, and the Send Message target was unclear. RECIPE step 7 wording was unclear for the 1.0.7 UI (a note was added to RECIPE.md in `4647c26`). The golden therefore has no Comment, Send Message, range If/Else or Play Sound example kinds; Phase 6 will need them from another source.

Extra UI facts from the user: the Log sub-action is at Core > Misc > Log (not Core > Logging > Log); log level chosen: Information (decoded `logLevel` is 2).

Observations only, not conclusions (for 01-06/01-07):

- A custom code event fired from `GoldenFire` reached the `Golden Queue` action with 14 arguments (user's log).
- The decimal rendered as `22,5` in the Log text (ru culture); `spikeCount` and `spikeFlag` rendered as `7` and `True`.
- F5 is CONFOUNDED. The decoded If/Else sub-actions show `input` values `spikeAmount.` (with a trailing dot, likely a typo, operation 5, value `20`), `spikeAmount` (operation 0, value `22.5`) and `spikeFlag` (operation 0, value `True`), all written without `%` signs, `autoType: true`. The inputs may therefore have been compared as literal text, not as the argument values. The results `IF-GT PASS / IF-EQ FAIL / IF-BOOL FAIL` do not show how Streamer.bot compares a decimal or a bool argument. Needs a re-test with `%spikeAmount%`-style inputs (and the comparison-value format, e.g. `22,5` vs `22.5`) in the 01-06 session; 01-07 must not write an F5 status from these three lines alone.

## Files Created/Modified

- `tools/golden/GoldenRuntime.cs` - golden runtime (Init registers `Golden: Event`; `GoldenPing`, `GoldenFire`, `Execute`, `Dispose`)
- `tools/golden/RECIPE.md` - Russian recipe, steps 0-10
- `tools/golden/golden-1.0.7.sb` - the user's real 1.0.7 export; `.gitattributes` has `*.sb -text`

## Decisions Made

- The golden was committed only after audit exit 0 and the user's explicit `commit`.
- Key names for Execute C# Method (99998: `executeCodeId, method, runOnUiThread, saveResultToVariable, saveToVariable`) and the custom code event trigger (18002: `name, eventName`) are now read from the golden, which settles assumption A4 for key names. Whether the trigger works as the spike expects is a live matter in later plans.
- If/Else shape in 1.0.7: type 120 with `input, operation, value, autoType, subActions`, containing two branch containers, 99901 (then) at index 0 and 99902 (else) at index 1, each with `random, subActions`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Recipe named the wrong menu path for Log**
- **Found during:** Task 2 (user report)
- **Issue:** RECIPE.md said Core > Logging > Log; in 1.0.7 it is Core > Misc > Log.
- **Fix:** Corrected the path and added the Information level; added a note that optional step 7 was unclear.
- **Files modified:** tools/golden/RECIPE.md
- **Committed in:** 4647c26

**Total deviations:** 1 auto-fixed (Rule 1). **Impact on plan:** none on the golden or the findings.

## Issues Encountered

- Step 7 and the Description-field question were not answered cleanly by the user (see observations above). The decoded file was used instead of the answer for E8.
- The If/Else inputs in the golden lack `%` signs and one has a stray dot (see F5). The file was committed as the user approved it; the builder uses it as a format template, not as test evidence.
- Carried over from 01-01: `tools/verify-stub.ps1` is STILL UNEXECUTED (the sandbox refused powershell.exe). `-Facts` values and the stub drift check remain unverified until someone runs `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/verify-stub.ps1 -StreamerBotDir <Streamer.bot folder> -Facts` from the merged checkout.
- The shell wrapper refused compound git commands in the worktree, so git calls were run as plain separate commands.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-01-09 mitigated (audit exit 0, blocking-human look, single-file pathspec commit); T-01-10 mitigated (read through the bounded decoder); T-01-12 mitigated (decoded JSON written only to the session scratchpad).

## User Setup Required

None. The user keeps the `GOLDEN |` and `SPIKE |` actions in Streamer.bot until the 01-06 run sheet says to delete them.

## Next Phase Readiness

- 01-05 can read templates from `tools/golden/golden-1.0.7.sb`. `GOLDEN | Examples` is absent, which the plan allows (optional).
- 01-06/01-07: F1 (no Exiting trigger in the picker) and E8 (no action-level description) have first observations; F5 needs a re-test with corrected inputs.

## Self-Check: PASSED

- Files exist: `tools/golden/GoldenRuntime.cs`, `tools/golden/RECIPE.md`, `tools/golden/golden-1.0.7.sb`.
- Commits `230d6c8`, `4647c26`, `6fe7d3f` are ancestors of HEAD; `git rev-list --count 0b0a1c2..HEAD` was 3 before this SUMMARY.
- `python -I tools/build_sb.py audit tools/golden/golden-1.0.7.sb` re-run after the commit: `audit: 0 hard, 141 review`.

---
*Phase: 01-live-spikes-build-harness*
*Completed: 2026-10-18*
