# Roadmap: Streamer.bot DonationAlerts Integration

## Overview

The roadmap starts by settling the Streamer.bot 1.0.7 unknowns that gate everything else. The user runs live spikes for shutdown, Dispose/recompile, custom trigger binding and argument typing, and provides a golden `.sb` export. This phase also delivers an offline compile harness and a `.sb` builder. Next comes a thin end-to-end walking skeleton: import, configure, authorize, start, a real donation reaches `DonationAlerts: Donation`, stop, and Streamer.bot exits cleanly. Later phases harden and extend that skeleton in vertical slices: resilience over hours and network drops, the full reaction-ready argument contract with goals and audio, then hands-free operation. The last phase ships the release `.sb`, Russian README and manual checklist.

Clean shutdown (no lingering `Streamer.bot.exe`) is the core value, so it is re-verified in every phase that adds I/O. Criteria tagged *(live: user confirms)* need the user's own run in Streamer.bot 1.0.7. They stay "not tested live" until the user reports the result. The live checks add up over the phases into the DOC-02 checklist.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Live Spikes & Build Harness** - Verify Streamer.bot 1.0.7 lifecycle/trigger/`.sb` behavior live; offline compile check and `.sb` builder
- [ ] **Phase 2: Walking Skeleton** - Import, Setup, Connect, Start, one real donation fires the trigger, Stop, clean exit
- [ ] **Phase 3: Resilient Connection** - Hours of uptime, reconnect with backoff, token refresh, no duplicate workers, offline test suite
- [ ] **Phase 4: Reaction-Ready Events** - Full `da*` donation contract, test donation, safe message, goals, audio download
- [ ] **Phase 5: Hands-Free Operation** - Auto-start, status and status triggers, clear auth errors, sign out, daily update check
- [ ] **Phase 6: Release Package & Russian Docs** - Release `.sb` with described actions and examples, Russian README, manual checklist

## Phase Details

### Phase 1: Live Spikes & Build Harness

**Goal**: Design decisions rest on behavior verified in the user's Streamer.bot 1.0.7. The source can be compile-checked offline and packaged from the repo into an importable `.sb`.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: VER-01, VER-03, PKG-04
**Success Criteria** (what must be TRUE):
  1. One documented command compile-checks the C# source offline against .NET Framework 4.8 reference assemblies and a CPH stub. It passes on clean source and fails on a deliberately broken line.
  2. A golden `.sb` exported from the user's Streamer.bot 1.0.7, with no secrets, is stored in the repo. One builder script produces a `.sb` from repo source with deterministic ids, and its check mode round-trips the output (decode, compare) with no differences.
  3. The spike `.sb` produced by the builder imports into Streamer.bot 1.0.7 without import or compile errors. Its custom trigger and `Execute C# Method` actions bind and run *(live: user confirms)*.
  4. The old shutdown hang is reproduced on purpose. With the spike's cancel-on-Dispose design, closing Streamer.bot while a background task and a pending listener are active logs `Cleaned up execute code instances` and `Streamer.bot exited`, and no `Streamer.bot.exe` stays in Task Manager *(live: user confirms)*.
  5. Spike findings are recorded in the repo, each marked "verified live" or "not verified": exit trigger existence, Dispose on recompile, Init vs Started ordering, custom trigger JSON shape, dictionary argument typing in If/Else, compiler language version, cross-AppDomain single-owner guard, and loopback listener under non-elevated Streamer.bot. The design decisions that follow from them are logged.

**Plans:** 6/7 plans executed

Plans:
**Wave 1**
- [x] 01-01-PLAN.md — Offline compile gate: net48 + CPH stub, self-test (CS1002/CS0246), stub drift check (wave 1)
- [x] 01-02-PLAN.md — `.sb` codec with bounded decode, plus decode/check/diff-ids/audit commands and tests (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 01-03-PLAN.md — Golden 1.0.7 export: Russian recipe, GoldenRuntime.cs, user export, audit, approved commit (wave 2, user checkpoints)
- [x] 01-04-PLAN.md — Spike sources DaSpikeA/DaSpikeB: cancel-on-Dispose host and probes, compile-checked (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 01-05-PLAN.md — Template-driven builder + spike manifest to dist/spike.sb with round-trip check (wave 3)
- [x] 01-06-PLAN.md — Evidence extractor, findings checker, FINDINGS skeleton, Russian run sheet (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*
- [ ] 01-07-PLAN.md — Live session in Streamer.bot 1.0.7 and recorded findings and decisions (wave 4, user checkpoint)

### Phase 2: Walking Skeleton

**Goal**: A streamer imports one `.sb`, sets two variables, authorizes, starts the connection, and sees a real donation fire `DonationAlerts: Donation`. Stopping the connection and closing Streamer.bot leaves nothing running.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: CONF-01, CONF-02, AUTH-01, AUTH-05, LIFE-01, LIFE-03, LIFE-04, CONN-01, EVT-01
**Success Criteria** (what must be TRUE):
  1. After the skeleton `.sb` is imported, `DA | Setup` creates missing variables with defaults and shows the exact redirect URI to register. Running Connect or Start with an empty `daClientId` or `daClientSecret` reports that exact variable name *(live: user confirms)*.
  2. `DA | Connect` opens the browser, completes OAuth with `state` validated, and stores tokens. A callback with a wrong or missing `state` is rejected *(offline test; live: user confirms the happy path)*.
  3. `DA | Start` returns immediately, and the log shows the donation and goal channel subscriptions as confirmed by the server. A real donation fires `DonationAlerts: Donation` exactly once; a DonationAlerts test alert also counts if the Phase 1 spike showed that it reaches the API channel. A repeated donation id is ignored *(offline dedupe test; live: user confirms)*.
  4. `DA | Stop` ends the socket, listener and background tasks within about 3 s. Closing Streamer.bot in each of the Running, Connecting and OAuth-pending states lets `Streamer.bot.exe` exit, with `Cleaned up execute code instances` and `Streamer.bot exited` in the log *(live: user confirms)*.
  5. The session log and the trigger arguments contain no client secret, access/refresh token or streamer account data, and the log contains no donor names or messages *(offline redaction tests; grep of the user's live log)*.

**Plans**: TBD

### Phase 3: Resilient Connection

**Goal**: Once started, the connection survives hours of uptime, network drops, token expiry and repeated start/restart/recompile. No donation is lost or duplicated, and DonationAlerts is never hammered with requests.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: CONN-02, CONN-03, CONN-04, AUTH-03, LIFE-02, VER-02
**Success Criteria** (what must be TRUE):
  1. After several hours of running, well past the socket/channel token TTL, the integration is still subscribed and fires `DonationAlerts: Donation` for a new donation *(live: user confirms long run)*.
  2. After a network drop or a server-side disconnect, the integration reconnects by itself with jittered backoff and stays under 60 REST requests per minute. It stops retrying when the server sends `reconnect:false`. A donation redelivered after a reconnect fires only once, and closing Streamer.bot during backoff still lets the process exit *(offline tests; live: user drops the network and confirms)*.
  3. On access-token expiry or a 401, including during reconnect, the integration refreshes once and concurrent callers share that refresh. It saves the new refresh token before using it and continues without user action. An `invalid_grant` response moves it into an authorization-required state instead of retry looping *(offline tests; live: user confirms recovery after expiry)*.
  4. Pressing Start or Restart repeatedly, recompiling the code, or re-importing the `.sb` never creates a second connection. The log shows one session, and each donation fires the trigger once *(live: user confirms)*.
  5. One command runs the offline unit tests for the Centrifugo codec and frame splitter (including batched and fragmented frames), event mapper, deduper, backoff and lifecycle state machine, and all of them pass.

**Plans**: TBD

### Phase 4: Reaction-Ready Events

**Goal**: The streamer can build amount reactions, chat thank-yous, TTS/OBS/audio playback and multi-currency handling from a complete, documented argument set, and receives goal progress events.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: EVT-02, EVT-03, EVT-04, EVT-05, GOAL-01, GOAL-02, AUD-01, AUD-02
**Success Criteria** (what must be TRUE):
  1. The test donation action fires `DonationAlerts: Donation` through the same dispatch path with `daIsTest=true`. Every listed `da*` argument is present on every event: unknown values are empty or false, and a missing main-currency amount gives `daHasAmountMain=false` instead of an invented value *(offline tests; live: user confirms arguments)*.
  2. If/Else sub-actions on `daAmount` / `daAmountFloor` route donations as documented, by exact value and by range, including decimal amounts under a ru-RU system locale *(offline parsing tests; live: user confirms If/Else routing)*.
  3. In `daMessageSafe`, leading `/`, `!` and `.` command prefixes and control/bidi characters are neutralized, so posting it to chat cannot trigger bot commands *(offline tests)*.
  4. `DonationAlerts: Goal updated` fires with `daGoal*` arguments only when goal values change. `DonationAlerts: Goal reached` fires once per goal when its target is reached *(offline tests; live: user confirms with a real goal)*.
  5. With audio download enabled, the donation audio file is on disk (https, allowed host, size cap, timeout) and its path is in `daAudioPath` when the trigger fires; the path is empty on failure or timeout. Old files are cleaned up automatically, and closing Streamer.bot during a download still exits cleanly *(offline tests; live: user confirms with one real audio donation)*.

**Plans**: TBD

### Phase 5: Hands-Free Operation

**Goal**: The integration can run on autopilot. It starts with Streamer.bot, reports its state, explains authorization problems clearly, signs out cleanly and checks for updates quietly.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: LIFE-05, LIFE-06, EVT-06, AUTH-02, AUTH-04, UPD-01
**Success Criteria** (what must be TRUE):
  1. When already authorized, launching Streamer.bot starts the connection automatically. A toggle global controls this (default on, and turning it off disables it). Closing Streamer.bot right after launch still exits cleanly *(live: user confirms)*.
  2. `DA | Status` and the status global show the current state (stopped, connecting, running, backoff, authorization required). The Connected, Disconnected and Authorization failed triggers fire on the matching transitions *(live: user confirms)*.
  3. Connect shows a clear, specific message for each of: port busy, timeout, access denied, invalid client credentials *(offline tests; live: user confirms at least port busy and access denied)*.
  4. `DA | Sign out` clears stored tokens and stops the connection, and a later Start reports that authorization is required *(live: user confirms)*.
  5. The update check runs at most once per day and never delays startup. A newer version is reported only in the log, never in chat. Closing Streamer.bot during a check still exits cleanly *(offline throttle tests; live: user confirms)*.

**Plans**: TBD

### Phase 6: Release Package & Russian Docs

**Goal**: A Russian-speaking streamer can install, configure, verify and troubleshoot the integration using one `.sb` and the README, and the manual checklist backs every live claim.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: PKG-01, PKG-02, PKG-03, DOC-01, DOC-02, DOC-03
**Success Criteria** (what must be TRUE):
  1. The release `.sb` imports into a clean Streamer.bot 1.0.7 profile without warnings, compiles, and shows all actions and triggers, and Setup and Connect work. Re-importing with Overwrite keeps the user's own actions and creates no duplicate queues or workers *(live: user confirms)*.
  2. Every action shows a clear name and a description of its purpose and required configuration. The disabled example actions (chat thank-you, amount-range router, audio playback) are included and work once the user enables them *(builder check; live: user confirms the examples)*.
  3. The Russian README explains:
     - what the integration does
     - requirements and compatibility (1.0.7+)
     - import and variables
     - start/stop/restart
     - how to verify events
     - the full argument list
     - troubleshooting

     It also warns that Streamer.bot backups, `globals.db` and logs can contain secrets.
  4. The manual live-test checklist covers lifecycle/shutdown, reconnect, repeated start/stop, events and cleanup. The user has run it on the release build, and each item is marked passed, failed or not tested live.

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Live Spikes & Build Harness | 6/7 | In Progress | - |
| 2. Walking Skeleton | 0/TBD | Not started | - |
| 3. Resilient Connection | 0/TBD | Not started | - |
| 4. Reaction-Ready Events | 0/TBD | Not started | - |
| 5. Hands-Free Operation | 0/TBD | Not started | - |
| 6. Release Package & Russian Docs | 0/TBD | Not started | - |
