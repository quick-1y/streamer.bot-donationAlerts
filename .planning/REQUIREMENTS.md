# Requirements: Streamer.bot DonationAlerts Integration

**Defined:** 2026-10-17
**Core Value:** Once started, every DonationAlerts donation reliably reaches Streamer.bot exactly once with correct data. Closing Streamer.bot leaves nothing running: no lingering `Streamer.bot.exe`, sockets or workers.

## v1 Requirements

### Verification & Harness

- [ ] **VER-01**: Developer can compile-check the integration source offline (net48 + CPH stub) with one command
- [ ] **VER-02**: Pure logic (Centrifugo codec/frame splitter, event mapper, deduper, backoff, lifecycle state machine) is covered by offline unit tests that pass
- [ ] **VER-03**: Live spike results from the user's Streamer.bot 1.0.7 (shutdown behavior, Dispose/recompile, custom trigger binding, argument typing, golden `.sb` export) are recorded in the repo and the design follows them

### Lifecycle

- [ ] **LIFE-01**: User can start the connection with one action; the action returns immediately and the connection runs in the background
- [ ] **LIFE-02**: Repeated Start/Restart (and recompile/re-import) never creates a second connection or worker
- [ ] **LIFE-03**: User can stop the connection with one action; all sockets, listeners and background tasks end within ~3 s
- [ ] **LIFE-04**: Closing Streamer.bot in any integration state (running, connecting, OAuth pending, backoff) lets `Streamer.bot.exe` exit; the Streamer.bot log shows `Cleaned up execute code instances` and `Streamer.bot exited`
- [ ] **LIFE-05**: Integration auto-starts when Streamer.bot launches if already authorized (toggle global, default on)
- [ ] **LIFE-06**: User can see the current connection status (Status action and a status global)

### Configuration

- [ ] **CONF-01**: Only `daClientId` and `daClientSecret` are required; missing or invalid settings are reported naming the exact variable
- [ ] **CONF-02**: A Setup action creates missing variables with defaults and shows the exact redirect URI to register in the DonationAlerts app

### Authorization

- [ ] **AUTH-01**: User can authorize via a Connect action that opens the browser and completes OAuth with `state` validation, storing tokens
- [ ] **AUTH-02**: User gets a clear message for port busy, timeout, access denied and invalid client credentials
- [ ] **AUTH-03**: Access token is refreshed automatically (on expiry or 401, including during reconnect), single-flight, with the new refresh token persisted before use
- [ ] **AUTH-04**: User can sign out, which clears stored tokens and stops the connection
- [ ] **AUTH-05**: Credentials, tokens and personal data never appear in logs or event arguments

### Realtime Connection

- [ ] **CONN-01**: Integration subscribes to donation and goal channels, and treats a subscription as active only after the server confirms it
- [ ] **CONN-02**: Connection stays alive for hours (socket/channel token refresh by TTL, keep-alive or idle watchdog)
- [ ] **CONN-03**: Integration reconnects automatically with jittered backoff, stays under the DonationAlerts rate limit (60 req/min), and honors server `reconnect:false`
- [ ] **CONN-04**: Batched and fragmented WebSocket frames are parsed without dropping events

### Donation Events

- [ ] **EVT-01**: Each donation fires the custom trigger `DonationAlerts: Donation` exactly once, deduplicated by donation id across reconnects
- [ ] **EVT-02**: Donation trigger always provides every argument with `da` prefix: `daDonationId`, `daDonor`, `daMessage`, `daMessageSafe`, `daMessageType`, `daIsAudio`, `daAmount`, `daCurrency`, `daAmountMain`, `daHasAmountMain`, `daAmountFloor`, `daAmountText`, `daAudioUrl`, `daAudioPath`, `daCreatedAt`, `daIsTest`
- [ ] **EVT-03**: Amounts are parsed culture-invariantly, and numeric comparisons in If/Else (by exact amount and by range) work as documented
- [ ] **EVT-04**: `daMessageSafe` contains the donor message with chat-command prefixes (`/`, `!`, `.`) and control/bidi characters neutralized
- [ ] **EVT-05**: User can fire a test donation action that goes through the same dispatch path with `daIsTest=true`
- [ ] **EVT-06**: Status triggers fire on Connected, Disconnected and Authorization failed

### Goals

- [ ] **GOAL-01**: Goal progress fires `DonationAlerts: Goal updated` with `daGoal*` arguments (title, raised, target, percent, currency, active, dates) only when values change
- [ ] **GOAL-02**: `DonationAlerts: Goal reached` fires once per goal when the target is reached

### Audio

- [ ] **AUD-01**: When enabled, donation audio is downloaded (https + host check, size cap, timeout) and its path is provided in `daAudioPath` before the trigger fires (or empty on failure/timeout)
- [ ] **AUD-02**: Downloaded audio files are cleaned up automatically

### Updates

- [ ] **UPD-01**: Update check runs at most once per day, never blocks startup, and reports a new version in the log (no chat message by default)

### Packaging

- [ ] **PKG-01**: A single `.sb` file imports cleanly into Streamer.bot 1.0.7+ with all actions, triggers and code included
- [ ] **PKG-02**: Every action has a clear name and a description of its purpose and required configuration
- [ ] **PKG-03**: Disabled example actions are included: chat thank-you, amount-range router, audio playback
- [ ] **PKG-04**: The `.sb` is built and validated from repo source with one script (deterministic ids, round-trip check)

### Documentation

- [ ] **DOC-01**: Russian README covers what it does, requirements/compatibility, import, variables, start/stop/restart, verifying events, the argument list and troubleshooting
- [ ] **DOC-02**: A manual live-test checklist covers lifecycle/shutdown, reconnect, repeated start/stop, events and cleanup, and marks what was not tested live
- [ ] **DOC-03**: README warns that Streamer.bot backups, `globals.db` and logs can contain secrets

## v2 Requirements

### Reliability

- **REL-01**: Missed donations during a disconnect are fetched via REST and dispatched (needs `oauth-donation-index` scope, re-consent, replay policy)
- **REL-02**: Deduplication state persists across Streamer.bot restarts
- **REL-03**: Stored tokens encrypted with DPAPI

### Events

- **EVT2-01**: Poll events

## Out of Scope

| Feature | Reason |
|---------|--------|
| Compatibility with old `DonationHandler_*` actions / legacy `da*` args | User chose a clean break |
| Streamer.bot 0.2.x support | Targeting 1.0.7+ only |
| Built-in chat/TTS/OBS behavior in the integration itself | Belongs in user actions; only disabled examples ship |
| Own currency conversion | Use DonationAlerts `amount_in_user_currency` only; never fabricate |
| Helper processes, killing/hiding processes | Shutdown must be fixed at the root |
| Chat-bound control actions by default | Bot chat can re-trigger them (observed in old logs) |
| Profanity filter | Not requested; out of integration scope |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| (filled by roadmap) | | |

**Coverage:**
- v1 requirements: 38 total
- Mapped to phases: 0
- Unmapped: 38 ⚠️

---
*Requirements defined: 2026-10-17*
*Last updated: 2026-10-17 after initial definition*
