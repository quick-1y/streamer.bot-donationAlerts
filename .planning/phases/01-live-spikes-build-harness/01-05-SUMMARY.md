---
phase: 01-live-spikes-build-harness
plan: 05
subsystem: infra
tags: [python, stdlib, streamer.bot, sb-format, golden-template, uuid5, unittest, spike-package]

requires:
  - phase: 01-live-spikes-build-harness
    provides: "01-02 codec and check/audit (tools/build_sb.py), 01-03 golden-1.0.7.sb, 01-04 spike/DaSpikeA.cs and DaSpikeB.cs, 01-01 compile gate"
provides:
  - "tools/build_sb.py build <package> [--golden] [--out] [--check]: golden templates + manifest -> canonical JSON -> .sb, with nine build-checks"
  - "tools/packages/spike.json: spike package manifest (25 actions built from 26 entries, queue DA Spike Queue, two code sub-actions)"
  - "Deterministic id scheme uuid5(manifest namespace, package/kind/name) with GUID remap for actions copied from the golden"
  - "tools/tests/test_build_sb.py BuildTests (33 tests, 82 in the suite) and a Package builder section in tools/README.md"
  - "dist/spike.sb (generated, gitignored, never committed)"
affects: [01-06, 01-07, phase-2, phase-6]

actuals:
  tokens: 15000
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Template-driven builder: deep-copy the golden object of each kind and override only keys it already has (set_existing); missing kind stops the build"
    - "verify_built returns '<check>: <detail>' findings so tests assert on the check name"
    - "Mutation tests prove each check fails on its own defect; disabling any single check makes its mutation test fail"

key-files:
  created:
    - tools/packages/spike.json
  modified:
    - tools/build_sb.py
    - tools/tests/test_build_sb.py
    - tools/README.md

key-decisions:
  - "expected_ids is a dict {stable name: id}; the ids check recomputes uuid5 from each name and compares the id set, so a changed or duplicated id is caught independently of the builder"
  - "build_model(manifest, templates, skipped=None) keeps the 2-tuple return; SKIP lines go into the optional skipped list"
  - "verify_built(model, json_bytes, ...) takes what read_sb returned for the written file and rebuilds in memory itself for the model and deterministic checks"
  - "A code sub-action may be embedded by at most one action (manifest validation), so code ids stay unique"
  - "Missing golden kind exits 1 (MissingTemplateError caught in the build command); other format/manifest errors exit 2"

patterns-established:
  - "Manifest sources are resolved with Path.resolve() and must stay under REPO_ROOT; the manifest is read with json.load only"
  - "Optional actions (optional: true) are the only ones skipped when a template kind is missing"

requirements-completed: [PKG-04]

plan_head_before: e5ce3be95443eb000df552625e72efc420324ea0
plan_head_after: e54576b03fdeba3f88e93b202dab779c40b3ec67
commits: 3

coverage:
  - id: D1
    description: "build subcommand writes dist/spike.sb from repo source and the golden; build --check prints PASS for roundtrip, model, bytecode, no-bom, deterministic, keysets, ids, refs, methods-exist (OFFLINE result; the file has NOT been imported into Streamer.bot)"
    requirement: PKG-04
    verification:
      - kind: integration
        ref: "python -I tools/build_sb.py build spike --check (exit 0, 9 PASS)"
        status: pass
      - kind: unit
        ref: "tools/tests/test_build_sb.py#BuildTests"
        status: pass
    human_judgment: false
  - id: D2
    description: "Key-set fidelity: every emitted object has the golden's key names and order; no invented fields; golden dump() fidelity"
    requirement: PKG-04
    verification:
      - kind: unit
        ref: "tools/tests/test_build_sb.py#BuildTests.test_keyset_mutation_added_key_gives_keysets_finding_for_every_object_kind"
        status: pass
      - kind: unit
        ref: "tools/tests/test_build_sb.py#BuildTests.test_golden_fidelity_dump_reproduces_golden_json"
        status: pass
    human_judgment: false
  - id: D3
    description: "Spike package manifest and embedded sources pass the offline compile gate"
    requirement: PKG-04
    verification:
      - kind: integration
        ref: "python -I tools/compile_check.py (3 passed, 0 failed)"
        status: pass
    human_judgment: false
  - id: D4
    description: "dist/spike.sb is accepted by Streamer.bot 1.0.7 on import and its code sub-actions compile there"
    requirement: PKG-04
    verification: []
    human_judgment: true
    rationale: "Nothing here was imported into Streamer.bot. Import acceptance, the C# compile inside Streamer.bot and the code sub-action references list are only observable in the live session (01-07 S1)."

duration: not measured (single session)
completed: 2026-10-18
status: complete
---

# Phase 1 Plan 05: Template-driven .sb builder Summary

**`python -I tools/build_sb.py build spike --check` builds `dist/spike.sb` (25 actions) from `spike/*.cs`, `tools/packages/spike.json` and the user's 1.0.7 golden, copying golden object shapes with uuid5 ids and proving round trip, key sets, ids, references and determinism; nothing was imported into Streamer.bot.**

## Performance

- **Tasks:** 3 (tracer, auto, auto with tests)
- **Files:** 1 created (`tools/packages/spike.json`), 3 modified (`tools/build_sb.py`, `tools/tests/test_build_sb.py`, `tools/README.md`)
- **Duration:** not measured

## Accomplishments

- `build <package> [--golden PATH] [--out PATH] [--check]` in `tools/build_sb.py`: `load_manifest` / `validate_manifest` (sources must resolve inside the repo, unknown action keys rejected), `Templates` (golden index), `stable_id`, `normalize_source`, `embed_source`, `set_existing`, `build_model`, `verify_built`.
- `python -I tools/build_sb.py build spike --check` exits 0 and prints `SKIP SPIKE | On exiting: golden lacks trigger:707`, `built dist/spike.sb actions=25 sha256-json=77445b94...`, and PASS for all nine build-checks. `check dist/spike.sb` exits 0 (0 failed); `audit dist/spike.sb` exits 0 (0 hard, 647 review notices from the key-inventory seed sets, as with the golden).
- Two builds give identical `.sb` bytes on this machine (checked by sha256 of the file for the 3-action tracer output, and by `test_two_builds_pack_to_identical_bytes_and_ids` for the full package); the decoded-JSON sha256 printed in the `built` line was the same across the re-runs.
- 33 new tests (`BuildTests`), suite total 82, all green. To show the tests are not vacuous, a scratch runner (session scratchpad, not committed) disabled each build-check in turn: for every check at least one named mutation test failed (roundtrip, model, bytecode, no-bom, deterministic x2, keysets x2, ids x2, refs x2, methods-exist).
- `python -I tools/compile_check.py` (default inputs) now compiles `spike/DaSpikeA.cs`, `spike/DaSpikeB.cs` and `tools/golden/GoldenRuntime.cs`: `compile_check: 3 passed, 0 failed`.
- `tools/README.md` has a "Package builder" section (commands, golden authority, what each check proves, determinism and zlib caveat, id scheme, known limits).

## Golden facts observed (assumption A4 settled)

Read from the decoded `golden-1.0.7.sb` (version 24, exportedFrom 1.0.7):

| Kind | Type | Key list (in file order) |
|------|------|--------------------------|
| Action | - | `id, queue, enabled, excludeFromHistory, excludeFromPending, name, group, alwaysRun, randomAction, concurrent, triggers, subActions, collapsedGroups` (no `description`) |
| Execute C# Code sub-action | 99999 | `name, description, references, byteCode, precompile, delayStart, saveResultToVariable, saveToVariable, id, weight, type, parentId, enabled, index` |
| Execute C# Method sub-action | 99998 | `executeCodeId, method, runOnUiThread, saveResultToVariable, saveToVariable, id, weight, type, parentId, enabled, index` (so `code_ref_key = executeCodeId`, `method_key = method`) |
| Trigger Streamer.bot Started | 706 | `id, type, enabled, exclusions` |
| Trigger Custom Code Event | 18002 | `name, eventName, id, type, enabled, exclusions` |
| Trigger Streamer.bot Exiting | 707 | not in the golden (picker did not offer it, 01-03) |
| Queue | - | `id, blocking, name` (golden queue `blocking: true`) |

- `index` is 0-based and dense per parent list. Top-level sub-actions have `parentId: null`; children of an If/Else branch container (99901 then / 99902 else) carry that container's id as `parentId`; the container itself has `parentId: null`.
- An action without a queue carries the null GUID `00000000-0000-0000-0000-000000000000` in `queue`.
- `weight` is written `0.0`. No `dump()` change was needed: `dump(json.loads(golden_json)) == golden_json` held from the start (01-02 `dump` already matches), and the fidelity tests lock it in.
- Spike package result: 26 manifest entries, 25 built actions; `SPIKE | On exiting` skipped because the golden has no 707 trigger. F1 for the exit trigger must be recorded from the 01-03 picker observation, as the plan states.

## Task Commits

1. **Task 1: end-to-end repo source to dist/spike.sb (tracer)** - `c063d04` (feat)
2. **Task 2: full spike manifest, golden action copies with GUID remap, remaining checks** - `47e873f` (feat)
3. **Task 3: builder tests and README section** - `e54576b` (test)

**Plan metadata:** committed separately (docs).

## Tracer feedback gate

Mode `end-of-phase`, tracer `<verify>` automated-only: after the Task 1 commit `python -I tools/build_sb.py build spike --check` (exit 0, all five Task 1 checks PASS) and `python -I tools/compile_check.py` (3 passed) were re-run, and execution continued to Task 2.

## TDD Gate Compliance

The plan type is `execute`; only Task 3 carries `tdd="true"`, and by the plan's own task order its tests follow the implementation of Tasks 1 and 2. There is therefore no RED commit and no RED evidence for this plan: no test was run against a missing implementation. The substitute evidence is the non-vacuity run described above (each check disabled, its mutation test fails). One commit `test(01-05)` carries the tests and README.

## Files Created/Modified

- `tools/build_sb.py` - build subcommand, manifest loading and validation, Templates, id helpers, build_model (plain and golden-copied actions), nine build-checks, `_cmd_build`
- `tools/packages/spike.json` - namespace `2d2b3ddb-9954-4395-a36f-e2f8ce1d0a64` (generated once, never change), 26 action entries, 2 code sources, queue `DA Spike Queue`
- `tools/tests/test_build_sb.py` - `BuildTests` appended; 01-02 tests unchanged
- `tools/README.md` - Package builder section

## Decisions Made

- See `key-decisions` in the frontmatter. Notably `verify_built` rebuilds from the manifest internally for the `model` and `deterministic` checks, so a caller only passes what `read_sb` returned.
- Exit code 1 for a missing required golden kind, as the plan's CLI line says; the other `SbFormatError` cases keep exit 2.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Stricter manifest validation than the plan lists**
- **Found during:** Task 1
- **Issue:** The plan asks for required-key validation and source containment (T-01-17, T-01-18). A typo in an action key, a duplicate action name, a code embedded twice or an `out` outside `dist/` would otherwise surface late or produce duplicate ids.
- **Fix:** `validate_manifest` rejects unknown action keys, duplicate names/keys, a code sub-action embedded more than once, a non-lowercase-UUID namespace, `golden` outside the repo, `out` outside `dist/`, and path-like package names. Tests cover these.
- **Files modified:** tools/build_sb.py, tools/tests/test_build_sb.py
- **Committed in:** c063d04, e54576b

**2. [Rule 2 - Missing Critical] Build refuses a golden with non-empty command/websocket/timer collections**
- **Found during:** Task 1
- **Issue:** The builder copies the golden envelope; a golden with commands or timers would silently ship them. The audit forbids them, but `build` did not enforce it.
- **Fix:** `build_model` raises `SbFormatError` if any of those collections is non-empty in the golden.
- **Committed in:** c063d04

**Total deviations:** 2 auto-fixed (both Rule 2). **Impact on plan:** no scope change; both sit inside the threat-model mitigations T-01-17/18/20.

## Issues Encountered

- The worktree shell wrapper refuses compound git commands and anything that mentions the `.git` directory in a command line, so git steps ran as separate plain calls. As a result the persisted plan ledger file (`gsd-plan-head-before-01-05`) could not be written; `commits` is measured with `git rev-list --count e5ce3be95443eb000df552625e72efc420324ea0..HEAD` = 3 before this SUMMARY commit, and `plan_head_before` is the base this worktree started from.
- Working-copy files are CRLF because of `core.autocrlf=true`; the first scripted multi-line replacement missed for that reason and was redone with the editor tool. Git normalizes line endings on commit (`LF will be replaced by CRLF` warnings).
- Carried over from 01-01: `tools/verify-stub.ps1` is still unexecuted.

## Hand-off notes for 01-06 / 01-07 (risks the builder cannot see)

1. **Golden handler inputs are inherited.** The three `SPIKE | On event (...)` actions are copies of the golden handler, including its If/Else `input` values `spikeAmount.` (stray dot), `spikeAmount` and `spikeFlag`, written without `%` signs (01-03 F5 notes). The built package therefore reproduces the confounded F5 test. The run sheet must have the user correct these inputs in the Streamer.bot UI (for example `%spikeAmount%` with `22,5` / `22.5` variants), or a later plan must add an input override to the builder (the manifest has no such field today and I did not invent one). The `SPIKE IF-*` lines from the imported package must not be read as F5 evidence before that.
2. **Code `references` list is the golden's** (`mscorlib.dll`, `System.Net.Http.dll`, `.\Newtonsoft.Json.dll`). `DaSpikeA.cs` uses `HttpListener`, `TcpListener` and `Stopwatch`, which live in System.dll, an assembly not in that list. The offline gate compiles against the whole net48 set and will not notice a missing reference. If the live import shows compile errors such as CS0246/CS0234 for those types, the references must be extended (UI, or a builder change in a later plan). This is an unverified risk, not a finding.
3. **Name collision with the golden-session actions.** `SPIKE | On event (dict)` also exists in the user's profile from the golden recipe (different ids). Run sheet S0 must delete the `GOLDEN |` / `SPIKE |` actions and `Golden Queue` before importing `dist/spike.sb`, otherwise two actions with the same name exist.
4. **No Exiting trigger.** `SPIKE | On exiting` is not in the package (SKIP line above); `SpikeOnExiting` stays reachable only through code.
5. `dist/spike.sb` is generated in this worktree only; it is gitignored and must be rebuilt in the merged checkout with `python -I tools/build_sb.py build spike --check`.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-01-17 mitigated (sources only from `codes[].source`, contained under the repo root, byteCode equals the normalized file, offline gate reads the same manifest); T-01-18 mitigated (`json.load` only, SbFormatError, exit 2); T-01-19 accepted (`dist/` ignored, `git ls-files dist` empty); T-01-20 mitigated (`set_existing`, keysets, refs, dangling golden id).

## User Setup Required

None for this plan. Importing `dist/spike.sb` into Streamer.bot is the live step in 01-07 (not done here).

## Next Phase Readiness

- 01-06 can document `python -I tools/build_sb.py build spike --check` and the import of `dist/spike.sb`; 01-07 owns the live import (S1) and its findings. Not verified here: import acceptance, the in-app compile, trigger binding, any runtime behavior.
- Phase 2-6 packages inherit the id scheme (`costly` to change after a user's first import) and the "only golden-backed kinds" rule; Comment, Send Message, range If/Else and Play Sound kinds are absent from the golden (01-03) and need a new golden export before a product package can use them.

## Self-Check: PASSED

- Files exist: `tools/build_sb.py`, `tools/packages/spike.json`, `tools/tests/test_build_sb.py`, `tools/README.md`; `dist/spike.sb` present locally and untracked (`git ls-files dist` empty).
- Commits `c063d04`, `47e873f`, `e54576b` are ancestors of HEAD; `git rev-list --count e5ce3be..HEAD` was 3 before this SUMMARY.
- Re-run after the last commit: `build spike --check` exit 0 (9 PASS), full unit suite 82 tests OK, `compile_check: 3 passed, 0 failed`.
- This covers offline checks only; no Streamer.bot import or live behavior is claimed.

---
*Phase: 01-live-spikes-build-harness*
*Completed: 2026-10-18*
