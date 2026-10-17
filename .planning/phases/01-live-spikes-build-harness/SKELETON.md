# Walking Skeleton: Streamer.bot DonationAlerts Integration

**Phase:** 1
**Generated:** 2026-10-17

> Scope note (orchestrator decision): Phase 2 delivers the end-to-end *integration* walking skeleton (import, setup, authorize, start, real donation fires the trigger, stop, clean exit). For Phase 1 the skeleton is the thinnest end-to-end *build/verify pipeline*. No Phase 2 integration scope is pulled in, and there is no database or UI.

## Capability Proven End-to-End

A C# code sub-action written in the repo passes the offline net48 gate, is packaged by the builder into `dist/spike.sb` using templates from the user's own 1.0.7 export, imports into the user's Streamer.bot 1.0.7 and runs. Closing Streamer.bot afterwards leaves no `Streamer.bot.exe` (live: user confirms).

Pipeline, with the plans that build each stage:

| Stage | Command / artifact | Plan |
|---|---|---|
| Repo source | `spike/DaSpikeA.cs`, `spike/DaSpikeB.cs` (one file = one code sub-action, `#if EXTERNAL_EDITOR` header) | 01-04 |
| Offline compile gate | `python -I tools/compile_check.py` (net48 reference assemblies + CPH stub, verdict by exit code + CS codes) | 01-01 |
| Format authority | `tools/golden/golden-1.0.7.sb` (user export, audited, human-approved) | 01-02, 01-03 |
| Builder | `python -I tools/build_sb.py build spike --check` producing `dist/spike.sb` | 01-02, 01-05 |
| Import + run | User imports `dist/spike.sb`, compiles, runs actions (RUNSHEET S1) | 01-06, 01-07 |
| Shutdown | Close with cancel-on-Dispose, check Task Manager (RUNSHEET S4) | 01-06, 01-07 |
| Evidence + record | `python -I tools/live_evidence.py ...` feeding `docs/live-spikes/FINDINGS.md`, gated by `python -I tools/check_findings.py` | 01-06, 01-07 |

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Runtime platform | Streamer.bot 1.0.x inline C# (`CPHInline`), compiled by Streamer.bot on .NET Framework 4.8 | Project constraint; nothing else runs in the streamer's setup |
| Source layout | One `.cs` per code sub-action, each compiled alone; `spike/` now, `src/` for product code from Phase 2; dev tooling under `tools/`; live docs under `docs/live-spikes/` | Matches Streamer.bot's per-sub-action compilation; keeps dev-only files out of the package |
| Class shape | `#if EXTERNAL_EDITOR public class CPHInline : CPHInlineBase #else public class CPHInline #endif` | Vendor-documented pattern; the same file is valid offline and in Streamer.bot |
| Offline verification | .NET SDK 9 `dotnet build` of a net48 csproj with `Microsoft.NETFramework.ReferenceAssemblies.net48` 1.0.3, Newtonsoft.Json 13.0.3, and a hand-written stub of the reflected 1.0.7 `IInlineInvokeProxy`; LangVersion 7.3 until live finding F6 | Executed in research; rejects net48-absent APIs; locale-independent verdicts |
| Package format authority | The user's golden 1.0.7 export; the builder deep-copies template objects and overrides only manifest-owned fields; key sets checked against the golden | CLAUDE.md "real export format, no invented fields" |
| Ids | `uuid5(namespace, "<package>/<kind>/<stable name>")` (rated costly: later packages inherit it) | Deterministic builds; stable identity across re-imports |
| Tooling language | Python 3 standard library, always run with `python -I`; tests with `unittest` | No installs; byte-exact serializer proven on official samples |
| Lifecycle design under test | Work in `Task.Run` owned by the instance; one `CancellationTokenSource`; `Dispose()` cancels, aborts listeners and sockets, bounded wait, never throws. Dispose-only shutdown; exit trigger 707 optional pending F1 | STATE.md decision; root-cause fix for the old shutdown hang |
| Event dispatch under test | Custom code-event triggers (`RegisterCustomTrigger` / `TriggerCodeEvent`) | Replaces the old name-based action dispatch; binding and typing verified live (F4, F5, E4, E7) |
| Honesty and privacy | Findings statuses `not verified` / `verified live` / `refuted live`, machine-checked; evidence is masked marker lines only | CLAUDE.md honesty and "never log PII" constraints made mechanical |

## Stack Touched in Phase 1

- [ ] Project scaffold: `tools/` gate, builder and tests, `spike/` sources, `.gitignore` / `.gitattributes` additions
- [ ] Routing: not applicable (no HTTP app). The equivalent is Streamer.bot actions bound to methods and custom triggers in the spike package
- [ ] Database: not applicable. The equivalent "real read and write" is the golden export read by the builder and the `.sb` written by it, plus non-persisted Streamer.bot globals in the ownership probe
- [ ] UI: not applicable. The user's interaction is importing and clicking spike actions in Streamer.bot (RUNSHEET)
- [ ] Deployment: a documented local full-pipeline run: `python -I tools/compile_check.py && python -I -m unittest discover -s tools/tests -t tools && python -I tools/build_sb.py build spike --check`, then import `dist/spike.sb` into Streamer.bot 1.0.7

## Out of Scope (Deferred to Later Slices)

- DonationAlerts OAuth, REST, Centrifugo, tokens (Phase 2)
- The product `DA | ...` actions, settings, argument contract (Phases 2 and 4)
- VER-02 unit tests for codec/mapper/deduper/backoff/state machine, and any xUnit project (Phase 3)
- Rewriting or deleting the legacy `integration.cs` / `updateChecker.cs` (Phase 2); they are never inputs of the gate
- Release `.sb`, Russian README, example actions, manual checklist (Phase 6)
- Raising the gate's LangVersion beyond what F6 reports, and pinning the Roslyn 5.x toolset (needs a .NET 10 SDK)

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this pipeline without changing its architectural decisions:

- Phase 2: import one product `.sb`, set two variables, authorize, start, and see a real donation fire `DonationAlerts: Donation`; stop and close cleanly
- Phase 3: the connection survives hours, drops, token expiry and repeated start/recompile, with an offline test suite
- Phase 4: the full `da*` argument contract, test donation, safe message, goals, audio download
- Phase 5: auto-start, status triggers, clear auth errors, sign out, daily update check
- Phase 6: release `.sb` with described actions and examples, Russian README, manual live checklist
