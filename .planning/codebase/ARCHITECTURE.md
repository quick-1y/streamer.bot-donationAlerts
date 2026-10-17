---
last_mapped_commit: 2047008445144024a44f608400bc03a71f717c2f
last_mapped_at: 2026-10-17
---
<!-- refreshed: 2026-10-17 -->

# Architecture

**Analysis Date:** 2026-10-17

## System Overview

```text
┌────────────────────────────────────────────────────────────────────┐
│                 Streamer.bot runtime (host process)                 │
│   Invokes Streamer.bot Actions; exposes `CPH` proxy and `args`      │
└───────┬───────────────────────────────┬────────────────────────────┘
        │ CPH method calls               │ CPH.ExecuteMethod / RunAction
        ▼                                ▼
┌──────────────────────────────┐  ┌──────────────────────────────────┐
│ CPHInline (facade/orchestr.) │  │ CPHInline (updateChecker)         │
│ `integration.cs`             │  │ `updateChecker.cs`                │
└───────┬──────────────┬───────┘  └──────────────┬───────────────────┘
        │              │                          │ WebClient -> GitHub API
        ▼              ▼                          ▼
┌──────────────┐ ┌──────────────────────────┐  (CheckAndAnnounce -> CPH.SendMessage)
│ Service      │ │ SocketService             │
│ OAuth + REST │ │ Centrifugo WebSocket      │
│ + HttpListener│ │ connect/subscribe/recv    │
└──────┬───────┘ └──────────┬───────────────┘
       │ Client (HttpWebRequest)│ EventObserver.Dispatch
       ▼                        ▼
┌──────────────────────────────────────────────┐
│ DonationAlerts (www.donationalerts.com,       │
│ centrifugo.donationalerts.com)                │
└──────────────────────────────────────────────┘
                        │ events (donation / goal)
                        ▼
┌──────────────────────────────────────────────┐
│ CPHInline event handlers (in DonationChecker  │
│ Loop) -> ExportDonation/ExportGoal ->         │
│ CPH.SetArgument -> CPH.RunAction(...)          │
└──────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `CPHInline` (main) | Public Streamer.bot action entry points (`Init`, `Connect`, `Start`, `Stop`, `CreateAuthLink`, `ObtainAccessToken`, `RefreshAccessToken`, `GetProfileInfo`, `DonationCheckerLoop`); lazy wiring of dependencies; token storage in global vars; export of event payloads to action arguments | `integration.cs` (lines ~34-564) |
| `CPHInline.PrefixedLogger` | Nested logger that prefixes messages with `-- Donation Alerts:` and routes to `CPH.LogDebug` / `CPH.LogWarn` | `integration.cs` (lines ~36-80) |
| `DonationAlertsSettings` | Plain settings DTO loaded from Streamer.bot global variables (`da*` keys) | `integration.cs` (lines ~21-32) |
| `Service` | OAuth authorize link, local `HttpListener` callback server, token obtain/refresh, profile fetch, Centrifugo channel subscribe-token fetch | `integration.cs` (lines ~1044-1414) |
| `Client` | Thin wrapper over `HttpWebRequest` for GET/POST/form-POST against `https://www.donationalerts.com` | `integration.cs` (lines ~1459-1566) |
| `SocketService` | Centrifugo WebSocket lifecycle: connect loop with reconnect, client-id handshake, channel subscription, message parsing, dispatch of donation/goal events | `integration.cs` (lines ~566-1042) |
| `EventObserver` | Minimal in-process pub/sub: `Subscribe(name, handler)` and `Dispatch(name, data)` | `integration.cs` (lines ~1568-1595) |
| `Helper` | Static MD5 hash helper used to de-duplicate repeated goal events | `integration.cs` (lines ~1597-end) |
| `BuildSuccessPage` / `BuildErrorPage` | Inline HTML responses returned to the browser after OAuth callback | `integration.cs` (lines ~1264-1414) |
| Update checker `CPHInline` | Separate Streamer.bot action: reads `daUpdateRepo`, queries GitHub releases API, compares versions, announces via chat | `updateChecker.cs` |
| Static success page | Standalone copy of the post-auth HTML page (same markup as the one embedded in `BuildSuccessPage`) | `successPage.html` |

## Pattern Overview

**Overall:** Single-file, action-oriented script (Streamer.bot C# inline code) with a facade class (`CPHInline`) that composes service, transport, and event layers. There is no build system, no project file, and no package manager; each `.cs` file is pasted or imported into a Streamer.bot C# action.

**Key Characteristics:**
- Each public method of `CPHInline` is a separate Streamer.bot action entry point; they are invoked by name from Streamer.bot (e.g., `Connect`, `Start`, `Stop`), not by other code in this repo.
- State is externalized: configuration, tokens, and the auth code live in Streamer.bot global variables (`CPH.GetGlobalVar` / `CPH.SetGlobalVar`), so the process holds almost no durable state.
- Lazy initialization: `EnsureInitialized()` (`integration.cs` line ~200) constructs `PrefixedLogger`, `DonationAlertsSettings`, `Service`, and `SocketService` on first use, and is called at the top of every public method.
- Event-driven inbound path: `SocketService` pushes parsed events into `EventObserver`; `DonationCheckerLoop` registers handlers that translate events into Streamer.bot arguments and run actions.
- Blocking I/O model: the socket loop uses `GetAwaiter().GetResult()` on async WebSocket calls and `Thread.Sleep` for reconnect backoff; the OAuth callback uses `HttpListener` with a `System.Timers.Timer` as a timeout guard.
- No dependency injection container; dependencies are passed through constructors (`Service(Client, PrefixedLogger, DonationAlertsSettings)`, `SocketService(Service, PrefixedLogger, DonationAlertsSettings)`).

## Layers

**Action facade (orchestration):**
- Purpose: Expose Streamer.bot-callable methods and sequence the OAuth, token, and socket steps.
- Location: `integration.cs` (`public class CPHInline`, lines ~34-564)
- Contains: Public action methods, event handler delegates, argument export helpers (`ExportDonation`, `ExportGoal`), token persistence (`StoreTokenData`), auto-refresh (`EnsureAccessToken`, `IsAccessTokenExpired`).
- Depends on: `Service`, `SocketService`, `PrefixedLogger`, `DonationAlertsSettings`, Streamer.bot `CPH` proxy, `args` dictionary.
- Used by: Streamer.bot Actions only.

**Service (OAuth + REST):**
- Purpose: Implement DonationAlerts OAuth 2.0 authorization-code flow and REST calls.
- Location: `integration.cs` (`public class Service`, lines ~1044-1414)
- Contains: `GetAuthLink`, `ServeAndListenAuth` (local `HttpListener` on `RedirectUrl`), `ObtainToken`, `RefreshToken`, `GetProfileInfo`, `ObtainChannelSubscribeToken`, HTML response builders, DTOs (`TokenResponse`, `ProfileInfoData`, `ChannelSubscribeResponse`, `ChannelSubscribeRequest`).
- Depends on: `Client`, `PrefixedLogger`, `DonationAlertsSettings`, `System.Net.HttpListener`.
- Used by: `CPHInline` (auth/token/profile), `SocketService` (profile refresh and channel token).

**HTTP transport:**
- Purpose: Single place where HTTP requests are built (User-Agent, Accept JSON, form encoding, UTF-8 response reading).
- Location: `integration.cs` (`public class Client`, lines ~1459-1566)
- Contains: `GET`/`POST`/`POSTForm` overloads that all delegate to `Perform(...)`.
- Depends on: `System.Net.HttpWebRequest`.
- Used by: `Service`.

**Realtime transport (Centrifugo):**
- Purpose: Maintain a WebSocket session to `wss://centrifugo.donationalerts.com/connection/websocket`, subscribe to channels, and parse inbound frames.
- Location: `integration.cs` (`public class SocketService`, lines ~566-1042)
- Contains: `ConnectLoop` (reconnect policy), `ConnectAndProcess` (single session), `ObtainSocketClientId`, `SubscribeToTheChannel`, message DTOs (`SocketMessage`, `DonationResponse`, `GoalProgressResponse`, `DonationData`, `GoalData`), event name constants (`EventStarted`, `EventRecievedDonation`, `EventGoalUpdated`, etc.).
- Depends on: `Service`, `PrefixedLogger`, `DonationAlertsSettings`, `EventObserver`, `Helper`.
- Used by: `CPHInline.DonationCheckerLoop` (subscribes handlers and calls `Start`), `CPHInline.Stop` (calls `Close`), `CPHInline.Dispose`.

**Eventing:**
- Purpose: Decouple socket parsing from Streamer.bot action dispatch.
- Location: `integration.cs` (`public class EventObserver`, lines ~1568-1595)
- Contains: `Handler` delegate `(string Event, Dictionary<string,string> Data = null)`, `Subscribe` (returns `this` for chaining), `Dispatch`.
- Depends on: nothing.
- Used by: `SocketService` (producer), `CPHInline.DonationCheckerLoop` (consumer).

**Update checker (independent action):**
- Purpose: Notify the streamer about newer GitHub releases.
- Location: `updateChecker.cs`
- Contains: `CheckAndAnnounce()` and `IsUpdateAvailable()` public entry points; private GitHub release fetch and `Version` comparison.
- Depends on: `System.Net.WebClient`, `Newtonsoft.Json`, Streamer.bot `CPH`.
- Used by: Its own Streamer.bot action (`DA | Update Checker`). The main script reaches it indirectly: `CPHInline.TryRunUpdateChecker()` (`integration.cs` line ~385) calls `CPH.ExecuteMethod(actionName, "CheckAndAnnounce")` for action names `DonationAlerts | Update Checker` or `DonationAlert Update Checker`.

## Data Flow

### Primary Request Path (authorization, one-time)

1. Streamer.bot runs action `DA | Connect` -> `CPHInline.Connect()` (`integration.cs` line ~101).
2. `EnsureSettings()` validates `daClientId`, `daClientSecret`, and related globals (`integration.cs` line ~266).
3. `CreateAuthLink()` builds the URL via `Service.GetAuthLink()`, opens the browser (`OpenUrl`, line ~369), and calls `Service.ServeAndListenAuth(...)` (line ~1064).
4. `ServeAndListenAuth` starts `HttpListener` on `daRedirectUrl` (default `http://127.0.0.1:8554/donationalerts/callback/`) and waits for `?code=`.
5. The callback delegate stores the code in global var `daCode` (line ~143) and the browser receives `BuildSuccessPage()` (line ~1264).
6. `ObtainAccessToken()` reads `daCode`, calls `Service.ObtainToken(code)` (line ~1149), and `StoreTokenData` persists `daAccessToken`, `daRefreshToken`, `daAccessTokenExpiresAt`.

### Primary Streaming Path (runtime, long-lived)

1. Streamer.bot runs `DA | Start` (in background) -> `CPHInline.Start()` (line ~112).
2. `EnsureAccessToken()` (line ~311) refreshes via `RefreshAccessToken()` (line ~170) if expired.
3. `DonationCheckerLoop()` (line ~401) fetches profile info, creates a fresh `SocketService`, registers handlers on `EventObserver`, and calls `SocketService.Start(accessToken, profileInfo)`.
4. `ConnectLoop` (line ~624) opens a `ClientWebSocket` to Centrifugo; `ConnectAndProcess` (line ~663) obtains a client id (`ObtainSocketClientId`), gets channel tokens (`Service.ObtainChannelSubscribeToken`), and subscribes (`SubscribeToTheChannel`).
5. Each frame goes to `ReceiveMessage()` (line ~746), is classified by `SocketMessage.RecognizeType()` as `donation` or `goal`, deserialized, and dispatched as `EventRecievedDonation` or `EventGoalUpdated`.
6. Donation handler (`integration.cs` line ~452): `ExportDonation` sets `da*` arguments (and legacy `da*` names), then runs `DonationHandler_<amount>` if it exists, else `DonationHandler_Default`, then always `DonationHandler_After` if it exists.
7. Goal handler (line ~446): `ExportGoal` sets `daGoal*` arguments and runs `DonationHandler_GoalHandler`. Duplicate goal payloads are suppressed by MD5 comparison in `SocketService` (line ~724-731).
8. On socket close or error, `ConnectLoop` sleeps `ReconnectDelaySeconds` and reconnects; on HTTP 401 it dispatches `EventAuthError` and exits; `Stop` sets `StopRequested` and closes the socket.

### Secondary Flow: Update Check

1. `CPHInline.Init()` (line ~91) calls `EnsureInitialized()` and then `TryRunUpdateChecker()`.
2. If an update-checker action exists, Streamer.bot executes its `CheckAndAnnounce` method.
3. `updateChecker.cs` reads `daUpdateRepo`, fetches `https://api.github.com/repos/{slug}/releases?per_page=100`, skips drafts and prereleases, compares versions, and sends a chat message through `CPH.SendMessage`.

**State Management:**
- Persistent: Streamer.bot global variables only (`daClientId`, `daClientSecret`, `daRedirectUrl`, `daScopes`, `daAccessToken`, `daRefreshToken`, `daAccessTokenExpiresAt`, `daSocketToken`, `daUserId`, `daCode`, `daUpdateRepo`, and the timing/flag settings).
- In-memory: `SocketService.Socket`, `SocketService.StopRequested`, `SocketService.PreviousGoalEventHash`, `CPHInline.Service`/`SocketService`/`Settings`/`Logger` (per-instance, lazily created).
- Per-action arguments: `CPH.SetArgument` values (`daDonation*`, `daGoal*`, legacy `da*`) are the output channel to downstream Streamer.bot actions.

## Key Abstractions

**`CPHInline` (action facade):**
- Purpose: The Streamer.bot entry class; every action method is a public member.
- Examples: `integration.cs` line ~34, `updateChecker.cs` line ~10.
- Pattern: Partial facade with lazy dependency construction; one class per script file.

**`EventObserver`:**
- Purpose: Named-event fan-out inside the process.
- Examples: `integration.cs` line ~1568; event name constants at `integration.cs` lines ~570-580.
- Pattern: Observer; handlers receive `(string Event, Dictionary<string,string> Data)`.

**`DonationAlertsSettings`:**
- Purpose: Snapshot of configuration for one `EnsureInitialized()` lifetime.
- Examples: `integration.cs` line ~21, populated by `LoadSettings()` (line ~214).
- Pattern: POCO populated from globals with typed defaults (`GetSetting`, `GetSettingInt`, `GetSettingBool`).

**`SocketService.DonationData` / `GoalData`:**
- Purpose: Wire DTOs that convert to `Dictionary<string,string>` via `ToDictionary()`, which becomes the event payload.
- Examples: `integration.cs` lines ~947-990 and ~1011-1042.
- Pattern: Deserialize with Newtonsoft into typed classes, then flatten to string map for the event bus and argument export.

## Entry Points

**Streamer.bot actions on `CPHInline`:**
- Location: `integration.cs` public methods (`Init`, `Dispose`, `Connect`, `Start`, `Stop`, `CreateAuthLink`, `ObtainAccessToken`, `RefreshAccessToken`, `GetProfileInfo`, `DonationCheckerLoop`).
- Triggers: Streamer.bot action buttons/hotkeys (README "DA | Connect", "DA | Start", "DA | Stop") and the Streamer.bot init hook calling `Init()`.
- Responsibilities: Each method is a self-contained step (auth, token, start, stop).

**Update checker action:**
- Location: `updateChecker.cs` (`CheckAndAnnounce`, `IsUpdateAvailable`).
- Triggers: Its Streamer.bot action (`DA | Update Checker`) or `CPHInline.Init()` through `TryRunUpdateChecker()`.
- Responsibilities: GitHub release check and chat announcement.

**Release announcement workflow:**
- Location: `.github/workflows/release-announce.yml`
- Triggers: GitHub `release` event with type `created`.
- Responsibilities: Posts release notes to Discord via a webhook secret. Not part of the runtime integration.

## Architectural Constraints

- **Threading:** The socket loop runs on the thread that invokes `Start`/`DonationCheckerLoop`; `ConnectLoop` blocks it with `Thread.Sleep` and synchronous waits on async WebSocket calls. The OAuth listener blocks the calling action until a code arrives or the timer closes the listener. Streamer.bot must run `DA | Start` in the background (documented in `README.md`).
- **Global state:** `CPHInline` has instance fields only; there are no static mutable singletons in the integration. `Helper` is static but stateless. `SocketService.PreviousGoalEventHash` is per-instance and is the only dedupe memory.
- **Circular imports:** Not applicable (single C# compilation unit per action). `SocketService` depends on `Service`, and `Service` does not depend on `SocketService`; this direction must be kept.
- **Single-file deployment:** All integration logic must stay in `integration.cs`; splitting it into multiple files would break the copy-paste/import model used by Streamer.bot actions.
- **Streamer.bot API surface:** `CPH` and `args` are injected by the Streamer.bot host at runtime. They are not defined in this repo, so the code cannot be compiled or run standalone.
- **Duplicate HTML:** The success page exists in both `successPage.html` and the verbatim string in `BuildSuccessPage()` (`integration.cs` line ~1264). Changes must be applied to both.

## Anti-Patterns

### Silent exception swallowing in hot paths

**What happens:** `SocketService.ConnectAndProcess` wraps message handling in `catch (Exception) { }` (`integration.cs` around line ~742); `CPHInline.FetchLatestGitHubVersion` and `GetGitHubReleaseVersionsAsync` in `updateChecker.cs` (lines ~75, ~91) also swallow all exceptions.
**Why it's wrong:** Parsing or handler failures disappear without a log line, which makes live-stream issues hard to diagnose.
**Do this instead:** Log through `Logger.Debug(...)` (or `Logger.Error`) in the catch, as `ConnectLoop` already does for socket errors (`integration.cs` line ~641).

### Recursion guard via action argument

**What happens:** `RefreshAccessToken` checks `args["refresh_token_recursion_protection"]` (`integration.cs` line ~176) and sets it with `CPH.SetArgument` (line ~192) to prevent re-entry.
**Why it's wrong:** The guard relies on the Streamer.bot argument store persisting across invocations, which is host-specific and not obvious from the code. A flag in an instance field would be explicit.
**Do this instead:** Keep the guard local to the call (e.g., a private bool parameter overload of `RefreshAccessToken`) rather than depending on host argument state.

### Blocking waits inside a long-running action

**What happens:** `SocketService` uses `.GetAwaiter().GetResult()` and `Thread.Sleep` in the reconnect loop (`integration.cs` lines ~671, ~690, ~754, ~658).
**Why it's wrong:** The whole action thread is held for the lifetime of the stream, and `Stop` must race against a blocked `ReceiveMessage`.
**Do this instead:** Keep this model (it matches Streamer.bot's action execution), but route cancellation through a `CancellationTokenSource` passed to `ReceiveAsync`, so `Close()` can interrupt receives deterministically.

## Error Handling

**Strategy:** Return `bool` from public action methods (`true` on success), log via `PrefixedLogger`, and surface user-facing failures with `CPH.SendMessage`. Exceptions thrown from `DonationCheckerLoop` when unauthorized (`integration.cs` line ~411) are the one deliberate exception path.

**Patterns:**
- HTTP errors: `WebException` is caught in `ConnectLoop`; a 401 dispatches `EventAuthError` and stops reconnecting (line ~636).
- OAuth listener errors: `WebException` and `HttpListenerException` return `false` from `ServeAndListenAuth` (lines ~1105-1114).
- Token refresh: a missing or expired token triggers `RefreshAccessToken`; failures return `false` and the action stops.
- Argument export: `GetValue(dict, key, fallback)` guards null and missing keys (line ~550).

## Cross-Cutting Concerns

**Logging:** `PrefixedLogger` (`integration.cs` line ~36) routes to `CPH.LogDebug` and `CPH.LogWarn`, always prefixed with `-- Donation Alerts:`. The update checker uses `CPH.LogDebug` directly.
**Validation:** `EnsureSettings()` (`integration.cs` line ~266) checks required globals; `EnsureAccessToken()` checks for a stored token; event payloads are validated by `IsValid()` on `DonationResponse` and `GoalProgressResponse`.
**Authentication:** OAuth 2.0 authorization code flow against `https://www.donationalerts.com/oauth/authorize` and `/oauth/token` (`integration.cs` lines ~1048-1049). Bearer tokens for profile and subscribe calls. The socket uses a Centrifugo connection token from the profile response.

---

*Architecture analysis: 2026-10-17*
