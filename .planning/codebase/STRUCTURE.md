---
last_mapped_commit: 2047008445144024a44f608400bc03a71f717c2f
last_mapped_at: 2026-10-17
---
# Codebase Structure

**Analysis Date:** 2026-10-17

## Directory Layout

```
streamer.bot-donationAlerts/
├── integration.cs              # Main DonationAlerts integration (all runtime logic)
├── updateChecker.cs            # Separate Streamer.bot action: GitHub release check
├── successPage.html            # Static copy of the post-OAuth success page
├── README.md                   # User-facing setup guide (Russian)
├── LICENSE                     # License text
├── CODE_OF_CONDUCT.md          # Community conduct policy
├── .gitignore                  # Git ignore rules
└── .github/
    ├── pull_request_template.md        # PR template
    └── workflows/
        └── release-announce.yml        # Discord release announcement workflow
```

Tooling directories excluded from this map per scope: `.claude/`, `.idea/`, `.planning/`.

## Directory Purposes

**Repository root:**
- Purpose: Holds all project code. There is no `src/` tree; each `.cs` file is a self-contained Streamer.bot C# inline script.
- Contains: `.cs` scripts, one HTML asset, Markdown docs, license.
- Key files: `integration.cs`, `updateChecker.cs`

**`.github/`:**
- Purpose: GitHub repository metadata and automation.
- Contains: PR template, workflow definitions.
- Key files: `.github/pull_request_template.md`, `.github/workflows/release-announce.yml`

**`.github/workflows/`:**
- Purpose: GitHub Actions definitions.
- Contains: One workflow, `release-announce.yml`, triggered on `release: created`. It fetches the release body via the GitHub API and posts to Discord with `Ilshidur/action-discord`, using the `DISCORD_WEBHOOK` secret.

**Note on `.github/ISSUE_TEMPLATE/`:** The directory is absent from the working tree (its two Russian-named template files are staged for deletion in git). Do not add new references to it.

## Directory Purposes (Code Units)

**`integration.cs` (1624 lines):** Single compilation unit containing:
- `DonationAlertsSettings` (line ~21): config DTO.
- `CPHInline` (line ~34): action facade, nested `PrefixedLogger` (line ~36), handlers for donation/goal export.
- `SocketService` (line ~566): Centrifugo WebSocket client, nested private DTOs (lines ~839-1042), public `DonationData` (line ~947) and `GoalData` (line ~1011).
- `Service` (line ~1044): OAuth, REST, `HttpListener`, nested DTOs `TokenResponse`, `ProfileInfoResponse`, `ProfileInfoData`, `ChannelSubscribeResponse`, `ChannelSubscribeRequest` (lines ~1415-1457), HTML builders (lines ~1264-1414).
- `Client` (line ~1459): HTTP transport.
- `EventObserver` (line ~1568): pub/sub.
- `Helper` (line ~1597): MD5 helper.

**`updateChecker.cs` (123 lines):** `CPHInline` class for the update action with private `GitHubReleaseResponse` DTO (line ~110).

**`successPage.html` (109 lines):** Standalone HTML/CSS page with Google Fonts links. Its markup is mirrored as a verbatim C# string in `integration.cs` `BuildSuccessPage()` (line ~1264); the file is not loaded at runtime.

## Key File Locations

**Entry Points:**
- `integration.cs`: public action methods on `CPHInline` (`Init`, `Connect`, `Start`, `Stop`, `CreateAuthLink`, `ObtainAccessToken`, `RefreshAccessToken`, `GetProfileInfo`, `DonationCheckerLoop`, `Dispose`).
- `updateChecker.cs`: `CheckAndAnnounce()` and `IsUpdateAvailable()`.

**Configuration:**
- `integration.cs` `LoadSettings()` (line ~214): reads Streamer.bot globals `daClientId`, `daClientSecret`, `daRedirectUrl`, `daScopes`, `daAuthTimeoutSeconds`, `daReconnectDelaySeconds`, `daMaxReconnectAttempts`, `daDownloadAudio`, `daUserAgent`.
- `updateChecker.cs` `GetRepoSlug()` (line ~53): reads `daUpdateRepo`; `DefaultRepoSlug` constant (line ~13) is empty.
- `integration.cs` constants (lines ~86-88): action names `DonationHandler_Default`, `DonationHandler_GoalHandler`, `DonationHandler_After`.
- `integration.cs` constants (lines ~568, ~1048-1051): Centrifugo host and DonationAlerts OAuth/API endpoints.
- `updateChecker.cs` line ~12: `CurrentVersion = "2.0.0"` (version compared against GitHub release tags).

**Core Logic:**
- `integration.cs` `CPHInline` (lines ~34-564): orchestration and argument export.
- `integration.cs` `SocketService` (lines ~566-1042): realtime channel.
- `integration.cs` `Service` (lines ~1044-1414): OAuth and REST.
- `integration.cs` `Client` (lines ~1459-1566): HTTP.

**Documentation:**
- `README.md`: setup steps, global variable reference, argument reference, action naming conventions, update setup, troubleshooting.

**Testing:**
- Not detected. No test project, test files, or test configuration exists in the repository.

**Build and Packaging:**
- Not detected. No `.csproj`, `.sln`, `package.json`, or CI build job. The only workflow is release announcement.

## Naming Conventions

**Files:**
- Lowercase or camelCase base names for scripts: `integration.cs`, `updateChecker.cs`. Mixed style; keep new script names camelCase to match `updateChecker.cs`.
- Uppercase `.md` for repo-level docs: `README.md`, `LICENSE`, `CODE_OF_CONDUCT.md`.
- Static assets lowercase camelCase: `successPage.html`.

**Directories:**
- Lowercase, dot-prefixed for GitHub metadata: `.github/`, `.github/workflows/`.

**C# identifiers:**
- Classes: PascalCase (`CPHInline`, `SocketService`, `DonationAlertsSettings`).
- Public action methods: PascalCase verbs matching Streamer.bot action names (`Connect`, `Start`, `Stop`).
- Private methods: PascalCase (`EnsureInitialized`, `ExportDonation`).
- Constants: PascalCase for `const string` (`DefaultHandlerActionName`, `SocketHost`), with `Default`/`Endpoint`/`Event` prefixes for groups (`EventStarted`, `EndpointToken`).
- Event names in the bus: lowercase snake_case strings (`"recieved_donation"`, `"goal_updated"`, `"auth_error"`). Note the existing misspelling `EventRecievedDonation` / `"recieved_donation"` is part of the public contract; keep it when extending.
- Global variables and action arguments: `da` prefix with camelCase (`daClientId`, `daDonationAmount`, `daGoalTarget`). Legacy aliases (`daName`, `daUsername`, `daAmount`, ...) must remain for backward compatibility.
- Action names: `DA | <Verb>` for the user-created Streamer.bot actions (README), `DonationHandler_<amount>` for amount-specific donation handlers.

## Where to Add New Code

**New Streamer.bot action entry point (user-callable):**
- Implementation: add a `public bool <Name>()` method to `CPHInline` in `integration.cs`, starting with `EnsureInitialized()` and, if needed, `EnsureSettings()`.
- Document the new action in `README.md` under "Быстрый старт" or a new section.

**New DonationAlerts REST endpoint:**
- Constant: add `private const string Endpoint<Name>` near lines ~1048-1051 in `integration.cs`.
- Call: add a method on `Service` (`integration.cs` lines ~1044-1414), using `Client.GET` or `Client.POST` / `POSTForm` on the `Client` instance.
- DTO: add a nested class beside `TokenResponse` / `ProfileInfoData` (lines ~1415-1457).

**New realtime event type:**
- Constants: add `Event<Name>` string to `SocketService` (`integration.cs` lines ~570-580).
- Parsing: add a `SocketMessage.Type<Name>` constant, extend `SocketMessage.RecognizeType()` (line ~907), and add a `case` in `ConnectAndProcess` (line ~705) that deserializes into a new response DTO.
- Handler: subscribe in `CPHInline.DonationCheckerLoop` (line ~417) and export arguments via a new `Export<Name>` method modeled on `ExportDonation` (line ~470).
- Document new `da<Name>*` arguments in `README.md`.

**New configuration value:**
- Add a property to `DonationAlertsSettings` (line ~21), read it in `LoadSettings()` with `GetSetting` / `GetSettingInt` / `GetSettingBool` (lines ~214-260), and document it in the README table.

**New update-checker behavior:**
- Implementation: `updateChecker.cs` only. The main script reaches it through `TryRunUpdateChecker()` (line ~385), so keep the `CheckAndAnnounce` method name stable.

**Shared helpers:**
- Small static utilities: `Helper` class at the end of `integration.cs` (line ~1597).
- Dictionary value access: use `CPHInline.GetValue(...)` (line ~550) pattern for payload reads.

**Tests:**
- No test location exists. If a test project is introduced, place it under `tests/` at the root and keep scripts compilable standalone for Streamer.bot import; there is currently no convention to follow.

## Special Directories

**`.github/workflows/`:**
- Purpose: GitHub Actions workflows.
- Generated: No.
- Committed: Yes.

**`.github/ISSUE_TEMPLATE/`:**
- Purpose: Issue templates (historically present).
- Generated: No.
- Committed: Staged for deletion in the current git state; absent from the working tree.

**`.planning/`, `.claude/`, `.idea/`:**
- Purpose: Tooling and IDE metadata. Excluded from project code layout.
- Generated: Yes (tool-managed or IDE-managed).
- Committed: Not part of the project source.

---

*Structure analysis: 2026-10-17*
