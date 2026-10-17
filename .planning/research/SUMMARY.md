# Project Research Summary

**Project:** Streamer.bot DonationAlerts Integration (clean rewrite)
**Domain:** Streamer.bot 1.0.x inline-C# integration (DonationAlerts OAuth + legacy Centrifugo v2 WebSocket), shipped as one `.sb` file
**Researched:** 2026-10-17
**Confidence:** MEDIUM overall. Stack and `.sb` envelope are well sourced. Lifecycle and argument semantics in Streamer.bot are the main unknowns and need a live spike on 1.0.7.

## Executive Summary

This is a long-lived realtime client running inside Streamer.bot's C# inline-code sandbox. It must do OAuth in a browser, hold a Centrifugo WebSocket for hours, and deliver each donation to the streamer's actions exactly once. The expert pattern is a thin Streamer.bot adapter over one in-process, cancellable core: a `DaHost` singleton owns a lifetime CancellationTokenSource, runs all I/O as background `async Task` work, and fires custom code-event triggers from one dispatcher. Control actions call the host via `Execute C# Method`. The package is one `.sb`, generated and validated from source by a stdlib-only Python script.

Recommended approach: target Streamer.bot 1.0.7+ on .NET Framework 4.8.1 with C# 7.3-safe syntax; use `HttpClient`, `ClientWebSocket`, and a loopback callback listener; hand-roll the legacy Centrifugo v2 JSON protocol (no modern SDKs); replace name-based dispatch with a registered custom trigger `DonationAlerts: Donation` plus a documented argument set; build lifecycle first, since it is the core value and constrains all I/O.

Key risks: (1) `Streamer.bot.exe` lingering after close, root cause only hypothesized; (2) a hand-built `.sb` that imports but binds wrongly; (3) realtime protocol details (about 10-minute token TTL, ping behavior, batched frames, per-client subscribe tokens) that silently drop donations if mishandled; (4) reconnect storms against the 60 req/min REST limit.

## Key Findings

### Recommended Stack
- Single `Execute C# Code` sub-action (`DonationAlerts Runtime`, precompiled), .NET Framework 4.8.1, C# 7.3-safe, `Newtonsoft.Json` as shipped by Streamer.bot. No runtime NuGet.
- `HttpClient` (one static instance, explicit timeouts): replaces WebClient/HttpWebRequest.
- `ClientWebSocket`: Centrifugo; supports `Abort()` for shutdown.
- `HttpListener` on `127.0.0.1` (or `TcpListener` fallback): OAuth callback. Sources conflict on preference; see Open Questions.
- `CancellationTokenSource` + `Task.Run` + `SemaphoreSlim`: lifecycle and single-flight refresh.
- Streamer.bot APIs: `Get/SetGlobalVar`, `RegisterCustomTrigger` (in `Init`), `TriggerCodeEvent(name, Dictionary<string,object>)`, `TryGetArg`, `Log*`, `GetVersion`. Do not use `CPH.SendMessage` (Twitch-only; chat can re-trigger commands).
- Minimum Streamer.bot version to state: 1.0.7. Do not target 1.1.0-alpha.
- `.sb` envelope (decoded from real 1.0.4 exports): `base64("SBAE" + gzip(UTF-8 JSON))`, export version 23. Execute C# Code = type 99999 with `byteCode` = base64 of source text. Execute C# Method = type 99998 with `executeCodeId` = code sub-action `id`. Global values are never exported. Import overwrites same-named items.
- Python 3 stdlib builder with `--check` round-trip mode; `python -I`.

### Expected Features

**Table stakes:**
- One-file `.sb` import; every action named and described: Connect, Start, Stop, Restart, Status, Sign out, Auto-start, Update check, Setup, Simulate/Test Donation.
- Custom trigger `DonationAlerts: Donation` with a stable argument set; every key set on every event.
- Minimal setup: client id, client secret, redirect URI. Everything else has code defaults.
- OAuth connect with random `state`, clear port-busy/timeout/access-denied errors, no secrets in logs.
- Idempotent Start/Stop/Restart; auto-start on "Streamer.bot Started", toggled by a global (default on).
- Reconnect with jittered backoff, refresh on 401, heartbeat, resubscribe confirmation.
- Exactly-once by donation `id` (bounded set), per-event dictionary args.
- Goal trigger `DonationAlerts: Goal updated`, change-only dedupe (user-requested).
- Optional audio download with timeout, size cap, https and host check, temp cleanup (user-requested).
- Update checker: at most once per day, non-blocking, quiet, never in `Init`, never chat by default (user-requested).
- Russian README: install, variables, start/stop/restart, verify, troubleshoot, secrets warning.
- Clean shutdown with no lingering `Streamer.bot.exe` (core value).

**Argument contract (naming style unresolved, see Open Questions):** `donationId`, `donorName`, `message`, `messageType`, `isAudio`, `amount` (decimal, original), `currency` (ISO 4217), `amountMain` (from `amount_in_user_currency`; if absent set `hasAmountMain=false`, never fabricate), `amountFloor` (for range routing), `amountText`, `audioUrl`, `audioPath` (only when downloaded), `isShown`, `createdAt` (verbatim), `isTest`.

**Differentiators:** disabled example actions (thank-you, amount router with If/Else, audio playback; may ship without trigger binding); `messageSafe` (strip leading `!`, `/`, `.` and control/bidi chars); lifecycle triggers Connected/Disconnected/AuthFailed; Goal Reached once per goal id with persisted state; persisted dedupe high-water mark.

**Defer (v2+):** REST catch-up (needs `oauth-donation-index`, re-consent, replay policy); poll events; custom alert sending; any backward-compat shim for `DonationHandler_*` / `da*` (out of scope).

**Avoid:** name-based dispatch, built-in chat/TTS/OBS behavior, own FX conversion, profanity filter, parallel REST polling, helper processes, raw JSON/PII in logs, large `da*` config surface.

### Architecture Approach
One source file with sections, compiled as one code sub-action. `CPHInline` is a thin adapter: `Init()` attaches the host and registers triggers (no network, no threads); `Dispose()` detaches with a bounded quiesce. Public parameterless `bool` entry points are called by thin control actions via `Execute C# Method`. Logic is behind injected seams (clock, RNG, HTTP, host API) so it is testable offline.

Components: CPHInline adapter; DaHost (state machine `Stopped/Starting/Connecting/Running/Backoff/AuthRequired/Stopping/Disposed`, idempotent Start/Stop, single-owner guard); Config (validate, name bad variables); TokenStore + OAuthFlow (single-flight refresh, persist-before-use, ephemeral listener with state check); RestClient (typed results, 60 req/min budget); CentrifugoClient + Supervisor (session vs. reconnect loop, refresh on `ttl`, watchdog); EventMapper + Deduper (decimal, invariant culture, LRU); Dispatcher (bounded queue, single consumer, `TriggerCodeEvent`); AudioDownloader, UpdateChecker, Logger/Redactor.

Actions group `DonationAlerts`: `DA | Runtime` (host, precompiled, no triggers), `DA | Setup`, `DA | Connect`, `DA | Start`, `DA | Stop`, `DA | Restart`, `DA | Status`, `DA | Sign out`, `DA | Auto-start` (Started trigger), `DA | Update check`, `DA | Simulate donation`; disabled examples in a separate group. Deterministic UUIDv5 ids. Dedicated blocking queue only for user alert handlers.

Shutdown flow: `Closing services` -> `Dispose` -> cancel CTS -> abort socket/listener -> dispatcher exits -> bounded join (2-3 s) -> dispose HttpClient/timers -> `Unloading` -> `Cleaned up` -> `Streamer.bot exited`.

### Critical Pitfalls
1. **Process does not exit.** Return immediately from entry points; all I/O cancellable on pool; Dispose cancels, aborts, joins bounded, never throws. No `Thread.Sleep`, `.Result`, unbounded `GetResult`, raw `new Thread`, `async void`. Verify with close during Running, OAuth pending, and backoff.
2. **Duplicate workers** (repeated Start, recompile, Init autostart, chat-triggered Connect). One host sub-action; precompile; state machine under lock; cross-AppDomain guard (named Semaphore or generation global; test which works); never autostart from `Init`; no chat-bound control actions by default; single-flight OAuth.
3. **Reconnect storm** (old fork ~250 attempts/min vs 60/min limit). Jittered backoff 1 s to 60 s; reset only after stable session (60 s); classify errors (5xx/transport to backoff; 401 to one refresh; `invalid_grant`/403 to `AuthRequired`); circuit breaker; cache socket token; rate-limit logs.
4. **Centrifugo generation and TTL.** Legacy v2 JSON (`id/method/params/result`); bad token closes with 3002 and `{"reason":"invalid token","reconnect":false}`. Accumulate fragments; split on newline; ignore unknown shapes; refresh socket and channel tokens (methods 10 and 11) before `ttl`, or reconnect cleanly; honor `reconnect:false`; idle watchdog independent of ping format; subscribe channels independently.
5. **Exactly-once is not push-only.** Dedupe by `id` only, bounded LRU (at least 1000), atomic check-and-mark before dispatch; document as at-least-once plus dedupe; backfill is v2; do not order by `created_at` until timezone verified.
6. **`.sb` that imports but is wrong.** Golden export from the user's 1.0.7 as template; UUIDv5 ids; referential integrity; UTF-8 no BOM; round-trip diff; references generated and asserted; `autoRunAction` null.
7. **Secrets and PII.** `globals.db` holds the client secret in clear text and is in backups. One redacting logger; log ids/counts/states/status/exception type only; no secrets in args; persist only tokens, expiry, user id, scopes, optional high-water mark; grep test on session logs; README warns about backups, `globals.db`, and logs.

## Implications for Roadmap

### Phase 0: Foundations and live verification spikes
**Rationale:** Shutdown behavior, recompile behavior, trigger binding, and re-import remapping cannot be settled from docs and gate everything.
**Delivers:** Offline harness (net48 reference assemblies, xUnit linking the source, primitive-only `CPHInlineBase` stub, `#error version` probe); lifecycle spike (background task survives return; Dispose cancels and logs; open listener and pending receive at close; custom trigger plus dictionary args; precompile ordering); golden `.sb` exported from the user's 1.0.7 under `tools/golden/`.
**Avoids:** Pitfalls 1, 9, 10, 14, 15.

### Phase 1: Core skeleton and lifecycle
**Rationale:** Lifecycle is the core value and constrains all I/O.
**Delivers:** Adapter, DaHost state machine, idempotent Start/Stop/Restart, bounded Dispose, single-owner guard, Logger with redaction and lifecycle markers, Config with named-variable warnings, `DA | Setup` and `DA | Status` (no network yet).
**Avoids:** Pitfalls 1, 2, 11, 15, 16, 25.

### Phase 2: OAuth and token store
**Rationale:** Socket needs tokens; subscribe needs user id.
**Delivers:** `DA | Connect` with random `state`, ephemeral loopback callback, hard timeout, fast port-busy failure, HTML-encoded success page; TokenStore with single-flight refresh, persist-before-use, `invalid_grant` to `AuthRequired`; `DA | Sign out`.
**Avoids:** Pitfalls 7, 8, 24.

### Phase 3: Realtime, dedupe, dispatch, event contract
**Rationale:** Where exactly-once, reconnect, and the donation contract are proven.
**Delivers:** Legacy v2 codec; CentrifugoClient session; Supervisor with backoff and circuit breaker; watchdog and ping; TTL-driven refresh; EventMapper (decimal, invariant); Deduper LRU; Dispatcher; `DonationAlerts: Donation` and `DonationAlerts: Goal updated` triggers; `DA | Simulate donation` through the same dispatch path; `messageSafe`.
**Avoids:** Pitfalls 3, 4, 5, 6, 13, 14, 17, 18, 23.

### Phase 4: Optional features
**Delivers:** Goal change-only dedupe and percent with zero-divide guard; audio download (https, host allow-list, size cap, deadline, janitor, dispatch after file ready or timeout); daily update check (`/releases/latest`, persisted throttle, tolerant version parse).
**Avoids:** Pitfalls 20, 21, 22.

### Phase 5: Packaging, examples, build validation
**Delivers:** `tools/build_sb.py` with `--check`; deterministic ids; `DA | Runtime` plus control actions; disabled Russian-named examples in a separate group; reference list asserted against `using` set; re-import safety.
**Avoids:** Pitfalls 9, 10, 26.

### Phase 6: Russian README and manual checklist
**Delivers:** Russian README (install; variables with Persisted note; start/stop/restart; exact Redirect URI text; verify steps; migration table from `DonationHandler_*`; troubleshooting; secrets warning); manual checklist with the Streamer.bot markers and the live list below.
**Avoids:** Pitfalls 11, 19, 26.

### Phase ordering rationale
- Lifecycle and `.sb` feasibility first: they gate everything and cannot be verified offline.
- Auth before realtime: the socket needs fresh tokens.
- Realtime before extras: goals, audio, and simulate share the dispatch path.
- Packaging after code: ids and references are generated from it.
- Docs last, so they describe verified behavior.

### Research flags
- **Phase 0 (spike, needs the user's Streamer.bot 1.0.7):** shutdown, recompile, Dispose timing, dictionary-to-args typing, type-18002 binding, `executeCodeId` remap, Semaphore visibility, exit trigger existence.
- **Phase 2:** HttpListener vs TcpListener under non-elevated Streamer.bot.
- **Phase 3 (largest unknown):** ping and idle timeout, `expires`/`ttl`, `reason`/`seq` placement, batched frames, subscribe reply shape. Short frame-kind capture, no payloads.
- **Phase 4:** audio `message` format and host; needs one real audio donation.
- **Phase 5:** import remapping on a clean profile.
- **Standard patterns (skip research-phase):** Phase 1 offline logic, Phase 2 code exchange and refresh, Phase 6 docs.

## Verify live in Streamer.bot 1.0.7 (consolidated)

**Lifecycle and shutdown**
1. Does the `Streamer.bot Exiting` trigger (type 707) exist? Sources disagree.
2. Does `Dispose()` run on recompile mid-session, or only domain unload?
3. Close with Running, OAuth pending, and backoff: do `Cleaned up execute code instances` and `Streamer.bot exited` both appear, and is the process gone within about 3 s?
4. Reproduce the old hang deliberately (blocked Execute, pending accept) before claiming the fix.
5. Is a named kernel Semaphore shared across code sub-action AppDomains?
6. Does precompiled `Init()` run before the Started trigger? Does Delayed Start change it?
7. Do triggerless or disabled actions still precompile and serve `ExecuteMethod`?

**Triggers, args, `.sb`**
8. JSON for custom code-event trigger (type 18002): which field holds the event name (`eventName` or `name`)? Does it bind when precompiled?
9. Do dictionary keys appear as `%key%` exactly (dots, case, non-strings)?
10. Do numbers and booleans keep types for If/Else numeric compare via the Dictionary and JSON overloads?
11. Does an imported 18002 trigger fire when its event was never registered?
12. After re-import with deterministic ids, does `Execute C# Method` still resolve? Which name does `CPH.ExecuteMethod` expect?
13. Language version Streamer.bot compiles with (`#error version`).
14. Do absolute `C:\Windows\...` reference paths resolve on non-C: installs? Is manual Find Refs needed?

**DonationAlerts**
15. Does OAuth `state` echo on redirect? If not, fail clearly; do not skip CSRF.
16. Real `expires_in`; does refresh rotate the refresh token?
17. Real socket and channel `ttl`; do refresh methods 10 and 11 work before expiry?
18. Server pings or client-initiated `{"method":7}`? Idle timeout?
19. Do batched newline frames occur? Capture frame kinds and timing only.
20. Placement of `reason` and `seq`; is recovery enabled?
21. Does `HttpListener` on `127.0.0.1:<port>` start for non-elevated Streamer.bot?
22. Is `amount_in_user_currency` always present? Source of main currency?
23. `created_at`: UTC or local?
24. Anonymous donors: is `username` null? Is `name` a constant label?
25. Does dashboard "test alert" arrive on the API channel, with what `id`?
26. Audio donation: what does `message` hold; which host and format?
27. ru-RU locale: amount parsing and update checker.

**Packaging**
28. Clean-profile import: no warnings, compiles, triggers visible after restart, Setup and Connect work.
29. Re-import with Overwrite: user examples kept, no duplicate queues.

## Open Questions (source conflicts; resolve in the named spike)
1. **Exit trigger 707:** STACK says it exists; ARCHITECTURE and PITFALLS say only Started is documented and Dispose is the shutdown hook. Resolve via item 1. Design so Dispose alone is sufficient.
2. **TriggerCodeEvent overload:** STACK prefers JSON string; others require Dictionary. Default to Dictionary with primitives only; resolve via item 10.
3. **Listener:** STACK keeps HttpListener with Abort; PITFALLS recommends TcpListener; ARCHITECTURE keeps Tcp as fallback. Resolve via item 3. Default: TcpListener if inconclusive.
4. **Donor name:** FEATURES uses `username` (`name` is constant `'Donations'`); PITFALLS says use `name` for anonymous donors. Resolve via item 24; use `username` with localized "Anonymous" fallback until verified.
5. **Argument key naming:** FEATURES bare camelCase; ARCHITECTURE dotted `da.*`; PITFALLS `donation*`. Pick one before Phase 3.
6. **Parameters:** dedupe LRU 1000 (overlap across sources); backoff full jitter 1 s to 60 s (ARCHITECTURE/PITFALLS over STACK's 5 s).
7. **Dispose join budget:** 2 s bounded, total target about 3 s.
8. **Ping cadence:** STACK ~25 s with 5 s reply vs PITFALLS watchdog at 60-90 s silence. Decide after item 18.
9. **Scopes:** keep v1 to `oauth-user-show`, `oauth-donation-subscribe`, `oauth-goal-subscribe`; backfill is v2.
10. **Simulate naming:** "Test Donation" (FEATURES) vs "Simulate donation" (PITFALLS). Pick one; same dispatch path.
11. **Chat output:** examples post to chat (FEATURES) vs no chat from integration (STACK/ARCHITECTURE). Compatible if chat lives only in disabled user-side examples.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Runtime, envelope, REST/OAuth well sourced; language version and trigger JSON unverified |
| Features | MEDIUM | Trigger mechanics from official docs; built-in argument names undocumented; some payload fields third-party only |
| Architecture | MEDIUM | Patterns high; Streamer.bot internals inferred from logs and docs; spike needed |
| Pitfalls | HIGH for runtime and reconnect (observed in logs); MEDIUM for protocol (thin apidoc, one live probe); LOW for hypotheses |

**Overall:** MEDIUM. Design is sound; core value (clean shutdown) and `.sb` binding depend on a spike not yet run.

### Gaps
- Shutdown root cause: hypothesized; Phase 0.
- Type-18002 JSON shape: inferred; golden export in Phase 0.
- Protocol beyond apidoc (ping, TTL, batching, publication shape): Phase 3 frame-kind capture, shapes only.
- Undocumented payload fields (`amount_in_user_currency`, donor name semantics, audio `message`, test alert): optional with explicit unknown flags; never fabricate.
- Streamer.bot 1.1.x alpha may change argument semantics; target 1.0.7+.
- Offline results must be reported as offline only; live behavior stays "not tested live" until the user runs the checklist.

## Sources
- **HIGH:** Streamer.bot docs repo (lifecycle, threading, Execute C# Code/Method, RegisterCustomTrigger, TriggerCodeEvent, globals, import/export, changelogs 0.2.x to 1.0.7); decoded real 1.0.4 `.sb` exports; user's 1.0.7 install and logs (read-only); DonationAlerts apidoc https://www.donationalerts.com/apidoc.
- **MEDIUM:** working Centrifugo v2.2.1 DonationAlerts client (coldbrew-app/coldbrew); community DonationAlerts SDKs (StimulCross/donation-alerts, @donation-alerts/events, @donation-alerts/api, kash-ts/alerts-SDK); Centrifugo protocol docs (contrast only); Tiltify and Pally.gg extensions; PedroZamecki/streamerz (type codes; not copied).
- **LOW:** single-author DonationAlerts walkthrough; third-party HttpListener ACL articles (partly contradicted locally).

---
*Research completed: 2026-10-17*
*Ready for roadmap: yes, with the Phase 0 spikes and Open Questions treated as gating items.*
