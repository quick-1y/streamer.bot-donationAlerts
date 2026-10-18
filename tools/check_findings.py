"""Honesty gate for docs/live-spikes/FINDINGS.md.

Usage:
    python -I tools/check_findings.py docs/live-spikes/FINDINGS.md

The file holds a findings table (one row per ID in REQUIRED_IDS) and a decisions
table. This script fails when the record claims more than it can prove:

- a status outside ALLOWED_STATUS (so "verified offline" is rejected: offline facts
  belong in the "Offline facts" section and never get a status);
- a live status ("verified live" / "refuted live") without non-empty evidence or
  without the user's dated confirmation "user YYYY-MM-DD";
- a "not verified" row that already carries a confirmation;
- a missing, duplicate or unknown finding ID;
- a decision (SD-nn) that cites a finding ID which does not exist.

Exit codes: 0 valid, 1 invalid (lines "ERROR <...>"), 2 file missing or no findings
table. Standard library only; the script imports nothing from its own folder.
"""

import re
import sys
from datetime import datetime
from pathlib import Path

REQUIRED_IDS = (
    ["F%d" % n for n in range(1, 10)]
    + ["E%d" % n for n in range(1, 9)]
    + ["SC3", "SC4a", "SC4b"]
)
ALLOWED_STATUS = {"not verified", "verified live", "refuted live"}
LIVE_STATUS = {"verified live", "refuted live"}
CONFIRMED_RE = re.compile(r"^user \d{4}-\d{2}-\d{2}$")
DECISION_ID_RE = re.compile(r"^SD-\d{2}$")
SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")

FINDINGS_HEADER = ["ID", "Question", "Status", "Evidence", "Confirmed", "Decision"]
DECISIONS_HEADER = ["ID", "Decision", "Driven by", "Consequence"]
REQUIRED_SECTIONS = ["## Session", "## Offline facts", "## Decisions"]

# Evidence that only looks filled in. A live status needs a real marker line or quote.
PLACEHOLDER_EVIDENCE = {"-", "--", "pending", "n/a", "none", "tbd", "todo"}


def split_row(line):
    """Split a markdown table row on pipes that are not preceded by a backslash."""
    parts = re.split(r"(?<!\\)\|", line.strip())
    if parts and parts[0].strip() == "":
        parts = parts[1:]
    if parts and parts[-1].strip() == "":
        parts = parts[:-1]
    return [part.strip().replace("\\|", "|") for part in parts]


def is_separator(cells):
    return bool(cells) and all(SEPARATOR_CELL_RE.match(cell) for cell in cells)


def find_table(lines, header):
    """Return [(line_number, cells), ...] for the table with this exact header, or None."""
    in_fence = False
    for index, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line.startswith("|"):
            continue
        if split_row(line) != header:
            continue
        rows = []
        for offset in range(index + 1, len(lines)):
            candidate = lines[offset]
            if not candidate.startswith("|"):
                break
            cells = split_row(candidate)
            if is_separator(cells):
                continue
            rows.append((offset + 1, cells))
        return rows
    return None


def present_sections(lines):
    found = set()
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            found.add(line.strip())
    return found


def valid_date(text):
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def check_finding_rows(rows, errors):
    counts = {"verified live": 0, "refuted live": 0, "not verified": 0}
    seen = set()
    total = 0
    for line_no, cells in rows:
        if len(cells) != len(FINDINGS_HEADER):
            errors.append(
                "ERROR line %d: expected %d cells, found %d" % (line_no, len(FINDINGS_HEADER), len(cells))
            )
            continue
        total += 1
        row_id, _question, status, evidence, confirmed, _decision = cells
        if row_id in seen:
            errors.append("ERROR %s: duplicate finding ID" % row_id)
        seen.add(row_id)
        if row_id not in REQUIRED_IDS:
            errors.append("ERROR %s: unknown finding ID" % row_id)
        if status not in ALLOWED_STATUS:
            errors.append(
                "ERROR %s: status '%s' is not allowed (use: %s)"
                % (row_id, status, ", ".join(sorted(ALLOWED_STATUS)))
            )
            continue
        counts[status] += 1
        if status in LIVE_STATUS:
            if not evidence or evidence.lower() in PLACEHOLDER_EVIDENCE:
                errors.append("ERROR %s: '%s' needs non-empty evidence" % (row_id, status))
            if not CONFIRMED_RE.match(confirmed) or not valid_date(confirmed[len("user "):]):
                errors.append(
                    "ERROR %s: '%s' needs Confirmed in the form 'user YYYY-MM-DD'" % (row_id, status)
                )
        elif confirmed:
            errors.append("ERROR %s: 'not verified' must have an empty Confirmed cell" % row_id)
    for required in REQUIRED_IDS:
        if required not in seen:
            errors.append("ERROR %s: missing finding row" % required)
    return total, counts


def check_decision_rows(rows, errors):
    seen = set()
    for line_no, cells in rows:
        if len(cells) != len(DECISIONS_HEADER):
            errors.append(
                "ERROR line %d: expected %d cells, found %d" % (line_no, len(DECISIONS_HEADER), len(cells))
            )
            continue
        row_id, _decision, driven_by, _consequence = cells
        if not DECISION_ID_RE.match(row_id):
            errors.append("ERROR %s: decision ID must look like SD-01" % (row_id or "line %d" % line_no))
        if row_id in seen:
            errors.append("ERROR %s: duplicate decision ID" % row_id)
        seen.add(row_id)
        entries = [entry.strip() for entry in driven_by.split(",") if entry.strip()]
        if not entries:
            errors.append("ERROR %s: 'Driven by' is empty" % row_id)
        for entry in entries:
            if entry not in REQUIRED_IDS:
                errors.append("ERROR %s: driven by unknown finding '%s'" % (row_id, entry))
    return len(rows)


def main(argv):
    if len(argv) != 1:
        print("usage: check_findings.py <FINDINGS.md>")
        return 2
    path = Path(argv[0])
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print("ERROR cannot read %s (%s)" % (path, type(exc).__name__))
        return 2
    lines = text.splitlines()

    findings_rows = find_table(lines, FINDINGS_HEADER)
    if findings_rows is None:
        print("ERROR no findings table")
        return 2

    errors = []
    sections = present_sections(lines)
    for section in REQUIRED_SECTIONS:
        if section not in sections:
            errors.append("ERROR missing section '%s'" % section)

    total, counts = check_finding_rows(findings_rows, errors)

    decision_rows = find_table(lines, DECISIONS_HEADER)
    if decision_rows is None:
        errors.append("ERROR no decisions table")
        decision_count = 0
    else:
        decision_count = check_decision_rows(decision_rows, errors)

    for error in errors:
        print(error)
    print(
        "check_findings: %d findings (verified live=%d, refuted live=%d, not verified=%d), %d decisions"
        % (total, counts["verified live"], counts["refuted live"], counts["not verified"], decision_count)
    )
    return 1 if errors else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
