# Stack Research

**Domain:** Streamer.bot 1.0.x inline-C# integration (OAuth + REST + Centrifugo realtime), shipped as one importable `.sb`
**Researched:** 2026-10-17
**Overall confidence:** MEDIUM-HIGH (runtime, `.sb` envelope and DonationAlerts REST/OAuth are well sourced; four items are explicitly UNVERIFIED and need a one-time live check, listed in "Open Verification Items")

Confidence legend used below:
- **HIGH** = official docs/changelog (Streamerbot/docs GitHub repo, donationalerts.com/apidoc) or a real `.sb` decoded locally.
- **MEDIUM** = a working third-party implementation or multi-source inference.
- **LOW** = inference only; do not build on it without the live check.

Note on method: the `docs.streamer.bot` website renders several C# pages as stubs ("missing documentation"). The real content lives in the public repo `github.com/Streamerbot/docs` (`streamerbot/3.api/3.csharp/...`), which was read directly. Real `.sb` samples (from the same repo's `4.examples/.imports/` and embedded import strings, exported by SB 1.0.4) were base64/gzip-decoded locally to read the schema.

---

## 1. Execution Environment (what the rewrite is compiled and run by)

| Fact | Value | Confidence | Source |
|------|-------|------------|--------|
| Runtime | .NET Framework **4.8.1** (CLR 4.0.30319). "Streamer.bot has been updated to .NET 4.8.1" in v1.0.0 | HIGH | docs repo `5.changelogs/.archive/v1.0.0.md`; VS Code recipe csproj uses `net481` |
| Compiler | Roslyn, bundled with Streamer.bot (Windows Defender false-positive note in v0.0.62 changelog). **Language version is NOT documented anywhere official** | HIGH that Roslyn is used / **UNVERIFIED** for the exact C# version | changelog `Version-0062.md` |
| Safe language subset to target | **C# 7.3** syntax; no runtime types missing from net48 (no `Span`, `Index/Range`, `ValueTuple`, `HashCode`) | MEDIUM (conservative choice; official examples already use `out string x`, `$""`, index initializers) | docs examples |
| Isolation | Each Execute C# Code sub-action is compiled into its own isolated `AppDomain` sandbox; exceptions in normal/Task code are caught and logged, **unhandled exceptions on raw background threads can crash the host** | HIGH | docs `4.threading-best-practices.md`; changelog 1.0.5/1.0.7 ("handle their own exceptions and do not bring down Streamer.bot", "crashes related to Execute C# Code and its AppDomain being unloaded") |
| Consequence of isolation | You cannot pass your own object types across the boundary (e.g. into `TriggerCodeEvent` dictionaries, no `JObject/JArray`). Use primitives or the **JSON overload** | HIGH | changelog v0.2.5 ("because of the way the C# code is handled and kept separate...") |
| Minimum Streamer.bot version to state in README | **1.0.7 (Stable, Aug 6 2026)**. It contains the C# exception-isolation + AppDomain-unload crash fixes + shutdown cleanup. 1.1.0-alpha.1 exists (Oct 9 2026) but is alpha; do not target it | MEDIUM (recommendation; the user's installed version is unknown - ask) | streamer.bot/changelogs |

### Class shape and lifecycle (all HIGH, docs `0.intro.md`, `2.lifecycle-methods.md`, `3.custom-methods.md`)

- The class **must** be named `CPHInline` and have `public bool Execute()`. SB makes it inherit `CPHInlineBase` (provides `CPH` and `args`). Extra top-level classes in the same source are compiled together (MEDIUM; the old fork already relied on it).
- `public void Init()`: "executed when your code is first compiled, **including during Streamer.bot startup**".
- `public void Dispose()`: "**always executed on destroy, including during Streamer.bot shutdown**". Both optional.
- "Precompile on Application Start" (sub-action toggle, default **false**): compile at startup instead of on first hit. Without it **`Init()` does not run at startup**, so custom triggers are not registered and the integration cannot auto-start. **Set `precompile: true`.** (`Delayed Start` is only for UI code; leave false.)
- v0.2.4 changelog: "Only `Init()` Execute C# Code that is in an **enabled action and sub-action** on startup". The core action must stay enabled.
- Public parameterless `bool` methods are callable from other actions via the **Execute C# Method** sub-action (type 99998) or `CPH.ExecuteMethod("<name>", "<Method>")`. The code sub-action needs a non-empty **Name** to be discoverable. A single compiled instance holds shared state (statics / fields) across calls. (Which "name" `ExecuteMethod` wants - action name or code-sub-action Name - is ambiguous in the docs; see Open Items.)
- `Execute()` returning `false` stops the remaining sub-actions of that action.
- Per-run `args` are isolated per action run (1.1.0 alpha; assume the same intent in 1.0.x). **Do not touch `args` directly**; use `CPH.TryGetArg<T>()` (docs: direct access "can result in a crashed code instance").

### Threading rules from the vendor (HIGH, `4.threading-best-practices.md`)

1. Never `async void`; always `async Task` so SB can log the failure.
2. Prefer `Task.Run`/`Task.Factory.StartNew` over `new Thread()` (raw threads run "outside the CPH execution frame" and unhandled exceptions there can crash SB).
3. Wrap everything in `try/catch`; own every background exception.

### Why `Streamer.bot.exe` likely lingers (project's reported symptom) - HYPOTHESIS, MEDIUM-LOW

Not documented by the vendor. Best-evidence mechanism: the old fork's `Start` runs a *synchronous* loop inside `Execute()` (`ConnectLoop` with `Thread.Sleep`, `ReceiveAsync(CancellationToken.None).GetAwaiter().GetResult()`, `HttpListener` waits). The action never returns, and on shutdown SB must unload the AppDomain while a thread is parked in a native wait; .NET Framework cannot abort threads blocked in native code, so unload/exit stalls. The design that removes the cause regardless of which factor is true:
- `Execute()`/`Start()` returns immediately; all I/O runs as cancellable `async Task` on the thread pool (background threads - they cannot keep the process alive).
- One `CancellationTokenSource` per session; every await gets the token; `ClientWebSocket.Abort()` and `HttpListener.Abort()` are called from `Dispose()` (they unblock pending receive/GetContext immediately, unlike `CloseAsync`).
- `Dispose()` cancels, aborts, disposes, then waits for the worker task with a **bounded** wait (<= ~2-3 s), never `Wait()` unbounded.
- Belt-and-braces: also bind an action to the **Streamer.bot Exiting** trigger (type 707) that calls the Stop method.

---

## 2. Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| C# inline code (`CPHInline`) in one Execute C# Code sub-action | language target **7.3**, .NET Framework 4.8.1 | Entire integration (OAuth, REST, WS, dedupe, lifecycle, update check) | Only supported extension mechanism; one sub-action = one compiled instance = shared state | HIGH |
| `System.Net.Http.HttpClient` (single `static readonly`, `Timeout` set) | in-box (net48 `System.Net.Http.dll`) | OAuth token endpoint, `/user/oauth`, `/centrifuge/subscribe`, GitHub releases, audio download | Vendor's own example (`4.examples/http-post.md`) uses exactly this and says creating one per call is "heavily discouraged". Replaces `HttpWebRequest`/`WebClient` (no timeout/cancel, `WebException.Response` null bugs, synchronous) | HIGH |
| `System.Net.WebSockets.ClientWebSocket` | in-box (`System.dll`) | Centrifugo connection | Works on Win 8+/10/11 .NET Framework; supports `Abort()`; the old fork already used it. Needs continuous `ReceiveAsync` with a token | HIGH |
| `System.Net.HttpListener` on `http://127.0.0.1:<port>/...` | in-box (`System.dll`) | OAuth redirect catch | Loopback prefix needs no admin/URL-ACL in the usual case (old fork default `http://127.0.0.1:8554/donationalerts/callback/`); `GetContextAsync()` is not cancellable -> must call `Abort()` on cancel/timeout/Dispose. Open the browser with `Process.Start(new ProcessStartInfo(url){UseShellExecute=true})` | MEDIUM |
| `Newtonsoft.Json` | the copy SB ships (reference `.\Newtonsoft.Json.dll`); compile tests against **13.0.3** (13.0.4 is latest stable) | All JSON in/out | Vendor: "`Newtonsoft.Json`, which is included in Streamer.bot by default". Use `JObject`/`JsonConvert` *inside* the sub-action only | HIGH |
| `CancellationTokenSource` + `Task.Run` + `SemaphoreSlim` | BCL | Lifecycle: single-flight start/stop, session cancel, token-refresh lock | Matches vendor threading guidance; makes Start/Stop idempotent | HIGH |

### Streamer.bot API surface to use (all signatures from `docs repo 3.methods/core`, HIGH unless noted)

| Need | Call | Notes |
|------|------|-------|
| Read/write settings & tokens | `T CPH.GetGlobalVar<T>(string name, bool persisted = true)`, `CPH.SetGlobalVar(string name, object value, bool persisted = true)`, `CPH.UnsetGlobalVar(name, persisted)` | Returns `null` if missing. Settings + tokens as persisted globals. Create missing settings with empty defaults in `Init()` so they show in the Variables viewer |
| Expose per-event data to handler actions | `CPH.SetArgument(string, object)` then fire trigger | Arguments set before the trigger fires are what `TriggerCodeEvent(eventName, useArgs: true)` forwards |
| Register custom triggers | `bool CPH.RegisterCustomTrigger(string triggerName, string eventName, string[] categories)` (v0.2.0) | Call in `Init()`; needs precompile. Appears under Triggers > Custom > `categories`. Make `eventName` unique (e.g. `daDonation`, `daGoal`) |
| Fire them | `void CPH.TriggerCodeEvent(string eventName, bool useArgs = true)`; overloads `(string, Dictionary<string,object>)` and `(string, string json)` (v0.2.5) | **Prefer the JSON-string overload** (vendor-stated reason: no custom types across the AppDomain boundary). How SB types JSON numbers into `%args%` is UNVERIFIED - see Open Items |
| Logging | `CPH.LogInfo / LogDebug / LogWarn / LogError / LogVerbose` | Listed in the Core>Logging index (page bodies are stubs). Prefix lines; never log tokens/secret/PII |
| Run user handler by name | `CPH.RunAction(string name, bool runImmediately = true)`, `CPH.ActionExists(name)` | `runImmediately=false` queues it in its own queue without waiting. Not needed if custom triggers are used |
| Read args | `bool CPH.TryGetArg<T>(string name, out T value)` (v0.2.3) | |
| Cross-action method call | `CPH.ExecuteMethod(name, method)`; sub-action `Execute C# Method` (type 99998) | Methods must be `public bool M()` with no parameters |
| Chat | `CPH.SendMessage(string, bool useBot=true, bool fallback=true)` is **Twitch-only** (YouTube/Kick have separate methods) | **Do not send chat from the integration.** Provide arguments/triggers; the streamer's handler uses platform-agnostic sub-actions. Update notice -> log + a global var, not chat spam |
| Version | `CPH.GetVersion()` (misc/get-version) | Can be logged on start |

### Supporting Libraries / BCL pieces

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `System.Security.Cryptography.RandomNumberGenerator` (mscorlib) | in-box | Random OAuth `state` (>=128 bit, hex/base64url) | Always; compare with ordinal constant-time-ish equality and single use |
| `System.Globalization.CultureInfo.InvariantCulture` | in-box | Parse `amount` (JSON number *or* string; third-party client handles both), `created_at`, build query strings | Always. SB sets culture from system culture on threads (1.0.5) - never rely on current culture |
| `Uri.EscapeDataString` + hand-rolled query parse | in-box | URL building / callback parsing | **Instead of `System.Web.HttpUtility`** (avoids the extra `System.Web.dll` reference the old fork needed) |
| `System.Collections.Concurrent.ConcurrentDictionary` / small LRU | in-box | Donation-id dedupe set (suggest ~500-1000 ids) | In-memory dedupe across reconnects; optionally persist last-seen id in a global |
| `System.IO.Path.GetTempPath()` + own subfolder | in-box | Audio download cache | Optional audio; stream with `ResponseHeadersRead`, enforce size cap + https + host allow-list, delete on Dispose and at start |

### Required `references` for the code sub-action (what goes in the `.sb`)

Format seen in real exports (HIGH): absolute framework paths and `.\` paths relative to the Streamer.bot folder.

```
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\mscorlib.dll
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\System.dll          (HttpListener, ClientWebSocket, Uri)
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\System.Core.dll     (LINQ - docs note it must be added explicitly)
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\System.Net.Http.dll (HttpClient)
.\Newtonsoft.Json.dll
```
Do **not** add `System.Web.dll`. The `C:\Windows` prefix is hard-coded in exports (non-C: Windows installs are a risk; the import checklist must say "press Compile; if refs fail press Find Refs").

---

## 3. The `.sb` Export Format (Streamer.bot 1.0.x) - decoded from real exports

**Envelope (HIGH; decoded locally from 3 official sample exports + independent confirmation in `PedroZamecki/streamerz`):**

```
file/text = base64( "SBAE"  +  gzip( UTF-8 JSON ) )
```
- No BOM. JSON is Newtonsoft-style (2-space indent, `\r\n`), but any valid JSON should parse (MEDIUM; mimic Newtonsoft anyway).
- .NET gzip header observed: `1f 8b 08 00 00000000 04 00` (mtime 0, XFL 4, OS 0). Generate with `zlib.compressobj(1, wbits=-15)` plus handwritten header/CRC32/ISIZE for deterministic, SB-identical bytes.
- A `.sb` file is just this base64 string (drag-drop onto the Import String box, or paste). The docs call it a "UUEncoded string" but it is plain base64 starting `U0JBR...`.
- Importing **overwrites existing items with the same name** by default (docs `09.import-export.md`) -> keep action names stable, and ids deterministic (uuid5) so re-import updates rather than duplicates.
- Import shows a warning to the user when the import contains an Execute C# Code sub-action (v1.0.0). README must mention it.

**Top level (HIGH, all 3 samples identical shape):**
```json
{
  "meta": { "name": "...", "author": "...", "version": "1.0.0", "description": "...",
            "autoRunAction": null, "minimumVersion": null },
  "data": { "actions": [...], "queues": [], "commands": [], "websocketServers": [],
            "websocketClients": [], "timers": [] },
  "version": 23,
  "exportedFrom": "1.0.4",
  "minimumVersion": "1.0.0-alpha.1"
}
```
- **Global variables are NOT part of an export** (only actions, queues, commands, WS servers/clients, timed actions). Secrets never travel in a `.sb`, but defaults cannot be shipped either. Create missing globals from `Init()` (or an auto-run "Setup" action).
- `meta.autoRunAction`: action to offer running after import (v0.2.3: user is prompted, runs only if they agree). Usable for first-run setup/readme log. Value format not seen populated - UNVERIFIED.
- Export `version` is 23 in SB 1.0.4 exports; SB's own `actions.json` is reported as v24 by a third party. Emit 23 (older export versions are accepted forward; only pre-0.2.0 exports are rejected as "too old").

**Action object (HIGH):** `id, queue (null | "000...0"), enabled, excludeFromHistory, excludeFromPending, name, group, alwaysRun, randomAction, concurrent, triggers[], subActions[]` (+ optional `collapsedGroups`).

**Execute C# Code sub-action, `type: 99999` (HIGH - seen verbatim):**
```json
{ "name": "DonationAlerts", "description": "...",
  "references": ["C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\mscorlib.dll", ".\\Newtonsoft.Json.dll"],
  "byteCode": "<base64 of the UTF-8 SOURCE TEXT, not compiled IL>",
  "precompile": false, "delayStart": false, "saveResultToVariable": false, "saveToVariable": "",
  "id": "<guid>", "weight": 0.0, "type": 99999, "parentId": null, "enabled": true, "index": 0 }
```
`byteCode` is plain base64 of the source (CRLF in samples, no BOM) - trivially generated from `integration.cs`.

**Execute C# Method, `type: 99998`:** fields `executeCodeId, method, runOnUiThread, saveResultToVariable, saveToVariable` (field names HIGH from third-party metadata extraction; `executeCodeId` presumably the code sub-action's `id` GUID - MEDIUM, verify).

**Other type codes (MEDIUM-HIGH; from `streamerz/src/types.rs`, extracted from Streamer.bot's own enums, cross-checked against the samples for 4/120/121/122/123/124/1009/1020):**
| Item | Code | JSON fields |
|------|------|-------------|
| Run Action | 4 | `actionId`, `runImmedately` (sic) |
| Global (Set) | 122 | `destination:0, variableName, persisted, source (0=variable,1=literal), value, autoType` |
| Global (Get) | 121 | `source, variableName, persisted, destinationVariable, defaultValue` |
| Set Argument | 123 | `variableName, value, autoType` |
| Log | 1020 | `logLevel, message` |
| Comment | 1009 | `value, color` |
| Trigger: Streamer.bot Started | 706 | |
| Trigger: Streamer.bot Exiting | 707 | |
| Trigger: Custom Event (UI) | 18001 | |
| **Trigger: Custom Code Event** | **18002** | extra field name for the event name **UNVERIFIED** |
| Trigger: Test | 702 | seen in sample with `variables` map |
Trigger object skeleton (HIGH): `{ "id", "type", "enabled": true, "exclusions": [] }` + type-specific fields (`commandId` for 401, `variables` for 702).

**How to generate it programmatically:** no official tool/SDK exists (a community "transparent JSON import" request is open: ideas.streamer.bot/posts/1469). Only independent reference: `PedroZamecki/streamerz` (Rust; `model.rs` `pack()/unpack()`, MIT-less/unknown license - read for understanding, do not copy). **Recommendation: a ~80-line stdlib-only Python 3 script** (`tools/build_sb.py`) that (1) reads `src/DonationAlerts.cs`, (2) builds the JSON with deterministic `uuid5` ids, (3) base64's the source into `byteCode`, (4) writes `dist/DonationAlerts.sb`; plus a `--check` mode that decodes any `.sb`, validates required keys/types, and round-trips `byteCode` back to the source. Run with `python -I`.

**Golden-file strategy (the single most valuable verification, 5 minutes of user time):** have the user build a throwaway skeleton in real SB 1.0.x (one action with Execute C# Code [named, precompile on], one with Execute C# Method pointing at it, a Custom Code Event trigger, a Streamer.bot Started trigger), Export, and commit the resulting `.sb` under `tools/golden/`. It contains no secrets (variables aren't exported). The generator's schema test then diffs against reality instead of against this document.

---

## 4. DonationAlerts: OAuth, REST, Centrifugo (official doc `https://www.donationalerts.com/apidoc`, read in full)

### OAuth 2.0 (HIGH)
| Item | Value |
|------|-------|
| Authorize | `GET https://www.donationalerts.com/oauth/authorize` params `client_id`(int) `redirect_uri` `response_type=code` `scope` (space-delimited) |
| Token | `POST https://www.donationalerts.com/oauth/token`, `application/x-www-form-urlencoded`; `grant_type=authorization_code` + `client_id client_secret redirect_uri code` |
| Refresh | same URL; `grant_type=refresh_token refresh_token client_id client_secret scope` (scope is listed as **required**) |
| Response | `token_type`, `access_token`, `expires_in` (seconds), `refresh_token`. Doc: refresh response "may" omit a new refresh token - then the old stays valid |
| Scopes | `oauth-user-show`, `oauth-donation-subscribe`, `oauth-donation-index` (REST list - enables catch-up), `oauth-custom_alert-store`, `oauth-goal-subscribe`, `oauth-poll-subscribe`. Doc says "3 scopes" but lists 6 |
| REST limits | **60 requests/min per application**. 401 body: `{"message":"Unauthenticated."}`; pagination via `data/links/meta` |
| `state` | **Not mentioned in the doc.** The platform looks like Laravel Passport (response shape `{"message":"Unauthenticated."}`, `oauth/authorize`), which echoes `state`. Send a random `state` and require it back; if the live check shows it is not echoed, fail with a clear message (don't silently skip CSRF). MEDIUM-LOW |
| Token lifetime | Doc example shows `expires_in: 631151999` (~20 years) - an example, not a guarantee. Treat as variable: store `expires_at`, refresh when < 60 s remain **and** on any 401 |
| Refresh-token rotation | Passport rotates refresh tokens (inference). **Persist the new refresh token synchronously before doing anything else, and serialize refreshes behind one `SemaphoreSlim`** (a parallel refresh with the old token can invalidate the pair). MEDIUM-LOW |

### REST endpoints used
- `GET /api/v1/user/oauth` (scope `oauth-user-show`): `data.{id, code, name, avatar, email, socket_connection_token}`. `id` is the stable user id (used in channel names). Never log `email`.
- `POST /api/v1/centrifuge/subscribe` body (JSON): `{"channels":["$alerts:donation_<id>","$goals:goal_<id>"],"client":"<uuid from WS connect>"}` -> `{"channels":[{"channel":"...","token":"..."}]}`; one call can fetch several channel tokens.
- `GET /api/v1/alerts/donations` (scope `oauth-donation-index`): paged list with the *documented* donation fields; use only for optional catch-up after a reconnect (budget: <= a few calls, within 1 req/s).

### Centrifugo realtime (HIGH for flow, MEDIUM for frames beyond the doc)
- URL `wss://centrifugo.donationalerts.com/connection/websocket`. **Server is Centrifugo v2.2.1** (the doc's connect reply shows `"version": "2.2.1"`) -> the legacy **v2 JSON protocol**, *not* the v3+/v5 `{"connect":{...}}` envelope. Do not follow modern Centrifugo docs/SDKs.
- Connect: `{"id":1,"params":{"token":"<socket_connection_token>"}}` (method omitted = 0) -> `{"id":1,"result":{"client":"<uuid>","version":"2.2.1", "expires":true,"ttl":N}}` (`expires/ttl` are present in practice, absent from the doc example).
- Subscribe: `{"id":2,"method":1,"params":{"channel":"$alerts:donation_<id>","token":"<channel token>"}}` -> `{"id":2,"result":{"expires":..,"ttl":..,"recoverable":..,"epoch":..,"seq":..,"gen":..,"publications":[..]}}`. **A subscribe is only verified by this reply** (doc shows `result.type=1/channel`); an `error` object means failure.
- Method ids (HIGH, standard Centrifugo v2 + matched by a working implementation): `0 connect, 1 subscribe, 7 ping, 10 refresh, 11 sub_refresh`. Push types in `result.type`: absent/`0` publication, `1 join, 2 leave, 3 unsubscribe, 4 message, 5 subscribe, 6 connect, 7 disconnect, 8 refresh`.
- **Token TTL (important, MEDIUM):** the one open-source Centrifugo-v2.2.1 DonationAlerts client found (`coldbrew-app/coldbrew`, PR #97, `internal/donationalerts/socket_session.go`) attributes "roughly ten-minute disconnects" to JWT expiry and implements: read `expires/ttl` from connect/subscribe replies, then before expiry fetch a fresh `socket_connection_token` (`GET /user/oauth`) and send `{"method":10,"params":{"token":..}}`, and fetch a fresh channel token (`POST /centrifuge/subscribe` with the current client id) and send `{"method":11,"params":{"channel":..,"token":..}}`. The old fork does neither -> silent death after ~10 min is the most probable cause of "no donations after a while". **Simplest correct strategy for v1: honour `ttl` and refresh; if refresh fails or `ttl` is missing, tear down and reconnect cleanly.**
- **Heartbeat (MEDIUM):** send app-level ping `{"id":N,"method":7}` every ~25 s, expect a correlated reply within ~5 s, else reconnect; empty `{}` frames and blank lines are no-ops. Keep a receive loop always pending so native WS ping/pong is answered.
- **Framing (MEDIUM):** a single WS text frame may carry **several newline-separated JSON messages** (v2 batching). Split on `\n` before parsing. Accumulate fragments until `EndOfMessage`; cap at ~1 MB.
- **Reconnect (MEDIUM):** backoff 5 s -> doubling -> 60 s cap, reset to 5 s after a *verified* subscribe; on each (re)connect fetch a fresh `socket_connection_token` (and refresh the OAuth token first if expired / on 401). Stop retrying on definitive auth failure (refresh returns 4xx) and surface "re-authorize".
- Server `disconnect`/`unsubscribe` pushes carry `{"reason","reconnect":bool}` -> honour `reconnect:false`.

### Channels and payloads
| Channel | Scope | Payload fields |
|---------|-------|----------------|
| `$alerts:donation_<user_id>` | `oauth-donation-subscribe` | Documented: `id, name("donation"), username, message_type("text"/"audio"), message, amount, currency(ISO 4217), is_shown(0/1), created_at("YYYY-MM-DD HH:MM:SS", timezone unspecified), shown_at(null)` |
| `$goals:goal_<user_id>` | `oauth-goal-subscribe` | Documented: `id, is_active, title, currency, start_amount, raised_amount (includes start_amount), goal_amount, started_at, expires_at(null)` |
| `$polls:poll_<user_id>` | `oauth-poll-subscribe` | out of scope for v1 |

Publication nesting (MEDIUM, from the old fork + the working Go client): `{"result":{"channel":"...","data":{"seq":N,"gen":G,"data":{<resource>}, "reason":"..."?}}}`. The doc says each message "carries the `reason` attribute in addition to the original resource" but not where; read `reason` from both `result.data.reason` and `result.data.data.reason`, treat as optional.

**Corrections to the old fork's assumptions:**
- Goal progress fields are `raised_amount`/`goal_amount`/`start_amount` (the old `daGoalCurrent/Target` names are invented labels; map from the real fields). `is_default` is not in the official doc (observed by the old fork) -> optional.
- **`amount_in_user_currency` is NOT in the official doc or the official-ish TypeScript SDK (`StimulCross/donation-alerts`).** It is observed in real payloads by third parties (`kash-ts/alerts-SDK` types it optional; `Pointauc` consumes it). MEDIUM: parse optionally; when absent, the main-currency argument is empty - never fabricate a conversion.
- `username` and `message` can be null/empty; `amount` may arrive as number or string; `id` is an integer (dedupe key). `message_type=="audio"` means `message` is an audio URL (only then run the download path).
- Dedupe key: `id` (+ channel). Same donation may be delivered again after reconnect/recovery.

---

## 5. Offline Validation Tooling (repo-only, nothing shipped)

**Smoke-tested on this machine (2026-10-17, Windows 11, .NET SDK 9.0.304):** a net48 xUnit project compiled the pattern below and `dotnet test` passed 2/2.

| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| .NET SDK (build host only) | 9.0.x (installed: 9.0.304) | Compile + test | Roslyn in the SDK is far newer than SB's; hence pin the language version below |
| `Microsoft.NETFramework.ReferenceAssemblies.net48` | 1.0.3 (`PrivateAssets=all`) | net48 reference assemblies without installing a Developer Pack (only the v4.7.1 pack is installed here) | Gives the BCL surface SB really has, so net48-missing APIs fail to compile |
| `<LangVersion>7.3</LangVersion>` | - | Conservative compile gate | Replace after the live `#error version` check reveals SB's real level |
| `Newtonsoft.Json` | 13.0.3 | Reference for tests | |
| xUnit | `xunit` 2.9.3 + `xunit.runner.visualstudio` 3.1.5 + `Microsoft.NET.Test.Sdk` 17.14.1 | Unit tests on net48 (same CLR family as SB) | Exact trio verified to restore and run here; newer `Test.Sdk` 18.x and `runner.visualstudio` 4.x exist but were not tried |
| Python 3 stdlib (`python -I`) | 3.13 installed | `.sb` builder/validator (section 3) | No pip deps |

**Real Streamer.bot DLLs are not on NuGet** (search for `Streamer.bot.Plugin.*` finds nothing official; a lone `StreamerBotDummy` package is an unvetted community stub - do not depend on it). The vendor's own approach (`api/csharp/recipes/visual-studio-code`) references `Streamer.bot.Plugin.Interface.dll`, `Streamer.bot.Common.dll`, `Twitch.Common.dll` from the installed SB folder with `<DefineConstants>EXTERNAL_EDITOR</DefineConstants>`. Recommendation: **ship a hand-written stub** (`tests/Stub/CPHInlineBase.cs`: an `IInlineInvokeProxy`-shaped fake with only the ~12 CPH methods actually used, recording calls) as the committed default, and document an *optional, uncommitted* second csproj that points `StreamerBotPath` at a real SB install for exact-signature checking.

Official class-shape trick so the same file compiles in SB and in tests (vendor-documented):
```csharp
#if EXTERNAL_EDITOR
public class CPHInline : CPHInlineBase
#else
public class CPHInline
#endif
{ ... }
```
Test csproj sketch:
```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net48</TargetFramework><LangVersion>7.3</LangVersion>
    <DefineConstants>EXTERNAL_EDITOR</DefineConstants><IsPackable>false</IsPackable>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="..\src\DonationAlerts.cs" />
    <PackageReference Include="Microsoft.NETFramework.ReferenceAssemblies.net48" Version="1.0.3" PrivateAssets="all" />
    <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.14.1" />
    <PackageReference Include="xunit" Version="2.9.3" />
    <PackageReference Include="xunit.runner.visualstudio" Version="3.1.5" />
  </ItemGroup>
</Project>
```
**Design rule that makes this testable:** keep the logic classes (frame splitter, Centrifugo message parser, donation/goal mapper, dedupe window, backoff schedule, reconnect/lifecycle state machine, OAuth state check, argument builder) free of `CPH` and sockets - inject `ITransport`, `IClock`, `ILogger`. Test those with plain xUnit; test lifecycle (start/stop/start idempotent, Dispose cancels within N ms, no leftover tasks) with a fake transport that blocks until cancelled. Anything touching real DonationAlerts or real SB stays on the manual checklist and must be reported as **not tested live**.

Compile-check also has to be run in SB itself (Compile button + the `#error version` probe) because net48 reference assemblies cannot prove SB's reference resolution.

---

## 6. Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| One Execute C# Code sub-action (single source file) | Several code sub-actions / external DLL ("Custom DLLs" recipe is a stub) | Never for v1: violates "one `.sb`, no extra files" and splits state across AppDomains |
| `HttpClient` (static) | `HttpWebRequest`/`WebClient` | Never; no timeout/cancel semantics, `WebException.Response` can be null (the old fork's null-ref bug) |
| `HttpListener` loopback callback | `TcpListener` + minimal HTTP parse | If `HttpListener` throws access-denied on a user's machine (URL ACL). Adds ~40 lines but no http.sys |
| Custom Code Event triggers (`RegisterCustomTrigger`/`TriggerCodeEvent`) | `CPH.RunAction("DonationHandler_<amount>")` naming convention (old contract) | If the live check shows custom triggers cannot be imported pre-bound; keep a documented `RunAction` fallback hook only if needed (user said no legacy compat) |
| JSON-string `TriggerCodeEvent` overload | Dictionary overload | If the live check shows numbers/bools arrive mistyped via JSON; then pass the dictionary with only primitives |
| Proactive `refresh`/`sub_refresh` per `ttl` (+ reconnect fallback) | Reconnect on every disconnect only | Acceptable as a v1 fallback; costs a brief gap, so pair with `oauth-donation-index` catch-up and id dedupe |
| Python stdlib `.sb` builder | PowerShell / small .NET tool | If the user will not have Python; but Python is installed here and gives byte-level control |
| xUnit on net48 | Plain console test exe | If xUnit packaging fights the machine; console asserts are the zero-dependency fallback |

## 7. What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `HttpWebRequest`, `WebClient`, `WebRequest.Create` (old fork: `Client`, `SaveFileToTemp`, `updateChecker.cs`) | Legacy; synchronous; no cancellation; `e.Response` null -> NRE in the old `WebError`; no per-request timeout | one `static HttpClient` with `Timeout` + `CancellationToken` |
| `Thread.Sleep`, `.GetAwaiter().GetResult()`, `.Wait()`, `.Result` (old fork: reconnect loop, every socket call, `listenTask...GetResult()`) | Blocks the action thread/AppDomain; prime suspect for the lingering process; deadlock-prone | `await Task.Delay(ms, token)`, `await` + token everywhere |
| `ReceiveAsync(CancellationToken.None)` / `CloseAsync` after `Abort()` | Cannot be cancelled; throws after abort and was swallowed | pass the session token; `Abort()` to unblock; `CloseAsync` with a short timeout token only for graceful stop |
| `new Thread(...)`, `async void`, `System.Timers.Timer` callbacks that throw | Vendor warns: unhandled exceptions escape the sandbox and can crash SB | `Task.Run` + `try/catch`, `async Task`, `Task.Delay` loops |
| `System.Web.HttpUtility` | Needs extra `System.Web` reference; the old fork carried it | `Uri.EscapeDataString` + manual parse |
| Modern Centrifugo SDKs/docs (`centrifuge-csharp`, v5 protocol, `{"connect":..}` envelopes) | DonationAlerts runs Centrifugo **2.2.1**; wire format differs | Hand-rolled v2 JSON client (small) |
| Raw WS frames / tokens / `email` / donor names in logs (old fork logs `rawMessage`) | Secrets + PII | Log ids, event types, counts, error categories only |
| `MD5` goal "dedupe hash" (old `Helper.GetMD5Hash`) | Hashing serialized objects is fragile and pointless | Compare `(goal id, raised_amount, goal_amount, is_active)` tuple of last-seen state |
| Global `ServicePointManager` changes (TLS/connection limits) | Process-wide; could affect Streamer.bot's other services | Leave defaults (net48 + Win10/11 negotiates TLS 1.2) |
| Chat output via `CPH.SendMessage` inside the integration | Twitch-only | Emit arguments/triggers; user's action posts to any platform |
| Targeting SB 1.1.0-alpha features or 0.2.x | Alpha churn; project scope is 1.0.x | Pin README to 1.0.7+ |
| `StreamerBotDummy` NuGet stub / invented `.sb` fields | Unvetted; "no invented fields" constraint | Own minimal stub + golden export |

## 8. Installation / Repo Bootstrap

```bash
# one-time on the dev machine (already present here: dotnet 9.0.304, python 3.13)
dotnet new sln -n DonationAlerts          # optional
cd tests && dotnet test                    # restores net48 refs, xunit, Newtonsoft from NuGet
python -I tools/build_sb.py                # -> dist/DonationAlerts.sb
python -I tools/build_sb.py --check dist/DonationAlerts.sb
python -I tools/build_sb.py --check tools/golden/skeleton.sb   # compare against a real export
```
No runtime packages are installed into Streamer.bot; the shipped artifact is `dist/DonationAlerts.sb` only.

## 9. Old-fork API audit (what to replace)

| Found in `integration.cs` / `updateChecker.cs` | Problem | Replacement |
|-----------------------------------------------|---------|-------------|
| `HttpWebRequest` (l.1531), `WebClient` (l.537; `updateChecker.cs` l.84), `WebException.Response` cast (l.47, 635) | Legacy, sync, null-response crash | `HttpClient` + status-code handling |
| `Thread.Sleep` (l.658), `GetAwaiter().GetResult()` (l.617, 671, 690, 754, 782, 812, 1102) | Blocking sync-over-async inside the action thread | async/await with tokens |
| `Execute`-time infinite loop `DonationCheckerLoop` from `Start()` | Action never returns; no lifecycle | `Start()` kicks `Task.Run` and returns; state in fields |
| `Dispose()` = `SocketService.Close()` only (l.96-100) | Does not cancel HttpListener, timers, update check, audio downloads | One `Shutdown()` that cancels the root CTS and aborts every resource, bounded wait |
| `Init()` runs `TryRunUpdateChecker()` every time (l.94) | Network I/O at startup, unthrottled | Daily throttle (persisted `lastUpdateCheck`), `Task.Run`, fully non-blocking |
| `System.Timers.Timer` `forceCloseTimer` (l.1097), `System.Web.HttpUtility` (l.1079+) | Callback exceptions escape; extra reference | `CancellationTokenSource.CancelAfter`, `Uri.EscapeDataString` |
| `CPH.ExecuteMethod(actionName, "CheckAndAnnounce")` (l.396) | Cross-action coupling + `ActionExists` guard on a legacy name | Direct in-class call (single source) |
| `CPH.SendMessage` for status (l.136, 280, 410-444) | Twitch-only, noisy | `CPH.LogInfo/LogWarn` + a status global |
| Single message per frame assumption (`ReceiveMessage` -> one JSON) | Breaks on newline-batched Centrifugo frames | split on `\n` |
| No ping, no `refresh`/`sub_refresh`, no `expires/ttl` handling | Silent drop (~10 min JWT expiry) | Section 4 |
| Goal mapped as `Current/Target` | Not the official field names | `raised_amount/goal_amount/start_amount` |

## 10. Open Verification Items (must be closed by a short live check in real SB 1.0.7+)

1. **Exact C# language/Roslyn version** SB compiles with: put `#error version` in a code sub-action, press Compile, read "Compiler version / Language version". Until then stay on C# 7.3. (UNVERIFIED)
2. **JSON of a Custom Code Event trigger (type 18002)** - which property carries the event name; and that an imported action with such a trigger binds correctly when the code is precompiled. Close via the golden export. (UNVERIFIED)
3. **`Execute C# Method` (type 99998) linking**: is `executeCodeId` the code sub-action's `id`, does it still resolve after re-import with deterministic ids, and which "name" `CPH.ExecuteMethod` expects. (MEDIUM)
4. **`TriggerCodeEvent(eventName, json)` typing**: do JSON numbers/bools land in `%args%` as numbers/bools (needed for "react by amount" If/Else numeric compares)? (UNVERIFIED)
5. **`state` echo and refresh-token rotation** on DonationAlerts, real `expires_in`, and real `ttl` of the socket JWT; plus where `reason`/`seq` sit in the publication. Observe once with logging of *shapes only*. (MEDIUM-LOW)
6. **Does `Dispose()` run in time at app exit** and does the process actually exit (the project's headline acceptance test): start the integration, close SB, confirm in Task Manager. (HYPOTHESIS on root cause)
7. Whether the `C:\Windows\...` reference prefix in the `.sb` resolves on non-C: Windows installs. (LOW risk, easy to document)

## Sources

- Streamerbot/docs (official docs source, read directly via GitHub): `streamerbot/3.api/3.csharp/0.guide/{0.intro,1.variables,2.lifecycle-methods,3.custom-methods,4.threading-best-practices,5.debugging}.md`, `1.recipes/visual-studio-code.md`, `3.methods/core/{globals,actions,triggers,set-argument,try-get-arg,parse}`, `3.api/1.sub-actions/core/csharp/execute-csharp-code.md`, `3.api/2.triggers/custom/code-event.md`, `2.guide/01.core/09.import-export.md`, `4.examples/http-post.md`, `5.changelogs/.archive/{v0.2.0,v0.2.3,v0.2.4,v0.2.5,v1.0.0,Version-0043,Version-0061,Version-0062}.md` - HIGH
- Streamer.bot changelogs: https://streamer.bot/changelogs, /v1.0.5, /v1.0.7, /v1.1.0 - HIGH
- Real `.sb` exports (SB 1.0.4) decoded locally: `4.examples/.imports/{chatbot-commands,wsgs.utils.curl,wsgs.utils.json.parse}.sb` - HIGH
- https://www.donationalerts.com/apidoc (full page text extracted and read) - HIGH
- `PedroZamecki/streamerz` (`DEVELOPING.md`, `src/model.rs`, `src/types.rs`; type codes extracted from Streamer.bot metadata) - MEDIUM
- `coldbrew-app/coldbrew` PR #97 and `internal/donationalerts/{socket_session,source,client}.go` (working Centrifugo-v2.2.1 DonationAlerts client: methods, TTL refresh, ping, batching, backoff) - MEDIUM
- `StimulCross/donation-alerts` (`packages/events/src/events/{donations,goals}`) and `kash-ts/alerts-SDK` (`amount_in_user_currency` optional) - MEDIUM
- https://github.com/Sinistral2099/Streamer.bot-Class-Library (net472 + C# 8.0 in an external class library; not evidence about SB's in-app compiler) - LOW
- NuGet registry queries for package versions (Newtonsoft.Json 13.0.4, xunit 2.9.3, Microsoft.NETFramework.ReferenceAssemblies.net48 1.0.3, etc.); local `dotnet test` smoke run - HIGH
- Local code: `integration.cs`, `updateChecker.cs`, `.planning/PROJECT.md`, `.planning/codebase/{STACK,INTEGRATIONS}.md`

---
*Stack research for: Streamer.bot 1.0.x DonationAlerts integration (rewrite)*
*Researched: 2026-10-17*
