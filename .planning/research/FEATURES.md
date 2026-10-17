# Feature Research

**Domain:** Streamer.bot 1.0.x donation-platform integration (DonationAlerts, single `.sb` import, C# inline code)
**Researched:** 2026-10-17
**Confidence:** MEDIUM overall. Custom-trigger mechanics and the DonationAlerts payload come from official docs (HIGH). Argument names of Streamer.bot's built-in donation integrations are undocumented ("This section is missing documentation"), so the comparison against them is MEDIUM/LOW. A few payload details are undocumented or unverified and are listed under "Verify live".

## Verdicts on the key questions

1. **Custom triggers instead of name-based handler actions: YES, replace.** `CPH.RegisterCustomTrigger(triggerName, eventName, string[] categories)` registers a trigger shown under Triggers > Custom (nested by `categories`). It is fired with `CPH.TriggerCodeEvent(eventName, Dictionary<string,object> args)` or `TriggerCodeEvent(eventName, string json)`. This is the same mechanism Streamer.bot's own integrations use. The user attaches the trigger to any number of actions in the UI, with no naming convention and no `ActionExists` probing. The docs say custom triggers must be re-registered on every boot, so register in `Init()` and enable "Pre-compile on application start" for that Execute Code sub-action. A trigger only appears in the UI after the code has run once.
2. **Fire with the dictionary overload, never the default `TriggerCodeEvent(eventName)`.** The default has `useArgs = true` and passes the calling action's variables. That would leak the Start action's arguments into user actions. The old fork's pattern (`CPH.SetArgument` then `RunAction`) shares mutable state between back-to-back donations. A per-event dictionary gives each triggered action its own immutable argument set.
3. **Reacting by amount is done inside the user's action, not by the trigger.** Custom code events have no trigger filter/range. Built-in Range filters exist only for built-in triggers such as cheers. The If/Else sub-action supports only Equals, Not Equals, Contains, Regex Match, Less Than, Greater Than (both exclusive, no `>=`), Does Not Exist, Is Null or Empty. Auto Type (default on) makes `100` numeric. The doc warns that without it "15" < "2". So:
   - Exact amount: If `%amount%` Equals `100` AND `%currency%` Equals `RUB`.
   - Range: If `%amount%` Greater Than `99` AND Less Than `501`. Exclusive bounds are awkward with decimals, so ship helper arguments (`amountFloor`) and a worked example.
   - Currency-agnostic tiers: compare `%amountMain%`.
4. **Do not use exact-amount named actions (`DonationHandler_<amount>`) as the contract.** Keep this only as a documented pattern the user can build with Run Action.

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| One-file `.sb` import with every action, code and variable stub; every action has a name and description | Pally/Tiltify extensions and all community extensions install by drag-and-drop import | MEDIUM | Export-format risk. Needs reproducible build/validate. Depends on the real 1.0.x schema |
| Custom trigger "DonationAlerts > Donation" fired once per donation | Built-in Streamlabs/StreamElements/Ko-fi/Tiltify-style integrations all expose a trigger that user actions attach to | MEDIUM | `RegisterCustomTrigger` in `Init()` plus `TriggerCodeEvent` with a dictionary. Register category as `["DonationAlerts"]` |
| Documented, stable donation argument set (see contract below) | Users write `%amount%`, `%donorName%` in sub-actions. Naming churn breaks their setups | LOW-MEDIUM | Parse the invariant-culture decimal. Publish types in README |
| One-click OAuth connect (`DA | Connect`): opens browser, local callback, stores tokens, success page | Built-in integrations use Connect buttons. Tiltify makes users run "Get Access Token" once | MEDIUM | CSRF `state`, port-busy and timeout errors, no secrets in logs. Already planned in PROJECT.md |
| Minimal user setup: only `daClientId` and `daClientSecret` (plus documented redirect URI) | Fewer variables means fewer support questions. Old fork required a long list of `da*` globals | LOW | Everything else has a code default. Hardcode scopes. The redirect URI default must match what the user registers in the DA app |
| Start / Stop / Restart actions, idempotent | Every extension has Connect/Disconnect. Pally has Connect/Heartbeat/Disconnected | MEDIUM | Depends on lifecycle design. Repeated Start must not duplicate connections |
| Auto-start on launch (Streamer.bot Started trigger plus `Init()` precompile), toggled by a global (default on) | Built-in integrations have "auto connect on startup". Pally docs tell users to enable Auto Connect | LOW | Needs a refreshed-token path so it works unattended |
| Auto reconnect with backoff, token refresh, heartbeat | Pally ships a manual heartbeat action because the platform needs one. Users expect "set and forget" | MEDIUM-HIGH | Already in Active requirements. Core value is exactly-once delivery |
| Exactly-once delivery (dedupe by donation `id` across reconnects) | Tiltify keeps `donationIdList` of the last 5 ids. Duplicate donations trigger double thank-yous and double rewards | LOW-MEDIUM | Bounded in-memory set (e.g. last 100-500 ids). Persistence across restarts is optional |
| Test Donation action (no real payment) | Tiltify reviewers asked for it. Streamer.bot has "Test Trigger". Without it users cannot verify setup | MEDIUM | `DA | Test Donation` fires the same trigger with synthetic data and `isTest = true`. Takes optional args (amount, currency, donor, message, type). Must use the identical code path as real events |
| Status feedback | Pally uses client Status = Open. Users otherwise cannot tell whether it works | LOW-MEDIUM | Log lines (no PII/secrets), a `daStatus` global (`connected`/`connecting`/`auth_error`/`stopped`) and optionally a toast. Confirm `CPH.ShowToastNotification` exists before promising it |
| Goal progress trigger "DonationAlerts > Goal Updated" with arguments | Kept by user request. DA exposes `$goals:goal_<id>` | MEDIUM | Dedupe by content (id, raised, goal, active, title). Do not hash volatile fields such as `reason` |
| Audio (voice) donations: expose the URL, and optionally download to a local file | Users asked for TTS/audio playback. DA `message_type` can be `audio`, and `message` then holds the audio URL (per old fork, MEDIUM) | MEDIUM | Opt-in download. Timeout, size limit, https + host check, temp cleanup. Always set `audioUrl`. Set `audioPath` only when downloaded |
| Update checker: at most once per day, non-blocking, failure-silent | Kept by user request | LOW | Store last-check time in a global. Run on a background task. Compare semantic versions. Skip drafts/prereleases |
| Russian README: install, variables, start/stop, verify, troubleshoot, secrets warning | Audience is Russian-speaking. `.sb` exports/backups contain secrets | LOW | Include the amount-routing recipe and the argument table |
| Clean shutdown (no lingering `Streamer.bot.exe`) | Core value, user-confirmed bug | HIGH | Cancellation tokens everywhere. Use supported lifecycle hooks. Needs live verification |

### Donation argument contract (recommended)

The Streamer.bot convention is camelCase. Use bare, unambiguous names, because per-event dictionary args cannot collide with other actions' args. Set every key on every event (empty string/0/false when absent) so `%x%` never prints literally.

| Argument | Type | Source field | Notes |
|----------|------|--------------|-------|
| `donationId` | int/string | `id` | Dedupe key. Also useful for logging |
| `donorName` | string | `username` | The donor's display name. Fall back to a localized "Anonymous" when empty. **Do not use DA `name`**: in the raw payload it is a constant label (`'Donations'`), not the donor. The old fork exposed it as `daDonationName` |
| `message` | string | `message` when `message_type == "text"` | Empty for audio donations |
| `messageType` | string | `message_type` | `text` or `audio` |
| `isAudio` | bool | derived | Lets If/Else branch without string compares |
| `amount` | decimal | `amount` | Original amount in donor's currency, invariant-culture number |
| `currency` | string | `currency` | ISO 4217 (RUB, USD, EUR...) |
| `amountMain` | decimal | `amount_in_user_currency` | Amount in the streamer's main currency. **Undocumented in the official docs**, but present in the raw payload and in the third-party `@donation-alerts/events` types (MEDIUM). If missing, set 0 and `hasAmountMain = false` rather than guessing |
| `amountFloor` | int | derived | `floor(amount)`. Makes exact-amount/range If/Else easier because the UI has no `>=` |
| `amountText` | string | derived | e.g. `100 RUB`. Handy for chat messages |
| `audioUrl` | string | `message` when audio | Always set for audio donations |
| `audioPath` | string | downloaded file | Only when download is enabled and succeeded |
| `isShown` | bool | `is_shown` | Optional, low value |
| `createdAt` | string | `created_at` | Documented as `YYYY-MM-DD HH.MM.SS`. Time zone unknown (verify). Pass through verbatim |
| `isTest` | bool | Streamer.bot convention | `true` from the Test Donation action. Same name as the general `isTest` variable |
| `daSource` / `eventSource` | string | constant | Optional. Identifies the integration if the user mixes several donation sources |

Not exposed: `payin_system`, `recipient*`, `created_at_ts`, `shown_at_ts`. They are undocumented and the DA library docs say not to depend on them.

Goal arguments (documented fields of `$goals:goal_<id>`): `goalId`, `goalTitle`, `goalCurrency`, `goalStartAmount`, `goalRaised` (`raised_amount`, includes the start amount), `goalTarget` (`goal_amount`), `goalIsActive` (`is_active` is an integer), `goalStartedAt`, `goalExpiresAt` (nullable), plus derived `goalPercent`. The old fork mislabelled these as `current`/`target`. Do not carry those names over.

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Pre-built example actions (disabled by default): "On Donation - thank you in chat", "Route by amount (If/Else)", "Play audio donation" | Tiltify's best feature is its documented If/Else routing recipe. Shipping it saves new users from the biggest learning curve | LOW-MEDIUM | Ship disabled so test donations never post to public chat unexpectedly. Needs the trigger attached in the export (verify schema) |
| Lifecycle triggers: `Connected`, `Disconnected`, `Authorization Failed` (re-auth needed) | Lets users wire their own OBS/toast/chat alerts for status. Built-in integrations show this only in the UI | LOW | Cheap once the trigger infrastructure exists. Fire only on state changes, not every retry |
| "Goal Reached" derived trigger (fires once when `raised >= target`) | Users commonly want a celebration action. DA only sends progress updates | MEDIUM | Needs transition detection and its own dedupe. Persist `lastReachedGoalId` so restarts do not re-fire |
| Chat-safe message argument (`messageSafe`) | Echoing a donor message to chat can run Twitch commands (`/ban`, `/timeout`, `!command`) with broadcaster rights. Few integrations protect against it | LOW | Strip leading `/`, `.`, `!` and control characters. At minimum document the risk in the README (do that in v1) |
| Missed-donation catch-up after reconnect via REST `GET /alerts/donations` (scope `oauth-donation-index`) | Donations arriving during a drop are not lost | HIGH | Conflicts with "exactly once" if done naively. Needs dedupe and a "do not replay history on first start" rule. Defer |
| Persisted dedupe across Streamer.bot restarts (last N ids in a global var) | Prevents replay if DA redelivers after a restart | LOW-MEDIUM | Optional. Bounded list |
| Per-event dedicated action queue guidance | Concurrent donations are processed in order, and a long TTS action does not block other actions | LOW | README plus setting the queue on the example actions |
| Throttled, quiet update notice: log plus optional toast, chat announcement off by default | The old fork posts in public chat on every Init | LOW | Announce each new version once |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Name-based dispatch (`DonationHandler_<amount>`, `_Default`, `_After`, `_GoalHandler`) | Old fork behavior; "exact amount" intuitive | Hidden naming convention, one handler per amount, float formatting traps ("100" vs "100.0"), races with shared args, brittle on rename. Clean break was decided | Custom trigger plus If/Else routing in the user's action. Ship an example |
| Built-in chat thank-you message, TTS, OBS control | "Works out of the box" | Reimplements what Streamer.bot sub-actions already do, hard-codes language/format, risks public chat spam during tests, and widens the code surface | Expose arguments; ship disabled example actions |
| Own currency conversion through an external FX API | Multi-currency thresholds | Extra dependency, rate drift, network failures, wrong money values | Use DA's `amount_in_user_currency` as `amountMain`, and always expose original `amount` + `currency` |
| Profanity/moderation filter on messages | Safety | Language-specific, unreliable, false confidence | Provide `messageSafe` (command-stripping only). Leave moderation to the user |
| REST polling fallback loop in parallel with the websocket | "Redundancy" | Doubles delivery paths and breaks exactly-once | Reconnect with backoff, optionally add one-shot catch-up later |
| Helper process / tray app / background service | Easier async work | Contradicts PROJECT.md constraints and causes lingering-process issues | In-process C# with cancellation tokens |
| Requesting extra OAuth scopes (`oauth-custom_alert-store`, `oauth-poll-subscribe`, `oauth-donation-index`) in v1 | "Might need later" | Larger permission prompt, larger blast radius if a token leaks | Request only `oauth-user-show`, `oauth-donation-subscribe`, `oauth-goal-subscribe`. Add scopes when a feature needs them |
| Exposing raw JSON blobs (`daDonationRaw`) and PII/frames in logs | Debugging | Leaks donor data into logs and exports | Opt-in debug flag that redacts tokens and message text |
| Large configuration surface (many `da*` globals for timing/retries) | Flexibility | Setup friction, support burden | Constants in code. Expose only: client id, secret, redirect URI (advanced), autostart, download audio, update check |
| Backward-compat shim for old `da*` argument names | Smooth upgrade | Explicitly out of scope; doubles contract maintenance | Document the migration table in README |
| Public chat announcement of updates | Visibility | Viewers see broadcaster-only chores | Log/toast |
| Poll/other DA event types in v1 | Completeness | Not requested, extra scope | Future |

## Feature Dependencies

```
Single .sb export format knowledge (validated)
    └──requires──> Everything below (nothing can ship without it)

Lifecycle core (idempotent Start/Stop, cancellation, Init()/Started trigger)
    └──requires──> Realtime connection (heartbeat, reconnect, subscribe confirm)
                       └──requires──> OAuth connect + token storage + refresh (401 path)
                                          └──requires──> Minimal settings (clientId/secret/redirect)

Realtime connection ──produces──> Donation events ──requires──> Dedupe by id
    └──feeds──> Custom trigger registration (Init) + TriggerCodeEvent(dictionary)
                    ├──feeds──> Donation argument contract
                    │              ├──enhances──> Amount routing example (amountFloor, amountMain)
                    │              └──enhances──> Chat-safe message
                    ├──feeds──> Test Donation action (same code path, isTest)
                    └──feeds──> Goal Updated trigger ──enhances──> Goal Reached trigger

Audio donation (messageType=audio) ──requires──> Donation contract
    └──optionally requires──> Audio download (timeout, size limit, host check, cleanup)

Status feedback (log/global/toast) ──enhances──> Lifecycle triggers (Connected/Disconnected/AuthFailed)

Update checker ── independent (needs only daily throttle global)

Catch-up via REST ──conflicts──> Exactly-once unless dedupe-by-id and no-history-on-first-start exist
Name-based dispatch ──conflicts──> Custom triggers (do not keep both)
```

### Dependency Notes

- **Test Donation requires the real trigger path.** If it takes a different code path, it proves nothing about real events. Build one `DispatchDonation(Donation)` method that both the websocket handler and the test action call.
- **Dedupe sits before dispatch.** The test action bypasses dedupe or uses unique synthetic ids.
- **Auto-start requires token refresh at startup.** A stale access token on launch must refresh, not fail.
- **Goal Reached requires Goal Updated plus persisted state.** Otherwise a restart refires a reached goal.
- **Example actions require the trigger to be attachable in the export.** If the code-event trigger type cannot be embedded in the `.sb`, ship examples without the trigger and tell the user to add it from Custom > DonationAlerts. This is the biggest open packaging question.
- **Audio playback requires downloaded file persistence.** The local file must outlive the action that plays it, so cleanup is by age/at start, not immediately after dispatch.

## MVP Definition

### Launch With (v1)

- [ ] Single `.sb`: Connect, Start, Stop, Restart, Test Donation, Update Check, Init/auto-start, with descriptions
- [ ] OAuth connect with state validation, token storage and refresh
- [ ] Reliable realtime connection with heartbeat, backoff, resubscribe, clean shutdown
- [ ] Custom trigger `Donation` with the documented argument contract; dedupe by id; per-event dictionary args
- [ ] Custom trigger `Goal Updated` with documented goal args; content-based dedupe
- [ ] Test Donation action (text and audio variants) using the real dispatch path
- [ ] Status via log plus `daStatus` global; auth-failed surfaced
- [ ] Optional audio download with guards and cleanup
- [ ] Daily non-blocking update check; logs plus optional toast
- [ ] Russian README with the amount-routing recipe, argument table, secrets warning, troubleshooting
- [ ] Manual test checklist for the user to run live

### Add After Validation (v1.x)

- [ ] Example actions (disabled): thank-you in chat, amount router, play audio. Trigger: packaging question resolved
- [ ] Lifecycle triggers Connected/Disconnected/Authorization Failed. Trigger: users ask for status alerts
- [ ] `messageSafe` argument. Trigger: users echo messages to chat (README warning goes in v1)
- [ ] Goal Reached trigger. Trigger: users ask for goal celebrations
- [ ] Persisted dedupe across restarts

### Future Consideration (v2+)

- [ ] REST catch-up of missed donations (needs a replay policy)
- [ ] Poll events (`oauth-poll-subscribe`)
- [ ] Custom alert sending (`oauth-custom_alert-store`)

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Donation custom trigger plus argument contract | HIGH | MEDIUM | P1 |
| Exactly-once (dedupe) | HIGH | LOW | P1 |
| OAuth connect and refresh | HIGH | MEDIUM | P1 |
| Realtime reliability and clean shutdown | HIGH | HIGH | P1 |
| Single `.sb` import | HIGH | MEDIUM | P1 |
| Test Donation action | HIGH | MEDIUM | P1 |
| Status feedback (log/global) | HIGH | LOW | P1 |
| Auto-start on launch | HIGH | LOW | P1 |
| Goal Updated trigger | MEDIUM | MEDIUM | P1 (kept by user) |
| Audio download | MEDIUM | MEDIUM | P1 (kept by user) |
| Update checker (daily, quiet) | LOW-MEDIUM | LOW | P1 (kept by user) |
| Russian README plus amount recipe | HIGH | LOW | P1 |
| Example actions | HIGH | LOW-MEDIUM | P2 |
| Lifecycle triggers | MEDIUM | LOW | P2 |
| `messageSafe` | MEDIUM | LOW | P2 |
| Goal Reached | MEDIUM | MEDIUM | P2 |
| Persisted dedupe | LOW | LOW-MEDIUM | P3 |
| REST catch-up | MEDIUM | HIGH | P3 |

## Competitor Feature Analysis

| Feature | Streamer.bot built-ins (Streamlabs, StreamElements, Ko-fi, Patreon, TipeeeStream, Treatstream...) | Tiltify extension (v2.1) | Pally.gg extension | Our Approach |
|---------|------|------|------|------|
| Delivery | In-app integration, trigger per event type | Polling timer every 2s, not websocket | Streamer.bot websocket client plus a heartbeat action every 50s | Websocket (Centrifugo), in-process |
| Setup | Connect in Integrations UI (docs for most variables say "missing documentation") | Import, create app, paste id/secret into an action, run "Get Access Token", enable a timer | Import, edit API key in client settings, adjust a client index in code if order differs | Import, fill 2 variables, run Connect once |
| Reacting by amount | Trigger filters where the platform supports them | If/Else sub-actions (highest to lowest) or C# `RunAction` | Sub-actions after the C# step | If/Else on `%amount%`/`%currency%` in the user's action, with a shipped recipe |
| Argument names | Platform-specific | `donationId`, `donorName`, `donorAmount` (USD), `donorComment` | `pallyMessage`, `displayName`, `grossAmountInCents` | Documented camelCase set including currency and main-currency amount |
| Dedupe | Handled internally | Last 5 ids global | None noted | Bounded id set |
| Test | Test Trigger (generic) | Not confirmed | None described | Dedicated Test Donation action |
| Status | UI status/log | Token refresh check | Client Status = Open | Log, `daStatus` global, optional lifecycle triggers |
| Auto start | Built-in | Timer must be enabled by hand | Auto Connect checkbox | Started trigger plus `Init()` precompile |
| SAMMI "Donation Triggers" (Streamlabs/StreamElements, not DonationAlerts) | Creates trigger buttons per donation exposing username and amount | | | Equivalent pattern: one trigger per event type, minimal args |

I found no existing DonationAlerts integration for Streamer.bot, SAMMI, Lumia or Touch Portal. Those searches returned nothing relevant, so this project has no direct community competitor to match.

## Verify live (not confirmable from docs)

| Item | Why it matters |
|------|----------------|
| Exact `.sb` representation of a Custom Code Event trigger attached to an action | Determines whether examples and the main action can be shipped pre-wired |
| `message_type` values and where the audio URL lives (`message`) | Documented only as `text` or `audio`. URL location comes from old fork behavior |
| `amount_in_user_currency` always present, and the streamer's main currency code | Official docs do not list it. The profile does not return a main-currency field, so `mainCurrency` may have to be a user setting or stay unlabelled |
| `created_at` time zone | Documented format only |
| `CPH.ShowToastNotification` availability in 1.0.x | Only matters for the optional toast |
| Whether `TriggerCodeEvent(string, Dictionary<string,object>)` preserves numeric types for If/Else Auto Type | The method page is inconsistent (shows a `bool useArgs` example not matching the listed overloads). Test on the real client |
| Test Trigger on a custom code event: what arguments it carries | Not documented, so ship a dedicated Test Donation action |

## Sources

- Streamer.bot RegisterCustomTrigger: https://docs.streamer.bot/api/csharp/methods/core/triggers/register-custom-trigger (HIGH, official; notes `Init()` and precompile, added in 0.2.0)
- Streamer.bot TriggerCodeEvent: https://docs.streamer.bot/api/csharp/methods/core/triggers/trigger-code-event (HIGH on overload list, page inconsistent on `useArgs`)
- Custom Code Event: https://docs.streamer.bot/api/triggers/custom/code-event and https://docs.streamer.bot/api/triggers/custom/custom-code-event (HIGH)
- Trigger Custom Event sub-action: https://docs.streamer.bot/api/sub-actions/core/triggers/custom-event-trigger (HIGH)
- Triggers guide (Range/Text filters, Test Trigger, Refresh Triggers): https://docs.streamer.bot/guide/core/triggers (HIGH)
- If/Else sub-action operators and Auto Type: https://docs.streamer.bot/api/sub-actions/core/logic/if-else (HIGH)
- Test trigger and `isTest`: https://docs.streamer.bot/api/triggers/core/test (HIGH)
- DonationAlerts API docs (scopes, `$alerts:donation_<id>`, `$goals:goal_<id>`, profile, custom alert): https://donationalerts.com/apidoc (HIGH, official)
- `@donation-alerts/events` raw donation types (`amount_in_user_currency`, `name: 'Donations'`, `reason`): https://cdn.jsdelivr.net/npm/@donation-alerts/events@4.0.0/README.md (MEDIUM, third-party typing, "undocumented, may change")
- `@donation-alerts/api` (raw donation fields, goals only via realtime): https://cdn.jsdelivr.net/npm/@donation-alerts/api@4.0.0/README.md (MEDIUM)
- Tiltify extension: https://extensions.streamer.bot/t/tiltify-integration/250 (HIGH for what it states)
- Pally.gg extension: https://extensions.streamer.bot/t/pally-gg-donation-integration/1142 (HIGH for what it states)
- Streamer.bot built-in integration pages (StreamElements, Streamlabs, Ko-fi, TipeeeStream): "missing documentation", so no argument lists were available (LOW)
- Old fork payload mapping: `integration.cs` lines 470-527 and 947-1041 (local, HIGH for current behavior, includes bugs noted above)
- Research-plan/cache seam was not used. Findings came from direct WebFetch/WebSearch and were not stored in the research cache.

---
*Feature research for: Streamer.bot DonationAlerts integration*
*Researched: 2026-10-17*
