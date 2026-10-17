# Phase 1: Live Spikes & Build Harness - Pattern Map

**Mapped:** 2026-10-17
**Files analyzed:** 20 new/modified
**Analogs found:** 4 partial / 20 (the rest are new tooling with no in-repo analog)

Tracked-source check: `git ls-files` confirms `integration.cs`, `updateChecker.cs`, `.gitignore`, `.claude/CLAUDE.md` and `.planning/**` are tracked. No capability mirrors are used.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `spike/DaSpikeA.cs` | CPHInline host (spike) | event-driven + background tasks | `integration.cs` (CPHInline shape, Init/Dispose, bool actions) | role-match (shape only) |
| `spike/DaSpikeB.cs` | CPHInline probe | request-response | `updateChecker.cs` (small second CPHInline) | role-match |
| `tools/compile-check/Stub/CphStub.cs` | stub/utility | n/a | none (use RESEARCH Pattern 3 signatures) | no analog |
| `tools/compile-check/CompileCheck.csproj` | config | n/a | none (RESEARCH Pattern 1 verbatim) | no analog |
| `tools/compile_check.py` | CLI tool | batch / subprocess | none | no analog |
| `tools/fixtures/compile/{good,bad_syntax,net48_gap}.cs` | test fixture | n/a | `updateChecker.cs` (small valid CPHInline for good.cs) | partial |
| `tools/build_sb.py` | CLI tool | transform / file-I/O | none | no analog |
| `tools/packages/spike.json` | config/manifest | n/a | none | no analog |
| `tools/golden/RECIPE.md`, `docs/live-spikes/RUNSHEET.md` | docs (Russian) | n/a | `README.md` (Russian tone) | partial |
| `tools/golden/GoldenRuntime.cs` | CPHInline | n/a | `updateChecker.cs` | role-match |
| `tools/live_evidence.py` | CLI tool | file-I/O filter | none | no analog |
| `tools/check_findings.py` | CLI tool | validation | none | no analog |
| `tools/tests/test_build_sb.py` (+ `__init__.py`) | test | n/a | none (RESEARCH Pitfall 2) | no analog |
| `docs/live-spikes/FINDINGS.md` | docs | n/a | none | no analog |
| `tools/README.md` | docs | n/a | none | no analog |
| `.gitignore` (modify) | config | n/a | itself (lines `.vs`, `dist`) | exact |
| `.gitattributes` (new) | config | n/a | none | no analog |
| `.planning/PROJECT.md` (modify, Key Decisions) | docs | n/a | itself | exact |

## Pattern Assignments

### `spike/DaSpikeA.cs`, `spike/DaSpikeB.cs`, `tools/golden/GoldenRuntime.cs` (CPHInline, event-driven)

**Analog:** `integration.cs` lines 34-128, `updateChecker.cs` lines 1-27.

**Class shape** (`updateChecker.cs` 1-27): usings at top (`System`, `System.Net`, `Newtonsoft.Json`, `System.Collections.Generic`), then one `public class CPHInline`, public `bool` parameterless action methods, `private const string` PascalCase constants, `CPH.LogDebug("UpdateChecker: ...")` with a fixed prefix.

**Lifecycle shape** (`integration.cs` 91-100): public `Init()`/`Dispose()` (note: `Dispose` is a public void; null-guard fields before use):
```csharp
public void Init() { EnsureInitialized(); ... }
public void Dispose()
{
    if (SocketService != null)
        SocketService.Close();
}
```
Spike differs: Dispose must cancel a `CancellationTokenSource`, abort the listener, bounded `Task.WaitAll`, never throw (RESEARCH Pattern 5 skeleton lines 297-320, copy it).

**Conditional base class** (copy from RESEARCH Pattern 2): `#if EXTERNAL_EDITOR public class CPHInline : CPHInlineBase #else public class CPHInline #endif`. The old files lack this, so they do not compile in the gate.

**Private state form** (`integration.cs` 81-84): `private X Y { get; set; }` auto-property for new private state. Allman braces, 4 spaces, no trailing whitespace. Single-statement `if` without braces is accepted.

**Logging**: wrap CPH logging in a prefixed helper like `PrefixedLogger` (`integration.cs` 36-80, prefix const + `_CPH.LogDebug(message)`); spike prefix must be `SPIKE <runId>` per RESEARCH. Also write to the `%TEMP%` trace file (no analog).

**Anti-pattern (do NOT copy), shutdown hang:** `integration.cs` 1096-1103 and 658:
```csharp
Task listenTask = func.Invoke();
var forceCloseTimer = new System.Timers.Timer(Math.Max(5, timeoutSeconds) * 1000);
forceCloseTimer.Elapsed += ForceCloseServer;
...
listenTask.GetAwaiter().GetResult();   // blocks action thread
Listener.Close();
// ConnectLoop: Thread.Sleep(TimeSpan.FromSeconds(...))  // line 658, uncancellable
```
This is the pattern `SPIKE | Block (repro)` should mimic deliberately (sync wait on listener + `Thread.Sleep`); every other spike path must use `Task.Run` + token. Also avoid `throw e;` (use `throw;`) and empty `catch (Exception) { }` without a trace line, except in Dispose where best-effort swallowing is intended.

**Globals/args naming:** `da` prefix (`daCode`, `daAccessToken`); spike events `daSpikeDict`, `daSpikeJson`, `daSpikeNoReg` match.

---

### `tools/compile-check/*`, `tools/compile_check.py`, `tools/build_sb.py`, `tools/live_evidence.py`, `tools/check_findings.py`, tests (new tooling)

**No analog in repo** (repo has only C# and a YAML workflow). Planner uses RESEARCH.md directly:
- csproj: Pattern 1 block (RESEARCH lines 189-210).
- Stub members: Pattern 3 list (lines 236-254); exclude `TwitchClientId`/`TwitchOAuthToken`; `CPHInlineBase` `[Serializable]`, get-only `CPH` and `args`.
- `.sb` serializer/pack/unpack: Pattern 4 code (lines 275-287).
- Python conventions to apply to all tools: stdlib only, `python -I`, `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`, pass/fail by exit code and `CS\d+` regex, no sibling imports (or explicit sys.path insert), `tools/tests/__init__.py` plus `python -I -m unittest discover -s tools/tests -t tools`.
- Default compile inputs come from `tools/packages/*.json`; never glob root `*.cs` (old files do not compile and are BOM+CRLF).

### `.gitignore` (modify)
Current content is exactly two lines: `.vs`, `dist`. Append `tools/compile-check/obj/`, `tools/compile-check/bin/`, `__pycache__/`. Do not touch the staged deletions of `.github/ISSUE_TEMPLATE/*`.

## Shared Patterns

### C# style (all `.cs` under spike/, tools/golden/, fixtures)
**Source:** `.claude/CLAUDE.md` Conventions + `integration.cs`. 4 spaces, Allman, LF-or-normalized endings (builder normalizes), `string.IsNullOrWhiteSpace`, `TryParse` with `CultureInfo.InvariantCulture`, public action methods return `bool`, camelCase locals, PascalCase constants. Comments in Russian only where user-facing.

### Secrets/PII
**Source:** CLAUDE.md Security. Never log tokens/PII; spike and tools must not read `data/` files or Twitch proxy properties. Golden audit regexes from RESEARCH lines 364-368.

### Honesty
Findings statuses limited to `not verified` / `verified live` / `refuted live`; offline results labelled offline.

## No Analog Found

All Python tools, csproj, CPH stub, manifest JSON, `.gitattributes` (`*.sb -text`), FINDINGS/RUNSHEET/RECIPE docs: use RESEARCH.md patterns. `README.md` is the only Russian-language doc reference for tone.

## Metadata

**Analog search scope:** repo root (`integration.cs`, `updateChecker.cs`, `.gitignore`), `.planning/`
**Files scanned:** 3 source files read (targeted ranges), tracked file list
**Pattern extraction date:** 2026-10-17
