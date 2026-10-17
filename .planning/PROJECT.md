# Streamer.bot DonationAlerts Integration

## What This Is

A DonationAlerts integration for Streamer.bot 1.0.x that a streamer installs with a single `.sb` import, configures with a few global variables, and starts with one action. After that, real-time donations and goal progress arrive in Streamer.bot as clearly named arguments and triggers. The streamer can then react by amount, post to chat, drive OBS/TTS and handle multi-currency donations. This is a full rewrite of a raw, buggy fork. Backward compatibility with the old fork is not required.

## Core Value

Once started, every DonationAlerts donation reliably reaches Streamer.bot exactly once with correct data. Closing Streamer.bot leaves nothing running: no lingering `Streamer.bot.exe`, sockets or workers.

## Requirements

### Validated

<!-- Capabilities the current fork already attempts. They exist in code but are buggy and will be rewritten, not kept as-is. -->

- ✓ OAuth 2.0 authorization-code flow against DonationAlerts with local `HttpListener` callback — existing (has CSRF/state, port-in-use and null-response bugs)
- ✓ Token persistence in Streamer.bot globals with refresh-token renewal — existing (no refresh on reconnect)
- ✓ Centrifugo WebSocket subscription to donation and goal channels — existing (blocking, leaky, no keep-alive)
- ✓ Export of donation/goal payloads to Streamer.bot arguments and dispatch to handler actions — existing (contract to be redesigned)
- ✓ Optional donation audio download to temp — existing (no timeout/cleanup)
- ✓ GitHub release update checker with chat announcement — existing (runs on every Init, unthrottled)

### Active

- [ ] Audit the existing implementation against the real Streamer.bot 1.0.x execution model and the current official DonationAlerts API docs, and record the findings
- [ ] Rewrite the integration as a clean, single-file Streamer.bot C# implementation, without legacy contract compatibility
- [ ] Reliable OAuth connect: `state` validation, clear errors (port busy, bad credentials, timeout), no secrets in logs
- [ ] Reliable realtime connection: keep-alive/heartbeat, reconnect with backoff, token refresh on 401 during reconnect, verified subscribe confirmation
- [ ] Donations delivered exactly once (deduplicated by id across reconnects), with a new, clearly named argument contract that supports:
  - reacting by exact amount and by amount ranges
  - chat messages (donor name, message, amount, currency)
  - OBS/TTS use (message text, audio file path when audio download is enabled)
  - multi-currency (original amount + currency, plus amount in the streamer's main currency)
- [ ] Goal progress events with deduplication
- [ ] Optional audio download with timeout, size limit, host/scheme check and temp cleanup
- [ ] Update checker throttled (at most once per day) and non-blocking
- [ ] Correct lifecycle: start/stop is idempotent; repeated start/stop never creates duplicate connections or workers; app shutdown cleanly cancels background work, sockets, listeners and timers so `Streamer.bot.exe` exits, using Streamer.bot-supported lifecycle mechanisms (not just a manual Stop)
- [ ] Single importable `.sb` file (real Streamer.bot 1.0.x export format) containing all needed actions, triggers, code and variable setup, with a clear name and description on every action
- [ ] Reproducible way to produce/validate the `.sb` from source in the repo
- [ ] Russian-language README: what it does, requirements, import, variables, start/stop/restart, verifying events, troubleshooting
- [ ] Test as much as practical offline (compile check, unit-testable parsing/dedupe/lifecycle logic), plus a manual test checklist the user runs in real Streamer.bot

### Out of Scope

- Backward compatibility with the old `DonationHandler_<amount>` / legacy `da*` argument contract — the user chose a clean break
- Streamer.bot 0.2.x support — targeting 1.0.x only
- Extra helper processes/services, killing processes, or hiding lingering processes as a shutdown workaround — the root cause must be fixed instead
- Heavy dependencies or build systems beyond what is needed to validate and package the script
- Discord release-announce workflow improvements — CI tooling, not part of the integration (may be touched only incidentally)

## Context

- Brownfield: codebase mapped in `.planning/codebase/` (ARCHITECTURE, STACK, INTEGRATIONS, CONCERNS, etc.). Current code: `integration.cs` (~1600 lines, compile error at line 89), `updateChecker.cs`, `successPage.html` (duplicate of embedded HTML), Russian `README.md`.
- CONCERNS.md lists many defects: missing semicolon, null `WebException.Response`, no OAuth `state`, PII/raw frames in logs, no donation dedupe, reconnect counter never resets, token not refreshed on reconnect, `Close()` races with blocked `ReceiveAsync`, unsynchronized shared state, swallowed exceptions, undisposed responses/sockets/WebClient, blocking sync-over-async, and no keep-alive.
- Shutdown symptom (user-confirmed): after closing Streamer.bot, `Streamer.bot.exe` itself stays in Task Manager. The likely cause is a long-running action thread or foreground thread blocked in `ReceiveAsync`/`Thread.Sleep`/`HttpListener` that is never cancelled on app exit. This must be verified against how Streamer.bot runs actions and shuts down.
- User's use cases: reactions by donation amount, chat thank-you messages, OBS control/TTS/audio playback, donations in multiple currencies.
- User has Streamer.bot installed locally and will run imports and manual test checklists. Offline verification must clearly state what was not tested live.
- Communicate with the user in Russian.

## Constraints

- **Platform**: Streamer.bot 1.0.x on Windows, C# inline code (`CPHInline`, `CPH` API), compiled by Streamer.bot (.NET Framework 4.8). Only APIs that Streamer.bot actually supports
- **Distribution**: One `.sb` import. It may not depend on extra files or processes, and must use the real export format (no invented fields)
- **Source of truth**: Current official DonationAlerts API documentation for OAuth, REST and Centrifugo
- **Dependencies**: Only what Streamer.bot provides (e.g. Newtonsoft.Json, BCL). No extra NuGet packages at runtime
- **Security**: Never log credentials/tokens/PII. Never commit secrets. The README warns that `.sb` exports/backups contain secrets
- **Repo hygiene**: Preserve unrelated local changes (e.g. staged deletions of `.github/ISSUE_TEMPLATE/*`, untracked `.idea/`, `.claude/`)
- **Honesty**: Do not claim behavior was verified unless it was actually tested

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Full rewrite with a new argument/trigger contract (clean break) | Old fork is raw and buggy, and the user doesn't need old setups to keep working | — Pending |
| Target Streamer.bot 1.0.x only | Allows the current export format and features (e.g. custom triggers) | — Pending |
| Keep goal events, audio download, update checker in v1 | User wants all of them | — Pending |
| README in Russian | Audience is Russian-speaking (DonationAlerts) | — Pending |
| Fix shutdown at the root via supported lifecycle hooks | User forbids workarounds such as killing or hiding processes | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-17 after initialization*
