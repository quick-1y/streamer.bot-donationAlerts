---
last_mapped_commit: 2047008445144024a44f608400bc03a71f717c2f
last_mapped_at: 2026-10-17
---
# Coding Conventions

**Analysis Date:** 2026-10-17

## Naming Patterns

**Files:**
- Source files use lowercase camelCase names: `integration.cs`, `updateChecker.cs`
- Other assets use lowercase names: `successPage.html`, `README.md`, `LICENSE`
- Each `.cs` file is a Streamer.bot C# inline script (one `CPHInline` class per file). There are no namespaces or folder-based modules.

**Classes and Types:**
- PascalCase for all classes: `CPHInline`, `DonationAlertsSettings`, `SocketService`, `Service`, `Client` (referenced in `integration.cs`)
- Nested helper types are PascalCase: `CPHInline.PrefixedLogger`, `Service.TokenResponse`, `Service.ProfileInfoData`, `SocketService.DonationData`
- Private wire/DTO classes used only for JSON are nested in their owner and named `<Action><Direction>`: `SocketClientRequest`, `SocketClientResponse`, `SubscribeRequestData`, `DonationResponseData`, `GitHubReleaseResponse` (`updateChecker.cs`)

**Methods:**
- PascalCase for all methods, public and private: `Connect()`, `EnsureInitialized()`, `FetchLatestGitHubVersion(string repoSlug)`, `GetRepoSlug()`
- Boolean-returning action entry points (called by Streamer.bot actions) are public and return `bool`: `Init`, `Connect`, `Start`, `Stop`, `CreateAuthLink`, `ObtainAccessToken`, `RefreshAccessToken`, `GetProfileInfo`, `DonationCheckerLoop` (`integration.cs`), `IsUpdateAvailable`, `CheckAndAnnounce` (`updateChecker.cs`)
- Predicate-style helpers use `Is`/`Has` prefixes: `IsAccessTokenExpired()`, `IsUpdateAvailable()`, `IsValid()`, `IsDraft`, `IsPreRelease`
- Setup-style helpers use `Ensure` prefix: `EnsureInitialized()`, `EnsureSettings()`, `EnsureAccessToken()`
- Getters for configuration use `Get` prefix: `GetSetting`, `GetSettingInt`, `GetSettingBool`, `GetArgString`, `GetValue`

**Variables and Parameters:**
- Local variables and private fields: camelCase: `accessToken`, `profileInfo`, `repoSlug`, `targetPath`
- Parameters are camelCase in most places: `string repoSlug`, `string fileUrl`, `string currentVersion`
- Exception: some event-handler delegate parameters and `Dictionary` parameters are PascalCase: `Dictionary<string, string> Donation`, `Dictionary<string, string> GoalData`, `string Event`, `Dictionary<string, string> Data`. New code should use camelCase (`donation`, `goalData`) to match the rest of the file.
- Private instance properties use the `{ get; set; }` auto-property form even when private (`private Service Service { get; set; }`, `private PrefixedLogger Logger { get; set; }`). Follow this form when adding private state in `CPHInline` and `Service`.
- `private HttpListener Listener = null;` in `Service` is a field, not a property. Both forms coexist; prefer the property form for new members.

**Constants:**
- `private const string` with PascalCase names: `DefaultHandlerActionName`, `DefaultGoalHandlerActionName`, `Prefix`, `CurrentVersion`, `DefaultRepoSlug` (`integration.cs`, `updateChecker.cs`)
- Endpoint constants are prefixed with `Endpoint`: `EndpointAuthorize`, `EndpointToken`, `EndpointProfileInfo`, `EndpointSubscribe` (`integration.cs`)
- Event name constants are public and prefixed with `Event`: `EventStarted`, `EventConnected`, `EventGoalUpdated`, `EventRecievedDonation` (`integration.cs`)
- Known typo to preserve for compatibility: `EventRecievedMessage` and `EventRecievedDonation` (misspelled "Received"). Do not rename these without updating all callers.

**Streamer.bot Global Variables and Arguments:**
- Global variables and argument keys are camelCase with a `da` prefix: `daClientId`, `daClientSecret`, `daRedirectUrl`, `daAccessToken`, `daRefreshToken`, `daAccessTokenExpiresAt`, `daSocketToken`, `daUserId`, `daUpdateRepo`
- Action output arguments exported to Streamer.bot use the `da` prefix with a domain segment: `daDonationAmount`, `daDonationUsername`, `daGoalTitle`, `daGoalCurrent`, `daAudioUrl`
- Keep this prefix for any new global or argument. Document new keys in `README.md` under the settings table.

**Types of Configuration:**
- Settings DTO properties are PascalCase: `ClientId`, `ReconnectDelaySeconds`, `UserAgent` (`DonationAlertsSettings` in `integration.cs`)

## Code Style

**Formatting:**
- Indentation: 4 spaces. No tabs.
- Brace style: Allman (opening brace on its own line) for all types, methods, control blocks, and lambdas:
  ```csharp
  public bool Connect()
  {
      EnsureInitialized();
      if (!EnsureSettings())
          return false;
  ```
- Single-statement `if` bodies omit braces and are indented on the next line. Multi-statement bodies use braces. Mixing both is common. Keep braces when a body spans more than one statement.
- Line endings: LF (no CR characters found in `integration.cs`).
- Encoding: `README.md` is UTF-8 with BOM; `integration.cs` is UTF-8 and the README and comments are in Russian. Keep comments and user-facing strings consistent with the existing language of the surrounding file (README and log/chat messages are Russian in places; code comments are minimal).
- Blank lines separate logical blocks inside methods. Some members are not separated by blank lines (`CPHInline` members in `integration.cs` lines 89-100 run together). Prefer one blank line between methods.
- No automatic formatter or `.editorconfig` is present in the repository. Formatting is by convention only.

**Linting:**
- Not configured. No analyzers, StyleCop, or `.editorconfig` detected.

**Trailing whitespace:**
- Present in some lines (`EventAuthError    = "auth_error"; ` in `integration.cs` line 576). Avoid adding new trailing whitespace.

## Import Organization

**Order (as used in `integration.cs` and `updateChecker.cs`):**
1. `System` and `System.*` namespaces (`System`, `System.Net`, `System.Text`, `System.Web`, `System.Threading.Tasks`, `System.IO`, ...)
2. Third-party namespaces (`Newtonsoft.Json`)
3. `System.Collections.Generic` and remaining `System.*` imports appear interleaved. The order is not strictly sorted. Add new `using` lines at the top of the file without reordering existing ones.

**Path Aliases:**
- Not applicable. C# `using` directives are used without aliases. Fully qualified names are used when disambiguating: `System.Timers.Timer` in `Service.ServeAndListenAuth` (`integration.cs` line 1097).

**Dependencies:**
- Only `Newtonsoft.Json` is referenced as an external package (`JsonConvert`, `JsonProperty`). Streamer.bot provides the `CPH` and `IInlineInvokeProxy` types at runtime. Do not add NuGet dependencies without a clear need, because the script runs inside Streamer.bot's host.

## Error Handling

**Pattern for action entry points:**
- Public `bool` methods validate prerequisites first (`EnsureInitialized()`, then `EnsureSettings()`, then the operation), return `false` on failure, and report the reason via `Logger.Error`/`Logger.Debug` and/or `CPH.SendMessage` for user-facing messages:
  ```csharp
  public bool Start()
  {
      EnsureInitialized();
      if (!EnsureSettings())
          return false;

      if (!EnsureAccessToken())
          return false;

      return DonationCheckerLoop();
  }
  ```
- Exceptions are used only in the socket loop to signal fatal state: `throw new Exception("Unauthorized")` in `DonationCheckerLoop` (`integration.cs` line 411) and `throw new Exception("Socket is closed")` in `ObtainSocketClientId`.

**Network errors:**
- `WebException` is caught specifically where the status code matters, and converted to a log entry via `Logger.WebError(e)` (`PrefixedLogger.WebError` in `integration.cs`).
- Use `HttpWebResponse` status checks for auth vs. transient errors: `if (response != null && response.StatusCode == HttpStatusCode.Unauthorized)` (`SocketService.ConnectLoop`).
- Re-throwing uses `throw e;` in `Service.GetProfileInfo` and `Service.ObtainChannelSubscribeToken`. Prefer `throw;` for new code so the stack trace is preserved.

**Swallowing exceptions:**
- Non-critical operations use empty catch blocks: `catch (Exception) { }` in `updateChecker.cs` (`FetchLatestGitHubVersion`, `GetGitHubReleaseVersionsAsync`), `SocketService.Close`, and inside the message loop of `ConnectAndProcess`. This is intentional for best-effort operations, but it hides failures. When adding code, log in the catch block with `Logger.Debug` (the `updateChecker.cs` class has no logger, so use `CPH.LogDebug` as it already does for the repo-slug check).

**Null handling:**
- Use `string.IsNullOrWhiteSpace(...)` for strings. Do not use `== null || == ""`.
- Dictionary access is guarded: `data != null && data.ContainsKey(key) && data[key] != null` (helper `GetValue` in `integration.cs`). Use `GetValue(dict, key, fallback)` rather than indexing directly.
- Argument access is guarded by `GetArgString`, which handles the Streamer.bot `args` dictionary.

**Parsing:**
- Use `TryParse` with `CultureInfo.InvariantCulture` and `NumberStyles`/`DateTimeStyles` explicitly: `int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out int parsed)`, `DateTime.TryParse(... DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal ...)`.
- Timestamps are stored as ISO 8601 with `"o"` format and compared in UTC: `expiresAt.ToString("o")`, `DateTime.UtcNow`.

## Logging

**Framework:** Streamer.bot `CPH` API. The `PrefixedLogger` class in `integration.cs` wraps `CPH.LogWarn` and `CPH.LogDebug`.

**Patterns:**
- Use `Logger.Debug(message, extra...)` for normal flow and `Logger.Error(message, extra...)` for failures. `Logger` is only available in `CPHInline`/`Service`/`SocketService`. `updateChecker.cs` calls `CPH.LogDebug` directly with the prefix `"UpdateChecker: "`.
- The `PrefixedLogger` adds the prefix `-- Donation Alerts:` to every message. Do not add the prefix manually.
- Extra values are passed as additional parameters and are joined with `", "`. Example: `Logger.Debug("Auth link", authLink);`.
- Do not log secrets. Current code logs the auth link URL (which contains only the client_id) and the raw profile JSON (`Logger.Debug("Retrieved user profile info", profile.Data.Id, json)`). Do not add logging of `daClientSecret`, `daAccessToken`, or `daRefreshToken`.
- User-facing messages go through `CPH.SendMessage(...)` with plain sentences. Example: `"DonationAlerts watcher is running"`.

## Comments

**When to Comment:**
- File header block uses a dashed banner with module metadata:
  ```csharp
  ///----------------------------------------------------------------------------
  ///   Module:     DonationAlerts Integration for Streamer.bot
  ///   Repository: (set after publishing)
  ///----------------------------------------------------------------------------
  ```
  Use the same `///` banner form for any new file.
- Inline comments are rare. Code is expected to be self-describing through method and constant names.
- Known TODO-style placeholder: `Repository: (set after publishing)` and `DefaultRepoSlug = ""` must be filled before release.

**JSDoc/TSDoc (XML doc):**
- Not used. No `///<summary>` blocks found.

## Function Design

**Size:**
- Most methods are short (under 30 lines). Two exceptions are large: `ConnectAndProcess` (about 80 lines, message switch) and `BuildSuccessPage` in `Service` (HTML string). When adding logic, extract a helper instead of growing these methods.

**Parameters:**
- Pass dependencies through constructors. `Service(Client client, CPHInline.PrefixedLogger logger, DonationAlertsSettings settings)` and `SocketService(Service, Logger, Settings)` show the pattern. Do not use static singletons for new services.
- Use `Dictionary<string, string>` as the event payload type between components. Keep this shape for new events so Streamer.bot argument export stays uniform.

**Return Values:**
- Action methods return `bool`. Data-fetch methods return a DTO or `null` on failure (`ObtainToken`, `GetProfileInfo`, `FetchLatestGitHubVersion`).
- Collections returned from failed fetches are empty lists, not `null` (`GetGitHubReleaseVersionsAsync` returns `new List<GitHubReleaseResponse>()`).

## Module Design

**Exports:**
- Each file exposes one public `CPHInline` class (the Streamer.bot entry point). Other public types are nested inside it or in the same file. Only `CPHInline` methods are callable from Streamer.bot actions via `CPH.ExecuteMethod`.
- `updateChecker.cs` is a separate Streamer.bot script with its own `CPHInline` class. It is invoked from `integration.cs` by name: `CPH.ExecuteMethod("DonationAlerts | Update Checker", "CheckAndAnnounce")`.

**Barrel Files:**
- Not applicable. There is one file per script, and no shared module is imported between scripts.

**Action Naming (Streamer.bot):**
- Actions are named `DA | <Verb>` in the README (`DA | Connect`, `DA | Start`, `DA | Stop`). Default handler actions use `DonationHandler_<Name>` (`DonationHandler_Default`, `DonationHandler_GoalHandler`, `DonationHandler_After`) and amount-specific `DonationHandler_<amount>`. Follow these names when documenting new actions.

## Pull Request and Commit Conventions

- PR checklist is in `.github/pull_request_template.md`. Items: updated integration code, exported `install.sb` and `update.sb` actions, and bumped the version in `updateChecker.cs`.
- Keep the version in `updateChecker.cs` (`CurrentVersion = "2.0.0"`) in sync with the User-Agent default `StreamerBot-DonationAlerts/2.0` in `integration.cs` (`LoadSettings`).
- Release tags are semver-like (`v2.0.0`), parsed by `ParseVersion` in `updateChecker.cs` after stripping a leading `v`. Tags must be parseable by `System.Version`.

---

*Convention analysis: 2026-10-17*
