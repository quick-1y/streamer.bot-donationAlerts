---
phase: 01-live-spikes-build-harness
plan: 04
subsystem: testing
tags: [csharp, streamer-bot, cph, spike, httplistener, tcplistener, cancellation, appdomain, compile-gate]

requires:
  - phase: 01-live-spikes-build-harness
    provides: "01-01 offline compile gate (tools/compile_check.py) and CPH stub"
provides:
  - "spike/DaSpikeA.cs: cancel-on-Dispose spike host with 23 public bool probes plus Init/Dispose (compiles offline at LangVersion 7.3)"
  - "spike/DaSpikeB.cs: second code sub-action for cross-AppDomain/ownership probes (compiles offline at LangVersion 7.3)"
  - "Pinned marker vocabulary SPIKE <A|B> <8-hex id> <MARKER> <details> written to CPH.LogInfo and %TEMP%/da-spike-trace.log"
affects: [01-05, 01-06, 01-07, phase-2]

actuals:
  tokens: 9700
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns: ["Task.Run tracked in a list, linked CancellationTokenSource, Dispose cancels then aborts owned I/O then bounded Task.WaitAll(2000)", "dual-channel logging (CPH.LogInfo plus append-only %TEMP% trace file)", "every public probe wrapped in try/catch logging exception type name only"]

key-files:
  created:
    - spike/DaSpikeA.cs
    - spike/DaSpikeB.cs
  modified: []

key-decisions:
  - "Booleans in marker details are lowercase (true/false) through a Flag() helper in both files, so live_evidence parsing sees one spelling; the plan only wrote <bool>"
  - "The accept loops of both listeners trace HTTP-ACCEPT-END with a kind=http|tcp detail instead of inventing a TCP-ACCEPT-END marker, keeping the pinned marker list unchanged"
  - "TriggerCodeEvent is void in the reflected 1.0.7 stub, so FIRE ok=true means only that the call did not throw"

patterns-established:
  - "Probe return policy: returns immediately, background work tracked in tasks, failures log ERROR method=<name> type=<ExceptionTypeName> and return false"
  - "Hang repro isolated: the repro listener is a property referenced only in SpikeBlockRepro, never in Dispose or CloseOwnedIo"

requirements-completed: [VER-03]

duration: 25min
completed: 2026-10-18
status: complete
plan_head_before: 0b0a1c29ba972cde1a2919aa0c27ace3197f32d3
plan_head_after: be1eff9ca5444dba4a1c8a55995f1b47e5256b43
commits: 2

coverage:
  - id: D1
    description: "spike/DaSpikeA.cs and spike/DaSpikeB.cs each pass the offline gate as their own compilation at LangVersion 7.3 (OFFLINE result only)"
    requirement: VER-03
    verification:
      - kind: integration
        ref: "python -I tools/compile_check.py --files spike/DaSpikeA.cs spike/DaSpikeB.cs"
        status: pass
    human_judgment: false
  - id: D2
    description: "All 24 pinned DaSpikeA public bool methods and the DaSpikeB methods exist; static privacy and hygiene greps pass (no account name, no exception messages, no wildcard prefixes, no process control, repro listener absent from Dispose and CloseOwnedIo)"
    requirement: VER-03
    verification:
      - kind: other
        ref: "Task 2 method-presence one-liner plus acceptance greps (see Self-Check)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Runtime behavior of the spike (Dispose cancel timing, abort timing, hang repro, trigger binding, argument typing, ownership, loopback binds)"
    requirement: VER-03
    verification: []
    human_judgment: true
    rationale: "Nothing here was executed inside Streamer.bot. Every runtime claim waits for the live run recorded in 01-07 and docs/live-spikes/FINDINGS.md."
---

# Phase 1 Plan 04: Spike code (DaSpikeA / DaSpikeB) Summary

**Two throwaway Streamer.bot code sub-actions with a cancel-on-Dispose host, loopback HTTP/TCP listeners, a deliberate old-fork hang repro, custom-trigger firing, privacy-safe argument dump, and semaphore/global/AppDomain ownership probes, compile-checked offline only (nothing run live).**

## Performance

- **Duration:** about 25 min
- **Started:** 2026-10-18T10:08Z (approx.)
- **Completed:** 2026-10-18T10:35Z (approx.)
- **Tasks:** 2 (tracer, auto)
- **Files created/modified:** 2 (`spike/DaSpikeA.cs` about 32 KB, `spike/DaSpikeB.cs` about 6 KB)

## Accomplishments

- `python -I tools/compile_check.py --files spike/DaSpikeA.cs spike/DaSpikeB.cs` prints `OK` for both and `compile_check: 2 passed, 0 failed`, exit 0. This is an OFFLINE compile against net48 reference assemblies plus the hand-written CPH stub at C# 7.3, not proof of behavior inside Streamer.bot.
- All 24 pinned public bool methods exist on DaSpikeA (`SpikeInfo` ... `SpikeExecByName`, `Execute`), plus `Init()` and `Dispose()`. DaSpikeB has `SpikeBInfo`, `SpikeBOwnSemTry`, `SpikeBOwnSemRelease`, `SpikeBOwnGenCheck`, `SpikeBOwnStatic`, `Execute`, `Init()`, `Dispose()`.
- `Dispose()` (cancel mode) cancels the shared token, runs `CloseOwnedIo()` (aborts the main HTTP listener, stops the TCP probe and receive listeners, closes the receive sockets, cancels the heartbeat, releases the owner semaphore), waits at most 2000 ms for tracked tasks, logs `DISPOSE-BEGIN` / `DISPOSE-END`, and never throws. Noop mode only logs the two markers.
- `SpikeBlockRepro` blocks the action thread on synchronous `HttpListener.GetContext()` then `Thread.Sleep(600000)`, with no token and no tracking. The listener property is referenced only inside that method (checked with awk over `Dispose` and `CloseOwnedIo`).

## Tracer feedback gate

Mode: not auto (`mode: yolo`, `auto_advance: false`), `human_verify_mode` = end-of-phase, tracer `<verify>` is automated-only. The task's verify was re-run after the Task 1 commit (`fe7b70c`): 2 passed, 0 failed. Tracer verified end-to-end, expansion continued.

## Task Commits

1. **Task 1: spike lifecycle host DaSpikeA core + DaSpikeB complete (tracer)** - `fe7b70c` (feat)
2. **Task 2: DaSpikeA probes (listeners, receive, abort timing, repro, fire, dump, ownership, exec)** - `be1eff9` (feat)

**Plan metadata:** committed separately with this SUMMARY (docs).

## Markers actually emitted, per method (for the 01-06 run sheet)

Format: `SPIKE <A|B> <8-hex instance id> <MARKER> <details>`. Booleans are lowercase `true`/`false`. Lines go to `CPH.LogInfo` and `%TEMP%\da-spike-trace.log` (with local timestamp `yyyy-MM-dd HH:mm:ss.fff`), except the lines marked (trace only), which are written only to the trace file.

DaSpikeA:

| Method | Markers and details |
|---|---|
| `Init()` | `INIT domain= domainName= pid= regDict= regJson=` (registers `DA Spike: Dict`/`daSpikeDict` and `DA Spike: Json`/`daSpikeJson`, category `DA Spike`; never `daSpikeNoReg`) |
| `Dispose()` | `DISPOSE-BEGIN mode=<cancel\|noop> tasks=<n>`; then `DISPOSE-END mode=noop`, or `DISPOSE-END mode=cancel ms=<n> allDone=<bool>` |
| `SpikeInfo` | `INFO domain= clr= fw= sb= culture= elevated=<true\|false\|unknown> pid= mode= tasks= init=` |
| `SpikeBgStart` | `BG-START already=<bool>`; in background (trace only) `BG-TICK n=<n>` every 2 s, `BG-CANCELLED`, `BG-ERROR type=`; every 5th tick also logged via both channels |
| `SpikeBgStop` | `BG-STOP` |
| `SpikeModeCancel` / `SpikeModeNoop` | `MODE dispose=<cancel\|noop>` |
| `SpikeOnStarted` / `SpikeOnExiting` | `STARTED init=<bool>` / `EXITING init=<bool>` |
| `Execute` | `EXECUTE` |
| `SpikeListenHttp` | `HTTP-BIND port= elevated=` or `HTTP-BIND-FAIL code= elevated=` (or `HTTP-BIND already=true`); background `HTTP-ROUNDTRIP ok= ms= [type=]`; `HTTP-LOCALHOST-BIND ok=<bool> [code=\|type=]`; accept loop end (trace only) `HTTP-ACCEPT-END kind=http reason=token\|type=` |
| `SpikeListenTcp` | `TCP-BIND port=` or `TCP-BIND-FAIL code=<SocketError name>` (or `TCP-BIND already=true`); background `TCP-ROUNDTRIP ok= ms= [type=]`; accept loop end (trace only) `HTTP-ACCEPT-END kind=tcp reason=token\|type=` |
| `SpikePendingReceive` | `RECV-PENDING port=` (or `paired=false`, or `already=true`); later (trace only) `RECV-END read=<n>` or `RECV-END type=<exception type>` |
| `SpikeAbortTiming` | three lines `ABORT-MS kind=<http\|tcp\|recv> skipped=true` or `ms=<n> completed=<bool>` |
| `SpikeBlockRepro` | `BLOCK-ENTER port=<port+2>` then blocks; `ERROR` only if the bind itself fails |
| `SpikeFireDict` / `SpikeFireJson` / `SpikeFireUnregistered` | `FIRE kind=<dict\|json\|noreg> ok=<bool>` |
| `SpikeFireBackground` | `FIRE kind=background thread= pool= ok=` (from a pool thread) |
| `SpikeDumpArgs` | `DUMP args=null`, or one `DUMP key=<spike key> type=<FullName\|null>` per key containing "spike" (case-insensitive, ordinal order), `DUMP-OTHER count=<n>`, `DUMP-TRYGET decimal=<bool> int=<bool>` |
| `SpikeOwnSemTry` | `OWN-SEM acquired= createdNew=` (or `acquired= already=true`) |
| `SpikeOwnSemRelease` | `OWN-SEM released=<bool>` |
| `SpikeOwnGenClaim` | `OWN-GEN claimed=<instance id>` |
| `SpikeOwnGenCheck` | `OWN-GEN seen=<value> mine=<bool>` |
| `SpikeOwnStatic` | `OWN-STATIC set=<instance id> staticBefore=<value\|null> domain=<id>` |
| `SpikeExecByName` | three `EXEC target=<action-name\|code-name\|wrong-name> result=<true\|false\|exception type>` |
| any failing probe | `ERROR method=<name> type=<exception type name>` |

DaSpikeB (same line format with code `B`): `INIT domain= domainName= pid=`, `DISPOSE-BEGIN`, `DISPOSE-END`, `INFO domain= domainName= pid=`, `OWN-SEM acquired= createdNew=`, `OWN-SEM released=`, `OWN-GEN seen=`, `OWN-STATIC seen= domain=`, `ERROR method= type=`.

## Files Created/Modified

- `spike/DaSpikeA.cs` - main spike host (lifecycle, heartbeat, listeners, pending receive, abort timing, events, ownership probes, ExecuteMethod probe, hang repro)
- `spike/DaSpikeB.cs` - second code sub-action for cross-AppDomain probes

## Decisions Made

- Lowercase booleans through `Flag()` (see key-decisions); applied to both files, which means Task 2's commit also touched `DaSpikeB.cs` (two lines plus the helper), although the plan listed only `DaSpikeA.cs` for that task.
- Accept-loop end uses the existing `HTTP-ACCEPT-END` marker with `kind=`, no new marker.
- A second call to `SpikeListenHttp`, `SpikeListenTcp`, `SpikePendingReceive` or `SpikeOwnSemTry` while the resource exists logs `already=true` and returns true instead of rebinding (a second bind of the same port would only produce a misleading `HTTP-BIND-FAIL`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical consistency] Lowercase boolean formatting helper**
- **Found during:** Task 2
- **Issue:** default C# bool concatenation prints `True`/`False`, while the plan's samples (`already=true`, `skipped=true`, `elevated=true`) are lowercase; mixed casing would complicate marker matching in the evidence filter.
- **Fix:** `Flag(bool)` helper, used for every boolean detail; Task 1 call sites were switched in the Task 2 commit.
- **Files modified:** spike/DaSpikeA.cs, spike/DaSpikeB.cs
- **Committed in:** be1eff9

**2. [Rule 1 - Interpretation] Idempotent re-entry guards on listeners/semaphore**
- **Found during:** Task 2
- **Issue:** the plan does not say what a repeated probe call does; rebinding the same port would log a failure that looks like a real finding.
- **Fix:** `already=true` guard (see Decisions Made).
- **Committed in:** be1eff9

**Total deviations:** 2 small additions, no scope change. **Impact:** run sheet authors must expect lowercase booleans and the `already=true` form.

## Issues Encountered

- A first combined `git` shell command was refused by the worktree sandbox; commands were split into plain separate git calls. No effect on results.
- Git warns "LF will be replaced by CRLF" on `git add` (autocrlf on this machine). The files are written with LF; the offline style check (no tabs, no trailing whitespace, no BOM) passes on the working copy.

## Known Stubs

None. The spike files are deliberately throwaway probes; nothing renders data from empty placeholders.

## Threat Flags

None beyond the plan's threat model. T-01-13: only `127.0.0.1`, `localhost` and `IPAddress.Loopback` binds exist (`grep` for `http://+` / `http://*` finds nothing). T-01-14: no `GetCurrent().Name`, no `.Message`, `DUMP` logs only types of keys containing "spike" and a count of the rest, elevation is a boolean. T-01-15: Dispose is cancel-on-Dispose with a 2000 ms bounded wait; the repro is one isolated method. The static greps verify code text only; they say nothing about runtime behavior.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 01-05 (manifest) and 01-06 (run sheet) can use the pinned names and the marker table above verbatim.
- Not verified: everything at runtime. In particular, the following are unmeasured assumptions until 01-07: whether Streamer.bot compiles the files at C# 7.3 with its own class rewrite, whether `RegisterCustomTrigger` / `TriggerCodeEvent` accept the used overloads, whether `HttpListener` binds without elevation, whether `Task.WaitAll(2000)` is enough, and whether `SpikeBlockRepro` reproduces the hang.
- Note for the runbook: `SpikeBlockRepro` is meant to hang Streamer.bot's shutdown; RUNSHEET S6 must run it last and name the manual recovery.

## Self-Check: PASSED

- `spike/DaSpikeA.cs` and `spike/DaSpikeB.cs` exist on disk; commits `fe7b70c` and `be1eff9` are ancestors of HEAD.
- Re-ran after the final commit: gate `compile_check: 2 passed, 0 failed` (exit 0); method-presence check `missing []`; style check `style-bad []`; all Task 1 and Task 2 acceptance greps (positive and negative) passed.
- This check covers the committed files and the offline gate only; no live behavior is claimed.

---
*Phase: 01-live-spikes-build-harness*
*Completed: 2026-10-18*
