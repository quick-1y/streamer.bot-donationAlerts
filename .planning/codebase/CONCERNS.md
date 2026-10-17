---
last_mapped_commit: 2047008445144024a44f608400bc03a71f717c2f
last_mapped_at: 2026-10-17
---
# Codebase Concerns

**Analysis Date:** 2026-10-17

Scope: tracked project files only (`integration.cs`, `updateChecker.cs`, `successPage.html`, `README.md`, `.github/`, `.gitignore`). Tooling directories (`.claude/`, `.idea/`, `.planning/`) are excluded. The repository has no build project, no tests, and no CI build; all C# files are Streamer.bot inline scripts (`CPHInline` classes) compiled by Streamer.bot itself, so nothing in the repo verifies that they compile.

## Blocking Defects

**Missing statement terminator breaks compilation of the main integration:**
- Issue: The `TextPleaseConnect` constant is declared without a trailing semicolon, so `integration.cs` cannot compile. Everything else in the integration (Connect, Start, token handling) is unusable until this is fixed.
- Files: `integration.cs` (line 89)
- Impact: Streamer.bot reports a compile error on import; no DonationAlerts action works.
- Fix approach: Change line 89 to end with `";`. Because no compile step exists in the repo, consider adding a `.csproj` or a Roslyn check (see Test Coverage Gaps).

**Auth-link helper calls `WebError` with a possibly-null response:**
- Issue: `PrefixedLogger.WebError` casts `e.Response` to `HttpWebResponse` and dereferences it without a null check. For transport failures (DNS error, timeout, connection refused) `WebException.Response` is null, so this throws `NullReferenceException`.
- Files: `integration.cs` (lines 45-51, called from lines 1145, 1175, 1205, 1237)
- Impact: The original network error is replaced by a `NullReferenceException`. In `GetProfileInfo` (line 1143-1146) the rethrow path therefore never reaches `FetchProfileInfo`'s `catch (WebException)` (line 354), so the token-refresh fallback is skipped and `DonationCheckerLoop` fails with an unrelated exception.
- Fix approach: `var response = e.Response as HttpWebResponse; if (response == null) { Error("WebException: " + e.Status); return; }`.

## Security Considerations

**OAuth flow has no `state` parameter and the local callback accepts any code:**
- Risk: `GetAuthLink` (line 1118-1122) builds the authorize URL without `state`, and `ServeAndListenAuth` (lines 1064-1117) accepts any GET to the callback with a `code` query parameter. While the listener is open (default 90 s, `daAuthTimeoutSeconds`), any page the user visits can make the browser request `http://127.0.0.1:8554/donationalerts/callback/?code=<attacker code>`. The attacker's code is stored in `daCode` (line 143) and exchanged, linking the streamer's Streamer.bot to the attacker's DonationAlerts account (login CSRF).
- Files: `integration.cs` (lines 129-147, 1064-1117, 1118-1122)
- Current mitigation: Listener only runs during `Connect`, and only on loopback.
- Recommendations: Generate a random `state` per `CreateAuthLink`, include it in the authorize URL, store it in memory, and reject callbacks whose `state` does not match before calling the handler. Reject callbacks when no `Connect` is pending.

**Client secret and OAuth tokens stored as plain Streamer.bot globals:**
- Risk: `daClientSecret` is read from globals (line 218), and `daAccessToken` / `daRefreshToken` / `daSocketToken` / `daCode` are written with persistence enabled (`CPH.SetGlobalVar(..., true)`, lines 143, 301-303, 350). Persisted globals are written to Streamer.bot's data store in clear text; anyone with access to the Streamer.bot profile, a backup, or an exported `.sb` file can impersonate the streamer's DonationAlerts app and account. The `daRefreshToken` grants long-term access.
- Files: `integration.cs` (lines 217-218, 143, 301-303, 350-351), `README.md` (settings table, lines in "Настройки")
- Current mitigation: None in code. README only says to fill globals.
- Recommendations: Document that `.sb` exports and backups contain these secrets. Do not persist `daCode` at all (it is single-use). Prefer keeping the client secret in an environment variable read via `Environment.GetEnvironmentVariable`, and avoid exporting it in `install.sb` / `update.sb` (see the PR checklist in `.github/pull_request_template.md`).

**Personal data and raw payloads written to the debug log:**
- Risk: `Service.GetProfileInfo` logs the full profile JSON, which includes `email` and `socket_connection_token` (`integration.cs` line 1139: `Logger.Debug("Retrieved user profile info", profile.Data.Id, json)`). The socket loop logs every raw WebSocket frame, including donation messages and sender names (`integration.cs` line 697: `Logger.Debug(rawMessage)`). The subscribe handshake response is also logged in full (line 821).
- Files: `integration.cs` (lines 697, 821, 1139)
- Current mitigation: Logs go through `LogDebug`, which Streamer.bot shows only when debug logging is on.
- Recommendations: Log only the profile id; log message type and channel, not the body. Remove `json` from line 1139 and `rawMessage` from lines 697 and 821. The README promises "Чистые логи" (clean logs), which the current logging contradicts.

**OAuth error and success pages duplicated; unescaped message interpolation:**
- Risk: `BuildErrorPage` injects its `message` argument with `string.Format` without HTML encoding (`integration.cs` line 1412). Current callers pass constants, so there is no active XSS, but the pattern is unsafe if a message ever includes request data. The success HTML is duplicated (`integration.cs` lines 1266-1374 vs `successPage.html`), see Tech Debt.
- Files: `integration.cs` (lines 1376-1413), `successPage.html`
- Current mitigation: All messages are hard-coded.
- Recommendations: HTML-encode the message (`HttpUtility.HtmlEncode`) before inserting it.

**Remote audio files downloaded to a predictable temp path without cleanup:**
- Risk: `SaveFileToTemp` downloads an arbitrary URL supplied by the DonationAlerts payload (`integration.cs` lines 502-504, 529-549) to `Path.GetTempPath()` with a name derived from the donation id. Files are never deleted, and an existing file with the same name is silently overwritten. The download has no size limit and no timeout.
- Files: `integration.cs` (lines 502-504, 529-549)
- Current mitigation: Name is built from a numeric id plus `.wav`, so path traversal is not possible from the id itself.
- Recommendations: Enforce an `https://` scheme and an allow-list of hosts; cap download size; delete files after the action runs or rotate a cache directory.

**CI workflow handles a secret with an unpinned third-party action:**
- Risk: `.github/workflows/release-announce.yml` passes `DISCORD_WEBHOOK` to `Ilshidur/action-discord@master` (line 26). A branch reference lets the upstream change at any time while the secret is in scope. The workflow also has no `permissions:` block.
- Files: `.github/workflows/release-announce.yml` (lines 23-26)
- Current mitigation: Secret is scoped to one step.
- Recommendations: Pin the action to a commit SHA, add `permissions: contents: read`, and consider replacing the action with a `curl` POST to the webhook.

## Tech Debt

**Two copies of the success page with no shared source:**
- Issue: The success HTML lives in `integration.cs` (`BuildSuccessPage`, lines 1264-1375) and in `successPage.html` (repo root). The root file is not referenced by any code and the two copies differ only in quoting style, so they will drift.
- Files: `integration.cs` (lines 1264-1375), `successPage.html`
- Impact: Edits to one copy are silently ignored by users.
- Fix approach: Delete `successPage.html` or make the build copy it into the C# string. Keep one source.

**Version number maintained in four places by hand:**
- Issue: The version appears in `updateChecker.cs` (`CurrentVersion = "2.0.0"`, line 12), in the default User-Agent (`integration.cs` line 225, line 1466), and in the README default (`README.md`, `daUserAgent` row). The PR checklist (`.github/pull_request_template.md`) requires a manual bump of `updateChecker.cs` only.
- Files: `updateChecker.cs` (line 12), `integration.cs` (lines 225, 1466), `README.md`, `.github/pull_request_template.md`
- Impact: Update notifications compare against a stale value if the bump is forgotten; User-Agent reports the wrong version.
- Fix approach: Keep one `const` in `integration.cs` and reference it from the checker, or generate the User-Agent from the checker constant.

**Placeholder repository metadata left in source:**
- Issue: Both headers say `Repository: (set after publishing)` (`integration.cs` line 19, `updateChecker.cs` line 8). `DefaultRepoSlug` is empty (`updateChecker.cs` line 13), so update checking is disabled unless the user sets `daUpdateRepo`.
- Files: `integration.cs` (line 19), `updateChecker.cs` (lines 8, 13)
- Fix approach: Fill in the real `owner/repo` and set `DefaultRepoSlug` to it.

**Build artifacts are not in the repo and the build step is undocumented:**
- Issue: The PR checklist requires exporting Actions to `install.sb` and `update.sb`, but neither file, nor the export procedure, exists in the repository. `.gitignore` ignores `dist` and `.vs` only.
- Files: `.github/pull_request_template.md`, `.gitignore`
- Impact: Releases depend on the maintainer's local Streamer.bot setup; results cannot be reproduced.
- Fix approach: Document the export step in `README.md` or add a script that produces the `.sb` files.

**Repository hygiene:**
- Issue: `.idea/` is untracked and not ignored (only `.vs` and `dist` are in `.gitignore`). The two Russian issue templates under `.github/ISSUE_TEMPLATE/` are staged for deletion in the current index, and the PR template checkboxes use `- [] ` instead of `- [ ]`.
- Files: `.gitignore`, `.github/ISSUE_TEMPLATE/` (staged deletions), `.github/pull_request_template.md` (lines 5-7)
- Fix approach: Add `.idea/` and `.claude/` to `.gitignore`; confirm whether the issue-template deletion is intended; fix the checkbox syntax.

**Mixed languages across the repo:**
- Issue: Code comments and identifiers are English, while `README.md`, the PR template, the workflow message, and the (deleted) issue templates are Russian. The success page is English, the error page is English, and the Discord announcement is Russian.
- Files: `README.md`, `.github/pull_request_template.md`, `.github/workflows/release-announce.yml`, `integration.cs` (lines 1266-1413)
- Impact: Contributors and users who read only one language cannot maintain all parts.
- Fix approach: Decide on the user-facing language per artifact and document it in `README.md`.

## Known Bugs

**Release announcer posts raw JSON and a stray quote to Discord:**
- Symptoms: The Discord message contains surrounding double quotes and literal `\r\n` sequences, a stray `"` after the description, and a literal `{{GITHUB_SERVER_URL}}/{{GITHUB_REPOSITORY}}` instead of the repository URL.
- Files: `.github/workflows/release-announce.yml` (lines 17-21, 31, 34)
- Trigger: Any published release.
- Causes: `jq '.body'` is run without `-r`, so the output is a quoted JSON string with escaped newlines; the `%0A` / `%0D` substitutions therefore never apply. Line 31 has a trailing `"`. Line 34 uses Mustache-style braces, which GitHub Actions does not expand (it needs `${{ github.server_url }}` and `${{ github.repository }}`).
- Workaround: None; fix the workflow.
- Fix approach: `jq -r '.body'`; drop the `%` substitutions unless they are needed for a specific sink; remove the stray quote; use `${{ github.server_url }}/${{ github.repository }}`. Replace `::set-output` with `echo "desc=..." >> "$GITHUB_OUTPUT"`, and upgrade `actions/checkout@v2` to a current major.

**Update check runs on every `Init` and posts to chat:**
- Symptoms: Each invocation of `Init()` makes a synchronous GitHub API call (`integration.cs` line 94, `TryRunUpdateChecker`), and when a newer release exists it posts a message to the Streamer.bot chat (`updateChecker.cs` line 24). The check is not rate-limited or cached.
- Files: `integration.cs` (lines 91-95, 385-400), `updateChecker.cs` (lines 20-27, 80-93)
- Trigger: Each `Init`; the unauthenticated GitHub API allows 60 requests per hour per IP.
- Workaround: Leave `daUpdateRepo` empty.
- Fix approach: Cache the last-checked time in a global, check at most once per day, and run the check asynchronously so it never blocks `Init`.

**Donation alert can be handled twice; no deduplication:**
- Symptoms: Goal updates are de-duplicated by hash (`integration.cs` lines 724-731), but donations are not. After a reconnect (`ConnectLoop`, lines 624-662) any donation delivered again is dispatched again, and `daDonationId` is available but unused for dedupe. The Centrifugo `recoverable` / `seq` fields that could support recovery are parsed (`SubscribeResponseData`, lines 888-893) but ignored.
- Files: `integration.cs` (lines 707-716, 624-662, 888-893)
- Trigger: Socket reconnect during an active stream.
- Workaround: None in the integration.
- Fix approach: Keep a bounded set of recent donation ids and skip repeats.

**Silent failure when the callback port is taken:**
- Symptoms: If `127.0.0.1:8554` is already in use, `HttpListener.Start()` throws `HttpListenerException`, which is caught and logged only at debug level (`integration.cs` lines 1110-1114). The user sees the "Open the authorization page" message and then nothing.
- Files: `integration.cs` (lines 1064-1117, 1110-1114)
- Trigger: Another application on port 8554, or a previous Connect still holding the listener.
- Workaround: Change `daRedirectUrl` and the DonationAlerts app redirect URL to another port.
- Fix approach: Log this at Error level with the port number and suggest changing `daRedirectUrl`.

**Expired access token during reconnect stops the watcher:**
- Symptoms: Access tokens are checked only at `Start` (`EnsureAccessToken`, line 311-325). The socket loop reuses the same `accessToken` string for the lifetime of the session (`DonationCheckerLoop` line 414, `ConnectLoop` line 627). When a reconnect occurs after expiry, `GetProfileInfo` returns 401, `ConnectLoop` dispatches `EventAuthError` and breaks (lines 633-640), and no refresh is attempted.
- Files: `integration.cs` (lines 311-325, 414, 624-641, 667)
- Trigger: A stream longer than the token lifetime with at least one socket drop after expiry.
- Workaround: Click **DA | Start** again (which refreshes first).
- Fix approach: On a 401 inside `ConnectLoop`, call `RefreshAccessToken()` and retry once before dispatching `EventAuthError`; read the current token from globals on each reconnect rather than capturing it.

**Silent `Close()` path skips the disconnect event:**
- Symptoms: `SocketService.Close()` calls `Socket.Abort()` and then `CloseAsync`. On an aborted socket `CloseAsync` throws, the exception is swallowed by `catch (Exception) { }`, and `Observer.Dispatch(EventDisconnected)` and `Socket = null` never run.
- Files: `integration.cs` (lines 609-623)
- Trigger: **DA | Stop**.
- Fix approach: Call `CloseAsync` first with a timeout, then `Abort()` only if it fails; dispatch the disconnect event in a `finally`.

**Subscribe reports success even when the server did not confirm:**
- Symptoms: `SubscribeToTheChannel` reads at most four frames and then dispatches `EventSubscribed` regardless of whether a matching response arrived (`integration.cs` lines 815-836). If fewer than four frames arrive, `ReceiveMessage` blocks indefinitely (see Fragile Areas).
- Files: `integration.cs` (lines 800-837)
- Fix approach: Return a bool from `SubscribeToTheChannel`; only dispatch `EventSubscribed` when the matching response is read; fail the connection otherwise.

## Performance Bottlenecks

**Synchronous network calls on the Streamer.bot action thread:**
- Problem: `Start` runs the entire socket loop synchronously, `ConnectLoop` blocks with `GetAwaiter().GetResult()` on every async call, and `Thread.Sleep` is used for reconnect delay. Donation handling calls `SaveFileToTemp` (a synchronous `WebClient.DownloadFile` with no timeout) before running the handler action (`integration.cs` lines 503-504, 529-549).
- Files: `integration.cs` (lines 112-122, 624-662, 671-682, 754, 1071-1102, 529-549)
- Cause: The integration is written against the synchronous Streamer.bot `CPH` API but also uses `ClientWebSocket` and `HttpListener` asynchronously, forced back to sync.
- Improvement path: Run the socket loop on a background `Task` owned by `SocketService`, and download audio asynchronously before dispatching the event. Give `WebClient` and `HttpWebRequest` explicit timeouts (default `HttpWebRequest.Timeout` is 100 s; `WebClient` has none).

**Unbounded receive loop with no keep-alive:**
- Problem: `ReceiveMessage` waits with `CancellationToken.None` and no timeout (`integration.cs` lines 746-762). The integration never sends pings or checks heartbeat, so a silently dropped connection is only detected by TCP.
- Files: `integration.cs` (lines 684-693, 746-762)
- Improvement path: Use a linked `CancellationTokenSource` with a timeout and a periodic ping; treat no traffic for N seconds as a disconnect.

**Per-request connection and response handling:**
- Problem: `Client.Perform` does not dispose `HttpWebResponse` (`integration.cs` line 1555) and creates a fresh `ClientWebSocket` on every reconnect without disposing the previous one (line 669). `updateChecker.cs` creates a `WebClient` that is never disposed (line 84).
- Files: `integration.cs` (lines 1529-1566, 669), `updateChecker.cs` (lines 84-87)
- Improvement path: Wrap responses and sockets in `using` blocks, or dispose them explicitly in the reconnect path.

## Fragile Areas

**Socket loop state shared across threads without synchronization:**
- Files: `integration.cs` (`StopRequested`, `Socket`, `PreviousGoalEventHash`, lines 583-590, 609-623)
- Why fragile: `Close()` is called from another Streamer.bot action (**DA | Stop**) while `ConnectLoop` is blocked in `ReceiveAsync`. `Close()` sets `Socket = null`, so the loop can dereference null (`Socket.State` at line 684 or 674) and the `catch (Exception)` at line 742 or the outer loop swallows it. Flags have no `volatile` or lock.
- Safe modification: Use a single `CancellationTokenSource` for stop, pass its token to `ReceiveAsync`, and do not null out the socket field from another thread.
- Test coverage: None.

**Reconnect attempt counter never resets:**
- Files: `integration.cs` (lines 626, 651-656)
- Why fragile: `attempt` increments on every disconnect across the whole session and is never reset after a successful connection. With `daMaxReconnectAttempts` > 0, a long stream with occasional drops permanently stops the watcher after N total drops, even if every reconnect succeeded.
- Safe modification: Reset `attempt` to 0 after `EventSubscribed`.

**Recursive token refresh guarded by Streamer.bot action arguments:**
- Files: `integration.cs` (lines 176-177, 192, 359; `FetchProfileInfo` recursion)
- Why fragile: Recursion protection relies on `args["refresh_token_recursion_protection"]` being set on the current action context. If `FetchProfileInfo` is invoked from a different action or thread, the guard does not apply, and a persistent WebException can recurse across refresh cycles.
- Safe modification: Replace recursion with a single retry flag passed as a parameter.

**Global-variable-driven configuration with silent fallback:**
- Files: `integration.cs` (lines 214-227, 259-265, 266-289)
- Why fragile: `GetSettingInt` and `GetSettingBool` silently return defaults for malformed values (for example `daReconnectDelaySeconds = "five"` becomes `5` with no warning). `WarnIfMissingScope` logs only at debug level. Action arguments override globals without any log.
- Safe modification: Log a warning when a configured value fails to parse.

**Generic exception swallowing in the message loop:**
- Files: `integration.cs` (lines 698-742, 621, 647-649 region)
- Why fragile: Every exception while handling a socket message is discarded by `catch (Exception) { }` (line 742), including handler exceptions raised by the Streamer.bot actions dispatched from `Observer.Dispatch`. A bug in a user's `DonationHandler_*` action is therefore invisible.
- Safe modification: Catch only JSON deserialization errors there, and log the exception type and message at Error level.

**Donation/goal payload field names:**
- Files: `integration.cs` (lines 947-990, 991-1041)
- Why fragile: Field names (`message_type`, `amount_in_user_currency`, `raised_amount`, `goal_amount`) mirror an undocumented-in-repo DonationAlerts WebSocket schema. `GoalData.IsActive` and friends are typed `bool` and `double`; a schema change causes silent `0` / `false` values or dropped events (`IsValid` requires `Amount > 0`, line 935, so zero-amount events are silently dropped).
- Safe modification: Keep `daDonationRaw` / `daGoalRaw` (already exported) as the fallback, and log dropped events at Debug level.

**Auth flow blocks the caller indefinitely on timer failure:**
- Files: `integration.cs` (lines 1097-1103)
- Why fragile: The force-close timer closes the listener while `GetContextAsync` is pending; the resulting `HttpListenerException` / `ObjectDisposedException` is raised from `listenTask.GetAwaiter().GetResult()`, and only `HttpListenerException` is caught. The timer object is never disposed, so repeated Connect calls accumulate timers.
- Safe modification: Use `Listener.GetContext` with a `CancellationToken` and dispose the timer in a `finally`.

## Scaling Limits

**Single WebSocket per Streamer.bot instance:**
- Current capacity: One DonationAlerts account, one `SocketService`, channels `$alerts:donation_{id}` and `$goals:goal_{id}` (`integration.cs` lines 1209-1218).
- Limit: Not designed for multiple accounts; `SocketService` and `Service` are singletons stored in fields of the `CPHInline` instance, and globals (`daAccessToken`, `daUserId`) are not namespaced.
- Scaling path: Namespace globals per account (for example `daAccessToken_<userId>`) and keep one `SocketService` per account.

**Temp audio files accumulate:**
- Current capacity: No limit; one WAV file per audio donation in `Path.GetTempPath()` (`integration.cs` line 534).
- Limit: Grows for the life of the machine.
- Scaling path: Delete files after the handler action completes, or use a rolling cache of fixed size.

## Dependencies at Risk

**Newtonsoft.Json and System.Web:**
- Risk: The code uses `Newtonsoft.Json` (`integration.cs` line 7) and `System.Web.HttpUtility` (line 4), which must be referenced in the Streamer.bot C# environment. Neither dependency is declared anywhere in the repo.
- Impact: Import fails on a fresh Streamer.bot install if these references are missing; the requirement is undocumented.
- Migration plan: Document the required references in `README.md`, or use `System.Text.Json` and `Uri.EscapeDataString` to remove the dependency on `System.Web`.

**GitHub Actions versions:**
- Risk: `actions/checkout@v2` (`.github/workflows/release-announce.yml` line 12) is an old major version, `Ilshidur/action-discord@master` is unpinned (line 26), and `::set-output` (line 21) is a deprecated command.
- Impact: Workflow may stop working or run unreviewed code with the webhook secret.
- Migration plan: Upgrade to current majors, pin SHAs, and replace `::set-output` with `$GITHUB_OUTPUT`.

**Google Fonts loaded at runtime:**
- Risk: Both success and error pages load fonts from `fonts.googleapis.com` / `fonts.gstatic.com` (`integration.cs` lines 1274, 1386; `successPage.html` line 9). The callback page makes third-party requests on every connection, and the OAuth success page depends on external availability for styling.
- Impact: Minor privacy leak (IP and referrer sent to Google); fallback fonts are used offline.
- Migration plan: Inline or self-host the font files, or use system fonts.

## Missing Critical Features

**No refresh before expiry during a live session:**
- Problem: Tokens are refreshed only on `Start` or after a failed profile call (see Known Bugs).
- Blocks: Reliable multi-hour streams without a manual restart.

**No user-visible health status:**
- Problem: Connection state is reported only through chat messages on connect and auth failure. There is no status global or action for "watcher running / last event time".
- Blocks: Streamers cannot tell whether the watcher is stalled after a silent drop (see Performance Bottlenecks, no keep-alive).

**No way to revoke tokens from the integration:**
- Problem: **DA | Stop** closes the socket but leaves `daAccessToken` and `daRefreshToken` in place.
- Blocks: Clean sign-out; a leaked refresh token stays valid until the user revokes it in DonationAlerts.

## Test Coverage Gaps

**No tests and no build verification:**
- What's not tested: All of `integration.cs` and `updateChecker.cs`, including the message parser (`SocketMessage.RecognizeType`), token expiry logic (`IsAccessTokenExpired`), and version comparison (`ParseVersion`). The missing semicolon at `integration.cs` line 89 shows the code has never been compiled as committed.
- Files: `integration.cs`, `updateChecker.cs`
- Risk: Regressions and compile errors ship unnoticed; the `.sb` export is the only check.
- Priority: High
- Fix approach: Add a small `.csproj` that compiles both files against stubs for `CPH` / `IInlineInvokeProxy`, plus unit tests for `RecognizeType`, `FormatAmountForAction`, `ParseVersion`, and `IsAccessTokenExpired`. Add a CI job that runs them.

**Socket and auth flow untested:**
- What's not tested: Reconnect behavior, subscribe handshake, auth-listener timeout, and the `Close()` path.
- Files: `integration.cs` (lines 566-837, 1044-1158)
- Risk: The bugs in Known Bugs and Fragile Areas remain undetected.
- Priority: High
- Fix approach: Abstract `ClientWebSocket` and `HttpWebRequest` behind interfaces and test against a fake Centrifugo server.

**Release workflow untested:**
- What's not tested: The release announcement output (see Known Bugs).
- Files: `.github/workflows/release-announce.yml`
- Risk: Every release posts a malformed Discord message.
- Priority: Medium
- Fix approach: Run the workflow on a draft release or add a `workflow_dispatch` dry-run mode that prints the message.

---

*Concerns audit: 2026-10-17*
