import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path

import check_findings
import live_evidence

REPO_ROOT = Path(__file__).resolve().parents[2]
FINDINGS_PATH = REPO_ROOT / "docs" / "live-spikes" / "FINDINGS.md"

PII_LINE = "[2026-10-17 10:00:00.000 INF] Connected as SomeStreamer someone@example.com"
GUID = "e08e2a62-cbf7-44bf-86b6-8ebd941e8595"


def run_main(module, argv):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = module.main(argv)
    return code, buffer.getvalue()


def set_row(text, row_id, status=None, evidence=None, confirmed=None):
    """Rewrite the Status/Evidence/Confirmed cells of one findings row."""
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if line.startswith("| " + row_id + " |"):
            cells = re.split(r"(?<!\\)\|", line)
            # cells[0] and cells[-1] are the empty pieces around the outer pipes
            if status is not None:
                cells[3] = " " + status + " "
            if evidence is not None:
                cells[4] = " " + evidence + " "
            if confirmed is not None:
                cells[5] = " " + confirmed + " "
            lines[index] = "|".join(cells)
            return "\n".join(lines)
    raise AssertionError("row not found: " + row_id)


def drop_row(text, row_id):
    kept = [line for line in text.split("\n") if not line.startswith("| " + row_id + " |")]
    return "\n".join(kept)


def duplicate_row(text, row_id):
    out = []
    for line in text.split("\n"):
        out.append(line)
        if line.startswith("| " + row_id + " |"):
            out.append(line)
    return "\n".join(out)


class CheckFindingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.skeleton = FINDINGS_PATH.read_text(encoding="utf-8")

    def check(self, text):
        path = Path(self.tmp.name) / "FINDINGS.md"
        path.write_text(text, encoding="utf-8")
        return run_main(check_findings, [str(path)])

    def test_skeleton_passes_with_20_not_verified(self):
        code, out = self.check(self.skeleton)
        self.assertEqual(code, 0, out)
        self.assertIn(
            "check_findings: 20 findings (verified live=0, refuted live=0, not verified=20), 0 decisions",
            out,
        )

    def test_skeleton_file_itself_passes(self):
        code, out = run_main(check_findings, [str(FINDINGS_PATH)])
        self.assertEqual(code, 0, out)

    def test_unconfirmed_live_claim_fails_when_confirmed_is_empty(self):
        text = set_row(self.skeleton, "F2", status="verified live", evidence="SPIKE A 1a2b3c4d DISPOSE-BEGIN")
        code, out = self.check(text)
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR F2", out)

    def test_unconfirmed_live_claim_fails_when_confirmed_has_wrong_shape(self):
        text = set_row(
            self.skeleton, "F2", status="verified live", evidence="marker", confirmed="user yesterday"
        )
        code, out = self.check(text)
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR F2", out)

    def test_live_claim_without_evidence_fails(self):
        text = set_row(self.skeleton, "F2", status="refuted live", evidence="", confirmed="user 2026-10-17")
        code, out = self.check(text)
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR F2", out)

    def test_live_claim_with_evidence_and_confirmation_passes(self):
        text = set_row(
            self.skeleton, "F2", status="verified live", evidence="SPIKE A 1a2b3c4d DISPOSE-BEGIN",
            confirmed="user 2026-10-17",
        )
        code, out = self.check(text)
        self.assertEqual(code, 0, out)
        self.assertIn("verified live=1", out)
        self.assertIn("not verified=19", out)

    def test_offline_status_is_rejected(self):
        text = set_row(self.skeleton, "F6", status="verified offline", evidence="roslyn file version")
        code, out = self.check(text)
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR F6", out)

    def test_unknown_status_is_rejected(self):
        text = set_row(self.skeleton, "F6", status="probably")
        code, out = self.check(text)
        self.assertEqual(code, 1, out)

    def test_missing_f7_row_fails(self):
        code, out = self.check(drop_row(self.skeleton, "F7"))
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR F7", out)

    def test_duplicate_f7_row_fails(self):
        code, out = self.check(duplicate_row(self.skeleton, "F7"))
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR F7", out)

    def test_unknown_finding_id_fails(self):
        extra = "| F10 | invented | not verified |  |  | pending |"
        text = self.skeleton.replace("| SC4b |", extra + "\n| SC4b |")
        code, out = self.check(text)
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR F10", out)

    def test_not_verified_row_with_confirmation_fails(self):
        text = set_row(self.skeleton, "E1", confirmed="user 2026-10-17")
        code, out = self.check(text)
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR E1", out)

    def test_decision_driven_by_unknown_finding_fails(self):
        text = self.skeleton.rstrip("\n") + "\n| SD-01 | use semaphore | F99 | none |\n"
        code, out = self.check(text)
        self.assertEqual(code, 1, out)
        self.assertIn("SD-01", out)

    def test_decision_driven_by_known_findings_passes(self):
        text = self.skeleton.rstrip("\n") + "\n| SD-01 | use semaphore | F2, F7 | guard in Phase 2 |\n"
        code, out = self.check(text)
        self.assertEqual(code, 0, out)
        self.assertIn("1 decisions", out)

    def test_decision_with_bad_id_or_duplicate_id_fails(self):
        row = "| SD-01 | a | F2 | b |\n"
        code, out = self.check(self.skeleton.rstrip("\n") + "\n" + row + row)
        self.assertEqual(code, 1, out)
        code, out = self.check(self.skeleton.rstrip("\n") + "\n| D-1 | a | F2 | b |\n")
        self.assertEqual(code, 1, out)

    def test_escaped_pipe_stays_inside_one_cell(self):
        text = set_row(self.skeleton, "E1", evidence="a \\| b")
        code, out = self.check(text)
        self.assertEqual(code, 0, out)

    def test_missing_file_exits_2(self):
        code, _ = run_main(check_findings, [str(Path(self.tmp.name) / "nope.md")])
        self.assertEqual(code, 2)

    def test_missing_findings_table_exits_2(self):
        code, out = self.check("# nothing here\n")
        self.assertEqual(code, 2, out)
        self.assertIn("ERROR no findings table", out)

    def test_missing_required_section_fails(self):
        text = self.skeleton.replace("## Offline facts", "## Something else")
        code, out = self.check(text)
        self.assertEqual(code, 1, out)
        self.assertIn("Offline facts", out)


class LiveEvidenceSliceTests(unittest.TestCase):
    def make_log(self, tmp, lines):
        path = Path(tmp) / "log.log"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_pii_line_is_never_printed_and_guids_are_masked(self):
        lines = [
            PII_LINE,
            "[2026-10-17 10:00:01.000 DBG] InlineCode :: Creating instance '" + GUID + "'",
            "[2026-10-17 10:00:02.000 INF] SPIKE A 1a2b3c4d INIT domain=2",
            "    continuation line mentioning SPIKE and secret@example.org",
            "[2026-10-17 10:00:03.000 INF] Closing services...",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_log(tmp, lines)
            code, out = run_main(live_evidence, ["--log", str(path)])
        self.assertEqual(code, 0, out)
        self.assertIn("SPIKE A 1a2b3c4d INIT", out)
        self.assertIn("InlineCode :: Creating instance '<id>'", out)
        self.assertIn("Closing services", out)
        self.assertNotIn(GUID, out)
        self.assertNotIn("someone@example.com", out)
        self.assertNotIn("SomeStreamer", out)
        self.assertNotIn("secret@example.org", out)

    def test_filter_lines_respects_since_and_masks_hex_runs(self):
        hexrun = "ab" * 20
        lines = [
            "[2026-10-17 09:00:00.000 INF] SPIKE A 11111111 INFO early",
            "[2026-10-17 11:00:00.000 INF] SPIKE A 22222222 INFO " + hexrun,
        ]
        kept = live_evidence.filter_lines(lines, "2026-10-17 10:00")
        self.assertEqual(len(kept), 1)
        self.assertIn("22222222", kept[0])
        self.assertNotIn(hexrun, kept[0])
        self.assertIn("<id>", kept[0])

    def test_missing_log_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _ = run_main(live_evidence, ["--log", str(Path(tmp) / "missing.log")])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
