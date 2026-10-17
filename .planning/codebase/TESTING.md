---
last_mapped_commit: 2047008445144024a44f608400bc03a71f717c2f
last_mapped_at: 2026-10-17
---
# Testing Patterns

**Analysis Date:** 2026-10-17

## Test Framework

**Runner:**
- Not detected. The repository contains no test project, no `*Tests.cs` or `*.Tests.csproj` files, and no test runner configuration.
- Config: Not applicable.

**Assertion Library:**
- Not detected.

**Run Commands:**

```bash

# No test commands are defined. The repository has no build or test tooling.

# Validation is manual, inside Streamer.bot (see "Manual Verification" below).

```

**Tracked files relevant to quality checks:**
- `.github/workflows/release-announce.yml` runs only on `release: created`. It sends a Discord notification and does not run compile or test steps.
- `.github/pull_request_template.md` lists manual checklist items only. No automated checks are required before merge.

## Test File Organization

**Location:**
- No test files exist. There is no test directory.

**Naming:**
- Not applicable.

**Structure:**
- Not applicable. If tests are added, see the recommendation below.

## Test Structure

**Suite Organization:**
- Not applicable. No test suites exist.

**Patterns:**
- Not applicable.

## Mocking

**Framework:** Not detected.

**Testability constraints in the current code:**
- The `CPH` object (Streamer.bot API) is accessed directly as a global in `integration.cs` and `updateChecker.cs` (for example `CPH.GetGlobalVar<string>("daClientId")`, `CPH.SendMessage(...)`, `CPH.SetArgument(...)`). Code paths that touch `CPH` cannot be unit-tested without a fake.
- Network calls are made directly with `WebClient`, `HttpWebRequest`, and `ClientWebSocket`, created inline (for example `new WebClient()` in `updateChecker.cs` `GetGitHubReleaseVersionsAsync` and `SaveFileToTemp` in `integration.cs`). There is no abstraction to inject a test double.
- `Client` and `Service` take their dependencies through constructors (`Service(Client client, CPHInline.PrefixedLogger logger, DonationAlertsSettings settings)`), so `Service` can be tested with a fake `Client`. This is the existing seam to use.
- `SocketService` receives `Service`, `PrefixedLogger`, and `DonationAlertsSettings` through its constructor, so it can also be driven with a test `Service`.

**What to Mock (if tests are introduced):**
- The `CPH` interface (`IInlineInvokeProxy`) and its methods: `GetGlobalVar`, `SetGlobalVar`, `SetArgument`, `SendMessage`, `LogDebug`, `LogWarn`, `ActionExists`, `RunAction`, `ExecuteMethod`.
- The HTTP boundary used by `Client` (`GET`, `POSTForm`) and by `updateChecker.cs` (GitHub releases API).
- The WebSocket boundary (`ClientWebSocket`) in `SocketService`.

**What NOT to Mock:**
- `DonationAlertsSettings` (plain DTO).
- `ParseVersion` and version-comparison logic in `updateChecker.cs`. Test it directly.
- `FormatAmountForAction`, `GetValue`, `NormalizeRedirectUrl`, and `IsAccessTokenExpired` (pure functions over strings and time).

## Fixtures and Factories

**Test Data:**
- No fixtures exist. Realistic payloads for future tests can be taken from the JSON shapes the code deserializes:
  - GitHub release list: `html_url`, `tag_name`, `name`, `prerelease`, `draft` (see `GitHubReleaseResponse` in `updateChecker.cs`).
  - DonationAlerts socket message: a dictionary keyed by `"result"` with a `type` discriminator (see `SocketMessage.RecognizeType` and `DonationResponse` in `integration.cs`).

**Location:**
- Not applicable. Recommended location if added: `tests/fixtures/`.

## Coverage

**Requirements:** None enforced. No coverage tool is configured.

**View Coverage:**

```bash

# Not available. No coverage tooling is configured.

```

## Test Types

**Unit Tests:**
- None. Candidates for first unit tests (pure logic, no `CPH` dependency):
  - `CPHInline.ParseVersion` (`updateChecker.cs`): handles `v` prefix, rejects empty and non-version strings.
  - `CPHInline.GetRepoSlug` fallback behavior when `daUpdateRepo` is empty.
  - `CPHInline.NormalizeRedirectUrl` (`integration.cs`): adds a trailing `/`.
  - `CPHInline.FormatAmountForAction` (`integration.cs`): normalizes `"5.00"` to `"5"` and keeps non-numeric input unchanged.
  - `CPHInline.GetValue` (`integration.cs`): fallback when key missing or value null.
  - `SocketService.DonationData` and goal hashing via `Helper.GetMD5Hash`: duplicate goal suppression depends on stable hashing.

**Integration Tests:**
- None. The OAuth flow (`Service.ServeAndListenAuth`, `GetAuthLink`, `ObtainToken`, `RefreshToken`) and the Centrifugo WebSocket flow (`SocketService.ConnectAndProcess`, `SubscribeToTheChannel`) require live DonationAlerts credentials and a running Streamer.bot host.

**E2E Tests:**
- Not used. The integration is verified by running the actions in Streamer.bot against DonationAlerts.

## Manual Verification

Because no automated tests exist, the verification steps below are the only checks in the repository. Follow them before merging changes (also reflected in `.github/pull_request_template.md`):

1. Import the integration into Streamer.bot and confirm it compiles. Note: the current `integration.cs` line 89 (`TextPleaseConnect`) has no terminating semicolon, so it will not compile until fixed.
2. Run **DA | Connect** and confirm the browser opens, the local callback (`daRedirectUrl`, default `http://127.0.0.1:8554/donationalerts/callback/`) receives the code, and `successPage.html` content is shown.
3. Run **DA | Start** and confirm the log shows `Connected to the socket` and `Authorized successfully`.
4. Trigger a test donation and confirm the `DonationHandler_<amount>` action runs and the `da*` arguments are populated.
5. Restart the connection with an expired token to exercise `RefreshAccessToken` (the `refresh_token_recursion_protection` guard in `integration.cs` prevents infinite recursion).
6. For `updateChecker.cs`, set `daUpdateRepo` to a repository with a newer release tag and confirm the chat announcement.

## Common Patterns

**Async Testing:**
- Not applicable. The code uses blocking calls (`GetAwaiter().GetResult()`, `Thread.Sleep`) and does not expose async test entry points.

**Error Testing:**
- Not applicable. Error paths are exercised manually by invalid settings (`EnsureSettings` lists missing `daClientId`, `daClientSecret`, `daRedirectUrl`) and by an expired or missing token.

## Recommendations for Adding Tests

- Add a separate test project (for example `tests/DonationAlerts.Tests/`) that compiles `integration.cs` and `updateChecker.cs` with a stub `CPH`/`IInlineInvokeProxy` and `Newtonsoft.Json`. Place it outside the Streamer.bot script folder so it is not exported.
- Start with the pure helpers listed under "Unit Tests" above; they need no network.
- Keep `CPH` calls out of new pure helpers so they remain testable.

---

*Testing analysis: 2026-10-17*
