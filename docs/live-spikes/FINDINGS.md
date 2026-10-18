# Live spike findings (Phase 1)

This file is the honest record of what was and was not observed in the user's Streamer.bot 1.0.7. It is machine-checked.

Validate it with:

```text
python -I tools/check_findings.py docs/live-spikes/FINDINGS.md
```

Status rules:

- Allowed statuses are exactly `not verified` (the default), `verified live` and `refuted live`.
- A live status (`verified live` or `refuted live`) needs a non-empty Evidence cell AND a Confirmed cell of the form `user YYYY-MM-DD` (the user's own dated confirmation). A `not verified` row has an empty Confirmed cell.
- There is no "verified offline" status. Facts established without running Streamer.bot go in `## Offline facts` together with the command that reproduces them. They never get a status.
- Evidence cells hold only masked marker lines produced by `tools/live_evidence.py` plus short quotes from the user's own report. Never paste raw Streamer.bot logs, account names, e-mail addresses or tokens.
- Every decision in `## Decisions` has an ID `SD-nn` and names the finding IDs that drive it.

## Session

- Date: pending
- Start time: pending
- HEAD commit: pending
- dist/spike.sb sha256-json: pending
- Streamer.bot version: pending

## Findings

| ID | Question | Status | Evidence | Confirmed | Decision |
|----|----------|--------|----------|-----------|----------|
| F1 | Does the exit trigger (event type 707) exist and fire? Order versus Dispose; is CPH usable there? | not verified |  |  | pending |
| F2 | Is Dispose called on recompile (old instance disposed, new one initialized)? | not verified |  |  | pending |
| F3 | Init versus Streamer.bot Started ordering | not verified |  |  | pending |
| F4 | JSON shape of the Custom Code Event trigger and of Execute C# Method | not verified |  |  | pending |
| F5 | Do dictionary argument values keep numeric and bool types in If/Else comparisons? | not verified |  |  | pending |
| F6 | Which C# language version does Streamer.bot compile with? | not verified |  |  | pending |
| F7 | Cross-AppDomain single-owner guard (named semaphore, non-persisted global, or static field) | not verified |  |  | pending |
| F8 | Loopback HttpListener and TcpListener bind and abort under non-elevated Streamer.bot | not verified |  |  | pending |
| F9 | Exact clean-shutdown log marker strings | not verified |  |  | pending |
| E1 | Which name form does CPH.ExecuteMethod expect? | not verified |  |  | pending |
| E2 | Does a triggerless action precompile and serve methods? | not verified |  |  | pending |
| E3 | Are deterministic ids preserved on import, and are duplicates created on re-import? | not verified |  |  | pending |
| E4 | Does CPH.TriggerCodeEvent work from a background pool thread? | not verified |  |  | pending |
| E5 | Does a background Task.Run survive the method return, and is the instance reused? | not verified |  |  | pending |
| E6 | Does CPH logging work inside Dispose? | not verified |  |  | pending |
| E7 | Does an imported custom trigger fire without RegisterCustomTrigger naming its event? | not verified |  |  | pending |
| E8 | Does the 1.0.7 action editor have a description field? | not verified |  |  | pending |
| SC3 | Does the spike .sb import into 1.0.7 without import or compile errors, and do the custom trigger and Execute C# Method bind and run? | not verified |  |  | pending |
| SC4a | Does closing Streamer.bot with a background task and a pending listener in cancel mode log `Cleaned up execute code instances` and `Streamer.bot exited`, leaving no Streamer.bot.exe? | not verified |  |  | pending |
| SC4b | Is the old shutdown hang reproduced on purpose with `SPIKE \| Block (repro)`? | not verified |  |  | pending |

## Offline facts

These were established without running Streamer.bot. They are not findings and carry no status. Each line gives the command that reproduces it.

- Offline: EventType values StreamerbotStarted = 706, StreamerbotExiting = 707, CustomEvent = 18001, CustomCodeEvent = 18002, plus the bundled Roslyn and Newtonsoft.Json file versions. Command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/verify-stub.ps1 -StreamerBotDir <Streamer.bot folder> -Facts`
- Offline: the compile gate rejects a broken line (CS1002) and APIs that net48 lacks (CS0246). Command: `python -I tools/compile_check.py --self-test`
- Offline: the golden export serializer round-trips byte for byte (golden fidelity). Command: `python -I -m unittest discover -s tools/tests -t tools`

## Prior observations (not evidence, no status)

Taken from the golden session recorded in `.planning/phases/01-live-spikes-build-harness/01-03-SUMMARY.md`. They are inputs for the live session, not findings:

- F1: in the user's trigger picker `Streamer.bot Exiting` was not offered (reported by the user in the golden session).
- E8: the decoded golden export has no `description` key on any action (the user's yes/no answer was ambiguous).
- F5: the golden If/Else results are confounded (input `spikeAmount.` with a stray dot, inputs written without `%`, decimal rendered as `22,5` in the ru culture). They say nothing yet about numeric or bool comparison and must be re-tested.

## Decisions

Filled from the research decision rules after the live session (plan 01-07). Rows use IDs `SD-nn` and cite finding IDs in "Driven by".

| ID | Decision | Driven by | Consequence |
|----|----------|-----------|-------------|
