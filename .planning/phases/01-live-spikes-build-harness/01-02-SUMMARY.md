---
phase: 01-live-spikes-build-harness
plan: 02
subsystem: infra
tags: [python, stdlib, streamer.bot, sb-format, gzip, base64, audit, unittest]

requires: []
provides:
  - "tools/build_sb.py: byte-exact .sb codec (dump/pack/unpack_bytes/unpack/read_sb), bounded decoder, decode/check/diff-ids/audit subcommands"
  - "tools/tests/test_build_sb.py: 49 unittest cases runnable with python -I -m unittest discover -s tools/tests -t tools"
  - ".gitattributes: *.sb -text so core.autocrlf=true never rewrites .sb files"
affects: [01-03 golden vetting, 01-05 template-driven build subcommand, 01-07 finding E3 (diff-ids)]

actuals:
  tokens: 10350
  tasks: 3
  commits: 6

plan_head_before: af80be78751b5d67adc37da6b0fd383cded0a83c
plan_head_after: c48fb6886baae5292f8451ec3ea6bb94bded7cbc

tech-stack:
  added: []
  patterns:
    - "Python stdlib only dev tooling under tools/; untrusted .sb parsed with strict base64, bounded zlib.decompressobj(31), json.loads only"
    - "Audit findings print rule, JSON path and a 3-char masked preview; REVIEW/INFO values are redacted when they match a secret rule"
    - "Exit codes: 0 ok, 1 findings, 2 format/usage error (ERROR <message> on stderr)"

key-files:
  created:
    - tools/build_sb.py
    - tools/tests/__init__.py
    - tools/tests/test_build_sb.py
    - .gitattributes
  modified: []

key-decisions:
  - "Unknown keys relative to the 1.0.4 sample key sets are REVIEW lines only; explicit allow-listing is the human decision in 01-03"
  - "audit --allow-prefix extends DEFAULT_ALLOWED_PREFIXES rather than replacing them"
  - "long-token ignores runs with 2 or fewer distinct characters (divider lines such as ==== or ----) to limit false positives in decoded C# source"
  - "A byteCode that cannot be decoded is a HARD structure:bytecode-undecodable finding in audit, because it cannot be audited"
  - "user-profile-path rule accepts one or more backslashes or slashes so C# escaped paths (C:\\\\Users\\\\) are caught"

patterns-established:
  - "TDD per task with RED commit (failing tests) then GREEN commit, RED evidence validated by gsd-tools check tdd-red-evidence"
  - "Tests import build_sb as a top-level module; discovery uses -s tools/tests -t tools with tools/tests/__init__.py"

requirements-completed: [PKG-04]

coverage:
  - id: D1
    description: "Byte-exact .sb codec: base64(SBAE + gzip(CRLF 2-space JSON, no BOM)) round trips; non-ASCII stays unescaped"
    requirement: "PKG-04"
    verification:
      - kind: unit
        ref: "tools/tests/test_build_sb.py#CodecTests"
        status: pass
      - kind: other
        ref: "scratchpad smoke over 3 official 1.0.4 samples: canonical_roundtrip=True for all"
        status: pass
    human_judgment: false
  - id: D2
    description: "Bounded decoder rejects cap+1, trailing data, truncated stream, missing magic, bad base64, BOM, invalid UTF-8, oversize input; exact cap accepted; decode/check/audit exit 2"
    requirement: "PKG-04"
    verification:
      - kind: unit
        ref: "tools/tests/test_build_sb.py#LimitTests"
        status: pass
    human_judgment: false
  - id: D3
    description: "check and diff-ids subcommands: canonical round trip, id format and uniqueness, GUID reference resolution, byteCode decodability, id comparison"
    requirement: "PKG-04"
    verification:
      - kind: unit
        ref: "tools/tests/test_build_sb.py#CheckTests,DiffIdsTests"
        status: pass
    human_judgment: false
  - id: D4
    description: "audit subcommand flags secret patterns and forbidden shape without printing matched values, lists unknown keys as REVIEW"
    requirement: "PKG-04"
    verification:
      - kind: unit
        ref: "tools/tests/test_build_sb.py#AuditTests"
        status: pass
    human_judgment: true
    rationale: "Regex coverage against real exports can only be judged on the user's golden in the 01-03 human checkpoint; unit tests use synthetic plants"

duration: 24min
completed: 2026-10-18
status: complete
---

# Phase 1 Plan 02: .sb Codec and Safety Tooling Summary

**Stdlib-only `tools/build_sb.py` with a byte-exact `.sb` codec, a gzip-bomb-safe decoder and `decode` / `check` / `diff-ids` / `audit` subcommands (masked secret findings, REVIEW key inventory), backed by 49 offline unit tests.**

## Performance

- **Duration:** ~24 min
- **Started:** 2026-10-18T10:01Z (approx)
- **Completed:** 2026-10-18T10:26Z
- **Tasks:** 3 (all TDD: RED then GREEN each)
- **Files modified:** 4 created, 0 modified

## Accomplishments

- Tracer slice: `pack`/`unpack`/`dump` produce and read the observed envelope, and the `decode` CLI (with `--pretty` and `--out`) works end to end.
- `unpack_bytes` enforces hard limits: input cap, strict base64, `SBAE` magic, `zlib.decompressobj(31)` with `max_length = cap + 1`, `eof`, `unconsumed_tail` and `unused_data` checks, BOM and strict UTF-8 rejection. Malformed files give exit 2 from decode/check/audit/diff-ids.
- `check` runs six generic structural checks (roundtrip, utf8-no-bom, ids-format, ids-unique, refs-resolve, bytecode-utf8) with PASS/FAIL lines; `diff-ids` compares action/queue/sub-action/trigger ids.
- `audit` scans string values and decoded byteCode for the planned secret patterns, enforces empty commands/websocket*/timers and action-name prefixes, prints only rule + JSON path + 3-char masked preview, and lists unknown keys, author and queues as REVIEW for the 01-03 human checkpoint.
- Fidelity smoke (offline, scratchpad only, no sample content recorded): the three official 1.0.4 samples (`chatbot-commands.sb`, `wsgs.utils.curl.sb`, `wsgs.utils.json.parse.sb`) were fetched into the session scratchpad. All three decode, re-serialize to identical decoded bytes (`canonical_roundtrip=True`) and pass all six `check` checks (0 HARD). Result: PASS. This does not prove anything about 1.0.7 or about Streamer.bot accepting a built file; that is the golden fidelity test in 01-05 and the live import in later plans.

## Task Commits

1. **Task 1: End-to-end codec slice (tracer)** - RED `1eb2e7d` (test), GREEN `8943823` (feat)
2. **Task 2: Bounded decode limits, check, diff-ids** - RED `0e19ab0` (test), GREEN `7cb0968` (feat)
3. **Task 3: Secret and shape audit** - RED `8fc3bb2` (test), GREEN `c48fb68` (feat)

**Plan metadata:** committed separately as `docs(01-02): complete .sb codec and safety tooling plan`.

## TDD Gate Compliance

- Each task has a `test(01-02)` RED commit before its `feat(01-02)` GREEN commit. No REFACTOR commits (none needed).
- RED evidence per task was run through `gsd-tools check tdd-red-evidence` and returned `RED_EVIDENCE_OK` (`target_test_failed`): Task 1 target `test_pack_unpack_round_trip` (skeleton raised NotImplementedError; 6 failing), Task 2 target `test_unpack_bytes_rejects_one_byte_over_cap` (assertion: no exception raised for cap+1; 20 failing), Task 3 target `test_audit_planted_patterns_are_hard_and_never_echoed` (audit subcommand missing; 16 failing).
- Semantic assessment: in each RED run the named target test executed and failed because the planned behavior was absent, not because of syntax, import or fixture faults.
- Task 1 RED added a skeleton `build_sb.py` (constants, `SbFormatError`, functions raising `NotImplementedError`) so the failures are test-level errors rather than an import failure.

## Files Created/Modified

- `tools/build_sb.py` - codec, bounded decoder, structural check, diff-ids, audit, CLI.
- `tools/tests/__init__.py` - empty; makes discovery work under `python -I` (RESEARCH Pitfall 2).
- `tools/tests/test_build_sb.py` - 49 tests: codec, limits, check, diff-ids, audit; helper `make_model()`.
- `.gitattributes` - `*.sb -text`.

## Decisions Made

- Unknown keys are REVIEW only (as planned); `audit --allow-prefix` is additive to the defaults (plan left this open).
- `meta.author` is always reported as a REVIEW line (even when null) so the human sees it at the 01-03 checkpoint.
- Display values in REVIEW/INFO lines are replaced by `<redacted: matches a secret rule>` if they match a secret pattern, and are capped at 80 characters.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Undecodable byteCode fails the audit**
- **Found during:** Task 3
- **Issue:** The plan scans decoded byteCode but did not say what happens when a byteCode value cannot be decoded; silently skipping it would let unaudited code pass (information-disclosure false negative, T-01-08).
- **Fix:** `audit` emits `HARD structure:bytecode-undecodable <path>` and counts it as a finding.
- **Files modified:** tools/build_sb.py, tools/tests/test_build_sb.py
- **Committed in:** 8fc3bb2 (test), c48fb68 (feat)

**2. [Rule 2 - Missing Critical] Redaction of REVIEW/INFO display values**
- **Found during:** Task 3
- **Issue:** `REVIEW meta.author=<value>` and `INFO ... names` would print a secret-looking value verbatim, contradicting the "never print the matched secret" prohibition.
- **Fix:** `_safe()` redacts values that match any secret rule and truncates long values.
- **Files modified:** tools/build_sb.py, tools/tests/test_build_sb.py
- **Committed in:** 8fc3bb2, c48fb68

**3. [Rule 1 - Bug] Test fixture for the uppercase-id case**
- **Found during:** Task 2 GREEN
- **Issue:** `ACTION_ID.upper()` equals `ACTION_ID` (all digits), so the case was not malformed and the test failed against correct code.
- **Fix:** Use a hex-letter GUID in upper case in the test.
- **Committed in:** 7cb0968

**4. [Rule 2 - Missing Critical] Hardening details beyond the plan text**
- RecursionError from `json.loads` on hostile nesting is mapped to `SbFormatError` (exit 2); `OSError` on unreadable files gives `ERROR cannot read file` and exit 2; `user-profile-path` accepts repeated backslashes/slashes; `long-token` skips runs with 2 or fewer distinct characters.
- **Committed in:** 7cb0968, c48fb68

---

**Total deviations:** 4 auto-fixed (1 bug, 3 missing-critical). **Impact on plan:** no scope creep; all within tools/build_sb.py and its tests.

## Issues Encountered

- The shell wrapper refuses some compound git commands in a worktree, so git steps were run as separate plain commands. A one-off heredoc edit mangled a `\x` escape in the `BOM` constant; it was caught by the unit tests and fixed by a direct edit in the same task.
- `tools/__pycache__/` and `tools/tests/__pycache__/` exist untracked in this worktree. They were not staged; the ignore rule is added by 01-01 in the same wave (`git ls-files '*__pycache__*'` is empty).

## Known Stubs

None.

## Threat Flags

None. The tools only read local files and write to stdout or an explicit `--out` path.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 01-03 can run `python -I tools/build_sb.py decode <golden> --pretty` and `audit <golden>` to vet the user's export; the REVIEW lines (author, queues, unknown keys) are the input for the human checkpoint. On real samples with queues/triggers the REVIEW list is long because only action, sub-action 99999/120/99900, meta, data and top have seed key sets.
- 01-05 extends the same module with `build`; `KNOWN_KEYS` and the id helpers are ready to reuse.
- `python -I -m unittest discover -s tools/tests -t tools` passes (49 tests). Nothing here was run against Streamer.bot 1.0.7 or verified live.

## Self-Check: PASSED

- Created files exist: `tools/build_sb.py`, `tools/tests/__init__.py`, `tools/tests/test_build_sb.py`, `.gitattributes`.
- Task commits exist on HEAD: 1eb2e7d, 8943823, 0e19ab0, 7cb0968, 8fc3bb2, c48fb68.
- Full unit suite: 49 tests, OK. `decode|check|diff-ids|audit --help` exit 0; `check` without a file exits 2.

---
*Phase: 01-live-spikes-build-harness*
*Completed: 2026-10-18*
