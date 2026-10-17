---
last_mapped_commit: 2047008445144024a44f608400bc03a71f717c2f
last_mapped_at: 2026-10-17
---
# External Integrations

**Analysis Date:** 2026-10-17

## APIs & External Services

**DonationAlerts (primary service):**
- Host: `https://www.donationalerts.com` (constant `Client.TargetHost` in `integration.cs`)
  - Authorize: `GET /oauth/authorize` (`EndpointAuthorize`) - opened in the system browser; params `client_id`, `redirect_uri`, `scope`, `response_type=code`
  - Token: `POST /oauth/token` (`EndpointToken`) - form-urlencoded; used for authorization_code exchange and `refresh_token` grant
  - Profile: `GET /api/v1/user/oauth` (`EndpointProfileInfo`) - Bearer auth; returns user `Id` and `SocketConnectionToken`
  - Channel subscribe tokens: `POST /api/v1/centrifuge/subscribe` (`EndpointSubscribe`) - Bearer auth; returns channel names and per-channel tokens
  - SDK/Client: custom `Client` class wrapping `HttpWebRequest` in `integration.cs` (~line 1459)
  - Auth: `daClientId` / `daClientSecret` global variables; user access and refresh tokens stored in `daAccessToken` / `daRefreshToken`

**DonationAlerts Centrifugo real-time feed:**
- WebSocket: `wss://centrifugo.donationalerts.com/connection/websocket` (`SocketHost` in `SocketService`, `integration.cs` ~line 568)
  - SDK/Client: `System.Net.WebSockets.ClientWebSocket`; Centrifugo JSON protocol (connect, subscribe requests/responses)
  - Auth: connection token from profile endpoint (`daSocketToken`); channel tokens from subscribe endpoint
  - Subscribed events: donations and goal progress (`DonationResponse`, `GoalProgressResponse` message types in `integration.cs`)

**DonationAlerts media (audio alerts):**
- Donation audio URLs are passed through from donation payloads and downloaded to a temp file via `WebClient.DownloadFile` (`SaveFileToTemp`, `integration.cs` ~line 529), with `User-Agent` set to `daUserAgent`. Only active when `DownloadAudio` setting is enabled.

**GitHub REST API (update check):**
- Endpoint: `GET https://api.github.com/repos/{owner}/{repo}/releases?per_page=100` in `updateChecker.cs` (`GetGitHubReleaseVersionsAsync`)
  - SDK/Client: `System.Net.WebClient`, `User-Agent: StreamerBot-DonationAlerts`
  - Auth: none (public, unauthenticated)
  - Repository slug from global `daUpdateRepo`; empty slug disables the check
  - Ignores draft and pre-release entries; compares `TagName` against `CurrentVersion` (`2.0.0`)

**Google Fonts (browser-side only):**
- `https://fonts.googleapis.com` and `https://fonts.gstatic.com` loaded by `successPage.html` and the HTML templates in `integration.cs` (~lines 1272 and 1384)

**Discord (CI only):**
- `Ilshidur/action-discord@master` GitHub Action in `.github/workflows/release-announce.yml` posts release announcements
  - Auth: `secrets.DISCORD_WEBHOOK` (GitHub repository secret)

## Data Storage

**Databases:**
- None. No database client or ORM is used.

**File Storage:**
- Local temp directory only, for downloaded donation audio files (`SaveFileToTemp` in `integration.cs`)

**Caching:**
- None. Token state is kept in Streamer.bot global variables (`CPH.SetGlobalVar(..., true)`), which are persisted by Streamer.bot.

## Authentication & Identity

**Auth Provider:**
- DonationAlerts OAuth 2.0 (authorization code flow with refresh tokens)
  - Implementation: user opens the authorize URL in the browser (`CreateAuthLink`, `OpenUrl`); a local `HttpListener` on `daRedirectUrl` (default `http://127.0.0.1:8554/donationalerts/callback/`) receives `code` (`Service.ServeAndListenAuth`, timeout `daAuthTimeoutSeconds`); code is exchanged for tokens (`ObtainAccessToken`); `RefreshAccessToken` uses the stored refresh token; access token expiry is tracked in `daAccessTokenExpiresAt`.
  - Scopes (default): `oauth-user-show`, `oauth-donation-subscribe`, `oauth-goal-subscribe`
  - Note: `daClientSecret` is stored as a Streamer.bot global variable in plain configuration; the code does not encrypt it.

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry or similar)

**Logs:**
- Streamer.bot logging via `CPH.LogDebug` / `CPH.LogWarn`, wrapped by `CPHInline.PrefixedLogger` (`integration.cs` ~line 36)

## CI/CD & Deployment

**Hosting:**
- Not applicable. Code is distributed as a Streamer.bot action and installed manually.

**CI Pipeline:**
- GitHub Actions: `.github/workflows/release-announce.yml`, triggered on `release` created events. Runs on `ubuntu-latest`, fetches the release body via the GitHub API with `curl`, and posts to Discord.

## Environment Configuration

**Required env vars:**
- None. Configuration is via Streamer.bot global variables.

**Required Streamer.bot globals:**
- `daClientId`, `daClientSecret` (required)
- `daRedirectUrl`, `daScopes`, `daAuthTimeoutSeconds`, `daReconnectDelaySeconds`, `daUserAgent`, `daUpdateRepo` (optional)

**Secrets location:**
- Streamer.bot global variables (client secret, tokens). A `.env` file is not present.
- CI secret: `DISCORD_WEBHOOK` in GitHub repository secrets.

## Webhooks & Callbacks

**Incoming:**
- Local OAuth redirect callback: `GET {daRedirectUrl}` served by `HttpListener` in `integration.cs` (`ServeAndListenAuth`), reads `code` from the query string and returns `successPage.html`-style HTML.
- None exposed to the public internet.

**Outgoing:**
- Centrifugo WebSocket subscription (persistent, not a webhook)
- Discord webhook from GitHub Actions on release creation (`.github/workflows/release-announce.yml`)
- Streamer.bot chat message via `CPH.SendMessage` when an update is available (`updateChecker.cs`)

---

*Integration audit: 2026-10-17*
