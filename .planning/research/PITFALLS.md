# Pitfalls Research

**Domain:** Streamer.bot 1.0.x inline-C# integration with DonationAlerts (OAuth 2.0 + legacy Centrifugo WebSocket), shipped as a single `.sb` import
**Researched:** 2026-10-17
**Overall confidence:** HIGH for Streamer.bot runtime/lifecycle and `.sb` format (observed directly on the user's Streamer.bot 1.0.7 install, its logs and real exports); MEDIUM for DonationAlerts protocol details (official docs are from ~2019 and thin; one live probe done); LOW for items explicitly marked `[HYPOTHESIS]`.

## How to read this file

Evidence tags used below:

- `[OBSERVED]` - seen directly: the user's Streamer.bot 1.0.7 logs (`<StreamerBot install dir>\logs`), its `data\actions.json`, a decoded real `.sb`, reflection on `Streamer.bot.Plugin.Interface.dll`, or a live probe of `wss://centrifugo.donationalerts.com`. Highest trust.
- `[DOCS]` - official Streamer.bot docs repo (cloned in the session scratchpad) or the official DonationAlerts apidoc.
- `[WEB]` - third-party article/forum, cross-checked only loosely. Treat as MEDIUM at best.
- `[HYPOTHESIS]` - inference that must be verified in a live test before the design relies on it. These are listed again in "Open questions to verify live" at the end.

Phase names below are **suggested labels by responsibility** (the roadmapper may merge or rename them, but the pitfall -> responsibility mapping should be kept):

| Label | Responsibility |
|-------|----------------|
| **A. Audit + Offline Harness** | audit of old code vs real runtime, net48 compile check, CPH stub, unit-test seams |
| **B. Lifecycle Core** | supervisor, Start/Stop/Dispose, cancellation, single-instance guarantees |
| **C. OAuth + Token Store** | authorize flow, callback listener, token refresh, secrets handling |
| **D. Realtime Client** | Centrifugo connect/subscribe/keep-alive/reconnect, dedupe, backfill |
| **E. Event Contract** | argument names/types, custom triggers, amount/currency, chat-safe text |
| **F. Optional Features** | goals, audio download, update checker |
| **G. `.sb` Packaging** | build/validate the import file |
| **H. Docs + Manual Checklist** | Russian README, live test checklist |

---

## Evidence from this machine (why the "known defects" list is not the whole story)

These are facts from the user's actual Streamer.bot 1.0.7 logs of the old fork. They drive the ranking below.

1. **The lingering `Streamer.bot.exe` is reproducible in the logs.** Clean shutdowns look like: `Closing services...` -> `InlineCode :: Cleaning up 'N' execute code instances` -> `InlineCode :: Cleaned up execute code instances` -> `Streamer.bot exited` (about 1-2 s total). Two different failure shapes were found:
   - **Shape 1 (2026-10-17 17:26:01 and 17:29:00):** log ends right after `Cleaning up '1' execute code instances` - no `Cleaned up`, no `exited`. At that moment the instance was busy inside `Connect` (HttpListener / browser loop). The AppDomain unload never completed. The user then started Streamer.bot again twice within ~10 s (the previous process was still alive/invisible).
   - **Shape 2 (2026-10-14 20:35:54):** `Cleaned up execute code instances` is logged, but `Streamer.bot exited` never appears. Cause unknown (`[HYPOTHESIS]`: a foreground thread or a native wait that survives the domain unload). Needs live reproduction with the new code.
2. **Self-triggering loop.** `Connect` is bound to a chat trigger; the integration posts a bot chat message; that bot message triggers `Connect` again (log: `Queueing 'Connect' (..., TwitchChatMessage) ... initiated by <bot>`), opening a browser tab every ~350 ms, repeatedly, including **after** `Closing services...` had started (new work was still being spawned during shutdown). The user's other moderation action also ran on every bot message.
3. **Reconnect storm.** 6197 `Ready to connect to the socket` in one 90-minute session (~250 attempts/minute at peak), against a DonationAlerts REST limit of 60 requests/minute/app. Log lines appeared doubled/tripled at the same millisecond (duplicate workers). 187 `Subscribe response ... code 103 permission denied`, 2x `code 101 unauthorized`, 21x HTTP 504 from the DonationAlerts API.
4. **Thread aborts on recompile/stop.** `Donation socket stopped, Поток находился в процессе прерывания` (= `ThreadAbortException` text, localized). Streamer.bot loads inline code in an isolated AppDomain and logs `InlineCode :: Unloading '<id>'` per instance at shutdown.
5. **Culture bug in the update checker.** `FormatException` from `Convert.ToDouble(...)` inside `GetNewerGitHubVersion` on a Russian-locale machine (`System.Number.ParseDouble`). The same class of bug will hit amount parsing.
6. **Secrets/PII in logs and backups.** The old debug log contains the profile JSON (including an e-mail address), OAuth auth codes, and path info; SB keeps these in `logs\` which users paste into support chats. `globals.db` (inside every `backup\*.zip`) holds `daClientSecret` in clear text.
7. **Persisted globals on this machine contain only `daClientId` and `daClientSecret`** (no tokens) - the old setup was re-initialized recently; the new README must handle "clean" state.
8. **The user already has actions bound to the old custom trigger event `da.donation.any` and using `%daUsername% %daAmount% %daCurrency% %daMessage%`** (action `[DonationAlerts] Донат`, plus a `MiniChat.MemeAlerts.TopUp` event from a separate tool). Under the clean-break contract these will go silent, not error.

---

## Critical Pitfalls

### Pitfall 1: `Streamer.bot.exe` does not exit - the integration blocks or outlives AppDomain unload

**What goes wrong:** After the user closes Streamer.bot, the process stays in Task Manager. New launch may fail to bind the OAuth port because the old process still owns it.

**Why it happens:** Inline code runs in an isolated AppDomain `[DOCS: "isolated AppDomain sandbox"] [OBSERVED: "Unloading '<id>'"]`. Shutdown calls `Dispose()` on instances and unloads the domain; `AppDomain.Unload` aborts managed threads but **cannot abort a thread blocked in native code** (`HttpListener.GetContext`, a blocking socket read, `Thread.Sleep` in a catch-and-continue loop). A `catch (Exception) {}` around the loop plus `while(true)` can also resurrect work after a `ThreadAbortException`-driven stop. Long-running work done *as an action* (the old `DonationCheckerLoop`) is also an action that never completes. There is **no "Streamer.bot closing" trigger** in the docs trigger list - `Dispose()` is the only supported shutdown hook `[DOCS]`.

**How to avoid:**
- One **Supervisor** object per `CPHInline` instance owning a single `CancellationTokenSource`. `Dispose()` = cancel, close/abort the socket and listener, then a **bounded** wait (<= 2 s total, never infinite `Join`/`Wait()`), never throw, idempotent.
- `Start` action must **return immediately** after launching the worker with `Task.Run` (docs prefer Task over `new Thread`; `new Thread` is foreground by default and dedicated threads run outside the CPH execution frame `[DOCS]`). Never run the receive loop *in* the action's thread.
- Every wait is cancellable: `ReceiveAsync(ct)`, `Task.Delay(ms, ct)`, `ConnectAsync(uri, ct)`. Never `Thread.Sleep`, never `.GetAwaiter().GetResult()` without a timeout, never `CPH.Wait()` in loops (it has no cancellation).
- Make unblocking explicit: to stop `HttpListener.GetContextAsync` call `listener.Close()` (and observe the faulted task); to stop `ClientWebSocket` call `Abort()` after a short `CloseAsync` timeout. Prefer a plain `TcpListener(IPAddress.Loopback, port)` for the single OAuth callback (see Pitfall 8) - `Stop()` reliably unblocks `AcceptTcpClientAsync`.
- Check `ct.IsCancellationRequested` **before spawning anything** (browser open, reconnect, retry) so no new work starts once Dispose began.
- Wrap every `CPH.*` call made from the worker in try/catch for `AppDomainUnloadedException` / `RemotingException` / `ThreadAbortException`; treat them as "stop", do not log as errors.
- No `System.Threading.Timer` callbacks without try/catch (unhandled exception on a raw timer/thread callback can bypass the sandbox and crash the host `[DOCS]`); no `async void`.
- Before declaring a bug, check the user's `windowSettings.minimizeToTrayOnClose` (currently `false` on this machine) so a legitimate tray-minimized process is not misdiagnosed.

**Warning signs:** Log after `Closing services...` lacks `Cleaned up execute code instances` or `Streamer.bot exited`; Task Manager shows `Streamer.bot.exe` for > 5 s after close; port 8554 "in use" on next launch; a second launch appears to do nothing.

**Verification gate (offline):** unit test that calls `Dispose()` while the worker is (a) blocked in a fake receive that only honors the token, (b) blocked in accept, (c) inside a reconnect delay - and asserts return < 2 s and no new task started afterwards. **Verification gate (live):** open Streamer.bot, Start, close the window, confirm the three log markers and that the process is gone within ~3 s; repeat while Connect/OAuth is pending and while reconnecting.

**Phase to address:** B (Lifecycle Core) - first implemented phase; H adds the live checklist. A must provide the harness that makes the test above possible.

---

### Pitfall 2: Duplicate workers - repeated Start, recompile, Init-autostart, self-triggering chat command

**What goes wrong:** Two or more sockets/loops run at once: doubled log lines, doubled donations, token-refresh races, `103 permission denied` on subscribe, rate-limit exhaustion.

**Why it happens:** (a) `Start` is bound to several triggers (manual + `Streamer.bot Started` + chat command); (b) editing the code in the Streamer.bot editor recompiles -> **new instance in a new AppDomain** while the old one is being aborted - `static` fields do **not** protect across domains; (c) autostarting from `Init()` (Init runs on every compile, "including during Streamer.bot startup" `[DOCS]`); (d) the bot's own chat message re-triggers a chat-bound `Connect`/`Start` `[OBSERVED]`; (e) Streamer.bot's `Default` queue is non-blocking so concurrent executions are allowed `[DOCS]`.

**How to avoid:**
- Lifecycle as an explicit state machine guarded by `Interlocked`/lock: `Stopped -> Starting -> Running -> Stopping`. `Start` in any state other than `Stopped` returns `true` with an Info log ("already running"); `Stop` when `Stopped` is a no-op.
- Cross-instance (cross-AppDomain) guard through something **shared in the main domain**: a non-persisted global `da.worker.generation` (GUID written by the new instance in `Start`; every worker loop iteration compares and exits if it no longer owns the generation). A process-wide named `Mutex` is the alternative; choose one and test it with two instances.
- `Init()` must be cheap, idempotent and side-effect-light: validate config, `RegisterCustomTrigger(...)`, nothing network-related. Autostart belongs to an action bound to the `Streamer.bot Started` trigger (visible, user-disableable), not to `Init`.
- **Never bind control actions (Connect/Start/Stop) to a chat command by default**; if offered, command must have `ignoreBotAccount: true` (field exists in exported commands `[OBSERVED]`), restricted permissions, and the integration must never send chat text containing the command string. Provide manual-run + hotkey instead.
- Single-flight OAuth: while an authorization is pending a second `Connect` returns immediately with "already pending, open <url from log>".

**Warning signs:** Same log line twice with identical timestamp; more than one `Authorized`/`Subscribed` per start; browser opens repeatedly; `permission denied` counter rising.

**Phase to address:** B (state machine, generation guard, Init policy); E (no chat output with command text); G (which triggers the `.sb` binds).

---

### Pitfall 3: Reconnect storm / thundering retries against a 60 req/min API

**What goes wrong:** The integration retries in a tight loop, each attempt hitting `GET /api/v1/user/oauth` and `POST /api/v1/centrifuge/subscribe` (and opening a fresh WebSocket). DonationAlerts documents a limit of **60 requests per minute per application** `[DOCS]`; the old log shows ~250 attempts/minute `[OBSERVED]`. Result: 429/504s, token revocation risk, a 2.8 MB log per day, and a service that never stabilizes.

**Why it happens:** Retry counter never resets or never backs off; every error class is treated the same; the subscribe round-trip is repeated for failures that retrying cannot fix (`invalid token`, `permission denied`, revoked consent).

**How to avoid:**
- Exponential backoff with **full jitter**: 1 s, 2, 4 ... capped at 60 s. Reset the attempt counter only after the connection has been **stable** (subscribed and >= 60 s alive), not merely connected.
- **Classify** before retrying: transport error / 5xx / 504 / timeout -> backoff; HTTP 401 -> refresh token once (single-flight) then retry once; `invalid_grant` or 403 / insufficient scope -> **stop and tell the user** (one Error line, state `NeedsAuth`); Centrifugo close with `"reconnect":false` -> **do not reconnect blindly** (Pitfall 4).
- Cache `user id` and `socket_connection_token`; call `/user/oauth` again only when the socket says the token is invalid, not on every attempt. Keep REST usage under a self-imposed budget (e.g. <= 10/min) with a token-bucket.
- Circuit breaker: after N consecutive failed cycles (e.g. 8) move to `Failed`, log once, stop; user presses Start again.
- Rate-limit your own logging: log state transitions, not every attempt; at most one repeated-error line per minute.
- Ensure single worker first (Pitfall 2), otherwise backoff multiplies across workers.

**Warning signs:** > 10 connection attempts per minute in the log; HTTP 429/504 bursts; `Ready to connect` count growing faster than wall-clock minutes.

**Phase to address:** D (Realtime Client); the policy table (error class -> action) belongs in D's plan; unit-testable offline with a fake clock.

---

### Pitfall 4: Wrong Centrifugo protocol generation (DonationAlerts speaks the legacy v2-era JSON protocol)

**What goes wrong:** Using a current Centrifugo/centrifuge client library, or hand-coding frames from today's centrifugal.dev docs, silently fails or is rejected. Parsing is also fragile in ways that lose donations.

**Facts:**
- Connect: `{"params":{"token":"<socket_connection_token>"},"id":1}` -> reply `{"id":1,"result":{"client":"<uuid>","version":"2.2.1"}}` `[DOCS]`. Subscribe: `{"id":2,"method":1,"params":{"channel":"...","token":"..."}}`; replies use `result`/`error`; pushes have **no `id`**; the donation object sits at `result.data.data`, with `result.channel` and `result.data.seq` around it `[DOCS][WEB]`. Current Centrifugo (v3+) uses named commands (`{"connect":{...}}`), different push envelopes and server-initiated pings - none of that applies here.
- Live probe `[OBSERVED]`: sending `{"id":1,"params":{"token":"x"}}` to `wss://centrifugo.donationalerts.com/connection/websocket` is accepted as a legacy connect and the server closes with WebSocket code **3002** and reason `{"reason":"invalid token","reconnect":false}` - i.e. Centrifugo "disconnect advice" in the close reason.
- Error codes seen: `101 unauthorized`, `103 permission denied` `[OBSERVED]`.
- The protocol allows **several JSON documents per WebSocket message separated by `\n`** (batching) `[DOCS: transport doc for newer protocols; legacy JSON uses the same convention - HYPOTHESIS for DA's server]`. The old code runs `JsonConvert.DeserializeObject` on the whole message - a batched frame throws and the donation is dropped.
- Keep-alive: for the legacy protocol the client sends `{"method":7}` (PING) roughly every 25 s; whether DA's server also sends `{}` pings is **unknown** `[HYPOTHESIS]` (the DA docs say nothing; third-party DA clients show no ping at all `[WEB]`).

**How to avoid:**
- Write a tiny dedicated frame codec: receive full messages (loop until `EndOfMessage`, cap total size e.g. 1 MB), split on `\n`, parse each line independently, dispatch by shape (`id` present -> reply; no `id` + `result.channel` -> push; empty `{}` -> ping, answer `{}` if the server sends it). **Unknown shapes are logged at Debug (type only) and ignored**, never thrown on.
- Do not take a NuGet/Centrifuge client dependency (also forbidden by the constraints).
- Implement an **inactivity watchdog** independent of ping format: any inbound frame resets it; no frame for ~60-90 s -> send a ping; no reply in 10 s -> treat as dead, Abort, reconnect with backoff. First live test captures **frame kinds and timing only (no payload)** to settle the ping question, and the result is written into the manual checklist.
- Read the close reason: parse `{"reason","reconnect"}`; `reconnect:false` -> go to `NeedsAuth`/`Failed` instead of retrying (after one token refresh attempt if the reason is `invalid token`).
- Treat subscribe success as: a reply with matching `id` and **no `error`**; pushes that arrive before the reply are queued/processed, not discarded (the old code reads exactly 4 frames).
- Subscribe donation and goal channels independently; one failing (e.g. missing scope) must not tear down the other.

**Warning signs:** `JsonReaderException: Additional text encountered`; connection drops every ~N seconds with no error; close code 3xxx in the log; donation visible on DonationAlerts dashboard but no event fired.

**Phase to address:** D. Flag: **needs a short live capture** (frame kinds, ping) - this is the single biggest unknown in the realtime path.

---

### Pitfall 5: Subscribe tokens are per channel *and per client id*; stale reuse yields `103 permission denied`

**What goes wrong:** After each reconnect a new `client` UUID is issued; channel tokens obtained for the old UUID (or fetched concurrently by a duplicate worker) are rejected - `103 permission denied` (187 times in the old log `[OBSERVED]`) - which the old loop then retried at full speed.

**Why it happens:** Flow is: `GET /user/oauth` -> socket token -> WebSocket connect -> `client` UUID -> `POST /centrifuge/subscribe {channels:[...], client:<uuid>}` -> per-channel `token` -> `subscribe` command `[DOCS]`. Tokens are tied to that `client`. Caching "the subscribe token" across reconnects, or doing the POST before the connect reply arrives, breaks it.

**How to avoid:**
- Always run the full sequence per connection; never cache channel tokens beyond a single connection. Request **both channels in one POST** (saves rate budget).
- Channel names are `$alerts:donation_<user_id>` and `$goals:goal_<user_id>` (user id from `/user/oauth`; `$polls:poll_<id>` exists but is out of scope) `[DOCS]`. Validate that the channel in the reply equals the requested one.
- On `103` retry the **whole** sequence once with fresh tokens; second `103` -> stop with a clear message ("scope missing or app not authorized for this channel"), do not loop.

**Warning signs:** `permission denied` immediately after `Authorized successfully`; works at first Start, fails on reconnect.

**Phase to address:** D.

---

### Pitfall 6: "Exactly once" is not achievable by push alone - duplicates *and* gaps

**What goes wrong:** (a) Duplicates: DonationAlerts "might occasionally send duplicates" `[WEB]`, plus reconnect redelivery, duplicate workers, and recompile overlap. (b) Gaps: donations made while the socket is down (network blip, Streamer.bot restart, token problem) are never pushed again - the legacy channel is not guaranteed recoverable (`recoverable`/`seq` were parsed but ignored in the old code; whether DA enables recovery is `[HYPOTHESIS]`).

**How to avoid:**
- Dedupe key = donation `id` only (never a message hash; never `amount+name`). Keep a **bounded LRU** (>= 1000 ids) behind a lock, checked-and-marked atomically *before* dispatch, and persist a **high-water mark** (`lastDonationId`, plain persisted global) so a restart does not replay.
- Decide and document the delivery semantics explicitly as **"at-least-once from DonationAlerts + dedupe = effectively once while connected"**. If PROJECT.md's "reliably reaches Streamer.bot exactly once" must also cover downtime, add an optional **REST backfill on (re)connect**: `GET /api/v1/alerts/donations` (needs scope `oauth-donation-index`, which the old default scopes did not request - adding it forces a re-consent `[DOCS]`), filtered by `id > lastDonationId` and a **max age** (e.g. 10 min) so a stale donation from last night is not announced on a new stream. Keep it off by default or behind one setting; count it against the REST budget.
- `created_at` is `YYYY-MM-DD HH:MM:SS` with **no time zone** `[WEB]` - do not use it for ordering or age checks without verifying the zone live; use local receive time.
- Goals: dedupe on `(goal id, raised_amount, goal_amount, is_active)`; but **zero amounts are legitimate** (a fresh goal), unlike donations - the old `IsValid` (`Amount > 0`) silently dropped them.

**Warning signs:** the same donor thanked twice around a reconnect; a donation missing after a 30 s network drop; a restart re-fires the last donation.

**Phase to address:** D (LRU, high-water mark, backfill decision); the semantic wording belongs to the README (H) and PROJECT.md decision log.

---

### Pitfall 7: OAuth token lifecycle - refresh races, un-persisted rotation, giant `expires_in`, scope changes

**What goes wrong:** Two components refresh at once; the new refresh token is dropped; the integration stops after the first reconnect past expiry; adding a scope later "does nothing".

**Facts:** `expires_in` in the official example is **631151999** s (~20 years) and no lifetime policy is stated `[DOCS]`; refresh may or may not return a new refresh token ("if not, the existing one stays valid") `[DOCS]`; `401` body `{"message":"Unauthenticated."}` `[DOCS]`; token request is `POST /oauth/token` with `grant_type, client_id, client_secret, redirect_uri, code` (and `refresh_token` + `scope` for refresh) `[DOCS]`. Real lifetime of a given token is `[HYPOTHESIS]`.

**How to avoid:**
- **Single-flight refresh** (`SemaphoreSlim(1,1)`, re-read the stored token after acquiring the lock - another caller may have refreshed already).
- On success **persist atomically and immediately**: new access token, `refresh_token` *if present in the response else keep the old one*, computed expiry. Persist *before* using the token.
- Trust `401` as the source of truth; use `expires_in` only as a hint (refresh if < 5 min left, checked lazily before a REST call or reconnect). **Never schedule a timer from `expires_in`**: 631151999 s overflows `System.Threading.Timer`/`Task.Delay` limits (int milliseconds, ~24.8 days) and throws `ArgumentOutOfRangeException`.
- Parse `expires_in` defensively (could be string or number; clamp).
- `invalid_grant` on refresh = revoked/expired refresh token -> state `NeedsAuth`, stop, instruct the user to run Connect again. No retry loop.
- Scope set is fixed per authorization; changing scopes (e.g. adding `oauth-donation-index`) requires a new Connect. Store the granted scopes next to the token and warn on mismatch (the old `WarnIfMissingScope` logged at Debug only).
- Token request errors: parse body for `error`/`error_description`; never log the request body (contains the secret).

**Warning signs:** works for the first stream, `EventAuthError` after a reconnect; two refresh calls within one second in the log; refresh returns 200 but next request still 401 (old refresh token reused after rotation).

**Phase to address:** C; D consumes it (reconnect must call `GetValidAccessToken()` each time, never capture a token string).

---

### Pitfall 8: OAuth callback listener - redirect URI exact match, HttpListener quirks, favicon, state, port ownership

**What goes wrong:** The authorize page shows a redirect error; the browser loads the callback but the listener never sees `code`; the listener consumes `/favicon.ico` as "the" callback; the port is permanently busy after a hung process; browser tabs multiply.

**Facts and traps:**
- The redirect URI must be the one registered in the DonationAlerts app; the apidoc only says "specified during client registration" `[DOCS]` - treat it as **exact string match** (scheme, host `127.0.0.1` vs `localhost`, port, path, **trailing slash**). On this machine `http://127.0.0.1:8554/donationalerts/callback/` was accepted by DA (8 successful code exchanges in the log) `[OBSERVED]`.
- `HttpListener` prefixes **must end with `/`**, which may differ from what the user typed in the DA app form `[WEB]`. Normalize and **print the exact URI to register** in the README and in the log.
- `HttpListener` prefix registration lives in http.sys: an un-`Close()`d listener (or a hung process) keeps the prefix - second start fails with *"conflicts with an existing registration"* `[OBSERVED, localized Russian text]`. Non-admin rights: `localhost` prefixes are allowed without a URL ACL; literal-IP prefixes are reported to require one in some setups `[WEB]`; `127.0.0.1:8554` did start on this machine `[OBSERVED]` (elevation state unknown). **Prefer `TcpListener(IPAddress.Loopback, port)` + a minimal HTTP/1.1 response writer** - no URL ACL, no http.sys registration, no firewall prompt (loopback only), trivially cancellable. If `HttpListener` is kept, wrap in `try/finally { Close(); }` and test non-elevated.
- `localhost` may resolve to `::1` first on Windows; a listener bound to `127.0.0.1` then sees a delayed fallback or a refusal. Use the literal `127.0.0.1` in both the registered URI and the listener (`[WEB]`, test live).
- Browsers send `GET /favicon.ico` and sometimes prefetch: accept only the callback path, answer others with 404 and keep waiting.
- `state`: random >= 128-bit, single-use, constant-time compare; reject when no flow is pending. Handle `?error=access_denied&error_description=...` as a normal user outcome.
- Free-port conflict: if the port is busy, fail **fast** with an Error naming the port and the setting to change (old code only logged at Debug).
- Opening the browser: `Process.Start` with `UseShellExecute = true` and the URL as argument (not via `cmd /c start`, where `&` splits the URL). Print the URL to the **SB log (Info)** as a fallback - **not to chat** (chat output re-triggered Connect, Pitfall 2). Open the browser exactly once per Connect.
- Escape every value written into the success/error HTML (`WebUtility.HtmlEncode` from `System.dll`; avoid `System.Web`). No third-party font CDNs.

**Warning signs:** DA page "redirect_uri mismatch"/"invalid_client"; `Server is waiting` followed by timeout although the browser reached the page; HttpListenerException 183/32; many tabs.

**Phase to address:** C. Add to H: README section "Что вписать в Redirect URI" with the exact string.

---

### Pitfall 9: Compiles in your dev environment, fails in Streamer.bot (net48 runtime, per-sub-action references)

**What goes wrong:** Import succeeds but the code does not compile on the streamer's machine; or it compiles in a modern SDK but not in Streamer.bot. (The old file did not compile at all - missing `;` at line 89 - proving no build step ever ran.)

**Facts `[OBSERVED]`:** Streamer.bot 1.0.7 compiles with Roslyn **5.x** (`Microsoft.CodeAnalysis.CSharp.dll` 5.600) so the *language* is very new, but code runs on **.NET Framework 4.x** (`supportedRuntime ... v4.7.2`; docs' VS Code recipe uses `net481`). Roslyn will happily accept syntax whose supporting types do not exist on net48 (`record`/`init` -> `IsExternalInit`, `Span<T>`/ranges/indices, `IAsyncEnumerable`, `await using`, default interface members, `System.Text.Json` is in the SB folder but not referenced by default). `System.Net.Http.dll` is **not** shipped in the SB folder (it comes from the GAC) - needs an explicit reference. `compilerSettings.commonReferences` is empty on this machine, so everything must be declared per sub-action.

**Reference format in real exports `[OBSERVED]`:** `"references": ["C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\mscorlib.dll", "...\\System.dll", "...\\System.Net.Http.dll", ".\\Newtonsoft.Json.dll"]` - framework DLLs as absolute `Framework64` paths, SB-shipped DLLs as `.\Name.dll`. Whether Streamer.bot re-resolves a missing absolute path by file name (Windows on `D:`, 32-bit) is `[HYPOTHESIS]` - changelog says import "is more intelligent on how references are handled" `[DOCS]`. Docs also say that after adding `using` directives you must click **Find Refs** `[DOCS]` - an importer cannot click it, so the `.sb` must carry the complete list.

**How to avoid:**
- Offline compile check must mimic production: target **net48/net481**, reference the same assembly set (framework + `Newtonsoft.Json` + a CPH stub matching `IInlineInvokeProxy`), `LangVersion` conservative (stay with C# <= 9-ish constructs that need no new runtime types; no records/init/Span/ranges/async streams).
- Keep the reference list **minimal and explicit**: `mscorlib`, `System`, `System.Core`, `System.Net.Http` (only if used), `Newtonsoft.Json` as `.\Newtonsoft.Json.dll`. Avoid `System.Web` (use `Uri.EscapeDataString`, `WebUtility`), avoid `System.Web.Extensions`.
- Generate the `references` list from one source of truth in the build script and **assert** it equals the `using` set.
- Keep the CPH stub honest: generate/verify it against the real `Streamer.bot.Plugin.Interface.dll` by reflection locally (the real signatures were dumped this session: e.g. `TriggerCodeEvent(string,bool)`, `(string,Dictionary<string,object>)`, `(string,string)`; `RegisterCustomTrigger(string,string,string[])`; `SetGlobalVar(string,object,bool)`; `GetGlobalVar<T>(string,bool)`; `WebsocketConnect/Send/Disconnect/IsConnected(int)`).
- Do not depend on message text of exceptions (Windows localizes them - Russian in the logs); branch on types/status codes.

**Warning signs:** "Compiling Log" shows `(are you missing an assembly reference?)`; CS0518/CS0246 for `ValueTuple`, `IsExternalInit`, `HttpClient`; works from the editor, fails after import on another PC.

**Phase to address:** A (harness) and G (reference list generation); H (manual check: "open the code in the editor, press Compile").

---

### Pitfall 10: Hand-crafted `.sb` that Streamer.bot rejects, partially imports, or silently overwrites user data

**Verified format `[OBSERVED]` (decoded real exports from SB 1.0.4):** import string = `base64( "SBAE" + gzip( UTF-8 JSON ) )`. JSON envelope: `{ "meta": {name, author, version, description, autoRunAction, minimumVersion}, "data": {actions, queues, commands, websocketServers, websocketClients, timers}, "version": 23, "exportedFrom": "1.0.4", "minimumVersion": "1.0.0-alpha.1" }`. The live `data\actions.json` of 1.0.7 has `"version": 24` (importer must migrate 23 -> 24; do not forge a newer one). **No global variables are in the export.** C# sub-action = `type 99999` with `name, description, references[], byteCode, precompile, delayStart, saveResultToVariable, saveToVariable, id, weight, parentId, enabled, index`; **`byteCode` is Base64 of the UTF-8 *source text* (CRLF)**, not compiled bytecode. "Execute C# Method" = `type 99998` with `executeCodeId` (must equal the `id` of the 99999 sub-action), `method`, `runOnUiThread`. Custom code-event trigger = `type 18002` with `name` and `eventName` (stored in the action, so it survives import even before the code registers it). Command objects carry `ignoreBotAccount`. Queue reference = `action.queue` GUID (`00000000-...` = Default). Docs: import **overwrites same-named items by default** `[DOCS]`.

**What goes wrong:**
- Invalid gzip/base64 header or JSON shape -> "import string invalid".
- Non-unique or inconsistent GUIDs (`executeCodeId` pointing to a regenerated id; duplicated trigger ids) -> sub-action "code not found" or a lost Execute C# Method link. Whether SB remaps ids on import is `[HYPOTHESIS]`.
- Action `queue` GUID not present in `data.queues` -> action lands in a missing queue.
- A re-import **overwrites the user's customised handler actions** ("by name"), destroying their reactions.
- Fabricated fields (`"invented fields"` are forbidden by PROJECT.md) or too-high `minimumVersion` blocking the import.
- Wrong text encoding for Russian names/descriptions (UTF-8 required; real exports have no BOM; `utf-8-sig` on read only).
- Ids regenerated randomly each build -> every release looks like a brand new set of actions to anyone diffing/re-importing.

**How to avoid:**
- Treat a **real export from the user's own 1.0.7** as the golden template: ask the user to export one minimal action containing (1) an Execute C# Code sub-action, (2) an Execute C# Method sub-action, (3) a custom code-event trigger, (4) a non-default queue, (5) a command with `ignoreBotAccount`. The build script starts from that shape and only fills content.
- Build tool (Node/Python, no extra deps) must: generate **deterministic UUIDv5 ids** from stable names, enforce uniqueness and referential integrity (every `executeCodeId` exists, every `queue` exists, `index` contiguous), write UTF-8 without BOM, produce `SBAE`+gzip+base64 with no line wrapping, then **round-trip decode and diff** against the source model. Pin `meta.version` to the integration version (single source for the version constant, README, User-Agent, update checker - the old fork kept it in four places).
- Namespacing: prefix every action `DA | ...`, own group `DonationAlerts`, user-editable examples in a separate group named "...Примеры" and flagged disabled, so a re-import with Overwrite on system actions only is safe; document which items are safe to overwrite.
- `meta.autoRunAction`: leave `null`; running code on import surprises users.
- State plainly in README that the import was validated offline only until the manual checklist is done.

**Warning signs:** import dialog shows fewer items than expected; action opens but the C# sub-action is empty or points to "(none)"; duplicate `DonationAlerts - System` queues after the second import.

**Phase to address:** G (build/validate), with A providing the golden-file approach; H lists the "import on a clean profile" check.

---

### Pitfall 11: Secrets and PII leaking through logs, arguments, exports, backups

**What goes wrong:** Client secret/tokens/e-mail end up in `.sb`, in Streamer.bot logs the user pastes for support, in Action History, in WebSocket broadcasts, or in `backup\*.zip`.

**Observed:** old log contains the profile JSON (e-mail), auth codes and raw frames `[OBSERVED]`; `globals.db` with `daClientSecret` plaintext is zipped into every backup `[OBSERVED]`; Action History shows each action's arguments with values `[DOCS: action-history-variables]`; SB's own WebSocket server broadcasts events/args to connected clients `[OBSERVED: "Websocket Server :: Subscribing to"]`.

**How to avoid:**
- The `.sb` must contain **no** secret defaults and no tokens (globals aren't exported anyway - good; do not "fix" that by embedding them in code).
- Logging policy enforced in a single `Log` wrapper: never log token/secret/code/Authorization header/response bodies/raw frames/emails; log ids, counts, states, HTTP status, exception **type**. A unit test greps log output of the fake-server run for known secret strings.
- Never `CPH.SetArgument` a token or secret. Donation args are fine (they are the product) but mark noisy control actions `excludeFromHistory`.
- Don't persist single-use values (`code`, `state`). Persist only `refresh_token`, `access_token`, expiry, user id, granted scopes, `lastDonationId`.
- README (Russian): `.sb` is safe to share, but **backups, `data\globals.db`, and logs are not**; how to rotate the client secret in the DA dashboard if leaked.
- Anonymous donors have `username = null` `[WEB]`: do not log donor names or messages at Info; Debug only, and still not by default.

**Phase to address:** A (logging wrapper + grep test), C (storage layout), H (README warning).

---

### Pitfall 12: Unhandled exceptions kill actions silently - or crash the host

**What goes wrong:** (a) An exception in a plain action thread is caught by the sandbox and logged as `User script error executing '<Method>'` with an opaque `n<hash>.CPHInline` stack `[OBSERVED]`; users see "nothing happens". (b) An exception on a raw thread/`async void`/timer callback can escape and crash Streamer.bot `[DOCS]`. (c) `catch (Exception) {}` swallowing hides handler bugs (CONCERNS already notes this). (d) `Execute()` returning `false` stops the rest of the action silently `[DOCS]`.

**How to avoid:**
- Top-level `try/catch` in the worker's task body that logs `ex.GetType().Name` + message (no payload) and moves the state machine to `Failed`/backoff; never rethrow into the thread pool. Use `async Task`, never `async void` `[DOCS]`.
- Distinguish: `OperationCanceledException`/`ThreadAbortException`/`ObjectDisposedException` during stop = quiet; everything else = Error with rate limiting.
- Entry points called by sub-actions (`Start`, `Stop`, `Connect`, `Status`) return `true` on handled outcomes (so later sub-actions such as "chat: already running" still run) and `false` only for genuine failure; use "Save Result to Variable" (documented option) when the action chain must continue.
- The handler's own errors are not ours: events are delivered with `TriggerCodeEvent` (enqueue), so a failing user handler cannot kill the socket loop.

**Phase to address:** B (error taxonomy), D (per-frame isolation: a poisoned frame is logged and skipped, the loop continues).

---

### Pitfall 13: Blocking the reader or the queue - `RunAction` inline, blocking queues, long handlers

**What goes wrong:** The socket reader calls something that waits (`CPH.RunAction(name, true)`, `CPH.Wait`, an HTTP download, a sync `SendMessage` burst). Reading stalls -> no pong/ping -> server drops the connection -> reconnect -> backlog replays. Separately, putting the integration's own actions into a **blocking** queue serializes them behind user handlers (the user's donation queue is blocking and its handlers contain 300 ms + 2 s + 5 s + 500 ms delays `[OBSERVED]`).

**How to avoid:**
- The reader only: parse -> dedupe -> **enqueue to an internal bounded channel** -> continue reading. A separate dispatcher task calls `CPH.TriggerCodeEvent(eventName, Dictionary<string,object>)` (documented as an event raise; the handler actions run in *their* queues). Never use `RunAction(..., true)` from the worker.
- Control actions (`DA | Start/Stop/Connect/Status`) go to a **non-blocking** queue (Default or a dedicated non-blocking queue). A start action must not park inside a blocking queue.
- Backpressure: bounded dispatch queue (e.g. 100); on overflow log once and drop **oldest status noise first, never donations**; if donations back up, that is a user-handler design issue - surface a warning with queue length.
- Audio download and update check never happen on the reader/dispatcher path (Pitfall 20/21).

**Phase to address:** D (reader/dispatcher split), E (what the events look like), G (queue assignments in the `.sb`).

---

### Pitfall 14: CPH is a cross-AppDomain proxy - argument types, background-thread semantics, `useArgs`

**What goes wrong:** `TriggerCodeEvent` is called with the wrong overload or non-marshalable values: arguments are empty, the wrong action's args are reused, or a `SerializationException` appears.

**Facts:** CPH is an interface proxy into the main domain (`IInlineInvokeProxy` `[OBSERVED]`); inline code lives in a sandbox domain `[DOCS]`. `TriggerCodeEvent(string,bool useArgs)` uses "the variables of the current action" `[DOCS]` - from a background worker there is **no current action**, so its argument stack is empty/stale `[HYPOTHESIS on exact behaviour]`. `CPH.SetArgument` only affects the currently running action `[DOCS: arguments exist only within the scope of the current action]`. Overloads available in 1.0.7: `(string,bool)`, `(string,Dictionary<string,object>)`, `(string,string json)` `[OBSERVED]`.

**How to avoid:**
- From the worker always use the **Dictionary overload** and put only primitives in it: `string`, `int`, `long`, `bool`, `decimal`/`double`, `DateTime`. No `JObject`/`JToken`/custom classes (not guaranteed `[Serializable]`/available in the other domain).
- Never read `args` outside the `Execute` call that received it; copy what you need first.
- Don't mutate shared state from callbacks of the CPH proxy; assume each call is a remoting round-trip (cheap enough, but do not call it in tight loops or per frame).
- Offline tests must assert that every value placed into the dictionary is a primitive type.

**Phase to address:** E (contract + dispatcher), A (stub that fails on non-primitive values).

---

### Pitfall 15: Static state, `Init()` re-runs, and recompilation

**What goes wrong:** State silently resets or duplicates when the user edits/saves the C# (recompile) or when Streamer.bot restarts; singletons guarded by `static` do not guard anything across domains; `Init()` that connects causes a new worker per save; custom triggers disappear from the picker.

**Facts:** `Init()` runs "when your code is first compiled, including during Streamer.bot startup", `Dispose()` "on destroy, including shutdown" `[DOCS]`; log shows `Creating and compiling instance for '<name>'` on first use and `Unloading` at shutdown `[OBSERVED]`. A named Execute C# Code sub-action is one instance shared by all `Execute C# Method` calls (`Running 'Connect' entry point from instance '<guid>'`) `[OBSERVED]` - so instance fields are the shared state between `Start`/`Stop`/`Status` actions *as long as all use the same named code sub-action*. Custom triggers "need to be re-defined on every boot ... define in `Init()` and enable *Precompile on Application Start*"; they appear in the picker only once the registering code has run `[DOCS]`.

**How to avoid:**
- Put **all** logic in **one** named Execute C# Code sub-action (e.g. `DA Core`) and have thin control actions call methods via Execute C# Method (`Start`, `Stop`, `Connect`, `Status`) - they share one instance. Don't split state across several code sub-actions.
- `precompile: true` on that sub-action in the `.sb`, with `delayStart: false` (no UI), so `Init()` registers the triggers on boot. `Init()` also validates `CPH.GetVersion()` (warn if < 1.0.0) and loads config - nothing else.
- Persist state only through globals (with the right `persisted` flag, Pitfall 16); treat instance fields as cache.
- Recompile hygiene: `Dispose()` of the old instance must fully stop its worker (Pitfall 1) and the generation guard (Pitfall 2) must make a late-aborting old worker exit instead of competing.
- Tell the README reader: after editing the code, press **DA | Restart** (Stop + Start) - or document that saves recompile and drop the connection.

**Phase to address:** B.

---

### Pitfall 16: Global variables - persisted vs non-persisted are different namespaces; user typos; type drift

**What goes wrong:** The user fills `daClientId` in the Variables viewer without ticking *Persisted* (or the code reads the non-persisted slot): the setting "doesn't exist". Pasted values carry spaces/newlines/quotes. Defaults silently replace malformed values (the old `GetSettingInt`).

**Facts:** `SetGlobalVar(name, value, persisted)` - same name can exist as both persisted and non-persisted `[DOCS: example uses "myString" for both]`; `~name~` syntax resolves only **persisted** globals `[DOCS]`; **the `.sb` cannot carry global variable values** `[OBSERVED: export has no globals]`.

**How to avoid:**
- Read config from the persisted slot, fall back to non-persisted with a one-time Warn naming the mismatch; write runtime state (tokens, `lastDonationId`) persisted; write transient flags (generation, state) non-persisted.
- Provide a `DA | Setup` action (in the `.sb`) with Set Global Variable sub-actions (Persisted ticked) for the user-facing settings with empty placeholder values, or a `DA | Check config` method that validates and prints a **Russian, actionable** message ("не задан daClientId (Persisted)").
- Trim, strip BOM/quotes/CR/LF from every setting; validate `ClientId` is numeric, redirect URI parses, port in 1024-65535; on invalid values **warn and name the variable**, then use the default - never silently.
- Use a documented prefix for all variables (`da`), and a single `daVersion`-style marker to allow future migrations.

**Phase to address:** C (settings reader), G (Setup action), H (README table with the Persisted note).

---

## Moderate Pitfalls

### Pitfall 17: Amounts, currencies and culture

**What goes wrong:** `22.5` becomes `225` or throws on a ru-RU machine (the old update checker already did - `[OBSERVED]`); `0.1 + 0.2` style float error in range matches; `amount` vs `amount_in_user_currency` confusion; zero-decimal currencies shown as `100.00`.

**Prevention:**
- Parse JSON numbers with Newtonsoft into `decimal` (never `double`); format/parse strings **only** with `CultureInfo.InvariantCulture`; unit-run the whole test suite under `ru-RU` and `en-US` `CurrentCulture`.
- `amount` is a JSON number `[DOCS]` (e.g. `500`, `22.0`); `currency` is an ISO 4217 code `[DOCS]`; `amount_in_user_currency` is **not documented** in the apidoc but present in practice `[WEB]` and may be missing/0 when the rate is unavailable -> expose `amountMain` plus a boolean `amountMainKnown`; fall back to `amount` only when currency equals the account's main currency (get it from `/user/oauth` if present - `[HYPOTHESIS]` that the profile exposes it; else from config).
- Contract: numeric args as real numeric types for SB's `If`/compare sub-actions, **plus** string twins pre-formatted for chat/TTS (`donationAmountText = "22,5"` or `"22.5"` per a setting), so users don't need `%x:c2%` tricks. Document rounding (banker's vs away-from-zero: pick `MidpointRounding.AwayFromZero`, 2 dp, strip trailing zeros).
- Amount ranges (PROJECT requirement) are **not** provided by SB for custom code events (the built-in range trigger UI is for core triggers; note its quirk: "only Max set = exact match" `[DOCS]`). Decide the mechanism explicitly: one custom event + `If` sub-actions in user's action, or additional tier events (`donation.tier.<n>`) fired by a configurable list. Make range edges inclusive and document it. Exact-amount match must compare `decimal` values, not formatted strings.
- Guard `NaN/Infinity/negative` -> drop with Warn.

**Phase to address:** E (+ unit tests in A harness).

### Pitfall 18: Message/name text is hostile input (emoji, newlines, commands, variable syntax, `audio` type)

**What goes wrong:** Chat/TTS/OBS output breaks or is abused.

**Prevention:**
- `message_type` is `text` or `audio` `[DOCS]`; for `audio` the `message` carries the audio reference (URL) rather than text `[HYPOTHESIS - verify with a real audio donation]` - expose `donationIsAudio` and do **not** route that value to TTS/chat as text.
- `username` is `null` for anonymous donors `[WEB]` -> use `name`; empty -> localized "Аноним" via setting.
- Truncate by **text elements**, not `Substring` (emoji/surrogate pairs and combining marks; Twitch chat limit 500 chars). Replace `\r\n` with a space for chat; keep raw text in a separate arg for OBS text sources.
- Neutralize chat command/IRC injection when echoing to chat: if the first non-space char is `!`, `/`, `.` prepend a zero-width-safe prefix or quote; never let a donor message cause a bot message that starts a command (also removes the Pitfall 2 loop vector). Strip control characters and bidi overrides (U+202A-202E, U+2066-2069).
- `%...%` inside donor text is expanded by SB only where *our* template contains it; values are inserted as data. Still verify live that a donor message of `%rawInput%` / `%user%` isn't re-expanded (add to checklist) `[HYPOTHESIS - low risk]`.
- Keep the raw JSON (`donationRaw`) only if a setting enables it (it contains `recipient` info).

**Phase to address:** E.

### Pitfall 19: Test donations, `is_shown`, odd ids

**What goes wrong:** Dashboard test alerts or unshown/moderated donations are mishandled (dropped or double-announced).
**Prevention:** `is_shown` is 0/1 "shown in DA widgets" `[DOCS/WEB]`, not a validity flag - expose it, don't filter on it. Whether dashboard "test alert" reaches the API channel and what its `id` looks like is `[HYPOTHESIS]`; capture one live and put the result in the checklist. Dedupe with the id as an opaque string/long; never assume monotonic ids for the high-water mark unless live data proves it (use "seen set" + "max id" together). Provide a `DA | Simulate donation` action (calls the same dispatcher with a synthetic payload, flagged `donationIsTest=true`) so users can test handlers without real money - and so the manual checklist doesn't depend on real donations.
**Phase to address:** E (simulate action), H (checklist).

### Pitfall 20: Optional audio download - SSRF-ish, size, extension, cleanup timing, ordering

**What goes wrong:** Redirect to an arbitrary host, huge file, wrong extension (`.wav` hard-coded in the old code), file deleted before OBS/Play Sound uses it, unbounded temp growth, event fired before the file exists.
**Prevention:** `https` only; host allow-list (discover DA's media host(s) live and make the list a setting); disable auto-redirect or re-validate each hop; `Content-Length` cap **and** streaming byte cap (e.g. 10 MB); total timeout (e.g. 15 s) via `CancellationToken`; file name from donation id + extension from validated `Content-Type` (unknown -> reject); dedicated subfolder under `Path.GetTempPath()` created per run; **janitor**: delete files older than N hours on Start and by a low-frequency sweep; never delete immediately after dispatch. Use `HttpClient`/`HttpWebRequest` with explicit timeouts; dispose responses and streams. The donation event must be dispatched **after** the file is ready or after the timeout (then with `donationAudioPath = ""` and `donationAudioError`), and download runs off the reader thread (Pitfall 13). Raise `ServicePointManager.DefaultConnectionLimit` above 2 for concurrent downloads (minor).
**Phase to address:** F.

### Pitfall 21: Update checker blocks, spams, and breaks on culture

**What goes wrong:** GitHub unauthenticated limit is 60/h; `User-Agent` header is mandatory (403 otherwise); the old checker ran synchronously on every `Init` (which runs on every recompile), parsed versions with `Convert.ToDouble` (FormatException `[OBSERVED]`), and posted to chat (which re-triggers user moderation actions `[OBSERVED]`).
**Prevention:** run on the worker after Start, never in `Init`; persisted `lastUpdateCheckUtc` (<= 1/day); `System.Version.TryParse` / a tiny SemVer parser after stripping `v` and pre-release suffix; `Accept: application/vnd.github+json`, explicit `User-Agent`; use `/releases/latest` (1 request) instead of a 100-item list; failures are Debug-level and silent; announcement goes to the **log** and an optional event/arg (`DA | Update available`), chat only if the user enables it. Fill the real repo slug (CONCERNS: placeholder). Single `Version` constant shared with README/User-Agent.
**Phase to address:** F.

### Pitfall 22: Goal events - noisy, partial-failure, zero values

**What goes wrong:** Every donation updates goals (event spam); zero amounts dropped; failure to subscribe goals (missing scope `oauth-goal-subscribe`) kills the donation feed; `expires_at` null/past.
**Prevention:** goal channel is optional and independent (Pitfall 4); emit on **change only** (compare stored last state); fields per apidoc: `id, is_active (int), title, currency, start_amount, raised_amount, goal_amount, started_at, expires_at (nullable)` `[DOCS]`; use `decimal`; compute `percent` with divide-by-zero guard; include `goalIsActive` bool. Don't fire a "goal reached" twice (dedupe `reached` per goal id).
**Phase to address:** F.

### Pitfall 23: `ClientWebSocket` on .NET Framework - one send, one receive, abort semantics, close hangs

**What goes wrong:** Concurrent `SendAsync` from ping + subscribe throws; `CloseAsync` waits forever on a dead peer; reusing an `Aborted` socket; `ReceiveAsync` canceled via token leaves the socket unusable (expected); old sockets never disposed (CONCERNS).
**Prevention:** one `SemaphoreSlim` around every send; create a **new** `ClientWebSocket` per attempt and `Dispose()` it in `finally`; `CloseOutputAsync`/`CloseAsync` only with a 2-3 s linked token then `Abort()`; set `Options.KeepAliveInterval` explicitly (e.g. 20 s) but keep the app-level watchdog (do not rely on it `[HYPOTHESIS]`); receive buffer 8 KB with message-assembly cap; honor system proxy defaults; do not pin `ServicePointManager.SecurityProtocol` (leave OS defaults - on .NET 4.7.2+ that already means TLS 1.2+).
**Phase to address:** D.

### Pitfall 24: Process/OS issues around the OAuth browser hop

**What goes wrong:** No default browser, the browser opens on a different machine session, firewall prompts, corporate AV blocks loopback.
**Prevention:** loopback-only bind (no firewall prompt expected `[WEB]`, check live); if `Process.Start` throws, log the URL (Info) and keep waiting until timeout; timeout default 120 s, configurable; one flow at a time; close listener in `finally`; the success page says "можно закрыть вкладку" and contains no external resources.
**Phase to address:** C, H.

### Pitfall 25: Logging volume and localization

**What goes wrong:** Debug log floods (2.8 MB/day from the storm `[OBSERVED]`); Windows exception messages are localized (Russian), so string matching on `ex.Message` fails.
**Prevention:** state-transition logging, per-key rate limiter, never `ex.ToString()` of web exceptions with bodies; branch on `WebExceptionStatus`, HTTP status, `SocketError`, `WebSocketError` enums; always prefix lines with a fixed tag (`DA:`) so users can search; the README shows the 6-8 log lines of a healthy start.
**Phase to address:** A (wrapper), D.

### Pitfall 26: Re-import and the user's existing actions

**What goes wrong:** Re-importing overwrites edited actions; duplicate queue/groups; user's old `da.donation.any` handlers go silent.
**Prevention:** see Pitfall 10 naming/grouping; README "Миграция со старой версии": list the removed events/args and the new ones with a copy-paste mapping table; optionally ship a disabled compatibility action group is **out of scope** (clean break) - just document. Offer `DA | Status` printing counts of unused triggers.
**Phase to address:** G, H.

---

## Minor Pitfalls

### Pitfall 27: Reconnect on suspend/resume or network change
Sockets become half-open after sleep; TCP won't notice for minutes. Watchdog (Pitfall 4) + `NetworkChange.NetworkAvailabilityChanged`/`SystemEvents.PowerModeChanged` are optional hints only; do not rely on them (event subscriptions in an unloaded domain leak). Prefer watchdog only.

### Pitfall 28: `HttpWebRequest` defaults
Default `Timeout` 100 s, `ReadWriteTimeout` 5 min, `ServicePointManager.DefaultConnectionLimit = 2`, `Expect100Continue` adds latency on POST. Always set timeouts (10-15 s), dispose responses, set `User-Agent` (DonationAlerts and GitHub may reject empty). Consider one shared `HttpClient` per instance (disposed in `Dispose`) rather than `WebClient` (never disposed in the old code).

### Pitfall 29: Process-wide settings mutation
Do not change `ServicePointManager`/culture globally (`Thread.CurrentThread.CurrentCulture`) from inline code: both are per-domain/thread but easy to leak into Streamer.bot's formatting. Pass `CultureInfo.InvariantCulture` explicitly.

### Pitfall 30: Streamer.bot version drift
`CPH.GetVersion()` returns SemVer; 0.2.x is out of scope but a user may still run it. Warn once at `Init` when < 1.0.0 and refuse to start. Custom trigger/`TriggerCodeEvent` API arrived in 0.2.0-0.2.5 `[DOCS]`.

### Pitfall 31: Multiple Streamer.bot instances / profiles / OBS machines
Two SB processes using the same DA app collide on the callback port and (probably) on connections. Make the port configurable; document one instance per DA app; do not claim multi-account support (CONCERNS: not designed).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep `HttpListener` + `GetContext` in the action thread | Smallest diff from old code | Re-creates the unload hang and port-conflict bug | Never |
| `static` singleton for "already running" | Two lines | Useless across AppDomains/recompiles; false safety | Only as an additional in-domain guard, never the only one |
| Cache the access token string in a field for the loop | Simple | Expiry/rotation bugs on reconnect | Never; always call `GetValidAccessToken()` |
| `double` for amounts | Fewer conversions | Range-match and rounding bugs | Never |
| Log raw frames "just for debugging" | Fast diagnosis | PII + secrets in persisted logs | Only behind an explicit `daDebugRaw=true` that redacts tokens and warns loudly; default off |
| Hand-edit the `.sb` JSON once "just to test" | Quick | Unreproducible, GUID/reference drift | Never in the repo; scratch only |
| Inline HTML pages in C# strings | Single file | Escaping bugs, unreadable | OK if built from `/src` templates by the build script; single source |
| Depend on `System.Web` | `HttpUtility` convenience | Reference issues on import | Never (use `Uri`/`WebUtility`) |
| Broad `catch (Exception)` that continues | Loop "never dies" | Hides handler/protocol bugs; swallows aborts | Only at the outermost per-frame boundary with logging and rate limit |
| Real network in unit tests | Realistic | Flaky/can't run offline | Never; fake Centrifugo server + fake clock |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| DonationAlerts OAuth | Redirect URI differs by `/` or `localhost` vs `127.0.0.1` | Exact string from README; print it; normalize trailing slash for listener only |
| DonationAlerts OAuth | Scope string with commas/`+` confusion | Space-delimited, URL-encoded; the log shows `+` working `[OBSERVED]` |
| DonationAlerts REST | Ignoring 504/502 as "auth failed" | 5xx -> backoff; only 401 -> refresh; 400 `invalid_grant` -> NeedsAuth |
| DonationAlerts REST | Exceeding 60 req/min | Budget + cache user id/socket token |
| Centrifugo (legacy) | Using v3+ shapes/libraries | Hand-rolled minimal codec for `id/method/params/result` + `\n` batches |
| Centrifugo | Treating close code as generic | Parse close reason JSON `reconnect` flag (`3002` + `{"reconnect":false}` observed) |
| Centrifugo | Reusing channel tokens across connections | Re-POST `/centrifuge/subscribe` with the new `client` each time |
| Streamer.bot custom triggers | `TriggerCodeEvent(name, true)` from background thread | Dictionary overload with primitive values |
| Streamer.bot globals | Writing non-persisted, reading persisted (or vice versa) | One accessor per setting with a single declared slot + warning fallback |
| Streamer.bot import | Expecting `Find Refs`/globals to travel with the file | Explicit `references` list; Setup action; README table |
| GitHub API | No `User-Agent`, 100-item list, every Init | `/releases/latest`, UA, daily throttle |
| Twitch chat output | Echoing donor text with `!`/`/` prefixes or > 500 chars | Sanitize + truncate by text elements |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Unbounded reconnect rate | 250 attempts/min, 429/504 | Backoff + jitter + budget | Immediately on any persistent error |
| Reader does work inline (HTTP download, RunAction) | Missed pings, disconnects, delayed alerts | Reader -> bounded channel -> dispatcher | First audio donation or slow handler |
| Debug-logging every frame | MB-sized logs, disk I/O | State-only logging, rate limit | Hours of stream |
| Per-frame `JsonConvert` of whole message with exceptions for control | CPU spikes on batches | Split lines, parse lazily, ignore unknown | Burst of pushes (goal updates) |
| Unbounded temp audio folder | Disk fills | Janitor with age + size caps | Long-running machines |
| Unbounded dedupe set | Memory growth | LRU 1000-5000 | Months of uptime |
| `CPH.*` calls in tight loops | Cross-domain overhead | Batch/coalesce; call once per event | Thousands of events (not realistic here) |

Scale note: realistic load is a handful of events per minute for one streamer; the traps above are about *failure amplification*, not throughput.

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Callback accepts any `code` (no `state`) | Login CSRF links attacker's DA account (CONCERNS) | Random single-use `state`, pending-flow check |
| Callback bound to non-loopback / wildcard | LAN-reachable OAuth endpoint | `IPAddress.Loopback` only |
| Client secret/tokens in args, logs, `.sb`, error pages | Account takeover, support-chat leaks | Logging wrapper, no `SetArgument` of secrets, no defaults in `.sb` |
| Following audio URL to any host / unlimited size | SSRF-ish, disk/memory abuse | https, allow-list, caps, revalidated redirects |
| Echoing donor text raw into chat | Command injection, moderation-bypass, loops | Sanitize leading `!`,`/`,`.`; truncate; strip controls |
| Writing donor text into HTML pages or files unescaped | XSS in local pages | `WebUtility.HtmlEncode` on every interpolation |
| Persisting single-use `code` | Pointless secret at rest | Do not persist |
| Leaving refresh token after "Stop" | Long-lived credential | Provide `DA | Disconnect (forget tokens)`; README on revoking in DA |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Silent failures (port busy, bad secret, scope missing) logged at Debug | "Nothing happens" | Error-level one-liners in Russian with the exact fix |
| No status | Can't tell if watcher is alive after a drop | `DA | Status` action + non-persisted globals `daState`, `daLastEventAt`, `daLastErrorText` |
| Chat spam from status messages | Bot loops, moderation noise | Log only; chat only for donations if the user wires it |
| Contract rename without migration notes | Old actions silently dead | README mapping table old -> new |
| Setup requires reading code | Users give up | `DA | Setup` + `DA | Check config` actions with plain-language output |
| Restart after code edit unclear | Duplicate or dead workers | `DA | Restart`; document recompile drops the connection |
| English-only errors | Audience is Russian-speaking | All user-facing log lines and README in Russian; dev logs tagged, concise |

## "Looks Done But Isn't" Checklist

- [ ] **Shutdown:** closing Streamer.bot during (a) idle Running, (b) pending OAuth, (c) reconnect backoff each ends with `Cleaned up execute code instances` + `Streamer.bot exited` and no process in Task Manager within ~3 s.
- [ ] **Idempotent Start:** pressing Start 5x quickly and editing+saving the C# while running leaves exactly one `Subscribed` per channel.
- [ ] **No self-trigger:** the integration sends no chat message containing any command text; control actions are not bound to chat commands by default.
- [ ] **Reconnect:** killing the network for 2 min and restoring yields a bounded number of attempts (backoff), one resubscribe, no duplicate alerts.
- [ ] **Token expiry path:** forcing a 401 (edit stored access token to garbage) triggers exactly one refresh and continues; forcing `invalid_grant` ends in `NeedsAuth` with a clear message, no loop.
- [ ] **Dedupe:** replay the same donation JSON twice through the dispatcher -> one event; restart -> no replay of the last donation.
- [ ] **Culture:** full test suite green under `ru-RU` and `en-US`; `22,5` and `22.5` never leak into numeric args.
- [ ] **Amount contract:** exact-amount and range handler examples both fire from the simulate action.
- [ ] **Audio:** oversized/redirected/non-https URL is rejected; temp files cleaned on next Start.
- [ ] **Logs:** grep of a full session log for token/secret/e-mail/code returns nothing.
- [ ] **Import:** clean Streamer.bot profile (no old actions, no globals) -> import -> compile OK -> custom triggers visible after restart -> Setup -> Connect works.
- [ ] **Compile:** the *same* code compiles via the offline net48 harness and via SB "Compile" button (not only one of them).
- [ ] **Re-import:** second import with Overwrite on system items does not delete user example handlers or duplicate queues/groups.
- [ ] **Port conflict:** with port 8554 occupied, Connect fails in < 2 s with an Error naming the port.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Lingering process after close | LOW (user) / HIGH (if root cause unknown) | Kill via Task Manager once; capture log tail; compare markers; fix the blocked wait; add regression test |
| Duplicate workers | LOW | `DA | Stop`, wait for generation change, `Start`; if persists restart Streamer.bot |
| Revoked/invalid refresh token | LOW | `DA | Connect` again (new consent) |
| Secret leaked in a log/backup | MEDIUM | Rotate `client_secret` in DA app, revoke app authorization, re-Connect |
| Wrong redirect URI | LOW | Copy URI printed by `DA | Check config` into DA app form exactly |
| Missed donations during downtime | MEDIUM | Backfill (if enabled) else manual: DA dashboard history -> `DA | Simulate donation` with values |
| Broken `.sb` import | LOW | Re-export from repo build; compare with golden template; check Compiling Log |
| Reconnect storm hit rate limit | LOW | Wait 1-2 min; circuit breaker already stopped the loop; press Start |
| Imported over customised handlers | MEDIUM | Restore from Streamer.bot `backup\*.zip` (auto-backup at startup `[DOCS]`) |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 Process not exiting | B (A harness, H live) | Offline Dispose-while-blocked tests < 2 s; live log markers |
| 2 Duplicate workers / self-trigger | B, E, G | Offline double-Start test; two-instance generation test; live Start x5 + recompile |
| 3 Reconnect storm | D | Fake-clock policy tests; live network-cut |
| 4 Protocol generation / framing / keep-alive | D (+ live capture) | Fake Centrifugo server speaking legacy JSON incl. batched frames, `{}` pings, 3002 close; live frame-kind capture |
| 5 Per-client subscribe tokens | D | Fake server rejects stale token with 103; sequence test |
| 6 Dedupe + gaps | D (backfill decision), H | LRU/high-water unit tests; restart test |
| 7 Token lifecycle | C | Single-flight test; rotation/no-rotation test; huge `expires_in` test |
| 8 Callback listener | C | Port-busy test; favicon request test; wrong `state` test; non-elevated live test |
| 9 Compile environment | A, G | net48 compile in CI/local; SB Compile button |
| 10 `.sb` format | G (A golden file) | Round-trip decode, reference-integrity assertions, import on clean profile |
| 11 Secrets/PII | A, C, H | Log-grep test; README review |
| 12 Exceptions | B, D | Poisoned-frame test; fault injection |
| 13 Blocking reader/queues | D, E, G | Slow-handler simulation; queue assignment review |
| 14 CPH marshalling | E, A | Stub rejects non-primitives |
| 15 Static/Init/recompile | B | Recompile live test; Init idempotency test |
| 16 Globals | C, G, H | Check-config output tests |
| 17 Amount/currency/culture | E | ru-RU/en-US test matrix |
| 18 Hostile text | E | Table-driven sanitize tests (emoji, newline, `!cmd`, bidi) |
| 19 Test donations / simulate | E, H | Simulate action in checklist |
| 20 Audio | F | Local HTTP fixture with redirect/oversize/slow |
| 21 Update checker | F | Throttle + version-parse tests (`v1.2.3`, `1.2`, `ru-RU`) |
| 22 Goals | F | Change-only and zero-amount tests |
| 23 ClientWebSocket specifics | D | Close-hang and concurrent-send tests |
| 24 OS/browser hop | C, H | Manual |
| 25 Logging | A, D | Rate-limiter test |
| 26 Re-import | G, H | Second-import manual check |
| 27-31 Minor | D / B / H | Review during phase |

## Open questions to verify live (cannot be settled offline)

1. Does DonationAlerts' Centrifugo server send pings / require client `{"method":7}`? What idle timeout closes the socket? (Pitfall 4)
2. Real access-token TTL and whether refresh rotates the refresh token. (Pitfall 7)
3. Does a Streamer.bot import remap sub-action ids (`executeCodeId`) and re-resolve absolute `references`? (Pitfall 10, 9)
4. Does `HttpListener` on `127.0.0.1:<port>` start for a **non-elevated** Streamer.bot? (Pitfall 8) - or switch to `TcpListener` unconditionally (recommended).
5. Root cause of Shape 2 hang (unload completes, process stays). (Pitfall 1)
6. Does the dashboard "test alert" arrive on the API channel and with which `id`/fields? What does `message` hold for `audio`? Which host serves audio and in which format? (Pitfalls 18-20)
7. Does the legacy channel support recovery (`recoverable`, `seq`)? Is `amount_in_user_currency` always present? Is `created_at` UTC or Moscow time? (Pitfalls 6, 17)
8. Exact behaviour of `TriggerCodeEvent(name, true)` from a background thread vs the Dictionary overload (expected: Dictionary is required). (Pitfall 14)

## Sources

- [OBSERVED] User's Streamer.bot 1.0.7 install: `logs\log_20261014.log`, `logs\log_20261017.log`, `data\actions.json`, `data\settings.json` (compilerSettings, windowSettings), `Streamer.bot.exe.config`, `Microsoft.CodeAnalysis.CSharp.dll` 5.600.26, reflection over `Streamer.bot.Plugin.Interface.dll` (`IInlineInvokeProxy`) - HIGH.
- [OBSERVED] Decoded real exports (SB 1.0.4) in the session scratchpad (`sb\*.sb` -> `SBAE` + gzip JSON, version 23) - HIGH for the shape; ids/fields beyond those seen are not verified.
- [OBSERVED] Live probe of `wss://centrifugo.donationalerts.com/connection/websocket` with an invalid token: close 3002 `{"reason":"invalid token","reconnect":false}` - HIGH for that behaviour only.
- [DOCS] Streamer.bot docs repo (cloned; pages: lifecycle-methods, threading-best-practices, execute-csharp-code, custom-methods, import-export, triggers guide incl. Custom Triggers, actions/queues guide, variables guide, backup, TriggerCodeEvent/RegisterCustomTrigger, C# changelog notes) - https://docs.streamer.bot/api/csharp/guide/lifecycle-methods , https://docs.streamer.bot/api/csharp/guide/threading-best-practices , https://docs.streamer.bot/api/sub-actions/core/csharp/execute-csharp-code , https://docs.streamer.bot/api/csharp/recipes/visual-studio-code - MEDIUM-HIGH (several pages marked "missing documentation": custom DLLs, HttpClient).
- [DOCS] DonationAlerts API documentation (OAuth, scopes, Centrifugo connect/subscribe, donation/goal resources, 60 req/min) - https://www.donationalerts.com/apidoc - MEDIUM (dated, thin; some statements internally inconsistent, e.g. "3 scopes" listing six).
- [DOCS] Centrifugo client protocol (current/v3 docs, for contrast and for ping/batching conventions) - https://centrifugal.dev/docs/transports/client_protocol , https://centrifugal.dev/docs/3/transports/client_protocol - MEDIUM; legacy-protocol specifics are `[HYPOTHESIS]` where noted.
- [WEB] DonationAlerts realtime walkthrough (fields, duplicates warning, `username` null) - https://dev.to/fedor-pasynkov/real-time-donationalerts-notifications-with-python-oauth-websockets-3jep - LOW-MEDIUM (single author, no reconnect/ping coverage).
- [WEB] HttpListener URL ACL / prefix rules (CodeProject, Octopus, sisk docs) - LOW-MEDIUM; contradicted in part by the local observation that `127.0.0.1:8554` started.
- Project context: `.planning/PROJECT.md`, `.planning/codebase/CONCERNS.md`, `.planning/codebase/INTEGRATIONS.md`.

---
*Pitfalls research for: Streamer.bot 1.0.x + DonationAlerts (OAuth + legacy Centrifugo) integration, brownfield rewrite*
*Researched: 2026-10-17*
