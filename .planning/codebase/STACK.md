---
last_mapped_commit: 2047008445144024a44f608400bc03a71f717c2f
last_mapped_at: 2026-10-17
---
# Technology Stack

**Analysis Date:** 2026-10-17

## Languages

**Primary:**
- C# (.NET Framework style code, `CPHInline` class) - all integration logic in `integration.cs` and `updateChecker.cs`

**Secondary:**
- HTML/CSS (inline, with Google Fonts) - OAuth success/error page in `successPage.html` (also embedded as string templates in `integration.cs`, around lines 1270-1390)
- YAML - GitHub Actions workflow `.github/workflows/release-announce.yml`
- Markdown - documentation in `README.md` (Russian-language)

## Runtime

**Environment:**
- Streamer.bot C# execution runtime (the `CPH` API host object is injected by Streamer.bot; code is not a standalone executable)
- Uses `System.Net.HttpListener`, `System.Net.WebSockets.ClientWebSocket`, `System.Net.HttpWebRequest`, `System.Net.WebClient`

**Package Manager:**
- None. No NuGet manifest (`.csproj`, `packages.config`) is present in the repository.
- Lockfile: Not applicable

## Frameworks

**Core:**
- Streamer.bot inline C# action host (`CPHInline`, `CPH.*` API) - entry point and host for all actions (`Connect`, `Start`, `Stop`, `CheckAndAnnounce`, `IsUpdateAvailable`)

**Testing:**
- Not detected

**Build/Dev:**
- Not detected (scripts are pasted/imported into Streamer.bot; no build tooling in repo)

## Key Dependencies

**Critical:**
- `Newtonsoft.Json` (Json.NET) - JSON (de)serialization of OAuth tokens, profile, Centrifugo messages, and GitHub release data; used via `JsonConvert` and `[JsonProperty]` in `integration.cs` and `updateChecker.cs`
- Streamer.bot `CPH` API - `CPH.GetGlobalVar<T>`, `CPH.SetGlobalVar`, `CPH.SetArgument`, `CPH.SendMessage`, `CPH.LogDebug`, `CPH.LogWarn`

**Infrastructure:**
- `System.Net.HttpListener` - local OAuth redirect callback server (`Service.ServeAndListenAuth` in `integration.cs`)
- `System.Net.WebSockets.ClientWebSocket` - Centrifugo WebSocket client (`SocketService` in `integration.cs`)
- `System.Security.Cryptography` - imported in `integration.cs`
- `System.Timers`, `System.Threading`, `System.Diagnostics` (`Process`/`ProcessStartInfo` to open the browser)

## Configuration

**Environment:**
- Configured via Streamer.bot global variables, not environment variables or files. Read with `CPH.GetGlobalVar<string>` in `integration.cs` (settings loader around lines 215-240):
  - Required: `daClientId`, `daClientSecret`
  - Optional with defaults: `daRedirectUrl` (default `http://127.0.0.1:8554/donationalerts/callback/`), `daScopes` (default `oauth-user-show oauth-donation-subscribe oauth-goal-subscribe`), `daAuthTimeoutSeconds` (90), `daReconnectDelaySeconds` (5), `daUserAgent` (default `StreamerBot-DonationAlerts/2.0`), `daUpdateRepo` (GitHub `owner/repo` slug for update checks)
- Runtime state persisted as globals: `daCode`, `daAccessToken`, `daRefreshToken`, `daAccessTokenExpiresAt`, `daSocketToken`, `daUserId`
- No `.env` file present in the repository.

**Build:**
- No build configuration files present.
- `.gitignore` excludes `.vs` and `dist`.

## Platform Requirements

**Development:**
- Streamer.bot installed on Windows (the code opens the system browser via `ProcessStartInfo { UseShellExecute = true }` in `integration.cs`)
- A DonationAlerts OAuth client registered at https://www.donationalerts.com/application/clients

**Production:**
- Runs inside a Streamer.bot action on the streamer's machine; no server deployment
- Local port 8554 must be free for the OAuth callback listener (default redirect URL)

---

*Stack analysis: 2026-10-17*
