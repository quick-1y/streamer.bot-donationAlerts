<!-- GSD:project-start source:PROJECT.md -->

## Project

**Streamer.bot DonationAlerts Integration**

A DonationAlerts integration for Streamer.bot 1.0.x that a streamer installs with a single `.sb` import, configures with a few global variables, and starts with one action. After that, real-time donations and goal progress arrive in Streamer.bot as clearly named arguments and triggers. The streamer can then react by amount, post to chat, drive OBS/TTS and handle multi-currency donations. This is a full rewrite of a raw, buggy fork. Backward compatibility with the old fork is not required.

**Core Value:** Once started, every DonationAlerts donation reliably reaches Streamer.bot exactly once with correct data. Closing Streamer.bot leaves nothing running: no lingering `Streamer.bot.exe`, sockets or workers.

### Constraints

- **Platform**: Streamer.bot 1.0.x on Windows, C# inline code (`CPHInline`, `CPH` API), compiled by Streamer.bot (.NET Framework 4.8). Only APIs that Streamer.bot actually supports
- **Distribution**: One `.sb` import. It may not depend on extra files or processes, and must use the real export format (no invented fields)
- **Source of truth**: Current official DonationAlerts API documentation for OAuth, REST and Centrifugo
- **Dependencies**: Only what Streamer.bot provides (e.g. Newtonsoft.Json, BCL). No extra NuGet packages at runtime
- **Security**: Never log credentials/tokens/PII. Never commit secrets. The README warns that `.sb` exports/backups contain secrets
- **Repo hygiene**: Preserve unrelated local changes (e.g. staged deletions of `.github/ISSUE_TEMPLATE/*`, untracked `.idea/`, `.claude/`)
- **Honesty**: Do not claim behavior was verified unless it was actually tested

<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->

## Technology Stack

## Languages

- C# (.NET Framework style code, `CPHInline` class) - all integration logic in `integration.cs` and `updateChecker.cs`
- HTML/CSS (inline, with Google Fonts) - OAuth success/error page in `successPage.html` (also embedded as string templates in `integration.cs`, around lines 1270-1390)
- YAML - GitHub Actions workflow `.github/workflows/release-announce.yml`
- Markdown - documentation in `README.md` (Russian-language)

## Runtime

- Streamer.bot C# execution runtime (the `CPH` API host object is injected by Streamer.bot; code is not a standalone executable)
- Uses `System.Net.HttpListener`, `System.Net.WebSockets.ClientWebSocket`, `System.Net.HttpWebRequest`, `System.Net.WebClient`
- None. No NuGet manifest (`.csproj`, `packages.config`) is present in the repository.
- Lockfile: Not applicable

## Frameworks

- Streamer.bot inline C# action host (`CPHInline`, `CPH.*` API) - entry point and host for all actions (`Connect`, `Start`, `Stop`, `CheckAndAnnounce`, `IsUpdateAvailable`)
- Not detected
- Not detected (scripts are pasted/imported into Streamer.bot; no build tooling in repo)

## Key Dependencies

- `Newtonsoft.Json` (Json.NET) - JSON (de)serialization of OAuth tokens, profile, Centrifugo messages, and GitHub release data; used via `JsonConvert` and `[JsonProperty]` in `integration.cs` and `updateChecker.cs`
- Streamer.bot `CPH` API - `CPH.GetGlobalVar<T>`, `CPH.SetGlobalVar`, `CPH.SetArgument`, `CPH.SendMessage`, `CPH.LogDebug`, `CPH.LogWarn`
- `System.Net.HttpListener` - local OAuth redirect callback server (`Service.ServeAndListenAuth` in `integration.cs`)
- `System.Net.WebSockets.ClientWebSocket` - Centrifugo WebSocket client (`SocketService` in `integration.cs`)
- `System.Security.Cryptography` - imported in `integration.cs`
- `System.Timers`, `System.Threading`, `System.Diagnostics` (`Process`/`ProcessStartInfo` to open the browser)

## Configuration

- Configured via Streamer.bot global variables, not environment variables or files. Read with `CPH.GetGlobalVar<string>` in `integration.cs` (settings loader around lines 215-240):
- Runtime state persisted as globals: `daCode`, `daAccessToken`, `daRefreshToken`, `daAccessTokenExpiresAt`, `daSocketToken`, `daUserId`
- No `.env` file present in the repository.
- No build configuration files present.
- `.gitignore` excludes `.vs` and `dist`.

## Platform Requirements

- Streamer.bot installed on Windows (the code opens the system browser via `ProcessStartInfo { UseShellExecute = true }` in `integration.cs`)
- A DonationAlerts OAuth client registered at https://www.donationalerts.com/application/clients
- Runs inside a Streamer.bot action on the streamer's machine; no server deployment
- Local port 8554 must be free for the OAuth callback listener (default redirect URL)

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

## Naming Patterns

- Source files use lowercase camelCase names: `integration.cs`, `updateChecker.cs`
- Other assets use lowercase names: `successPage.html`, `README.md`, `LICENSE`
- Each `.cs` file is a Streamer.bot C# inline script (one `CPHInline` class per file). There are no namespaces or folder-based modules.
- PascalCase for all classes: `CPHInline`, `DonationAlertsSettings`, `SocketService`, `Service`, `Client` (referenced in `integration.cs`)
- Nested helper types are PascalCase: `CPHInline.PrefixedLogger`, `Service.TokenResponse`, `Service.ProfileInfoData`, `SocketService.DonationData`
- Private wire/DTO classes used only for JSON are nested in their owner and named `<Action><Direction>`: `SocketClientRequest`, `SocketClientResponse`, `SubscribeRequestData`, `DonationResponseData`, `GitHubReleaseResponse` (`updateChecker.cs`)
- PascalCase for all methods, public and private: `Connect()`, `EnsureInitialized()`, `FetchLatestGitHubVersion(string repoSlug)`, `GetRepoSlug()`
- Boolean-returning action entry points (called by Streamer.bot actions) are public and return `bool`: `Init`, `Connect`, `Start`, `Stop`, `CreateAuthLink`, `ObtainAccessToken`, `RefreshAccessToken`, `GetProfileInfo`, `DonationCheckerLoop` (`integration.cs`), `IsUpdateAvailable`, `CheckAndAnnounce` (`updateChecker.cs`)
- Predicate-style helpers use `Is`/`Has` prefixes: `IsAccessTokenExpired()`, `IsUpdateAvailable()`, `IsValid()`, `IsDraft`, `IsPreRelease`
- Setup-style helpers use `Ensure` prefix: `EnsureInitialized()`, `EnsureSettings()`, `EnsureAccessToken()`
- Getters for configuration use `Get` prefix: `GetSetting`, `GetSettingInt`, `GetSettingBool`, `GetArgString`, `GetValue`
- Local variables and private fields: camelCase: `accessToken`, `profileInfo`, `repoSlug`, `targetPath`
- Parameters are camelCase in most places: `string repoSlug`, `string fileUrl`, `string currentVersion`
- Exception: some event-handler delegate parameters and `Dictionary` parameters are PascalCase: `Dictionary<string, string> Donation`, `Dictionary<string, string> GoalData`, `string Event`, `Dictionary<string, string> Data`. New code should use camelCase (`donation`, `goalData`) to match the rest of the file.
- Private instance properties use the `{ get; set; }` auto-property form even when private (`private Service Service { get; set; }`, `private PrefixedLogger Logger { get; set; }`). Follow this form when adding private state in `CPHInline` and `Service`.
- `private HttpListener Listener = null;` in `Service` is a field, not a property. Both forms coexist; prefer the property form for new members.
- `private const string` with PascalCase names: `DefaultHandlerActionName`, `DefaultGoalHandlerActionName`, `Prefix`, `CurrentVersion`, `DefaultRepoSlug` (`integration.cs`, `updateChecker.cs`)
- Endpoint constants are prefixed with `Endpoint`: `EndpointAuthorize`, `EndpointToken`, `EndpointProfileInfo`, `EndpointSubscribe` (`integration.cs`)
- Event name constants are public and prefixed with `Event`: `EventStarted`, `EventConnected`, `EventGoalUpdated`, `EventRecievedDonation` (`integration.cs`)
- Known typo to preserve for compatibility: `EventRecievedMessage` and `EventRecievedDonation` (misspelled "Received"). Do not rename these without updating all callers.
- Global variables and argument keys are camelCase with a `da` prefix: `daClientId`, `daClientSecret`, `daRedirectUrl`, `daAccessToken`, `daRefreshToken`, `daAccessTokenExpiresAt`, `daSocketToken`, `daUserId`, `daUpdateRepo`
- Action output arguments exported to Streamer.bot use the `da` prefix with a domain segment: `daDonationAmount`, `daDonationUsername`, `daGoalTitle`, `daGoalCurrent`, `daAudioUrl`
- Keep this prefix for any new global or argument. Document new keys in `README.md` under the settings table.
- Settings DTO properties are PascalCase: `ClientId`, `ReconnectDelaySeconds`, `UserAgent` (`DonationAlertsSettings` in `integration.cs`)

## Code Style

- Indentation: 4 spaces. No tabs.
- Brace style: Allman (opening brace on its own line) for all types, methods, control blocks, and lambdas:
- Single-statement `if` bodies omit braces and are indented on the next line. Multi-statement bodies use braces. Mixing both is common. Keep braces when a body spans more than one statement.
- Line endings: LF (no CR characters found in `integration.cs`).
- Encoding: `README.md` is UTF-8 with BOM; `integration.cs` is UTF-8 and the README and comments are in Russian. Keep comments and user-facing strings consistent with the existing language of the surrounding file (README and log/chat messages are Russian in places; code comments are minimal).
- Blank lines separate logical blocks inside methods. Some members are not separated by blank lines (`CPHInline` members in `integration.cs` lines 89-100 run together). Prefer one blank line between methods.
- No automatic formatter or `.editorconfig` is present in the repository. Formatting is by convention only.
- Not configured. No analyzers, StyleCop, or `.editorconfig` detected.
- Present in some lines (`EventAuthError    = "auth_error"; ` in `integration.cs` line 576). Avoid adding new trailing whitespace.

## Import Organization

- Not applicable. C# `using` directives are used without aliases. Fully qualified names are used when disambiguating: `System.Timers.Timer` in `Service.ServeAndListenAuth` (`integration.cs` line 1097).
- Only `Newtonsoft.Json` is referenced as an external package (`JsonConvert`, `JsonProperty`). Streamer.bot provides the `CPH` and `IInlineInvokeProxy` types at runtime. Do not add NuGet dependencies without a clear need, because the script runs inside Streamer.bot's host.

## Error Handling

- Public `bool` methods validate prerequisites first (`EnsureInitialized()`, then `EnsureSettings()`, then the operation), return `false` on failure, and report the reason via `Logger.Error`/`Logger.Debug` and/or `CPH.SendMessage` for user-facing messages:
- Exceptions are used only in the socket loop to signal fatal state: `throw new Exception("Unauthorized")` in `DonationCheckerLoop` (`integration.cs` line 411) and `throw new Exception("Socket is closed")` in `ObtainSocketClientId`.
- `WebException` is caught specifically where the status code matters, and converted to a log entry via `Logger.WebError(e)` (`PrefixedLogger.WebError` in `integration.cs`).
- Use `HttpWebResponse` status checks for auth vs. transient errors: `if (response != null && response.StatusCode == HttpStatusCode.Unauthorized)` (`SocketService.ConnectLoop`).
- Re-throwing uses `throw e;` in `Service.GetProfileInfo` and `Service.ObtainChannelSubscribeToken`. Prefer `throw;` for new code so the stack trace is preserved.
- Non-critical operations use empty catch blocks: `catch (Exception) { }` in `updateChecker.cs` (`FetchLatestGitHubVersion`, `GetGitHubReleaseVersionsAsync`), `SocketService.Close`, and inside the message loop of `ConnectAndProcess`. This is intentional for best-effort operations, but it hides failures. When adding code, log in the catch block with `Logger.Debug` (the `updateChecker.cs` class has no logger, so use `CPH.LogDebug` as it already does for the repo-slug check).
- Use `string.IsNullOrWhiteSpace(...)` for strings. Do not use `== null || == ""`.
- Dictionary access is guarded: `data != null && data.ContainsKey(key) && data[key] != null` (helper `GetValue` in `integration.cs`). Use `GetValue(dict, key, fallback)` rather than indexing directly.
- Argument access is guarded by `GetArgString`, which handles the Streamer.bot `args` dictionary.
- Use `TryParse` with `CultureInfo.InvariantCulture` and `NumberStyles`/`DateTimeStyles` explicitly: `int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out int parsed)`, `DateTime.TryParse(... DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal ...)`.
- Timestamps are stored as ISO 8601 with `"o"` format and compared in UTC: `expiresAt.ToString("o")`, `DateTime.UtcNow`.

## Logging

- Use `Logger.Debug(message, extra...)` for normal flow and `Logger.Error(message, extra...)` for failures. `Logger` is only available in `CPHInline`/`Service`/`SocketService`. `updateChecker.cs` calls `CPH.LogDebug` directly with the prefix `"UpdateChecker: "`.
- The `PrefixedLogger` adds the prefix `-- Donation Alerts:` to every message. Do not add the prefix manually.
- Extra values are passed as additional parameters and are joined with `", "`. Example: `Logger.Debug("Auth link", authLink);`.
- Do not log secrets. Current code logs the auth link URL (which contains only the client_id) and the raw profile JSON (`Logger.Debug("Retrieved user profile info", profile.Data.Id, json)`). Do not add logging of `daClientSecret`, `daAccessToken`, or `daRefreshToken`.
- User-facing messages go through `CPH.SendMessage(...)` with plain sentences. Example: `"DonationAlerts watcher is running"`.

## Comments

- File header block uses a dashed banner with module metadata:
- Inline comments are rare. Code is expected to be self-describing through method and constant names.
- Known TODO-style placeholder: `Repository: (set after publishing)` and `DefaultRepoSlug = ""` must be filled before release.
- Not used. No `///<summary>` blocks found.

## Function Design

- Most methods are short (under 30 lines). Two exceptions are large: `ConnectAndProcess` (about 80 lines, message switch) and `BuildSuccessPage` in `Service` (HTML string). When adding logic, extract a helper instead of growing these methods.
- Pass dependencies through constructors. `Service(Client client, CPHInline.PrefixedLogger logger, DonationAlertsSettings settings)` and `SocketService(Service, Logger, Settings)` show the pattern. Do not use static singletons for new services.
- Use `Dictionary<string, string>` as the event payload type between components. Keep this shape for new events so Streamer.bot argument export stays uniform.
- Action methods return `bool`. Data-fetch methods return a DTO or `null` on failure (`ObtainToken`, `GetProfileInfo`, `FetchLatestGitHubVersion`).
- Collections returned from failed fetches are empty lists, not `null` (`GetGitHubReleaseVersionsAsync` returns `new List<GitHubReleaseResponse>()`).

## Module Design

- Each file exposes one public `CPHInline` class (the Streamer.bot entry point). Other public types are nested inside it or in the same file. Only `CPHInline` methods are callable from Streamer.bot actions via `CPH.ExecuteMethod`.
- `updateChecker.cs` is a separate Streamer.bot script with its own `CPHInline` class. It is invoked from `integration.cs` by name: `CPH.ExecuteMethod("DonationAlerts | Update Checker", "CheckAndAnnounce")`.
- Not applicable. There is one file per script, and no shared module is imported between scripts.
- Actions are named `DA | <Verb>` in the README (`DA | Connect`, `DA | Start`, `DA | Stop`). Default handler actions use `DonationHandler_<Name>` (`DonationHandler_Default`, `DonationHandler_GoalHandler`, `DonationHandler_After`) and amount-specific `DonationHandler_<amount>`. Follow these names when documenting new actions.

## Pull Request and Commit Conventions

- PR checklist is in `.github/pull_request_template.md`. Items: updated integration code, exported `install.sb` and `update.sb` actions, and bumped the version in `updateChecker.cs`.
- Keep the version in `updateChecker.cs` (`CurrentVersion = "2.0.0"`) in sync with the User-Agent default `StreamerBot-DonationAlerts/2.0` in `integration.cs` (`LoadSettings`).
- Release tags are semver-like (`v2.0.0`), parsed by `ParseVersion` in `updateChecker.cs` after stripping a leading `v`. Tags must be parseable by `System.Version`.

<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

## System Overview

```text

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

- Each public method of `CPHInline` is a separate Streamer.bot action entry point; they are invoked by name from Streamer.bot (e.g., `Connect`, `Start`, `Stop`), not by other code in this repo.
- State is externalized: configuration, tokens, and the auth code live in Streamer.bot global variables (`CPH.GetGlobalVar` / `CPH.SetGlobalVar`), so the process holds almost no durable state.
- Lazy initialization: `EnsureInitialized()` (`integration.cs` line ~200) constructs `PrefixedLogger`, `DonationAlertsSettings`, `Service`, and `SocketService` on first use, and is called at the top of every public method.
- Event-driven inbound path: `SocketService` pushes parsed events into `EventObserver`; `DonationCheckerLoop` registers handlers that translate events into Streamer.bot arguments and run actions.
- Blocking I/O model: the socket loop uses `GetAwaiter().GetResult()` on async WebSocket calls and `Thread.Sleep` for reconnect backoff; the OAuth callback uses `HttpListener` with a `System.Timers.Timer` as a timeout guard.
- No dependency injection container; dependencies are passed through constructors (`Service(Client, PrefixedLogger, DonationAlertsSettings)`, `SocketService(Service, PrefixedLogger, DonationAlertsSettings)`).

## Layers

- Purpose: Expose Streamer.bot-callable methods and sequence the OAuth, token, and socket steps.
- Location: `integration.cs` (`public class CPHInline`, lines ~34-564)
- Contains: Public action methods, event handler delegates, argument export helpers (`ExportDonation`, `ExportGoal`), token persistence (`StoreTokenData`), auto-refresh (`EnsureAccessToken`, `IsAccessTokenExpired`).
- Depends on: `Service`, `SocketService`, `PrefixedLogger`, `DonationAlertsSettings`, Streamer.bot `CPH` proxy, `args` dictionary.
- Used by: Streamer.bot Actions only.
- Purpose: Implement DonationAlerts OAuth 2.0 authorization-code flow and REST calls.
- Location: `integration.cs` (`public class Service`, lines ~1044-1414)
- Contains: `GetAuthLink`, `ServeAndListenAuth` (local `HttpListener` on `RedirectUrl`), `ObtainToken`, `RefreshToken`, `GetProfileInfo`, `ObtainChannelSubscribeToken`, HTML response builders, DTOs (`TokenResponse`, `ProfileInfoData`, `ChannelSubscribeResponse`, `ChannelSubscribeRequest`).
- Depends on: `Client`, `PrefixedLogger`, `DonationAlertsSettings`, `System.Net.HttpListener`.
- Used by: `CPHInline` (auth/token/profile), `SocketService` (profile refresh and channel token).
- Purpose: Single place where HTTP requests are built (User-Agent, Accept JSON, form encoding, UTF-8 response reading).
- Location: `integration.cs` (`public class Client`, lines ~1459-1566)
- Contains: `GET`/`POST`/`POSTForm` overloads that all delegate to `Perform(...)`.
- Depends on: `System.Net.HttpWebRequest`.
- Used by: `Service`.
- Purpose: Maintain a WebSocket session to `wss://centrifugo.donationalerts.com/connection/websocket`, subscribe to channels, and parse inbound frames.
- Location: `integration.cs` (`public class SocketService`, lines ~566-1042)
- Contains: `ConnectLoop` (reconnect policy), `ConnectAndProcess` (single session), `ObtainSocketClientId`, `SubscribeToTheChannel`, message DTOs (`SocketMessage`, `DonationResponse`, `GoalProgressResponse`, `DonationData`, `GoalData`), event name constants (`EventStarted`, `EventRecievedDonation`, `EventGoalUpdated`, etc.).
- Depends on: `Service`, `PrefixedLogger`, `DonationAlertsSettings`, `EventObserver`, `Helper`.
- Used by: `CPHInline.DonationCheckerLoop` (subscribes handlers and calls `Start`), `CPHInline.Stop` (calls `Close`), `CPHInline.Dispose`.
- Purpose: Decouple socket parsing from Streamer.bot action dispatch.
- Location: `integration.cs` (`public class EventObserver`, lines ~1568-1595)
- Contains: `Handler` delegate `(string Event, Dictionary<string,string> Data = null)`, `Subscribe` (returns `this` for chaining), `Dispatch`.
- Depends on: nothing.
- Used by: `SocketService` (producer), `CPHInline.DonationCheckerLoop` (consumer).
- Purpose: Notify the streamer about newer GitHub releases.
- Location: `updateChecker.cs`
- Contains: `CheckAndAnnounce()` and `IsUpdateAvailable()` public entry points; private GitHub release fetch and `Version` comparison.
- Depends on: `System.Net.WebClient`, `Newtonsoft.Json`, Streamer.bot `CPH`.
- Used by: Its own Streamer.bot action (`DA | Update Checker`). The main script reaches it indirectly: `CPHInline.TryRunUpdateChecker()` (`integration.cs` line ~385) calls `CPH.ExecuteMethod(actionName, "CheckAndAnnounce")` for action names `DonationAlerts | Update Checker` or `DonationAlert Update Checker`.

## Data Flow

### Primary Request Path (authorization, one-time)

### Primary Streaming Path (runtime, long-lived)

### Secondary Flow: Update Check

- Persistent: Streamer.bot global variables only (`daClientId`, `daClientSecret`, `daRedirectUrl`, `daScopes`, `daAccessToken`, `daRefreshToken`, `daAccessTokenExpiresAt`, `daSocketToken`, `daUserId`, `daCode`, `daUpdateRepo`, and the timing/flag settings).
- In-memory: `SocketService.Socket`, `SocketService.StopRequested`, `SocketService.PreviousGoalEventHash`, `CPHInline.Service`/`SocketService`/`Settings`/`Logger` (per-instance, lazily created).
- Per-action arguments: `CPH.SetArgument` values (`daDonation*`, `daGoal*`, legacy `da*`) are the output channel to downstream Streamer.bot actions.

## Key Abstractions

- Purpose: The Streamer.bot entry class; every action method is a public member.
- Examples: `integration.cs` line ~34, `updateChecker.cs` line ~10.
- Pattern: Partial facade with lazy dependency construction; one class per script file.
- Purpose: Named-event fan-out inside the process.
- Examples: `integration.cs` line ~1568; event name constants at `integration.cs` lines ~570-580.
- Pattern: Observer; handlers receive `(string Event, Dictionary<string,string> Data)`.
- Purpose: Snapshot of configuration for one `EnsureInitialized()` lifetime.
- Examples: `integration.cs` line ~21, populated by `LoadSettings()` (line ~214).
- Pattern: POCO populated from globals with typed defaults (`GetSetting`, `GetSettingInt`, `GetSettingBool`).
- Purpose: Wire DTOs that convert to `Dictionary<string,string>` via `ToDictionary()`, which becomes the event payload.
- Examples: `integration.cs` lines ~947-990 and ~1011-1042.
- Pattern: Deserialize with Newtonsoft into typed classes, then flatten to string map for the event bus and argument export.

## Entry Points

- Location: `integration.cs` public methods (`Init`, `Dispose`, `Connect`, `Start`, `Stop`, `CreateAuthLink`, `ObtainAccessToken`, `RefreshAccessToken`, `GetProfileInfo`, `DonationCheckerLoop`).
- Triggers: Streamer.bot action buttons/hotkeys (README "DA | Connect", "DA | Start", "DA | Stop") and the Streamer.bot init hook calling `Init()`.
- Responsibilities: Each method is a self-contained step (auth, token, start, stop).
- Location: `updateChecker.cs` (`CheckAndAnnounce`, `IsUpdateAvailable`).
- Triggers: Its Streamer.bot action (`DA | Update Checker`) or `CPHInline.Init()` through `TryRunUpdateChecker()`.
- Responsibilities: GitHub release check and chat announcement.
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

### Recursion guard via action argument

### Blocking waits inside a long-running action

## Error Handling

- HTTP errors: `WebException` is caught in `ConnectLoop`; a 401 dispatches `EventAuthError` and stops reconnecting (line ~636).
- OAuth listener errors: `WebException` and `HttpListenerException` return `false` from `ServeAndListenAuth` (lines ~1105-1114).
- Token refresh: a missing or expired token triggers `RefreshAccessToken`; failures return `false` and the action stops.
- Argument export: `GetValue(dict, key, fallback)` guards null and missing keys (line ~550).

## Cross-Cutting Concerns

<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-fast` for a trivial task inline, with no subagents and no PLAN.md
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
