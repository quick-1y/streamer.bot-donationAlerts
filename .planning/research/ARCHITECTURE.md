# Architecture Research

**Domain:** Long-lived realtime integration (OAuth + REST + Centrifugo WebSocket) running as inline C# inside Streamer.bot 1.0.x (Windows, .NET Framework)
**Researched:** 2026-10-17
**Confidence:** MEDIUM overall. Component design and patterns: HIGH. Streamer.bot internals: MEDIUM, because the official docs are thin on lifecycle and instance semantics and Streamer.bot is closed source and obfuscated. Most host facts below come from (a) the official docs, (b) the decompiled public interface of the locally installed Streamer.bot 1.0.7, (c) the user's own Streamer.bot 1.0.7 logs, and (d) the local `actions.json` schema. Every claim is tagged. Anything tagged INFER or UNVERIFIED must be proven by the lifecycle spike (section 7) before the roadmap commits to it.

**Evidence tags used below**

| Tag | Meaning |
|-----|---------|
| [DOCS] | Official docs.streamer.bot page or changelog (URL in Sources) |
| [IFACE] | Decompiled `Streamer.bot.Plugin.Interface.dll` from the local 1.0.7 install (the public `CPH` surface). The main `Streamer.bot.exe` is obfuscated and was NOT usable as evidence |
| [LOG] | Excerpt from the user's Streamer.bot 1.0.7 log files (2026-10-14 and 2026-10-17). Quoted in section 2 because the 10-14 file was rotated away during research |
| [EXPORT] | Field names in the local `data/actions.json` and the docs example `.sb` files (field names only, no values read) |
| [INFER] | Reasoned from the above, not directly observed |
| [UNVERIFIED] | Not confirmed anywhere; needs a spike |

---

## 1. Streamer.bot 1.0.x Execution Model (what the design may rely on)

| Question | Finding | Confidence / source |
|----------|---------|---------------------|
| Runtime | Streamer.bot is a WPF app on .NET Framework (CLR v4.0.30319, `supportedRuntime` 4.7.2 in `Streamer.bot.exe.config`). User code is compiled by a bundled Roslyn (5.6.x), so modern C# syntax compiles, but the BCL is the .NET Framework one. `Newtonsoft.Json` 13.0.3 ships beside the exe and is referenced as `.\Newtonsoft.Json.dll` | HIGH [IFACE]/[EXPORT]/file versions |
| Compile unit | Every "Execute C# Code" sub-action is compiled separately and gets its own instance. Log: `InlineCode :: Creating and compiling instance for '<Name>'` | HIGH [LOG] |
| Isolation | Each instance is unloaded individually: `InlineCode :: Unloading '<32-hex id>'`. Docs say scripts run in "an isolated AppDomain sandbox"; 1.0.7 changelog mentions a crash "tied to Execute C# Code's AppDomain being unloaded". Conclusion: one AppDomain per code sub-action instance. Consequence: `static` fields are NOT shared between different code sub-actions (or between two duplicate instances of the same code) | MEDIUM-HIGH [DOCS]+[LOG]+[INFER] |
| Instance lifetime | The instance is created once (at app start if "Precompile on Application Start", otherwise on first use) and then REUSED for every later execution: the same instance GUID is logged for every `Running 'Connect' entry point from instance 'c36c6f8b-...'`. There is no "keep alive" option in the 1.0.7 schema (C# sub-action fields: `byteCode, name, description, precompile, delayStart, references, saveResultToVariable, saveToVariable`). So instance fields and statics persist for the instance's life | HIGH [LOG]/[EXPORT] |
| Recompile | Saving/compiling changed code destroys the old instance mid-session: `Unloading '<id>'` lines appear far from shutdown, and running threads of the old instance die with `ThreadAbortException` (log message: "Donation socket stopped, Поток находился в процессе прерывания" = "Thread was being aborted"). The trigger for those mid-session unloads is inferred to be code re-save | MEDIUM [LOG]+[INFER] |
| Init / Dispose | `Init()` "executed when your code is first compiled, including during Streamer.bot startup". `Dispose()` "always executed on destroy, including during Streamer.bot shutdown". Both optional, `public void`, no `override` (the user class has no base class in source). Whether Dispose is also called on recompile is not documented | HIGH [DOCS]; recompile case UNVERIFIED |
| Hidden base class | The compiled class derives from `CPHInlineBase` (`[Serializable]`, virtual `Init/Dispose/Execute`, exposes `CPH` and `args`). `args` is an INSTANCE field replaced before each run (`___setArguments`) | HIGH [IFACE] |
| Concurrency | The default queue is non-blocking: executions overlap. The SAME instance is entered concurrently (log shows a second `Running 'Connect'` on the same instance while the first is still blocked). In 1.0.x `args` is therefore racy under overlap; 1.1.0-alpha adds "Execution Context Isolation, action args are isolated to each actual run" | HIGH [LOG]/[IFACE]/[DOCS changelog v1.1.0] |
| Duplicate-instance race | When two callers hit a not-yet-created target for the first time at the same instant, two instances of the same named sub-action were created and BOTH ran: `Creating and compiling instance for 'DonationAlert Update Checker'` x2 in the same millisecond, two different GUIDs, two concurrent `DonationCheckerLoop`. Mitigation: precompile the host at app start so the instance exists before any trigger fires, plus a cross-AppDomain single-owner guard (pattern 3) | HIGH that it happened [LOG]; cause MEDIUM [INFER] |
| Cross-action calls | `Execute C# Method` sub-action (type 99998, fields `executeCodeId, method, runOnUiThread, saveResultToVariable, saveToVariable`) or `CPH.ExecuteMethod(string executeCode, string methodName)`. Target method must be `public bool M()` with no parameters, and the code sub-action must have a `Name`. The target instance keeps its private state between calls | HIGH [DOCS]/[IFACE]/[EXPORT] |
| Action queues | Default queue is non-blocking; a blocking queue runs one action at a time. No action timeout is documented or observed. `RunAction(name, runImmediately=true)` runs inline in the caller's queue; `false` enqueues independently without waiting | HIGH [DOCS] |
| Return value | `Execute()`/method returning `false` stops the rest of the action unless "Save Result to Variable" is on | HIGH [DOCS] |
| Threads | Docs: prefer `Task.Run` over `new Thread`; never `async void`; unhandled exceptions on raw threads "can bypass exception barriers and crash the host". Docs say nothing about timers, blocking calls or process exit | HIGH [DOCS] |
| Lifecycle triggers | Only "Streamer.bot Started" exists (variables: none). There is NO documented "Streamer.bot Exiting/Closing" trigger. So `Dispose()` is the single shutdown hook. The "Started" trigger did fire real actions at launch (`Queueing '...' (..., StreamerbotStarted)`) | HIGH [DOCS]/[LOG] |
| Custom triggers | `CPH.RegisterCustomTrigger(triggerName, eventName, string[] categories)` (docs recommend calling it in `Init()` with precompile) and `CPH.TriggerCodeEvent(eventName, Dictionary<string,object> args)` / `(eventName, string json)` / `(eventName, bool useArgs=true)`. Trigger type in action exports: 18002 with fields `eventName, name`. The docs say the dictionary overload "specifies a dictionary of variables for the trigger" | API existence HIGH [IFACE]; that dictionary keys appear as `%args%` in handlers: MEDIUM [DOCS], needs spike |
| Globals | `GetGlobalVar<T>(name, persisted=true)`, `SetGlobalVar(name, value, persisted=true)`, `UnsetGlobalVar`. Persisted globals live in `data/globals.db` (LiteDB), in clear text | HIGH [IFACE] |
| Logging | `LogInfo/LogWarn/LogError/LogDebug/LogVerbose`. User runs at Debug level | HIGH [IFACE]/[LOG] |
| Variable names | Since 1.0.5 spaces are no longer allowed in variable names. Dots (`curl.url`) are used in official examples and are fine | HIGH [DOCS changelog] |
| References in `.sb` | The `references` array holds absolute framework paths (`C:\Windows\Microsoft.NET\Framework64\v4.0.30319\System.dll`, `...\System.Net.Http.dll`, `...\System.Core.dll`) plus the relative `.\Newtonsoft.Json.dll`. `ClientWebSocket`, `HttpListener` are in `System.dll`; `HttpClient` in `System.Net.Http.dll` | HIGH [EXPORT] |
| Built-in HTTP server | Streamer.bot has an HTTP server (default `127.0.0.1:7474`, off by default) but it only serves mapped files and `DoAction`; it exposes no request trigger. It cannot receive the OAuth callback. Rejected | HIGH [DOCS] |

---

## 2. Root-Cause Analysis: why `Streamer.bot.exe` lingers after close

### Observed shutdown outcomes (user's logs, Streamer.bot 1.0.7)

A healthy shutdown logs, in order: `Closing services...` -> `InlineCode :: Cleaning up 'N' execute code instances` -> `Unloading '<id>'` x N -> `Cleaned up execute code instances` -> service disconnects -> settings saves -> `Streamer.bot exited`. Those three marker lines are the objective pass/fail signal for every future manual test.

| Shutdown | Plugin work in flight at that moment | Result |
|----------|--------------------------------------|--------|
| 8 of 9 shutdowns on 2026-10-14 (incl. ones with `DonationCheckerLoop` blocked in receive/sleep) | Idle loops blocked in `ReceiveAsync`/`Thread.Sleep` | Clean: `Cleaned up` within 0.1-0.5 s, `Streamer.bot exited` about 1 s later |
| 2026-10-14 20:35:54 | A WebSocket handshake was mid-flight 2 s earlier (`Subscribe request has been sent`); loops later killed by thread-abort | `Cleaned up` logged, then NOTHING: no Twitch/BTTV disconnect lines, no settings save, no `Streamer.bot exited`. User started a new process 18 s later (and again 10 s after that) |
| 2026-10-17 17:26:01 and 17:29:00 | `DA \| Connect` blocked on the action thread in the OAuth `HttpListener` accept loop (`Server is waiting ...`) | `Cleaning up '1'` logged, then NO `Unloading` and NO `Cleaned up`; shutdown never finished. In the second case the old code's own timer fired at 17:29:10 (`Timer invoked`), i.e. plugin code was still executing 10 s after `Closing services...` |

So 3 of 11 shutdowns hung, and every hang had a plugin-owned blocking operation or in-flight I/O at the moment Streamer.bot began tearing the instance down. Both user-visible signs of a lingering process (no `Streamer.bot exited`, a new launch ~10 s later) match.

### Interpretation (what is established vs inferred)

Streamer.bot's shutdown is sequential and has no timeout. It disposes and unloads each code AppDomain. `AppDomain.Unload` aborts threads inside the domain and must wait for them; a thread that is inside an un-abortable region (pending overlapped I/O from `HttpListener`/`ClientWebSocket`, a blocked synchronous wait that the host is also waiting on, or a cross-domain call into `CPH` that is interrupted while the host holds a lock) stalls the whole sequence, and the process never reaches `Streamer.bot exited`. [INFER from LOG; exact blocking primitive UNVERIFIED]

Candidate causes, ranked:

| Candidate | Verdict | Evidence |
|-----------|---------|----------|
| A long-running `Execute()`/method that never returns (blocking socket loop, blocking OAuth listener) | CONTRIBUTING, strongly supported | The 17 Oct hangs (blocked `Connect`); old `Start` is documented as "must run in background" |
| `Dispose()` that does not quiesce everything (old `Dispose` only calls `SocketService.Close()`, which is null if only `Connect` ran; it never closes the `HttpListener`, the force-close timer, or the `ClientWebSocket` receive) | CONTRIBUTING, strongly supported | Old code + 17 Oct log |
| Pending overlapped I/O on `HttpListener`/`ClientWebSocket` at unload time | LIKELY | Both hang classes had one in flight; idle blocked receives were aborted fine |
| `ReceiveAsync(..., CancellationToken.None)` | CONTRIBUTING (makes teardown depend on thread-abort instead of cooperative cancel) | CONCERNS.md; the old receive can only end by abort |
| `System.Timers.Timer` | Does not keep a process alive by itself (pool thread), but proves the domain was not quiesced | `Timer invoked` after `Closing services...` |
| `Task.Run` loops | Safe (pool threads are background) IF cancellable | .NET semantics |
| Foreground `new Thread` | NOT used by the old fork (grep: no `new Thread`/`IsBackground`), but would by itself keep the process alive under .NET Framework (foreground threads in ANY AppDomain keep the process running). Forbid | .NET semantics; docs also discourage raw threads |
| Missing `AppDomain.ProcessExit` hook | Not the cause. Streamer.bot's own supported hook is `Dispose()`; `DomainUnload`/`ProcessExit` are only belt-and-braces | n/a |

### Design guarantees that follow (G1-G7)

| ID | Rule | Prevents |
|----|------|----------|
| G1 | Every entry point (`Start`, `Stop`, `Connect`, ...) returns in well under 1 s. No entry point contains a loop or an unbounded wait. The only bounded waits are the ones in `Stop`/`Dispose` (cap about 3 s) | Blocked action thread |
| G2 | All long-lived work is `Task.Run` on the pool, owned by one `DaHost` singleton and driven by one lifetime `CancellationTokenSource`. No `new Thread`, no `async void`, no `Task.Factory.StartNew(..., LongRunning)` that could be misconfigured | Foreground threads, unobserved exceptions |
| G3 | Every I/O call takes the token AND the token is registered for a hard abort: `ct.Register(() => socket.Abort())`, `ct.Register(() => listener.Abort())`; HttpClient calls use the token plus a per-request timeout | Un-cancellable receives, pending overlapped I/O |
| G4 | `Dispose()` = quiesce-before-return: cancel lifetime CTS, hard-abort sockets/listeners, join the worker with a bounded wait (about 3 s), dispose HttpClient/timers/semaphore, idempotent, never throws, never calls `CPH` after cancellation except guarded logging. The point is that Streamer.bot's `AppDomain.Unload` finds no live thread of ours | Hangs M1/M2 above |
| G5 | Prefer `Task.Delay(ct)` to timers. Any `Timer` is created by the host and disposed in `Dispose` | Callbacks after shutdown |
| G6 | One owner for the whole feature: static `DaHost` in the host code sub-action plus a cross-domain named `Semaphore` guard (pattern 3) | Duplicate connections from duplicate instances |
| G7 | Observable lifecycle: log `DA lifecycle: Init/Start/Stop/Dispose begin|end (elapsed ms)` at Info. Manual tests assert Streamer.bot's own `Cleaned up execute code instances` and `Streamer.bot exited` lines | Un-testable "it seems to close fine" |

---

## 3. Standard Architecture

### System Overview

```
                    Streamer.bot 1.0.x process (.NET Framework, WPF)
  +--------------------------------------------------------------------------------+
  |  Actions (in .sb)                         Code Event triggers (type 18002)     |
  |  DA|Connect  DA|Start  DA|Stop            da.donation  da.goal  da.status      |
  |  DA|Restart  DA|Status DA|Auto-start       ^  (user handler actions)           |
  |        |  Execute C# Method (public bool M(), no params)                       |
  |        v                                    |  CPH.TriggerCodeEvent(name, dict) |
  |  +--------------------------- AppDomain: "DonationAlerts Runtime" ----------+  |
  |  | CPHInline (thin adapter: Init/Dispose/Execute + public bool entry points)|  |
  |  |        |  delegates                                                      |  |
  |  |        v                                                                 |  |
  |  |  DaHost (static singleton, state machine, lifetime CTS, single-owner)    |  |
  |  |    |            |                |                 |                     |  |
  |  |  Config     TokenStore      Supervisor ------> Dispatcher (bounded queue)|  |
  |  |  (validate) (globals,       (backoff+jitter,    + consumer Task --------- +--+
  |  |             refresh 1x)      reconnect loop)         ^                    |  |
  |  |    |            |                |                   |                    |  |
  |  |  OAuthFlow   RestClient     CentrifugoClient    EventMapper + Deduper     |  |
  |  |  (state,     (1 HttpClient,  (1 session:        (pure, offline-testable)  |  |
  |  |   ephemeral   timeouts)      connect, subscribe,                          |  |
  |  |   listener)       |          idle watchdog)                               |  |
  |  |                   |                |             AudioDownloader  UpdateChecker|
  |  |  Logger (redaction, lifecycle markers)  Clock/Rng seams (tests)           |  |
  |  +---------------------------------------------------------------------------+  |
  +----------------------|----------------------------|-----------------------------+
                         v                            v
        www.donationalerts.com (OAuth, REST)   centrifugo.donationalerts.com (wss)
                         GitHub releases API (update check, daily)
```

### Component Responsibilities

| Component | Responsibility | Owns threads / I/O | Talks to | Offline-testable |
|-----------|----------------|--------------------|----------|------------------|
| `CPHInline` adapter | Public entry points only (`Init`, `Dispose`, `Execute`, `Connect`, `Start`, `Stop`, `Restart`, `Status`, `SignOut`, `CheckUpdates`, `EnsureDefaults`). Reads `args` once at entry; never keeps it. Wraps `CPH` into a small `IHostApi` (log, global get/set, trigger event, chat, register trigger) | none | `DaHost` | Compile check only |
| `DaHost` | Singleton lifecycle and state machine (`Stopped, Starting, Connecting, Running, Backoff, AuthRequired, Stopping, Disposed`). Idempotent `Start/Stop/Restart`, bounded `Dispose`, single-owner guard, status snapshot | Lifetime CTS, one worker `Task` | everything below | Yes (fake worker, fake clock) |
| `Config` | Reads globals into an immutable snapshot; validates (client id present, secret present, redirect URL is loopback `http://127.0.0.1:<port>/path/`, numeric ranges); returns a list of problems; no silent defaults for malformed values (warn) | none | `IHostApi` | Yes |
| `TokenStore` | Reads/writes access token, refresh token, expiry in persisted globals; single-flight refresh guarded by `SemaphoreSlim`; refresh at 80 percent of lifetime and on 401; clears on sign-out. Optional DPAPI (`ProtectedData`, CurrentUser) so tokens are not clear text at rest | none | `RestClient`, `IHostApi` | Yes (fake REST) |
| `OAuthFlow` | One pending flow at a time. Random 128-bit `state` (RNGCryptoServiceProvider), builds authorize URL, ephemeral loopback listener, validates path + `state` + single use, exchanges the code, serves HTML-encoded success/error page, hard timeout, cancel on `Dispose`. Never persists the code | Listener (ephemeral), one `Task` | `RestClient`, `TokenStore` | Partly (state/URL logic yes; listener via loopback test) |
| `RestClient` | The only HTTP user. One `HttpClient` (timeout about 15 s, fixed User-Agent), typed results (`Ok`, `Unauthorized`, `RateLimited(retryAfter)`, `Transient`, `Fatal`). Endpoints: token, refresh, user profile (`socket_connection_token`), `centrifuge/subscribe`, optional `alerts/donations` backfill. Respects the 60 requests/min API limit | none | DonationAlerts REST | Yes (fake handler) |
| `CentrifugoClient` | ONE session: connect with token, read client id, REST-subscribe for channel tokens, send subscribe frames, require confirmation with timeout, receive loop with fragment assembly + size cap, idle watchdog and protocol ping/pong, returns a `SessionEnd` reason (`ClosedByServer, Idle, AuthError, Fatal, Cancelled`). Never reconnects itself | One `ClientWebSocket`, registered for abort on cancel | `RestClient`, `EventSink` | Yes (fake server in tests) |
| `Supervisor` | The reconnect loop around sessions: exponential backoff with full jitter (1 s -> 60 s cap), reset after a stable session, refresh token once on `AuthError`, stop in `AuthRequired` on refresh failure, emit status events | The worker `Task` body | `CentrifugoClient`, `TokenStore`, `Dispatcher` | Yes (fake client, fake clock) |
| `EventMapper` | Tolerant JSON -> `DonationEvent`/`GoalEvent` (invariant culture, missing fields flagged, no silent drop of amount 0 without Debug log) -> flat `Dictionary<string,object>` for the new argument contract (original amount + currency + main-currency amount, message, donor, audio path) | none | pure | Yes |
| `Deduper` | Bounded LRU of donation ids (for example 500) and goal state tuples `(goalId, raised, isActive)`; optionally persists the last few ids in a global to survive a recompile | none | pure | Yes |
| `Dispatcher` | Bounded `BlockingCollection<T>` + one consumer `Task`. Calls `CPH.TriggerCodeEvent(eventName, dict)` in order, isolates receive loop from `CPH` latency, drops oldest with a warning on overflow, stops on cancel | One consumer `Task` | `IHostApi` | Yes |
| `AudioDownloader` | Async, own deadline (about 10 s) so a slow file never delays the event past the deadline (dispatch without audio and flag `audioError`); `https` only, host allow-list, size cap (header + streaming), numeric-id file names in a private temp dir, cleanup at start, on TTL and in `Dispose` | none (uses `RestClient`'s `HttpClient`) | `Dispatcher` pipeline | Yes |
| `UpdateChecker` | Fire-and-forget `Task`, at most once per 24 h (`lastCheck` persisted), short timeout, semver compare, log (and optional chat) once per new version; never runs inside `Init` or blocks anything | one short `Task` | GitHub API | Yes (version compare) |
| `Logger` | Prefix, levels, redaction (Bearer, JWT-shaped, `access_token`, `refresh_token`, `client_secret`, `code=`), duplicate throttling, lifecycle markers. Donor name and message text only at Debug and only via the mapper, never raw frames | none | `IHostApi` | Yes (redaction) |
| `Clock`, `Rng` | Seams for deterministic tests of backoff, expiry and state | none | n/a | n/a |

### Recommended Project Structure

The runtime artifact must be ONE C# file (project constraint), so the structure is one source file with sections, plus tooling around it:

```
src/
  DonationAlerts.cs        # the single Streamer.bot code body; sections in this order:
                           #   1 CPHInline adapter  2 DaHost  3 Config  4 TokenStore  5 OAuthFlow
                           #   6 RestClient  7 CentrifugoClient  8 Supervisor  9 EventMapper+Deduper
                           #  10 Dispatcher  11 AudioDownloader  12 UpdateChecker  13 Logger/Redactor
                           #  Interfaces (IHostApi, IClock, IRng, IHttp) live at the top
tools/
  build-sb.*               # generates the .sb from source + manifest (stable GUIDs) [owned by .sb research]
  check-compile.*          # Roslyn compile of src/DonationAlerts.cs against .NET Framework reference
                           # assemblies + stubs for CPHInlineBase/IInlineInvokeProxy
tests/
  DonationAlerts.Tests/    # compiles the SAME file (linked, not copied) with stubs; unit tests for
                           # Config, Backoff, Deduper, EventMapper, Redactor, state machine,
                           # TokenStore with fake REST, Supervisor with fake client/clock,
                           # CentrifugoClient against an in-test WebSocket server
  fakes/                   # fake Centrifugo + fake DonationAlerts REST server for integration tests
dist/
  DonationAlerts.sb        # build output (ignored by git or a release asset)
```

Structure rationale:
- Single file keeps the import model; sections plus interfaces at the top keep it navigable and testable.
- Tests link the production file rather than copy it, so a compile error (like the old missing semicolon at `integration.cs` line 89) fails CI immediately. The only test-time shim is a stub `CPHInlineBase`/`IInlineInvokeProxy` (the real `Streamer.bot.Plugin.Interface.dll` can be referenced from a local install via a property, never committed). How the stub base is attached to `CPHInline` (partial-class shim vs text transform in the build script) is UNVERIFIED because Streamer.bot's own rewriter may not like `partial`; use a build-time text transform unless the spike proves `partial` is safe.
- Everything that decides behavior (state, backoff, dedupe, parsing, redaction, URL building) takes interfaces for clock/random/HTTP/host so it is testable offline; only `CPHInline` and the real `IHostApi` touch `CPH`.

---

## 4. Architectural Patterns

### Pattern 1: Thin adapter + static host singleton

**What:** `CPHInline` contains no logic. It forwards to a `static DaHost` created in `Init()` (cheap, no network, no threads) and torn down in `Dispose()`.
**When to use:** Always. Statics live as long as the AppDomain; the instance is long-lived too, but nothing in 1.0.x guarantees the host never creates a second `CPHInline` in the same domain, so state must not depend on instance identity.
**Trade-offs:** Must guard against `Dispose()` of a stale instance shutting down a newer host (use an ownership token compared in `Dispose`). One extra indirection.

```csharp
public class CPHInline
{
    private object _token;                                   // ownership token for this instance

    public void Init()
    {
        try { _token = DaHost.Attach(new SbHostApi(CPH)); }  // no network, no Task here
        catch (Exception ex) { SbHostApi.SafeLog(CPH, ex); } // Init must never throw
    }

    public void Dispose()
    {
        try { DaHost.Detach(_token, TimeSpan.FromSeconds(3)); } catch { }  // quiesce, bounded
    }

    public bool Execute() { return true; }                   // required minimum; harmless
    public bool Start()   { return DaHost.Current.Start(); } // returns in milliseconds
    public bool Stop()    { return DaHost.Current.Stop(); }  // bounded wait
    public bool Connect() { return DaHost.Current.BeginConnect(); } // listener runs in background
}
```

### Pattern 2: Fire-and-forget worker with cooperative cancel and quiesce-before-return Dispose

**What:** `Start()` flips state under a lock and launches `Task.Run(() => RunAsync(cfg, ct))`; it never waits for the connection. `Stop()`/`Dispose()` cancel a CTS, hard-abort the socket/listener through registered callbacks, then join with a bounded wait.
**When to use:** All long-lived work.
**Trade-offs:** User feedback is asynchronous (status event, log, global) instead of an action result; that is the price of G1.

```csharp
public bool Start()
{
    lock (_gate)
    {
        if (_disposed) return false;
        if (_state == State.Running || _state == State.Connecting || _state == State.Backoff
            || _state == State.Starting) { Log.Info("Start ignored: already running"); return true; }
        if (!Config.TryLoad(_host, out var cfg, out var problems)) { Log.Error(problems); return false; }
        if (!_ownerGuard.TryAcquire()) { Log.Warn("Another DonationAlerts instance owns the connection"); return false; }
        _run = CancellationTokenSource.CreateLinkedTokenSource(_life.Token);
        var ct = _run.Token;
        SetState(State.Starting);
        _worker = Task.Run(() => SuperviseAsync(cfg, ct)).ContinueWith(OnWorkerEnded);  // never async void
    }
    return true;
}

public bool Stop() // idempotent, bounded
{
    CancellationTokenSource run; Task worker;
    lock (_gate) { run = _run; worker = _worker; _run = null; _worker = null; SetState(State.Stopping); }
    try { run?.Cancel(); } catch { }
    try { worker?.Wait(TimeSpan.FromSeconds(3)); } catch { }   // swallow cancel/aggregate
    run?.Dispose(); _ownerGuard.Release(); lock (_gate) SetState(State.Stopped);
    return true;
}
```

Inside I/O code: `using (ct.Register(() => socket.Abort())) await socket.ReceiveAsync(buf, ct).ConfigureAwait(false);`. Use `ConfigureAwait(false)` everywhere in background code (an action started with "run on UI thread" has a synchronization context).

### Pattern 3: Single-owner guard across AppDomains

**What:** A named kernel `Semaphore` (initial 1, max 1, name `Local\StreamerBot.DonationAlerts.Worker`) is acquired with `WaitOne(0)` when the worker starts and released in `Stop`/`Dispose`. A second instance (duplicate code sub-action, or the first-use race seen in the logs) cannot start a second connection.
**When to use:** Always, as defense in depth. The primary fix is `Precompile on Application Start` on the host sub-action plus having exactly one host sub-action.
**Trade-offs:** If an AppDomain dies without releasing, the handle is closed when the domain unloads, so the name is freed; a semaphore (not a `Mutex`) is used because it has no thread affinity and no abandoned-mutex exception. Needs a spike to confirm behavior across Streamer.bot's AppDomains [UNVERIFIED].

### Pattern 4: Event pipeline with a single consumer

**What:** `CentrifugoClient` frame -> `EventMapper` -> `Deduper` -> `Dispatcher.Enqueue` (returns immediately) -> consumer `Task` -> `CPH.TriggerCodeEvent("da.donation", dict)`.
**Why:** The receive loop must stay responsive to pings and cancellation, and `CPH` calls cross an AppDomain boundary and can be slow or throw during shutdown. Exactly-once effect = at-least-once delivery from DonationAlerts + dedupe by id before dispatch. A crash between receive and dispatch loses the event (DonationAlerts does not replay); the optional REST backfill (`GET /api/v1/alerts/donations`, scope `oauth-donation-index`) after each reconnect closes the gap and is deduped by the same ids.
**Argument passing:** use the dictionary overload of `TriggerCodeEvent`. Do NOT call `CPH.SetArgument` from the worker: outside an action execution there is no defined target context, and `args` is a shared instance field in 1.0.x.

```csharp
// consumer Task body
foreach (var ev in _queue.GetConsumingEnumerable(ct))
{
    if (ct.IsCancellationRequested) break;
    try { _host.TriggerCodeEvent(ev.EventName, ev.Args); }       // Dictionary<string,object>
    catch (Exception ex) { Log.Error("dispatch failed: " + Redactor.Scrub(ex.Message)); }
}
```

### Pattern 5: Reconnect state machine with backoff and jitter

**What:** Supervisor loop: `delay = rand(0, min(60 s, 1 s * 2^attempt))` (full jitter); `attempt` resets to 0 only after a session was subscribed AND stayed up at least 60 s; `AuthError` (401) triggers one single-flight token refresh then immediate retry; refresh failure -> `AuthRequired` (stop looping, emit `da.status`, tell the user to run `DA | Connect`); `Fatal` (bad config, 403 scope missing) -> stop, do not hot-loop.
**Cost model:** each reconnect = profile GET + subscribe POST = 2 requests against the 60/min limit; backoff cap keeps this at 2/min worst case. The channel tokens are bound to the new Centrifugo client id, so a reconnect always repeats the whole handshake (never reuse old channel tokens).
**Idle watchdog:** treat "no inbound frame for N seconds" (N derived from the server ping interval, for example 3x) as a dead connection and cancel the session; also send the protocol ping/pong the DonationAlerts Centrifugo version expects (exact framing belongs to the STACK/protocol research).

### Pattern 6: Ephemeral OAuth listener

**What:** `Connect` starts the browser and a background `Task` that owns an `HttpListener` bound to the configured loopback prefix. The task races `GetContextAsync()` against `Task.Delay(timeout, ct)`, validates path and `state`, answers exactly one valid callback (others get 400 without touching state), then `Close()`s the listener in `finally`. `ct.Register(() => listener.Abort())` ties it to `Dispose`. At most one flow may be pending; a second `Connect` cancels and replaces it.
**Fallback:** if the lifecycle spike shows an open `HttpListener` can stall unload even when aborted, replace it with a `TcpListener` on `127.0.0.1` and a 30-line request-line parser (deterministic `Stop()`, no http.sys kernel state, no URL-prefix conflicts). The user's log shows `HttpListener` on `http://127.0.0.1:8554/...` works without admin rights, and a second concurrent listener fails with a prefix-conflict message, which also proves the first flow's listener was still held by a blocked action thread.

### Pattern 7: Secrets and logging hygiene

All outbound log strings go through `Redactor.Scrub`. Log ids and amounts, not payloads. No raw frames, no profile JSON, no handshake bodies. Tokens: persisted globals only (cleared by `SignOut`), optionally DPAPI-protected with fallback to "please re-authorize" if unprotect fails (profile moved to another machine). The authorization `code` is never persisted. README must state that `.sb` exports and Streamer.bot backups can contain `globals.db` secrets.

---

## 5. The `.sb` Package: actions, triggers, code, invocation

(Field-level `.sb` encoding, GUID stability and import behavior are owned by the parallel `.sb` format research; this section defines WHAT goes in.)

**One host code sub-action, many one-line actions.**

| Action (group `DonationAlerts`) | Trigger | Sub-actions | Notes |
|---------------------------------|---------|-------------|-------|
| `DA \| Runtime (host, do not delete)` | none | Execute C# Code, `Name = "DonationAlerts Runtime"`, **Precompile on Application Start = on**, Delayed Start = off initially | The ONLY code sub-action in the package. Its `Execute()` returns `true` and does nothing. Description explains it must stay enabled and unrenamed. `Init()` attaches the host and registers custom triggers |
| `DA \| Setup (run once)` | none | Execute C# Method `EnsureDefaults` | Creates non-secret globals with defaults so they appear in the Variables UI; logs a checklist. Secrets (`client id`, `client secret`) are never shipped in the package |
| `DA \| Connect (authorize)` | none | Execute C# Method `Connect` | Returns immediately; browser opens; result via status event/log |
| `DA \| Start` | none | Execute C# Method `Start` | Idempotent |
| `DA \| Stop` | none | Execute C# Method `Stop` | Idempotent, bounded |
| `DA \| Restart` | none | Execute C# Method `Restart` | Stop then Start |
| `DA \| Status` | none | Execute C# Method `Status` | Logs state, last event time, token expiry (never the token) |
| `DA \| Sign out` | none | Execute C# Method `SignOut` | Stop, clear tokens locally |
| `DA \| Auto-start` | **Streamer.bot Started** | Execute C# Method `StartAuto` | `StartAuto` checks the `autoStart` global (default on) and returns false with a clear log line if not authorized |
| `DA \| Update check` | **Streamer.bot Started** (or Timed Action) | Execute C# Method `CheckUpdates` | Method itself enforces once per 24 h |
| `DA Example \| On donation` | Code Event `da.donation` | Log + chat message using the new args | Disabled by default; shows amount tiers with `If` |
| `DA Example \| On goal` | Code Event `da.goal` | Log | Disabled by default |
| `DA Example \| On status` | Code Event `da.status` | Log / optional chat | Disabled by default |

**Why auto-start is a trigger action, not `Init()`:** `Init()` runs while Streamer.bot is still bringing services up and also on any lazy compile (for example the first click on `DA | Stop` would otherwise auto-start the thing it is about to stop). A "Streamer.bot Started" action is explicit, visible, individually disableable, and was observed to fire normally at launch. Consequence: after the user re-saves code (recompile) the integration is stopped until `DA | Start` runs; document it. [INFER, spike S1 verifies ordering]

**Why Code Events instead of `RunAction` by naming convention:** (a) no dependency on user-named actions (the old `DonationHandler_<amount>` scheme), (b) arguments travel in the dictionary, independent of any execution context, (c) several handlers can subscribe, (d) amount filtering uses Streamer.bot's own `If` sub-actions, (e) a handler failure cannot break the receive loop. `RunAction` remains available for users but is not the contract.

**How methods are invoked:** every control action contains a single `Execute C# Method` sub-action whose `executeCodeId` points at the host sub-action's id and whose `method` is the public method name. From other code: `CPH.ExecuteMethod("DonationAlerts Runtime", "Start")`. All entry points are `public bool Name()` with no parameters, read `args` once at the top if they need any, and return quickly.

**Custom triggers registered in `Init()`:** `da.donation` ("DonationAlerts: Donation"), `da.goal` ("DonationAlerts: Goal progress"), `da.status` ("DonationAlerts: Connection status"). The `.sb` also carries the type-18002 triggers on the example actions. Whether an imported type-18002 trigger fires before `RegisterCustomTrigger` has run is UNVERIFIED (registration is known to affect the trigger picker; firing is expected to match by `eventName`).

**Queues:** default queue everywhere except a recommended blocking queue `DonationAlerts - Alerts` for user alert handlers so OBS/TTS reactions play one at a time (user-configured; do not rely on queue import behavior for the control actions).

---

## 6. Data Flow

### Startup / auto-start

```
Streamer.bot launches
  -> (precompile) compile host sub-action -> new AppDomain -> CPHInline ctor -> Init():
       DaHost.Attach (no I/O), RegisterCustomTrigger x3
  -> "Streamer.bot Started" fires -> DA | Auto-start -> Execute C# Method StartAuto
       -> DaHost.Start(): validate Config -> acquire owner guard -> Task.Run(Supervise) -> return true (ms)
Supervise (pool thread, background):
  token fresh? --no--> TokenStore.Refresh (single flight)
  RestClient.GetProfile -> socket_connection_token
  CentrifugoClient.Connect -> client id
  RestClient.Subscribe(client id, channels) -> channel tokens
  CentrifugoClient.Subscribe(frames) -> require confirmation (timeout)  => state Running, emit da.status
  receive loop (idle watchdog, ping/pong) ...
```

### Request Flow: donation event

```
DonationAlerts -> Centrifugo frame
  -> CentrifugoClient (assemble, size cap)
  -> EventMapper (typed, culture-invariant) -> Deduper (id seen? drop)
  -> [AudioDownloader, own deadline; failure => no audio, flag set]
  -> Dispatcher.Enqueue (returns immediately)
  -> consumer Task -> CPH.TriggerCodeEvent("da.donation", {da.id, da.amount, da.currency,
                       da.amountMain, da.donor, da.message, da.audioPath, ...})
  -> Streamer.bot ActionDispatcher queues every action with that Code Event trigger
  -> user's handler: chat message, OBS, TTS, tier logic
```

### State Management

```
State (DaHost, under one lock):  Stopped -> Starting -> Connecting -> Running
                                   ^            |            |          |
                                   |            +--- error --+--> Backoff (jittered) --> Connecting
                                   |                                    |
                                   +---- Stopping <---- Stop/Dispose    +--> AuthRequired (terminal until Connect)
Persisted (globals): config, tokens, expiry, lastUpdateCheck, (optional) recent donation ids
In-memory only:      dedupe LRU, queue, attempt counter, current session, last event time
```

### Key Data Flows

1. **Connect (OAuth):** `DA | Connect` -> `OAuthFlow` builds URL with random `state` -> browser opens -> background listener validates `state`, single use -> code exchange via `RestClient` -> `TokenStore` persists -> status event `da.status=authorized` -> user runs/auto-runs `Start`.
2. **Token refresh:** on 80 percent of lifetime, on any 401 from REST or on `AuthError` from a session. Single flight; refresh failure -> `AuthRequired`. (The DonationAlerts doc example shows very long `expires_in`, so refresh is rare but must still work.)
3. **Shutdown (the critical flow):** Streamer.bot `Closing services...` -> `Cleaning up 'N'` -> `Dispose()` -> `DaHost.Detach`: set `_disposed`, cancel lifetime CTS -> registered callbacks abort socket/listener -> dispatcher consumer exits -> bounded join (3 s) -> dispose HttpClient, semaphore, timers -> return -> `Unloading '<id>'` finds no live thread -> `Cleaned up execute code instances` -> `Streamer.bot exited`.
4. **Recompile during a stream:** same as shutdown for the old instance (if Dispose runs on recompile; UNVERIFIED, otherwise thread-abort), then a new instance and no worker until `DA | Start`. The Deduper is lost unless the optional persisted recent-ids global is used.

---

## 7. Suggested Build Order (dependencies and risk first)

Highest risk first, because both gate the whole project and neither can be verified offline.

| # | Stage | Builds | Verifies (pass criteria) | Depends on |
|---|-------|--------|---------------------------|------------|
| S1 | **Lifecycle spike** (real Streamer.bot 1.0.7, by the user, with a ~100-line throwaway host + a log-marker `Dispose`) | Host sub-action with `Init`/`Dispose`/`Start`/`Stop`; scenarios: (a) background `Task.Run` loop survives `Execute()` return; (b) `Dispose` cancels it and logs on app close; (c) Dispose on recompile? (d) is the instance and a `static` shared by two `Execute C# Method` actions; (e) duplicate first-use race with and without precompile; (f) open `HttpListener` + pending `ClientWebSocket.ReceiveAsync` at app close, with and without cooperative cancel in Dispose; (g) deliberately blocked `Execute()` to reproduce the old hang; (h) `RegisterCustomTrigger` in `Init` + `TriggerCodeEvent` with dictionary: do `%args%` appear; (i) named `Semaphore` visible across code sub-actions; (j) ordering of precompile `Init` vs "Streamer.bot Started" | Every close shows `Cleaned up execute code instances` and `Streamer.bot exited` and no process in Task Manager; (g) reproduces the hang so the fix is proven, not assumed | none |
| S2 | **`.sb` format spike** (parallel research) | Generate a minimal `.sb` with one host code sub-action + Execute C# Method + type-18002 trigger + "Started" trigger; import into 1.0.7 | Imports cleanly; ids stable on re-import; references resolve | none |
| S3 | **Offline harness** | `check-compile` + test project linking `src/DonationAlerts.cs` with `CPHInlineBase` stub | A deliberately broken file fails CI; empty host compiles | none |
| 1 | **Core skeleton** | `Logger/Redactor`, `Config`, `DaHost` state machine, adapter, owner guard, fake worker | Unit tests for idempotent Start/Stop/Restart, repeated Start/Stop creates one worker; manual: 20 rapid Start/Stop clicks, close app, markers in S1 | S1, S3 |
| 2 | **Auth** | `RestClient`, `TokenStore`, `OAuthFlow` (with `state`) | Tests: state mismatch, port busy, timeout, cancel; manual: real Connect, `DA \| Connect` closing mid-flow then closing the app | 1 |
| 3 | **Realtime** | `CentrifugoClient`, `Supervisor`, `EventMapper`, `Deduper`, `Dispatcher` | Fake-server tests: drop, duplicate frames, silent stall (watchdog), 401 -> refresh, subscribe never confirmed; manual: real test donation, router/Wi-Fi flap, close app while connected | 2 |
| 4 | **Extras** | `AudioDownloader`, `UpdateChecker`, optional REST backfill, DPAPI | Size/host/scheme/timeout tests; update check throttle | 3 |
| 5 | **Package + docs** | `.sb` build, examples, Russian README, manual test checklist | Fresh-profile import test by the user | S2, 1-4 |

Ordering rationale: lifecycle correctness is the stated core value and cannot be bolted on later (it constrains every component's I/O style), so S1 and Stage 1 precede any protocol work. Auth precedes realtime because the socket needs tokens. Extras are isolated, off the hot path, and cannot affect exit behavior if built to G1-G7.

**Research flags for phases**
- S1/Stage 1: needs hands-on verification in the user's Streamer.bot (cannot be settled by docs).
- Stage 3: protocol framing (Centrifugo version, ping/pong, subscribe response shape) needs the protocol-level research, not covered here.
- Stage 2: standard patterns; low risk except the HttpListener-vs-TcpListener decision made by S1.

---

## 8. Anti-Patterns

### Anti-Pattern 1: Hosting the loop in the action thread

**What people do:** `Start()` runs `while(!stop){ ReceiveAsync().GetAwaiter().GetResult(); Thread.Sleep(...); }`, README says "run in background".
**Why it's wrong:** The action thread is held for the whole stream; Streamer.bot's shutdown cleanup then waits on a plugin thread it can neither stop nor time out (see section 2: hangs). Also concurrent re-entry on the same instance.
**Do this instead:** G1/G2: return immediately; background `Task` owned by `DaHost`.

### Anti-Pattern 2: `Dispose()` that only "closes the socket"

**What people do:** Dispose calls `SocketService.Close()` if non-null.
**Why it's wrong:** Misses listeners, timers, pending sends, HttpClient, the worker itself; `Abort()` before `CloseAsync` throws and the disconnect event is lost.
**Do this instead:** G4 quiesce-before-return with bounded join.

### Anti-Pattern 3: `args` or `CPH.SetArgument` from background work

**What people do:** Set arguments from the socket thread and call `RunAction`.
**Why it's wrong:** No execution context exists for a background `Task`; `args` is a shared instance field in 1.0.x (races under overlap).
**Do this instead:** `TriggerCodeEvent(name, Dictionary<string,object>)`.

### Anti-Pattern 4: Multiple code sub-actions each holding a copy/part of the integration

**What people do:** Paste the same code into every action ("DA | Start", "DA | Stop", ...), or split state across several code sub-actions.
**Why it's wrong:** Each sub-action is its own AppDomain with its own statics; Start in one cannot see the connection of another; the logs show five simultaneous "Ready to connect" workers from such a setup.
**Do this instead:** exactly one host code sub-action; control actions call it with `Execute C# Method`.

### Anti-Pattern 5: Lazy first-use creation of the host

**What people do:** Let the first trigger create the instance.
**Why it's wrong:** Observed duplicate instances when two callers race.
**Do this instead:** Precompile on Application Start + owner guard.

### Anti-Pattern 6: Foreground or raw threads, `async void`, `Timer` leaks

**Why it's wrong:** Can keep the process alive or crash the host. **Instead:** `Task.Run`, `async Task`, `Task.Delay(ct)`, dispose timers.

### Anti-Pattern 7: Trusting the callback and the payload

Accepting any `?code=` (login CSRF), logging raw frames, downloading any URL. **Instead:** `state` validation, redaction, host/scheme/size checks, dedupe by id.

### Anti-Pattern 8: Chat output that can re-trigger commands

The user's 17 Oct log shows `DA | Connect` re-queued repeatedly by `TwitchChatMessage` events from the bot account right after it spoke (a command trigger matching the bot's own message). **Instead:** do not ship command triggers named like our messages; keep chat output opt-in, short and not command-shaped; tell users to exclude the bot account if they add chat commands.

---

## 9. Load and Capacity

| Concern | Expected | Design response |
|---------|----------|-----------------|
| Event rate | Donations: handfuls per minute at most; goals: low | Bounded queue (for example 256), drop-oldest with warning; single consumer is enough |
| REST budget | 60 requests/minute per application | 2 requests per reconnect, backoff cap 60 s, optional backfill is one page, no polling |
| Memory | Small | LRU of 500 ids, no payload retention, temp audio cleaned on TTL and `Dispose` |
| Multiple accounts | Out of scope | Not designed; state is one `DaHost` |
| Handler fan-out | User-defined | Streamer.bot queues per handler; recommend a blocking queue for alerts |

---

## 10. Integration Points

### External Services

| Service | Integration pattern | Notes |
|---------|---------------------|-------|
| DonationAlerts OAuth/REST | Single `HttpClient`, timeouts, typed results | 60 req/min; refresh on 401; `socket_connection_token` from profile; scopes: `oauth-user-show`, `oauth-donation-subscribe`, `oauth-goal-subscribe` (+ `oauth-donation-index` only for backfill) |
| Centrifugo `wss://centrifugo.donationalerts.com/connection/websocket` | `ClientWebSocket`, one per session | Channel tokens come from the REST subscribe call and are tied to the new client id; never reuse across sessions |
| GitHub releases | `HttpClient`, daily, short timeout | Unauthenticated limit 60/h per IP; throttle persisted |
| Browser | `CPH`/`Process.Start` for the authorize URL | Loopback redirect only |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Streamer.bot actions to host | `Execute C# Method` / `CPH.ExecuteMethod` (`public bool M()`) | Cross-AppDomain call; keep fast |
| Host to Streamer.bot | `CPH` proxy only: log, globals, `TriggerCodeEvent`, `SendMessage`, `RegisterCustomTrigger` | Guard every call with try/catch + cancellation check; calls can throw while the domain unloads |
| Supervisor to client | `SessionEnd` result, no exceptions for control flow | Keeps the state machine testable |
| Pipeline stages | In-process calls; the dispatcher queue is the only async boundary | Decouples receive loop from `CPH` latency |

---

## 11. Open Questions (UNVERIFIED, resolve in S1/S2)

1. Is `Dispose()` called when code is re-saved/recompiled mid-session, or is the domain just unloaded (thread abort)?
2. Exact blocking primitive behind the shutdown hangs (HttpListener overlapped I/O vs cross-domain `CPH` call vs wait on in-flight execution). The design (G1-G7) removes all candidates, but S1(g)/(f) should reproduce the hang first so the fix is demonstrated.
3. Do dictionary keys passed to `TriggerCodeEvent` appear as `%da.amount%`-style arguments in handlers exactly as written (dots, case, non-string values)?
4. Does an imported type-18002 trigger fire when its `eventName` was never registered via `RegisterCustomTrigger`?
5. Ordering of precompile `Init()` relative to services/"Streamer.bot Started"; does `Delayed Start` change it?
6. Is a named kernel `Semaphore` truly shared across Streamer.bot's per-instance AppDomains?
7. Does Streamer.bot's source rewriter accept `partial class CPHInline` (matters only for the test shim)?
8. Does the 1.1.0 line (alpha 2026-10-09) change instance/argument semantics ("Execution Context Isolation")? Target 1.0.x; re-test on 1.1.x before claiming support.
9. Does an action with no triggers, or a disabled action, still precompile and serve `ExecuteMethod`? (matters for the host action's shape)

---

## Sources

- Official lifecycle methods: https://docs.streamer.bot/api/csharp/guide/lifecycle-methods (HIGH)
- Official custom methods / ExecuteMethod: https://docs.streamer.bot/api/csharp/guide/custom-methods (HIGH)
- Official threading best practices (AppDomain sandbox, Task.Run, async void): https://docs.streamer.bot/api/csharp/guide/threading-best-practices (HIGH)
- Execute C# Code (precompile, delayed start, name): https://docs.streamer.bot/api/sub-actions/core/csharp/execute-csharp-code (HIGH)
- Execute C# Method: https://docs.streamer.bot/api/sub-actions/core/csharp/execute-csharp-method (HIGH)
- RegisterCustomTrigger: https://docs.streamer.bot/api/csharp/methods/core/triggers/register-custom-trigger (HIGH)
- TriggerCodeEvent / Custom Code Event trigger: https://docs.streamer.bot/api/csharp/methods/core/triggers/trigger-code-event and https://docs.streamer.bot/api/triggers/custom/code-event (MEDIUM, sparse)
- Actions and queues: https://docs.streamer.bot/guide/actions , https://docs.streamer.bot/faq/action-blocking (HIGH)
- Streamer.bot Started trigger: docs repo `streamerbot/3.api/2.triggers/core/streamerbot-started.md` (HIGH)
- HTTP server (static files/DoAction only): docs repo `streamerbot/3.api/5.http/0.guide/0.configuration.md` (HIGH)
- Changelogs: https://docs.streamer.bot/changelogs/v1.0.7 (AppDomain-unload crash fix, C# exception isolation), https://docs.streamer.bot/changelogs/v1.1.0 (Execution Context Isolation) (HIGH)
- Docs repository (raw markdown): https://github.com/Streamerbot/docs (HIGH)
- DonationAlerts API (OAuth, scopes, rate limit, Centrifugo, donations list): https://www.donationalerts.com/apidoc (HIGH; protocol framing deferred to protocol research)
- Local, read-only evidence: `Streamer.bot.Plugin.Interface.dll` 1.0.7 decompiled (`CPHInlineBase`, `IInlineInvokeProxy`), `Streamer.bot.exe.config`, `data/actions.json` field names, docs example `.sb` files, and the user's `logs/log_20261014.log` / `log_20261017.log` (excerpts summarized in section 2) (MEDIUM-HIGH as observation, LOW as proof of cause)
- Project context: `.planning/PROJECT.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONCERNS.md`

---
*Architecture research for: Streamer.bot 1.0.x DonationAlerts integration (brownfield rewrite)*
*Researched: 2026-10-17*
