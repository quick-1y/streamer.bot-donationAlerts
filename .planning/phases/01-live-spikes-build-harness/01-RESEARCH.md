# Phase 1: Live Spikes & Build Harness - Research

**Researched:** 2026-10-17
**Domain:** Offline C# compile gate (net48 + CPH stub), Streamer.bot `.sb` export/builder, live lifecycle spikes in Streamer.bot 1.0.7
**Confidence:** MEDIUM-HIGH for the offline toolchain (executed and observed this session); MEDIUM for the `.sb` builder (format confirmed on official 1.0.4 samples, 1.0.7 golden still pending); MEDIUM for spike design (answers are live-only by nature)

<user_constraints>
## User Constraints (from CONTEXT.md)

No CONTEXT.md exists for this phase. The user explicitly chose to continue WITHOUT `/gsd-discuss-phase`.

### Locked Decisions
None from CONTEXT.md. The following come from the roadmap, STATE.md and CLAUDE.md and are treated as binding:
- Roadmap Phase 1 goal, mode `mvp`, requirements VER-01, VER-03, PKG-04 and the five success criteria (copied under "Phase Requirements").
- STATE.md decision: "Design so that `Dispose()` alone is sufficient for shutdown; an exit trigger (type 707) is optional until the spike confirms it."
- STATE.md decision: the `.sb` builder (PKG-04) is built in Phase 1 against the user's golden 1.0.7 export and produces the spike package.
- CLAUDE.md constraints (see "Project Constraints"): no runtime NuGet, one `.sb`, real export format with no invented fields, never log or commit secrets, honesty about live behavior, preserve unrelated local changes.

### Claude's Discretion
Every open design choice in this phase is the researcher's recommendation, not a user decision. The planner should adopt each one as an explicit assumption (they are also listed in the Assumptions Log):
- Directory layout, builder language (Python 3 stdlib), LangVersion for the offline gate, spike method surface, findings file format and location, language of run-sheet documents.

### Deferred Ideas (OUT OF SCOPE)
- Anything belonging to Phases 2 to 6 (real OAuth, Centrifugo client, argument contract, README, release package).
- VER-02 unit tests for codec/mapper/deduper/backoff/state machine (Phase 3). No xUnit project is created in Phase 1.
- Rewriting or deleting the old `integration.cs` / `updateChecker.cs` (Phase 2). They do not compile today (known defect) and must NOT be a default input of the compile gate.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VER-01 | Developer can compile-check the integration source offline (net48 + CPH stub) with one command | "Offline compile gate" section: tested csproj + stub + Python driver design; broken-line and net48-gap failure modes observed |
| VER-03 | Live spike results from the user's Streamer.bot 1.0.7 are recorded in the repo and the design follows them | "Spike design" matrix F1-F9 / E1-E8, run sheet, findings file with machine-checked statuses, decision rules |
| PKG-04 | The `.sb` is built and validated from repo source with one script (deterministic ids, round-trip check) | "`.sb` format and builder" section: envelope decoded this session, byte-exact serializer proven on 3 official samples, template-from-golden design, check/audit modes |
</phase_requirements>

## Summary

Phase 1 has three deliverable families and one external dependency (the user). (1) A one-command offline compile gate: `python -I tools/compile_check.py`. It drives a tiny SDK-style csproj that references `Microsoft.NETFramework.ReferenceAssemblies.net48` (NuGet, dev-time only), `Newtonsoft.Json` 13.0.3 and a hand-written CPH stub. This was prototyped and executed here: a clean file builds in about 4 s, a missing semicolon fails with `CS1002` and exit code 1, and net48-absent APIs (`HashCode`, `Span<T>`) fail with `CS0246`. (2) A stdlib-only Python builder `tools/build_sb.py` that produces the `.sb` envelope (`base64("SBAE" + gzip(UTF-8 JSON))`). Python's `json.dumps(indent=2, ensure_ascii=False, separators=(',', ': '))` with CRLF reproduced all three official 1.0.4 sample exports byte-for-byte, so the serializer fidelity risk is retired. The builder must be template-driven from the user's golden 1.0.7 export (no invented fields). (3) A spike package (two small Execute C# Code sub-actions plus thin Execute C# Method actions, custom-trigger handlers and a run sheet) that answers the live questions with one import and about four Streamer.bot restarts.

The strongest new evidence this session: the user's installed Streamer.bot 1.0.7 `Streamer.bot.Common.dll` contains the enum members `EventType.StreamerbotExiting = 707` and `EventType.CustomCodeEvent = 18002`, so the exit trigger type exists in the 1.0.7 binary. Whether it fires, in what order relative to `Dispose()`, and whether `CPH` still works at that moment remains a live question. The bundled compiler is Roslyn 5.6.0-2 (file metadata), but the language version Streamer.bot passes to it is still unknown and needs the `#error version` probe. Pinning that Roslyn 5.x toolset in the offline gate does NOT work on the installed .NET SDK 9.0.304 (`MSB4062`, tested).

Everything about live behavior stays "not verified" until the user runs the run sheet. The findings file must carry an enforced status per finding (`verified live` / `not verified` / `refuted live`), checked by a script, so the honesty constraint is mechanical rather than aspirational.

**Primary recommendation:** Build in this order: (a) compile gate + self-test, (b) golden recipe and user export (user checkpoint, runs in parallel with the compile gate), (c) spike sources compile-checked by the gate, (d) the builder against the golden, (e) run sheet, evidence script and findings checker, (f) user live session, (g) record findings and decisions. Use `TcpListener` as the default OAuth-callback listener recommendation until the spike says otherwise, keep Dispose-only shutdown as the design, and start the offline gate at `LangVersion 7.3`, to be raised after finding F6.

## Architectural Responsibility Map

This phase has no browser/API/DB tiers. The tiers that own capabilities are:

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Offline compile check | Dev workstation (Python driver + dotnet SDK) | Repo (stub, fixtures) | Must run without Streamer.bot; fidelity limited to net48 reference assemblies |
| `.sb` build / check / audit | Dev workstation (Python stdlib) | Repo (manifest, golden) | Deterministic transform of repo source; golden is the only schema authority |
| Golden export | User + Streamer.bot 1.0.7 UI | Repo (stored artifact + audit) | Only the real app can emit the real format |
| Lifecycle / trigger / listener behavior | Streamer.bot host process (spike code) | User (observation) | Cannot be known offline |
| Evidence capture | Dev workstation script (filtered log markers, process check) | User (Task Manager confirmation) | Keeps PII out of what the user pastes |
| Findings record and decision log | Repo docs (checked by script) | `.planning/PROJECT.md` Key Decisions | Honesty constraint needs machine-checkable status |

## Project Constraints (from CLAUDE.md)

Extracted actionable directives (CLAUDE.md read this session; the planner must verify compliance):
- Platform: Streamer.bot 1.0.x on Windows, C# inline code (`CPHInline`, `CPH`), compiled by Streamer.bot (.NET Framework 4.8). Only APIs Streamer.bot actually supports.
- Distribution: one `.sb` import; no extra files or processes; real export format, "no invented fields".
- Dependencies: only what Streamer.bot provides (BCL, Newtonsoft.Json). No runtime NuGet. (Dev-time NuGet for reference assemblies is acceptable per orchestrator; it never ships.)
- Security: never log credentials/tokens/PII; never commit secrets; `.sb` exports and backups contain secrets.
- Honesty: do not claim behavior was verified unless actually tested. Offline results are reported as offline only.
- Repo hygiene: preserve unrelated local changes (staged deletions of `.github/ISSUE_TEMPLATE/*`, untracked `.idea/`, `.claude/`). Do not commit them with phase work.
- Code style for any C# written (spike code is real repo code): 4-space indent, Allman braces, no tabs, no trailing whitespace; `da` prefix for globals/arguments; prefer `throw;` over `throw e;`; log with a fixed prefix; user-facing strings consistent with surrounding language.
- Single-file deployment: each `.cs` file is one Streamer.bot code sub-action with one `CPHInline`; no shared module between scripts (so the compile gate must compile each source file as its own compilation).
- GSD enforcement: file edits only through GSD workflow commands.
- Conversation with the user is in Russian (memory + PROJECT.md). User-facing run-sheet / golden-recipe documents should be Russian (assumption A10).

## Standard Stack

### Core (dev-time only; nothing here ships into Streamer.bot)
| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| .NET SDK | 9.0.304 (installed) | `dotnet build` as the compiler driver | Already installed; its Roslyn reports `Compiler version: "4.14.0-3.25359.3"`, language `latest (13.0)` [VERIFIED: ran `#error version` through the SDK this session] |
| `Microsoft.NETFramework.ReferenceAssemblies.net48` | 1.0.3 | net48 reference assemblies without installing a Developer Pack | Only a v4.7.1 targeting pack is installed locally [VERIFIED: `ls "Reference Assemblies/.../.NETFramework/"` printed `v4.7.1`]; the package is owned by Microsoft/dotnetframework, 37,296,415 downloads [VERIFIED: NuGet search API] |
| `Newtonsoft.Json` | 13.0.3 | Reference for compile check | Matches the copy Streamer.bot ships [VERIFIED: file version `13.0.3.27908` on the user's install] |
| Python | 3.13.12 (installed), stdlib only | `compile_check.py`, `build_sb.py`, `check_findings.py`, `live_evidence.py` | `json`, `gzip`, `base64`, `uuid`, `hashlib`, `re`, `argparse`, `subprocess`, `unittest` cover everything; zlib 1.3.1 [VERIFIED: ran it] |
| PowerShell | 5.1.26100.2161 (installed) | Optional stub-drift check via reflection over the user's install | ReflectionOnlyLoad worked for the metadata probes in this session |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `Microsoft.NETFramework.ReferenceAssemblies.net481` | 1.0.3 | 4.8.1 reference set | Only if a future API gap proves net48 insufficient. Docs say Streamer.bot runs .NET Framework 4.8.1 and the vendor VS Code recipe uses `net481`; net48 is a strict subset, so passing net48 implies passing net481. Keep net48 (requirement text says net48). |
| `xunit` + friends | deferred | VER-02 unit tests | Phase 3, not Phase 1 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SDK Roslyn 4.14 | `Microsoft.Net.Compilers.Toolset` 5.6.0 (same generation as Streamer.bot's bundled 5.6.0-2) | FAILS on this machine: `error MSB4062 ... Could not load file or assembly 'System.Runtime, Version=10.0.0.0'` with SDK 9.0.304 [VERIFIED: ran it]. Needs a .NET 10 SDK. Do not pin. |
| `dotnet build` driver per source file | Direct `csc.dll` invocation | Faster but must hard-code SDK paths; MSBuild resolves the NuGet reference package for free |
| `gzip.compress(mtime=0)` | Hand-built gzip header mimicking .NET (`1f8b 0800 00000000 0400`) | No benefit: any valid gzip decodes. Python writes `1f8b08000000000002ff` [VERIFIED: ran it] |
| Python builder | PowerShell / Node (24.14.0 installed) | Python gives byte-level control and was proven byte-exact on the samples; Node would also work but adds no advantage |

**Installation (one-time; first restore needs NuGet.org, afterwards fully offline):**
```bash
dotnet restore tools/compile-check/CompileCheck.csproj
```
Offline proof: restore with an empty package source succeeded and the subsequent `--no-restore` build produced `CompileCheck.dll` because both packages sit in the global packages folder `~/.nuget/packages` [VERIFIED: ran it with `--source <empty dir>`].

**Version verification:** `Microsoft.NETFramework.ReferenceAssemblies.net48` versions list ends at `1.0.3`; `...net481` has only `1.0.3`; `Microsoft.Net.Compilers.Toolset` has `5.6.0` and `5.9.0`; Newtonsoft.Json latest stable is 13.0.4 (13.0.3 chosen deliberately to match Streamer.bot) [VERIFIED: NuGet flat-container index queries this session].

## Package Legitimacy Audit

The `gsd-tools package-legitimacy check` seam only supports `npm|pypi|crates` (`Error: Usage: gsd-tools package-legitimacy check --ecosystem <npm|pypi|crates>` [VERIFIED: ran it]), so NuGet packages were checked manually against the NuGet registry. No Python or npm packages are installed in this phase.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| Microsoft.NETFramework.ReferenceAssemblies.net48 1.0.3 | NuGet | multi-year (1.0.3 stable) | 37,296,415 total | github.com/Microsoft/dotnet (owners `dotnetframework`, `Microsoft`, verified) | OK (manual) | Approved, dev-time only, `PrivateAssets=all` |
| Newtonsoft.Json 13.0.3 | NuGet | 10+ yrs | 9,325,394,018 total | newtonsoft.com/json (owners `dotnetfoundation`, `jamesnk`, `newtonsoft`, verified) | OK (manual) | Approved, dev-time reference only; runtime copy is Streamer.bot's own |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none
Not recommended: `StreamerBotDummy` NuGet stub (unvetted community package); `Microsoft.Net.Compilers.Toolset` 5.6.0 (legitimate but unusable here).

## Architecture Patterns

### System Architecture Diagram

```
 repo sources (src/*.cs, spike/*.cs)           manifest (tools/packages/*.json)
        |                                              |
        |  (each .cs = its own compilation)            |  names, sources, triggers, method bindings
        v                                              v
 tools/compile_check.py  --->  dotnet build  --->  net48 refs + CPH stub + Newtonsoft 13.0.3
        |   exit code + "error CSnnnn" codes (locale-independent)
        |   --self-test: good.cs passes, bad_syntax.cs -> CS1002, net48_gap.cs -> CS0246
        v
   PASS gate  ------------------------------------------------------+
                                                                      |
 USER: Streamer.bot 1.0.7 UI --(follows tools/golden/RECIPE)--> golden-1.0.7.sb
        |                                                             |
        v                                                             v
 tools/build_sb.py audit golden        tools/build_sb.py build spike --check
   (no secrets, allow-listed shape)       templates from golden + manifest -> model
                                           -> canonical JSON (CRLF, 2-space) -> gzip -> "SBAE" -> base64
                                           -> dist/spike.sb  (re-decode, compare to model + repo source)
                                                                      |
 USER: import dist/spike.sb into Streamer.bot 1.0.7 (live) <----------+
        |  run sheet: S1 clicks, S2 restart, S3 recompile, S4 close(cancel), S5 close(noop), S6 close(block, repro)
        v
 tools/live_evidence.py  (filtered log markers + trace file + process check)  --> user pastes evidence
        v
 docs/live-spikes/FINDINGS.md  (status per finding)  --> tools/check_findings.py
        v
 decisions logged: FINDINGS.md "Decisions" + PROJECT.md Key Decisions
```

### Recommended Project Structure
```
src/                          # product sources (Phase 2+). Phase 1 creates nothing here.
spike/
  DaSpikeA.cs                 # main spike host: lifecycle, listeners, events, guards
  DaSpikeB.cs                 # tiny second code sub-action: cross-AppDomain probes only
tools/
  README.md                   # the documented commands (success criterion 1)
  compile_check.py            # one command; --self-test; --files; --lang
  compile-check/
    CompileCheck.csproj       # net48, EnableDefaultCompileItems=false, Compile Include=$(CcSource)
    Stub/CphStub.cs           # IInlineInvokeProxy subset + CPHInlineBase (dev-only, never shipped)
  fixtures/compile/           # good.cs, bad_syntax.cs, net48_gap.cs (self-test inputs)
  build_sb.py                 # build | check | audit | decode
  packages/spike.json         # package manifest (single source for names, sources, bindings)
  golden/
    RECIPE.md                 # Russian step list for the user's export
    GoldenRuntime.cs          # tiny source the user pastes (compile-checked by the gate)
    golden-1.0.7.sb           # the user's export (stored after audit)
  live_evidence.py            # post-close evidence extractor (markers only)
  check_findings.py           # validates docs/live-spikes/FINDINGS.md
  tests/                      # __init__.py + test_build_sb.py (unittest)
docs/live-spikes/
  RUNSHEET.md                 # Russian, numbered, expected log markers per step
  FINDINGS.md                 # status table + evidence + decisions
dist/                         # gitignored already
```
`.gitignore` currently contains exactly `.vs` and `dist` [VERIFIED: `cat .gitignore`]. Append `tools/compile-check/obj/`, `tools/compile-check/bin/`, `__pycache__/`. Add `.gitattributes` with `*.sb -text` (the repo has `core.autocrlf=true` [VERIFIED: `git config --get core.autocrlf` printed `true`] and no `.gitattributes`). Do not touch the pre-existing staged deletions.

### Pattern 1: Offline compile gate (tested)
**What:** One csproj, parametrized by `CcSource`, plus a driver that loops over sources, one compilation each.
**When to use:** Every `.cs` that becomes a Streamer.bot code sub-action.
**Example (tested form):**
```xml
<!-- tools/compile-check/CompileCheck.csproj - built and run this session -->
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net48</TargetFramework>
    <OutputType>Library</OutputType>
    <LangVersion Condition="'$(CcLangVersion)' == ''">7.3</LangVersion>
    <LangVersion Condition="'$(CcLangVersion)' != ''">$(CcLangVersion)</LangVersion>
    <DefineConstants>EXTERNAL_EDITOR</DefineConstants>
    <NoWarn>CS0114</NoWarn>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
    <GenerateAssemblyInfo>false</GenerateAssemblyInfo>
    <Deterministic>true</Deterministic>
    <ImplicitUsings>disable</ImplicitUsings>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="$(CcSource)" />
    <Compile Include="Stub\CphStub.cs" />
    <Reference Include="System.Net.Http" />
    <PackageReference Include="Microsoft.NETFramework.ReferenceAssemblies.net48" Version="1.0.3" PrivateAssets="all" />
    <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
  </ItemGroup>
</Project>
```
Driver contract (planner to implement in `compile_check.py`):
- `dotnet restore` once, then per file `dotnet build --no-restore -nologo -v q -p:CcSource=<abs path> -o <scratch dir>`.
- Set `DOTNET_CLI_UI_LANGUAGE=en` and `VSLANG=1033` in the child environment, but decide pass/fail by exit code and by regex `error (CS\d+)` / `error (NU\d+|MSB\d+)`, never by message text. The user's machine is Russian-localized: the observed output was `error CS1002: Требуется ";"` and `Сборка успешно завершена` [VERIFIED: ran it].
- `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at start (Russian console codepage; `python -I` ignores `PYTHON*` env vars).
- Default inputs: every `source` listed in `tools/packages/*.json`. Never glob `*.cs` at repo root (old `integration.cs` has a known compile error and is BOM+CRLF [VERIFIED: `file integration.cs` printed `UTF-8 (with BOM) text, with CRLF line terminators`]).
- `--self-test`: compile `good.cs` (expect exit 0), `bad_syntax.cs` (expect failure containing `CS1002`), `net48_gap.cs` using `HashCode`/`Span<int>` (expect failure containing `CS0246`). Prints PASS/FAIL per case; overall exit 0 only if all three behave as expected. This is the automated proof of "fails on a deliberately broken line".

Observed results [VERIFIED: ran them this session]: clean file builds in 3.76 s wall; `Bad.cs` (semicolon removed) exits 1 with `error CS1002`; `HashCode` and `Span<int>` produce `error CS0246`; `#error version` produces `CS1029: #error: 'version'` and `CS8304 ... Language version: latest (13.0)`; a compact spike skeleton using `Task.Run`, `HttpListener`, `CancellationTokenSource`, `Dictionary<string,object>` compiled under `LangVersion 7.3` with only CS0649 unused-field warnings.

### Pattern 2: Class-shape compatibility between Streamer.bot and the offline gate
**What:** Use the vendor-documented conditional so one source file is valid in both places.
```csharp
// Source: Streamerbot/docs streamerbot/3.api/3.csharp/1.recipes/visual-studio-code.md
#if EXTERNAL_EDITOR
public class CPHInline : CPHInlineBase
#else
public class CPHInline
#endif
```
The vendor page says the `#if` is only active in the external editor and the code compiles in Streamer.bot unchanged [CITED: raw.githubusercontent.com/Streamerbot/docs/main/streamerbot/3.api/3.csharp/1.recipes/visual-studio-code.md, summarized by fetch tool]. The vendor csproj also sets `<NoWarn>CS0114</NoWarn>` (user `Init()` hides the virtual base member without `override`). Recommendation: use this pattern rather than a text transform or `partial class`.

### Pattern 3: CPH stub that matches the real 1.0.7 interface (dev-only)
Real signatures, from reflection over the user's install (metadata only; no data files read) [VERIFIED: ReflectionOnlyLoad of `D:\Users\qu1ck1y\Documents\tw\StreamerBot\Streamer.bot.Plugin.Interface.dll`, FileVersion 1.0.0.0, Streamer.bot.exe FileVersion 1.0.7]:
```
CPHInlineBase: [Serializable] Init() / Dispose() / Execute()  (all public virtual; Execute returns System.Boolean)
               properties (get only): IInlineInvokeProxy CPH ; Dictionary<string,object> args
IInlineInvokeProxy (members the project needs):
  System.Boolean RegisterCustomTrigger(System.String triggerName, System.String eventName, System.String[] categories)
  System.Void TriggerCodeEvent(System.String eventName, System.Boolean useArgs=True)
  System.Void TriggerCodeEvent(System.String eventName, System.Collections.Generic.Dictionary`2[System.String,System.Object] args)
  System.Void TriggerCodeEvent(System.String eventName, System.String json)
  T GetGlobalVar(System.String varName, System.Boolean persisted=True)
  System.Void SetGlobalVar(System.String varName, System.Object value, System.Boolean persisted=True)
  System.Void UnsetGlobalVar(System.String varName, System.Boolean persisted=True)
  System.Boolean ExecuteMethod(System.String executeCode, System.String methodName)
  System.String GetVersion()
  System.Boolean TryGetArg(System.String argName, T& value)
  System.Void SetArgument(System.String variableName, System.Object value)
  System.Boolean RunAction(System.String actionName, System.Boolean runImmediately=True)
  System.Boolean ActionExists(System.String actionName)
  System.Void LogInfo / LogWarn / LogError / LogDebug / LogVerbose (System.String logLine)
  System.Void Wait(System.Int32 milliseconds)
```
The proxy also exposes `TwitchClientId` and `TwitchOAuthToken` properties [VERIFIED: same reflection run]. The stub must NOT include them, and no spike or product code may read or log them.

Stub rules: keep it minimal (only members actually used), mark `CPHInlineBase` `[Serializable]`, and ship an optional dev script `tools/verify-stub.ps1 -StreamerBotDir <path>` (adapted from the reflection used here) that diffs stub signatures against a local install. That script is never required for the gate and the real DLLs are never committed.

### Pattern 4: Template-driven `.sb` builder (no invented fields)
**What:** Treat the golden export as the only schema authority. For every object kind the builder emits (action, trigger type N, sub-action type M, queue, envelope), deep-copy the golden's instance of that kind and override only fields the manifest owns (`id`, `name`, `group`, `byteCode`, `method`, `eventName`, `index`, `parentId`, ...). If the golden lacks a needed kind the build fails with "re-export golden including X". `check` asserts that every emitted object has the same key set and key order as the golden's instance of the same kind.
**Envelope** [VERIFIED: decoded `chatbot-commands.sb`, `wsgs.utils.curl.sb`, `wsgs.utils.json.parse.sb` from Streamerbot/docs this session]:
```
file text = base64( b"SBAE" + gzip( UTF-8 JSON without BOM ) )
top-level keys: meta, data, version, exportedFrom, minimumVersion
sample values : "version": 23, "exportedFrom": "1.0.4", "minimumVersion": "1.0.0-alpha.1"
meta keys     : name, author, version, description, autoRunAction (null), minimumVersion (null)
data keys     : actions, queues, commands, websocketServers, websocketClients, timers
action keys   : id, queue, enabled, excludeFromHistory, excludeFromPending, name, group, alwaysRun, randomAction, concurrent, triggers, subActions, collapsedGroups
99999 keys    : name, description, references, byteCode, precompile, delayStart, saveResultToVariable, saveToVariable, id, weight, type, parentId, enabled, index
gzip header   : 1f8b0800000000000400 ; JSON uses CRLF, 2-space indent, `"key": value`
```
Sample C# sub-action values seen: `"precompile": false`, `"saveToVariable": null`, `"weight": 0.0`, references `C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\mscorlib.dll`, `...\\System.dll`, `.\\Newtonsoft.Json.dll`; `byteCode` base64 decodes to UTF-8 source with CRLF and no BOM [VERIFIED: decoded this session]. Other sub-action types seen: 10, 21, 24, 29, 50, 51, 120 (keys `input, operation, value, autoType, subActions`), 506, 1007, 1009, 99900 (group: `name, color, random, subActions`). Triggers seen: type 401 (`commandId`), type 702 (`variables`).
**Serializer (byte-exact, proven):**
```python
# Source: tested this session against the 3 official samples -> "identical: True" for all
def dump(obj):
    s = json.dumps(obj, indent=2, ensure_ascii=False, separators=(',', ': '))
    return s.replace('\n', '\r\n').encode('utf-8')   # no trailing newline, no BOM
def pack(obj):
    return base64.b64encode(b'SBAE' + gzip.compress(dump(obj), compresslevel=9, mtime=0))
def unpack(raw, max_bytes=64 * 1024 * 1024):
    data = base64.b64decode(raw.strip())
    assert data[:4] == b'SBAE'
    d = zlib.decompressobj(31)           # bounded decode (gzip-bomb guard)
    out = d.decompress(data[4:], max_bytes)
    assert not d.unconsumed_tail
    return json.loads(out.decode('utf-8'))
```
**Deterministic ids:** `str(uuid.uuid5(NAMESPACE, "<package>/<kind>/<stable-name>"))` with a fixed namespace constant stored in the script. Samples use lowercase hyphenated GUIDs [VERIFIED: sample ids]. When copying a golden template object, remap every golden GUID that appears as an `id` inside the template to `uuid5(NAMESPACE, "<package>/tpl/<old id>")` consistently (so `parentId`, `executeCodeId`, `actionId` references follow), and leave the null GUID `00000000-0000-0000-0000-000000000000` and unknown external GUIDs untouched.
**Source embedding:** read the source file, strip a UTF-8 BOM, normalize to a single line-ending form (recommend CRLF, matching the samples) before base64. `check` applies the same normalization when comparing. This neutralizes `core.autocrlf=true` and the BOM+CRLF working-tree files.
**Determinism claim to make:** same inputs produce the same decoded JSON bytes everywhere, and two builds on one machine produce identical `.sb` bytes (unit test). Do not promise identical compressed bytes across Python/zlib versions [ASSUMED: deflate output can differ between zlib builds].

### Pattern 5: Spike host with cancel-on-Dispose (compiled at C# 7.3 here)
The skeleton below compiled against net48 at `LangVersion 7.3` with the gate described above. It is the seed of the Phase 2 lifecycle, not final code. Key points: tasks are `Task.Run` (no raw threads), every wait takes the token, `Dispose()` cancels, aborts the listener/socket, joins with a bounded wait, never throws, and logs through BOTH `CPH.LogInfo` (may fail during shutdown) and an append-only trace file in `%TEMP%` (works even if the CPH proxy is gone).
```csharp
// Skeleton verified to compile (LangVersion 7.3, net48 refs); behavior NOT verified live.
public void Dispose()
{
    try
    {
        var sw = System.Diagnostics.Stopwatch.StartNew();
        Trace("Dispose begin mode=" + (_noopDispose ? "noop" : "cancel"));
        if (_noopDispose) return;                       // mode used only by the informative S5 close
        _cts.Cancel();
        try { if (_http != null) _http.Abort(); } catch (Exception) { }
        try { if (_tcp != null) _tcp.Stop(); } catch (Exception) { }
        Task[] snapshot; lock (_gate) snapshot = _tasks.ToArray();
        try { Task.WaitAll(snapshot, 2000); } catch (Exception) { }
        Trace("Dispose end ms=" + sw.ElapsedMilliseconds);
    }
    catch (Exception) { }
}
public bool SpikeHttpListenStart()
{
    _http = new HttpListener();
    _http.Prefixes.Add("http://127.0.0.1:18554/spike/");   // loopback only, never "+" or "*"
    _http.Start();
    lock (_gate) _tasks.Add(Task.Run(() => AcceptHttpAsync(_cts.Token)));  // returns immediately
    return true;
}
```

### Anti-Patterns to Avoid
- **Default-globbing `*.cs` in the compile gate:** pulls in the non-compiling old fork; drive inputs from package manifests.
- **Deciding pass/fail from compiler text:** localized (Russian here); use exit code and `CSnnnn` codes.
- **Hand-writing `.sb` JSON shapes from third-party notes:** violates "no invented fields"; always derive from the golden.
- **A spike that can only be judged by eye:** every spike step must emit a unique marker line so `live_evidence.py` can grep it.
- **`#error version` inside the importable spike:** the import would then carry a deliberate compile error and contradict success criterion 3. Keep that probe a manual 3-click step.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| net48 reference assemblies | A custom set of `-r:` paths to GAC DLLs | `Microsoft.NETFramework.ReferenceAssemblies.net48` NuGet package | GAC/runtime assemblies accept APIs absent from the reference set; the package rejects `HashCode`/`Span<T>` (observed) |
| Compiler invocation | A custom Roslyn host | `dotnet build` on the tested csproj | Reference resolution, deterministic flags and exit codes for free |
| gzip + base64 | Manual deflate/CRC code | `gzip.compress(mtime=0)`, `base64`, `zlib.decompressobj(31)` | Stdlib; bounded decode for hostile input |
| GUID generation | Random GUIDs or hashes of content | `uuid.uuid5` with a fixed namespace | Stable across builds; collision-safe |
| JSON canonicalization | A custom pretty printer | `json.dumps(indent=2, ensure_ascii=False, separators=(',', ': '))` + CRLF | Proven byte-identical to Newtonsoft output on the official samples |
| Version probing of Streamer.bot's compiler | Feature-ladder code in the import | Roslyn's `#error version` (diagnostic `CS8304`) | Built-in, prints compiler and language version [VERIFIED: ran it through the SDK compiler] |
| Pending-I/O abort | Thread aborts | `HttpListener.Abort()`, `TcpListener.Stop()`, `ClientWebSocket.Abort()` | Phase-2 design, spike measures them |
| Evidence privacy | Asking the user to paste whole logs | `live_evidence.py` printing only marker lines | Logs can contain PII; the old fork logged an e-mail |

**Key insight:** every piece of fidelity in this phase comes from an observed artifact (official samples, the user's golden, the real reference assemblies, the real install metadata). Hand-written "knowledge" of formats is exactly what the phase exists to eliminate.

## Offline compile gate: details the planner needs

1. **Single documented command** (put it in `tools/README.md`): `python -I tools/compile_check.py` (all manifest sources) and `python -I tools/compile_check.py --self-test`. Optional `--files <a.cs> <b.cs>`, `--lang <ver>`.
2. **LangVersion recommendation:** default `7.3` (conservative: SB's language version is unknown until F6). After F6, set it to `min(SB verified version, 13)` (SDK 9's `latest` is 13.0 [VERIFIED]). Note `net48` references already block runtime-dependent features (`init`/records need `IsExternalInit`, ranges need `Index/Range`, `Span`, `IAsyncEnumerable`), whichever LangVersion is chosen. The vendor's own external-editor csproj uses `<LangVersion>13.0</LangVersion>` [CITED: visual-studio-code.md recipe, summarized by fetch tool], which is evidence the in-app compiler is modern, not proof of its configured level.
3. **What the gate cannot prove** (state this in `tools/README.md`): Streamer.bot's own reference resolution, its language version, its class rewriting, and behavior at runtime. A pass means "compiles against net48 reference assemblies with the stub", nothing more.
4. **Stub honesty:** the stub is hand-written and only as correct as its signatures; use the optional reflection script to re-check after Streamer.bot updates.
5. **Per-file compilation:** because each code sub-action is compiled independently (CLAUDE.md "Single-file deployment"), never compile two product files in one assembly. The spike's `DaSpikeA.cs` and `DaSpikeB.cs` both declare `CPHInline` and would clash if combined.
6. **Warnings:** keep `TreatWarningsAsErrors` off in Phase 1 (CS0649/CS0114 noise from spike fields); revisit in Phase 2.

## `.sb` builder: commands and check semantics

| Command | Behavior | Failure signal |
|---------|----------|----------------|
| `build_sb.py build <package> --golden <file> --out <file>` | Load golden templates, apply manifest, embed normalized sources, write `.sb` | Non-zero exit, message names the missing golden kind |
| `build_sb.py build <package> --check` | Build in memory, write, re-decode, compare (a) canonical re-serialization equals decoded bytes, (b) decoded model equals in-memory model, (c) every `byteCode` decodes to the normalized repo source, (d) key sets/order match the golden per kind, (e) ids unique and equal to recomputed uuid5, (f) referential integrity (`executeCodeId`, `actionId`, queue ids, `parentId` all resolve), (g) UTF-8 no BOM, (h) second build is byte-identical | Exit 1 with a per-check diff list |
| `build_sb.py check <file>` | Same structural checks on any `.sb` without needing a manifest | Exit 1 |
| `build_sb.py audit <file>` | Secret and shape audit (below) | Exit 1 |
| `build_sb.py decode <file> [--pretty]` | Dump JSON with `byteCode` decoded, for human review before committing the golden | n/a |

**Golden audit (how the repo verifies "no secrets"):**
1. Structural: `commands`, `websocketServers`, `websocketClients`, `timers` must be empty arrays; every action name must start with the allow-listed prefixes (`GOLDEN |`, `SPIKE |`); every queue/action/sub-action key must belong to the key sets already seen in official samples or be explicitly allow-listed.
2. Content scan of all JSON string values AND decoded `byteCode`: JWT shape `eyJ[A-Za-z0-9_-]{8,}\.`, `Bearer\s`, `client_secret`, `access_token`, `refresh_token`, `oauth:`, e-mail regex, `[A-Za-z]:\\Users\\` paths, any hex or base64-like run of 32+ characters that is not a GUID or the `SBAE` payload.
3. Report `meta.author`, `meta.name`, counts and the set of sub-action types for a human review step.
4. Plan a `checkpoint:human-verify` where the user (or reviewer) reads `decode --pretty` output before the golden is committed. Automation reduces risk; it does not replace this look. Variables are not exported at all, so secrets can only enter via what the user typed into actions/code/meta, which the recipe keeps to harmless text.

## Spike design

### What the official docs already settle (and what they do not)
| Fact | Source | Status |
|------|--------|--------|
| `Init()` runs "when your code is first compiled, including during Streamer.bot startup"; `Dispose()` "is always executed on destroy, including during Streamer.bot shutdown"; both optional | [CITED: raw Streamerbot/docs `2.lifecycle-methods.md`, summarized by fetch tool] | Recompile case NOT documented (web search also found nothing) |
| `Name` is required for sharing methods with Execute C# Method; Precompile defaults to false | [CITED: raw docs `execute-csharp-code.md`] | Documented |
| Shared methods must be `public`, parameterless, return `bool`; `CPH.ExecuteMethod("YourActionName", "CustomMethod")` is the in-code form | [CITED: raw docs `3.custom-methods.md`] | Which name `ExecuteMethod` wants (action name vs code sub-action Name) is ambiguous: E1 |
| Core triggers folder in the docs repo lists `streamerbot-started.md` and `test.md` | [VERIFIED: file listing of `streamerbot/3.api/2.triggers/core/`] | Silence about an exit trigger is not evidence it does not exist |
| `EventType.StreamerbotExiting = 707`, `EventType.StreamerbotStarted = 706`, `EventType.CustomEvent = 18001`, `EventType.CustomCodeEvent = 18002` exist in the 1.0.7 binary | [VERIFIED: reflection over `Streamer.bot.Common.dll` in the user's install; output lines `Streamer.bot.Common.Events.EventType.StreamerbotExiting = 707`, `...CustomCodeEvent = 18002`] | Existence of the enum member only; firing/ordering is live (F1) |
| Streamer.bot bundles Roslyn `5.6.0-2.26263.10` | [VERIFIED: `Microsoft.CodeAnalysis.CSharp.dll` ProductVersion on the install] | Configured LangVersion unknown (F6) |
| Real log shape: `[2026-10-17 17:26:01.065 INF] Closing services...` then `InlineCode :: Cleaning up '1' execute code instances` | [VERIFIED: filtered grep of `log_20261017.log`; only the two hung shutdowns exist in the surviving log, neither shows `Cleaned up` nor `exited`] | The clean-shutdown marker strings (`Cleaned up execute code instances`, `Streamer.bot exited`) come from earlier research of a rotated log: treat as F9 to confirm live |

### Spike package contents (all built by `build_sb.py` from `spike/*.cs` + manifest + golden templates)
Code sub-actions (both Precompile ON, Delayed Start OFF):
- `DaSpikeA` (host, most methods), `DaSpikeB` (second AppDomain probe).

Actions (group `DonationAlerts Spike`, all names start `SPIKE |`; control actions are one `Execute C# Method` each):
| Action | Binds to | Purpose |
|--------|----------|---------|
| `SPIKE \| Runtime A` / `Runtime B` | no triggers | Hold the two code sub-actions. Also answers E2: does a triggerless action precompile and serve methods? |
| `SPIKE \| Info` | none | `SpikeInfo`: instance id, `AppDomain.CurrentDomain.Id/FriendlyName`, `Environment.Version`, `RuntimeInformation.FrameworkDescription`, `CPH.GetVersion()`, current culture, process elevation (`WindowsPrincipal.IsInRole(Administrator)`) |
| `SPIKE \| Bg start` / `Bg stop` | none | Background `Task.Run` heartbeat (trace file every 2 s, CPH log every 10 s); proves the task survives `Execute()` return (E5) |
| `SPIKE \| Listen HTTP` / `Listen TCP` / `Pending receive` | none | Pending `HttpListener.GetContextAsync` on `127.0.0.1:18554`, pending `TcpListener.AcceptTcpClientAsync` on an ephemeral loopback port, pending `ReadAsync` on a loopback socket pair. Each logs bind success or exception type, and a self-connect round trip (F8) |
| `SPIKE \| Abort timing` | none | Cancels each pending operation and logs elapsed ms for `Abort()` / `Stop()` unblocking |
| `SPIKE \| Mode cancel` / `Mode noop` | none | Switch what `Dispose()` does (default cancel). Noop exists only for the informative S5 close |
| `SPIKE \| Block (repro)` | none | Deliberately mimics the old fork: synchronous `listener.GetContext()` plus `Thread.Sleep` on the action thread. Used once, expected to hang the exit |
| `SPIKE \| Fire dict` / `Fire json` / `Fire from background` / `Fire unregistered` | none | `TriggerCodeEvent` with Dictionary (`decimal 22.5m`, `int 7`, `long`, `double`, `bool true`, `string`, `DateTime`, keys with dots and mixed case), JSON string overload, call from a pool thread (E6), and an event name never passed to `RegisterCustomTrigger` (E7) |
| `SPIKE \| On event (dict)` | Custom Code Event `daSpikeDict` | Handler template from the golden: Log of every `%arg%`, three If/Else blocks (numeric greater-than, numeric equal, boolean equal), each with PASS and FAIL logs (F5) |
| `SPIKE \| On event (json)` | Custom Code Event `daSpikeJson` | Same handler shape for the JSON overload |
| `SPIKE \| On event (unregistered)` | Custom Code Event `daSpikeNoReg` | Binds to an event whose trigger name was never registered (E7) |
| `SPIKE \| On started` | Streamer.bot Started | Logs a marker so Init-vs-Started order is visible by timestamps (F3) |
| `SPIKE \| On exiting` | Streamer.bot Exiting (707) | Logs a marker and calls `SpikeOnExiting` which also writes the trace file (F1) |
| `SPIKE \| Own: sem try/release`, `Own: gen claim/check`, `Own: static probe` (on A and B) | none | Cross-AppDomain guard probes (F7) |
| `SPIKE \| Exec by name` | none | `CPH.ExecuteMethod` with the action name, the code sub-action name and a wrong name; logs each `bool` result (E1) |

All spike log lines start with `SPIKE` plus a run id so `live_evidence.py` can filter them. No spike line may contain tokens, credentials, usernames or donor data (there are none in this phase).

### Finding matrix (success criterion 5 plus the extras this design needs)
| ID | Question | Spike mechanism | Offline knowledge now | Decision rule |
|----|----------|-----------------|-----------------------|---------------|
| F1 | Does the exit trigger (707) exist and fire? | `SPIKE \| On exiting` + trace file; look at order vs `Closing services...`/`Dispose` in S4 | Enum member exists in 1.0.7 binary [VERIFIED]; firing unknown | If it fires before Dispose and `CPH` works: optional belt-and-braces `DA \| On exit` action calling Stop; else drop. Design stays Dispose-only either way |
| F2 | Is `Dispose()` called on recompile? | S3: user edits the spike code, presses Compile/Save; trace file shows `Dispose begin` for the old instance id and `Init` for a new id | Not documented | If yes: no extra handling. If no (thread abort only): Phase 2/3 needs ownership takeover (generation guard) and tolerance for `ThreadAbortException`; README says recompile drops the connection |
| F3 | Init vs Started ordering | Timestamps of `Init` (trace + log) vs `SPIKE \| On started` | Unknown | If Init completes first: Auto-start via a Started-bound action is safe. If Started can run before Init: Auto-start method must be idempotent and tolerate a lazily compiled host |
| F4 | JSON shape of a Custom Code Event trigger and of Execute C# Method | Golden export (user-made) | Third-party notes say 18002 has `eventName` and `name`; 99998 has `executeCodeId, method, runOnUiThread, saveResultToVariable, saveToVariable` [CITED: prior research STACK/ARCHITECTURE, from third-party tooling and local field names; ASSUMED until golden] | Builder asserts key sets from the golden; any difference from the notes wins |
| F5 | Do dictionary values keep numeric/bool types in If/Else? | `Fire dict` vs `Fire json` and the three If/Else blocks in the handlers; also a C# `TryGetArg<object>` type dump | Unknown | If numeric compares pass: pass `decimal`/`int` in the dictionary. If not: add string twins plus `daAmountFloor` as `int`, or switch overload |
| F6 | Which language version does Streamer.bot compile with? | Manual: new Execute C# Code sub-action containing only `#error version`, press Compile, copy the `CS8304` line from the Compiling Log (3 clicks) | Compiler is Roslyn 5.6.0-2 [VERIFIED]; configured LangVersion unknown | Set the offline gate's `LangVersion` to `min(reported, 13)` |
| F7 | Cross-AppDomain single-owner guard | `DaSpikeA`/`DaSpikeB` each try a named kernel `Semaphore(1,1,"Local\\StreamerBot.DaSpike.Owner")` with `WaitOne(0)`, a non-persisted global generation claim, and a static field probe; then recompile A and retry | .NET named kernel objects are process-wide [ASSUMED]; per-instance AppDomain isolation is inferred from the `Unloading '<id>'` log lines [CITED: ARCHITECTURE.md research] | Prefer the semaphore if B sees A's hold and a recompiled A can re-acquire; else use the generation global; else rely on precompile + single instance |
| F8 | Loopback listener under non-elevated Streamer.bot | Bind probes for `HttpListener` (`127.0.0.1`, `localhost`) and `TcpListener`; log elevation state and exception type/`ErrorCode`; abort timing | The old fork used `http://127.0.0.1:8554/...` successfully (8 code exchanges in earlier log research) with unknown elevation [CITED: PITFALLS.md] | If HttpListener binds non-elevated and aborts under about 1 s: either is acceptable. Recommend TcpListener by default anyway (no http.sys registration surviving a hung process, no URL-prefix rules) unless TcpListener shows a problem |
| F9 | Exact clean-shutdown marker strings and timing | S4 evidence | Partially observed (`Closing services...`, `Cleaning up '1' execute code instances`) [VERIFIED]; `Cleaned up execute code instances`, `Streamer.bot exited` unconfirmed this session | Constants in `live_evidence.py` updated from the first clean log |
| E1 | Which name does `CPH.ExecuteMethod` expect | `SPIKE \| Exec by name` | Ambiguous docs | Use the working form everywhere |
| E2 | Triggerless / disabled action still precompiles and serves methods | `SPIKE \| Runtime A` has no triggers; check `Init` at startup | Unknown | If not: give the host action a harmless Started trigger |
| E3 | After import with deterministic ids: do links resolve, are ids preserved, duplicates on re-import | User imports twice, then re-exports the spike actions to `tools/golden/spike-reexport-1.0.7.sb`; `build_sb.py check` compares ids | Unknown | Defines how much "deterministic ids" actually buys for re-import |
| E4 | Does a background pool thread's `CPH.TriggerCodeEvent` work outside an action | `Fire from background` | Unknown; central to Phase 2 dispatcher | If it fails: dispatcher must hop through an action (`RunAction`/Execute Method) instead |
| E5 | Background `Task.Run` survives `Execute()`/method return; same instance reused | `Bg start` then repeated `Info` | Observed instance reuse in earlier logs [CITED: ARCHITECTURE.md] | Confirms LIFE-01 approach |
| E6 | `CPH.Log*` works inside `Dispose` | Compare CPH log vs trace file in S4 | Unknown | Keep the trace-file fallback for diagnostics only |
| E7 | Imported 18002 trigger fires although `RegisterCustomTrigger` never named its event | `Fire unregistered` | Unknown | Decides whether imported example actions can precede registration |
| E8 | Does the action editor have a description field in 1.0.7 (PKG-02) | Golden: user fills it if present; compare the golden action keys with the 1.0.4 sample keys (no `description` key there) | 1.0.4 action keys have no `description` [VERIFIED: sample] | If absent, use a Comment sub-action (type 1009 appears in samples) as the action description in Phase 6 |

### Closing scenarios and restart budget (one import, about four restarts)
| Step | What the user does | Expected | Informs |
|------|--------------------|----------|---------|
| S1 | Import `dist/spike.sb`; look for import warnings; open each code sub-action, press Compile; run `Info`, `Exec by name`, `Fire dict/json/background/unregistered`, `Own:*`, listener probes | No import/compile errors; markers in log | SC3, F4, F5, F7, F8, E1, E4, E7 |
| S2 | Restart Streamer.bot (Precompile ON) | `Init` for A and B at startup; `On started` marker ordering | F3, E2 |
| S3 | Edit spike code trivially, Compile/Save | Trace shows old-instance Dispose (or not) and new Init | F2, F7 (re-acquire) |
| F6 | Manual `#error version` probe | `CS8304` line | F6 |
| S4 | `Bg start` + `Listen HTTP` + `Pending receive` (mode cancel), close via window X or File exit, then run `live_evidence.py` | `Cleaned up execute code instances`, `Streamer.bot exited`, no `Streamer.bot.exe` in Task Manager | SC4, F1, F9, E6 |
| S5 (informative) | Relaunch; `Mode noop` + same background pieces; close | Observe whether a background task plus pending listener, without cancellation, hangs | Root-cause evidence for the cancel design |
| S6 (repro) | Relaunch; run `SPIKE \| Block (repro)`; close; if the process stays, record it, then kill via Task Manager | Expected: log ends after `Cleaning up '1' ...` and the process lingers (matches 2026-10-17 17:26 and 17:29 shapes) | SC4 "hang reproduced on purpose" |
| S7 | Delete or disable all `SPIKE |`/`GOLDEN |` actions in the user's profile | Clean profile | Hygiene |

If S6 does NOT hang, the old-hang root cause is not yet understood: record it as "not reproduced", do not claim the fix is proven, and extend the repro toward the old pattern (blocked `Connect` plus force-close timer) before Phase 2.

Run S6 last (kill may be required). Recommend the user make a Streamer.bot backup first and keep it outside the repo (backups contain secrets). Choose a different `HttpListener` port than the previous run after a forced kill; the orphaned process may still hold the prefix.

### Evidence capture (privacy-preserving)
`tools/live_evidence.py --sb-dir <StreamerBot dir> [--after-close]`:
- Finds the newest `logs/log_*.log`, locates the LAST `Closing services...`, prints only lines matching a fixed marker regex (`Closing services`, `InlineCode :: (Cleaning|Cleaned|Unloading|Creating)` with ids masked, `Streamer.bot exited`, lines containing `SPIKE`). Never prints other log content.
- Prints the tail of `%TEMP%\da-spike-trace.log` after a run-start offset recorded by the script (the user should not have to delete the file).
- Polls `tasklist /FI "IMAGENAME eq Streamer.bot.exe"` for up to 10 s and prints present/absent with PIDs.
- Never reads `data/`.
The user pastes this block (not a log file) into the findings evidence cell.

### Findings record (honesty enforced by a script)
`docs/live-spikes/FINDINGS.md` has a table, one row per ID in the matrix above, with columns `ID | Question | Status | Evidence | Confirmed | Decision`. Allowed `Status`: `not verified` (default), `verified live`, `refuted live`. A row may be `verified live`/`refuted live` only if `Evidence` is non-empty and `Confirmed` has the form `user YYYY-MM-DD`. "verified offline" is deliberately NOT an allowed status; offline facts go in a separate "Offline facts" section together with the command that reproduces them. `tools/check_findings.py` fails on a missing ID, unknown status, or an unconfirmed live claim. A "Decisions" section lists D-nn entries (decision, driven by finding IDs, consequence for Phase 2+). The planner should also add the decisions to `.planning/PROJECT.md` Key Decisions at phase end.

## Common Pitfalls

### Pitfall 1: Judging the compile gate by text
**What goes wrong:** String matching on "error" or on English messages breaks on the user's Russian-localized toolchain.
**Why:** MSBuild/Roslyn localize messages [VERIFIED: observed Russian output].
**How to avoid:** Exit code plus regex on `CS\d+`/`NU\d+`/`MSB\d+`; set `DOTNET_CLI_UI_LANGUAGE=en`.
**Warning signs:** Self-test passes on one machine and fails on another.

### Pitfall 2: `python -I` hides sibling modules and breaks unit-test discovery
**What goes wrong:** `ImportError: Start directory is not importable` or `ModuleNotFoundError: build_sb`.
**Why:** `-I` drops the script directory from `sys.path`.
**How to avoid:** Put `__init__.py` in `tools/tests/` and run `python -I -m unittest discover -s tools/tests -t tools` [VERIFIED: failed without `__init__.py`, passed with it]. Standalone scripts must not import siblings, or must insert their own directory explicitly.

### Pitfall 3: Golden contaminated with real content
**What goes wrong:** The user exports more than intended (commands, WebSocket clients, a real chat action) or pastes real values.
**How to avoid:** Recipe tells the user to start from an empty export (`Clear`), add only the named actions and the queue; `audit` enforces empty `commands/websocket*/timers`, name prefixes and secret patterns; human look at `decode --pretty` before commit.

### Pitfall 4: Line endings, BOM and `core.autocrlf` change the embedded source
**What goes wrong:** `byteCode` differs between machines; round-trip compare fails spuriously.
**Why:** `core.autocrlf=true` is set; existing files are BOM+CRLF.
**How to avoid:** Builder normalizes (strip BOM, single line-ending form) on both build and compare; add `.gitattributes` `*.sb -text`.

### Pitfall 5: Shutdown evidence lost because `CPH` is gone during Dispose
**What goes wrong:** Dispose runs but no line appears in the Streamer.bot log, looking like Dispose did not run.
**How to avoid:** Dual logging with the `%TEMP%` trace file; compare both in S4 (E6).

### Pitfall 6: Hang repro leaves a stuck process and a held port
**What goes wrong:** Next run fails to bind; Streamer.bot keeps running invisibly.
**How to avoid:** Run S6 last; kill via Task Manager; use a different port next time; record the PID/time in evidence.

### Pitfall 7: `#error version` in an importable package
**What goes wrong:** Import shows a compile error, contradicting success criterion 3.
**How to avoid:** Manual probe only (F6).

### Pitfall 8: Pinning the Roslyn 5.x toolset
**What goes wrong:** `MSB4062` on SDK 9.0.304 [VERIFIED].
**How to avoid:** Use the SDK compiler; treat language-version parity as the F6 decision.

### Pitfall 9: Deflate byte-stability assumed across machines
**What goes wrong:** CI or another contributor sees different `.sb` bytes for identical inputs.
**How to avoid:** Assert determinism on decoded JSON and same-machine rebuilds; do not commit built `.sb` files (`dist` is already ignored).

### Pitfall 10: Russian console encoding in Python
**What goes wrong:** `UnicodeEncodeError` when printing Cyrillic action names or paths.
**How to avoid:** `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at startup of every tool; `-I` ignores `PYTHONIOENCODING`.

### Pitfall 11: Treating the stub as truth
**What goes wrong:** Code compiles offline but calls a member whose real signature differs.
**How to avoid:** Stub built from the reflected 1.0.7 signatures (above); optional drift script; the phase still requires the live compile in Streamer.bot (S1).

### Pitfall 12: Credential-bearing proxy properties
`IInlineInvokeProxy` exposes `TwitchClientId` and `TwitchOAuthToken` [VERIFIED]. Never copy them into the stub, never read them in spike code, never log them.

## Code Examples

### `#error version` probe (manual step F6)
```csharp
// Source: Roslyn diagnostic CS8304; output observed through SDK compiler this session:
//   error CS8304: Compiler version: "4.14.0-3.25359.3 (6dbcfd2f)". Language version: latest (13.0).
#error version
```
Paste into a new throwaway Execute C# Code sub-action in Streamer.bot, press Compile, read the Compiling Log, then delete the sub-action.

### Stub (dev-only; matches reflected 1.0.7 signatures for the members listed)
```csharp
// tools/compile-check/Stub/CphStub.cs - built and used this session (subset shown)
using System;
using System.Collections.Generic;
public interface IInlineInvokeProxy
{
    bool RegisterCustomTrigger(string triggerName, string eventName, string[] categories);
    void TriggerCodeEvent(string eventName, bool useArgs = true);
    void TriggerCodeEvent(string eventName, Dictionary<string, object> args);
    void TriggerCodeEvent(string eventName, string json);
    T GetGlobalVar<T>(string varName, bool persisted = true);
    void SetGlobalVar(string varName, object value, bool persisted = true);
    void UnsetGlobalVar(string varName, bool persisted = true);
    void LogInfo(string logLine);
    void LogWarn(string logLine);
    void LogError(string logLine);
    void LogDebug(string logLine);
    void LogVerbose(string logLine);
    bool TryGetArg<T>(string argName, out T value);
    string GetVersion();
    bool ExecuteMethod(string executeCode, string methodName);
}
[Serializable]
public class CPHInlineBase
{
    public IInlineInvokeProxy CPH { get { return null; } }
    public Dictionary<string, object> args { get { return null; } }
    public virtual void Init() { }
    public virtual void Dispose() { }
    public virtual bool Execute() { return true; }
}
```

### Golden recipe (what the user does; Russian text belongs in `tools/golden/RECIPE.md`)
1. In Streamer.bot 1.0.7 create action `GOLDEN | Runtime` (group `Golden`). Add Core > C# > Execute C# Code: Name `GoldenRuntime`, fill Description, tick Precompile on Application Start, paste `tools/golden/GoldenRuntime.cs` (uses `System.Net.Http` and `Newtonsoft.Json` so Find Refs produces the authoritative reference list; `Init()` calls `RegisterCustomTrigger("Golden: Event", "goldenEvent", new[] { "Golden" })`; has `GoldenPing()` and `GoldenFire()` which fires `goldenEvent` with `spikeAmount=22.5m, spikeCount=7, spikeFlag=true, spikeText="x"`), click Find Refs, Compile (expect success).
2. Create action `GOLDEN | Call` with two Execute C# Method sub-actions (`GoldenPing`, `GoldenFire`) and triggers Core > Streamer.bot Started and Streamer.bot Exiting (if the picker does not offer Exiting, write that down: it is finding F1 data).
3. Create queue `Golden Queue` (blocking).
4. Create action `SPIKE | On event (dict)` (queue `Golden Queue`, trigger Custom > Golden > Golden: Event) with: a Log sub-action printing the four arguments; three If/Else blocks: `spikeAmount` greater than `20`, `spikeAmount` equals `22.5`, `spikeFlag` equals `true`; each with a Log `SPIKE IF-... PASS` and an Else Log `SPIKE IF-... FAIL`.
5. Run `GOLDEN | Call` and note which Log lines appeared (early partial answer to F5).
6. If the action editor has a Description field, fill it on each action (E8).
7. Export: open the Export dialog, Clear, add ONLY these actions and the queue, set Name/Author/Version/Description, Export to File, save as `golden-1.0.7.sb`. Do not add any other action, command, WebSocket client or timer.
8. Developer runs `python -I tools/build_sb.py audit tools/golden/golden-1.0.7.sb` and `decode --pretty`, reviews, then commits.

### Manifest sketch (`tools/packages/spike.json`)
```json
{
  "package": "spike",
  "namespace": "<fixed uuid constant stored once>",
  "meta": { "name": "DA Spike", "author": "streamer.bot-donationAlerts", "version": "0.0.1", "description": "..." },
  "codes": [
    { "key": "a", "name": "DaSpikeA", "source": "spike/DaSpikeA.cs", "precompile": true, "delayStart": false, "references": "from-golden" },
    { "key": "b", "name": "DaSpikeB", "source": "spike/DaSpikeB.cs", "precompile": true, "delayStart": false, "references": "from-golden" }
  ],
  "actions": [
    { "name": "SPIKE | Info", "group": "DonationAlerts Spike", "triggers": [],
      "subActions": [ { "kind": "method", "code": "a", "method": "SpikeInfo" } ] },
    { "name": "SPIKE | On event (dict)", "template": "golden:SPIKE | On event (dict)" }
  ]
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Run a blocking loop inside `Execute()` (old fork) | Return immediately; `Task.Run` owned by the instance; cancel on `Dispose()` | Vendor threading guidance (`Task.Run`, no `async void`, no raw threads) | Core design of the spike and Phase 2 |
| Name-based `RunAction` dispatch | Custom Code Event triggers via `RegisterCustomTrigger`/`TriggerCodeEvent` (v0.2.0+/0.2.5) | Streamer.bot 0.2.x | Spike verifies binding and typing in 1.0.7 |
| Developer Pack for reference assemblies | `Microsoft.NETFramework.ReferenceAssemblies.*` NuGet | Microsoft package, years old | Gate works without installing 4.8 targeting pack |

**Deprecated/outdated:** Do not use `StreamerBotDummy` stubs; do not use `System.Web` references; do not target 1.1.0-alpha features (alpha as of 2026-10-09 per prior research).

## Runtime State Inventory
Not a rename/refactor/migration phase: omitted. (Spike cleanup S7 covers the only runtime state the phase creates in the user's profile: imported `GOLDEN |`/`SPIKE |` actions, the `%TEMP%\da-spike-trace.log` file, and any non-persisted globals set by the generation-claim probe.)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `LangVersion 7.3` is an acceptable starting level for the offline gate; Streamer.bot accepts at least that | Offline compile gate | Low: the real compiler is Roslyn 5.6; F6 replaces the guess |
| A2 | Named kernel semaphores are visible across Streamer.bot's per-instance AppDomains | Spike F7 | Guard design falls back to generation global; spike decides |
| A3 | Each code sub-action instance lives in its own AppDomain | Spike F7 | If not, statics would be shared and the cross-domain guard is simpler; spike's static probe settles it |
| A4 | Execute C# Method (99998) field names are `executeCodeId, method, runOnUiThread, saveResultToVariable, saveToVariable` and 18002 carries `eventName` and `name` | F4 | Builder derives from golden, so wrong notes cost nothing |
| A5 | Clean-shutdown marker strings are exactly `InlineCode :: Cleaned up execute code instances` and `Streamer.bot exited` | F9 | `live_evidence.py` constants need one edit |
| A6 | CRLF line endings in embedded source are preferred/harmless in Streamer.bot (samples use CRLF) | Pattern 4 | Spike import (S1) shows it; LF would be the alternative |
| A7 | Deflate output may differ across zlib versions | Pitfall 9 | Only matters if someone compares compressed bytes; design avoids it |
| A8 | `RuntimeInformation`, `WindowsPrincipal`, `TcpListener`, `HttpListener`, `Semaphore` work inside Streamer.bot's sandbox AppDomain | Spike code | A probe may throw; every probe logs the exception type and continues |
| A9 | Streamer.bot 1.0.7 exports `version` 23 or 24 | Builder envelope | Builder copies the golden's value, so no impact |
| A10 | User-facing run sheet and golden recipe should be Russian; findings/tooling docs English | Structure | Cosmetic; user can ask for English |
| A11 | `TriggerCodeEvent` called from a pool thread outside any action context works | E4 | Phase 2 dispatcher design changes if it fails |
| A12 | Closing via the window X (not tray minimize) triggers the normal shutdown path; `minimizeToTrayOnClose` was false in earlier research | S4 | Wrong test; run sheet tells the user to confirm the process actually ends |

## Open Questions

1. **Does the 1.0.7 action editor expose an action description (PKG-02)?**
   - What we know: 1.0.4 action JSON has no `description` key [VERIFIED: sample keys].
   - What's unclear: whether 1.0.7 adds one.
   - Recommendation: golden step 6 and finding E8; fall back to a Comment sub-action.
2. **Should the golden be extended now with the Phase 6 example item kinds (Send Message, Play Sound, range If/Else)?**
   - Recommendation: yes if the user is willing, because each later user round-trip is expensive; keep it optional so Phase 1 is not blocked.
3. **Which of F8's two listeners ships?** Resolved by F8; default TcpListener.
4. **Where does `src/` product code start?** Phase 2. Phase 1 only adds `spike/`.
5. **Do we keep the spike actions in the repo permanently?** Recommend keep `spike/` sources and the package manifest (used by the build tests), delete the actions from the user's profile (S7).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| .NET SDK | Compile gate | yes | 9.0.304 (Roslyn 4.14.0-3.25359.3) | none; error clearly if `dotnet` missing |
| NuGet.org (first restore only) | Reference assemblies | yes | `Microsoft.NETFramework.ReferenceAssemblies.net48` 1.0.3 and Newtonsoft.Json 13.0.3 already in `~/.nuget/packages` | After first restore fully offline (tested with an empty source) |
| .NET Framework targeting pack 4.8 | (not needed) | no (only v4.7.1) | - | NuGet reference-assembly package |
| Python | Builder, tools | yes | 3.13.12 (`python` and `py`) | none |
| Node | (not needed) | yes | v24.14.0 | - |
| PowerShell | Optional reflection/stub drift script | yes | 5.1.26100.2161 | skip drift check |
| Streamer.bot | Live spikes, reflection probes | yes, running | 1.0.7 at `D:\Users\qu1ck1y\Documents\tw\StreamerBot\` | n/a |
| Legacy `csc.exe` in `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\` | (do not use) | yes | C# 5-era compiler | never use for the gate |

**Missing dependencies with no fallback:** none for offline work. Live work depends on the user.
**Missing dependencies with fallback:** targeting pack 4.8 (NuGet package used).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Python `unittest` (stdlib) for builder/tools; the compile gate's own `--self-test` for VER-01. No xUnit in Phase 1 |
| Config file | none (`tools/tests/__init__.py` required) |
| Quick run command | `python -I tools/compile_check.py --self-test` |
| Full suite command | `python -I tools/compile_check.py && python -I -m unittest discover -s tools/tests -t tools && python -I tools/build_sb.py build spike --check && python -I tools/check_findings.py docs/live-spikes/FINDINGS.md` |

### Phase Requirements -> Test Map
| Req ID / Criterion | Behavior | Test Type | Automated Command | File Exists? |
|--------------------|----------|-----------|-------------------|-------------|
| VER-01 / SC1 | Gate passes on clean source, fails on broken line with `CS1002`, rejects net48-absent API with `CS0246` | self-test | `python -I tools/compile_check.py --self-test` | Wave 0 |
| PKG-04 / SC2a | Golden has no secrets and expected shape | audit | `python -I tools/build_sb.py audit tools/golden/golden-1.0.7.sb` | Wave 0 (needs user export) |
| PKG-04 / SC2b | Builder output round-trips with no differences; two builds identical; ids deterministic | check mode + unit | `python -I tools/build_sb.py build spike --check` and `python -I -m unittest discover -s tools/tests -t tools` | Wave 0 |
| PKG-04 negative | Mutating one byte/field/id in output makes `check` fail | unit | in `tools/tests/test_build_sb.py` | Wave 0 |
| Serializer fidelity | `dump(parse(golden_json)) == golden_json` | unit | in `test_build_sb.py` (uses the committed golden; before it exists, develop against the three official samples fetched to a scratch dir, not committed) | Wave 0 |
| VER-03 / SC5 | Findings file has all IDs with valid statuses; live claims have evidence + user confirmation | script | `python -I tools/check_findings.py docs/live-spikes/FINDINGS.md` | Wave 0 |
| SC3 import without errors | Imports and compiles in Streamer.bot 1.0.7 | live (user confirms) | precursor: `build_sb.py check dist/spike.sb` + gate on spike sources | n/a |
| SC4 clean exit | `Cleaned up execute code instances`, `Streamer.bot exited`, no process | live (user confirms) | helper: `python -I tools/live_evidence.py --sb-dir <dir> --after-close` | Wave 0 |
| SC4 hang repro | Old pattern lingers | live (user confirms) | same helper | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -I tools/compile_check.py --self-test` and the unit suite once they exist.
- **Per wave merge:** full suite command above.
- **Phase gate:** full suite green plus findings checker green, with live items marked `not verified` unless the user confirmed.

### Wave 0 Gaps
- [ ] `tools/compile_check.py`, `tools/compile-check/CompileCheck.csproj`, `tools/compile-check/Stub/CphStub.cs`, `tools/fixtures/compile/{good,bad_syntax,net48_gap}.cs`
- [ ] `tools/build_sb.py`, `tools/packages/spike.json`, `tools/tests/__init__.py`, `tools/tests/test_build_sb.py`
- [ ] `tools/golden/{RECIPE.md,GoldenRuntime.cs}` then the user's `golden-1.0.7.sb`
- [ ] `spike/DaSpikeA.cs`, `spike/DaSpikeB.cs`
- [ ] `tools/live_evidence.py`, `tools/check_findings.py`, `docs/live-spikes/{RUNSHEET.md,FINDINGS.md}`
- [ ] `.gitignore` additions, `.gitattributes`
- Framework install: none beyond the one-time `dotnet restore`.

## Security Domain

`security_enforcement` is enabled (config.json, `security_asvs_level: 1`).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (no auth in this phase) | - |
| V3 Session Management | no | - |
| V4 Access Control | no | - |
| V5 Input Validation | yes | Bounded `zlib.decompressobj` decode, size cap and JSON-only parse for any `.sb` the tools read; regex-validated GUIDs |
| V6 Cryptography | no | uuid5 is for identity, not security |
| V8 Data Protection | yes | Golden audit, filtered evidence output, no secrets in spike code or logs |
| V14 Configuration | yes | Loopback-only listener binds in spike code; no wildcard prefixes |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secrets/PII committed via golden or findings | Information disclosure | `audit` structural + regex scan, human review checkpoint, evidence script prints markers only |
| Gzip bomb or malicious `.sb` given to `check`/`decode` | Denial of service | `decompressobj` with max size, reject trailing data |
| Spike listener reachable beyond loopback | Spoofing / EoP | Bind `127.0.0.1` only; unguessable path; abort on stop; spike cleanup S7 |
| `.sb` carries executable C# | Tampering | Streamer.bot shows the import warning for Execute C# Code; README (Phase 6) says so; do not embed anything unreviewed |
| Trace file in `%TEMP%` leaks | Information disclosure | Contains only marker text and ids generated by the spike; no user data exists in this phase |
| Credential-bearing CPH members (`TwitchOAuthToken`) misused | Information disclosure | Excluded from stub; forbidden in spike code |

## Sources

### Primary (HIGH confidence)
- Executed this session: `dotnet build` of the tested csproj (clean, broken-line, `#error version`, net48 gap, Toolset 5.6.0 failure, offline restore); Python round-trip of three official `.sb` samples; reflection over the user's Streamer.bot 1.0.7 `Streamer.bot.Common.dll` (`EventType` enum) and `Streamer.bot.Plugin.Interface.dll` (`CPHInlineBase`, `IInlineInvokeProxy`); file-version probe of `Streamer.bot.exe`, `Newtonsoft.Json.dll`, `Microsoft.CodeAnalysis*.dll`; filtered grep of marker lines in `logs/log_20261017.log` (no `data/` file was opened).
- Streamerbot/docs raw files via `gh api`: `streamerbot/4.examples/.imports/{chatbot-commands,wsgs.utils.curl,wsgs.utils.json.parse}.sb` (decoded), `streamerbot/3.api/1.sub-actions/core/csharp/{execute-csharp-code,execute-csharp-method}.md`, `streamerbot/3.api/3.csharp/0.guide/{3.custom-methods,5.debugging}.md`, `.../3.methods/core/triggers/{register-custom-trigger,trigger-code-event}.md`, `streamerbot/3.api/2.triggers/core/streamerbot-started.md`, `streamerbot/2.guide/01.core/09.import-export.md` (import overwrites same-named items by default; per-item Include/Overwrite toggles).
- NuGet registry queries (flat-container index, search API, nuspec) for package versions, owners and downloads.
- Project files read: `.planning/{REQUIREMENTS,STATE,ROADMAP,PROJECT,config.json}`, `.planning/research/{SUMMARY,STACK,ARCHITECTURE}.md`, first 456 lines of `PITFALLS.md`, `.claude/CLAUDE.md` (provided in context).

### Secondary (MEDIUM confidence)
- Vendor VS Code recipe (`visual-studio-code.md`, via fetch summarizer: `net481`, `LangVersion 13.0`, `EXTERNAL_EDITOR` pattern, `CS0114`).
- Official lifecycle-methods page content (via fetch summarizer).
- Prior project research on log observations, third-party `.sb` type notes (streamerz), and DonationAlerts behavior (not re-verified here).

### Tertiary (LOW confidence)
- Web search for an official "Streamer.bot Exiting" or "Dispose on recompile" statement returned nothing relevant; this is silence, not evidence.

## Metadata

**Confidence breakdown:**
- Standard stack / compile gate: HIGH. Executed end to end here, including negative cases and offline restore.
- `.sb` envelope and serializer: HIGH for the 1.0.4 sample format; MEDIUM for 1.0.7 until the golden exists.
- Spike design: MEDIUM. The mechanisms are straightforward; every outcome is live-only and unobserved.
- Pitfalls: HIGH for tooling pitfalls (each reproduced), MEDIUM for lifecycle pitfalls (inferred from prior logs).

**Research date:** 2026-10-17
**Valid until:** 2026-11-17 for tooling (stable); re-check the Streamer.bot version and the 1.1.x line before relying on spike results after any Streamer.bot update.
