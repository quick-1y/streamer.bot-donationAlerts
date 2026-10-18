import contextlib
import io
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import check_findings
import live_evidence

REPO_ROOT = Path(__file__).resolve().parents[2]
FINDINGS_PATH = REPO_ROOT / "docs" / "live-spikes" / "FINDINGS.md"

PII_LINE = "[2026-10-17 10:00:00.000 INF] Connected as SomeStreamer someone@example.com"
GUID = "e08e2a62-cbf7-44bf-86b6-8ebd941e8595"


def run_main(module, argv):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
        try:
            code = module.main(argv)
        except SystemExit as exc:  # argparse exits instead of returning
            code = exc.code
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


SINCE = "2026-10-17 09:30"
CLOSE_1 = "2026-10-17 10:30:00"
CLOSE_2 = "2026-10-17 23:55:00"


def build_sb_dir(root):
    """Synthetic Streamer.bot folder: three day logs, a data folder with a secret."""
    logs = Path(root) / "logs"
    logs.mkdir()
    (logs / "log_20261016.log").write_text(
        "[2026-10-16 12:00:00.000 INF] SPIKE A 00000000 INFO OLDDAY\n", encoding="utf-8"
    )
    (logs / "log_20261017.log").write_text(
        "\n".join(
            [
                "[2026-10-17 10:00:00.000 INF] SPIKE A 1a2b3c4d INIT domain=2",
                PII_LINE,
                "[2026-10-17 10:00:05.000 DBG] InlineCode :: Creating instance '" + GUID + "'",
                "[2026-10-17 10:30:00.000 INF] Closing services...",
                "[2026-10-17 10:30:01.000 DBG] InlineCode :: Cleaning up '1' execute code instances",
                "[2026-10-17 10:30:02.000 INF] Cleaned up execute code instances",
                "[2026-10-17 10:30:03.000 INF] Streamer.bot exited",
                "[2026-10-17 11:00:00.000 INF] SPIKE A 5e6f7a8b INFO after first close",
                "[2026-10-17 23:55:00.000 INF] Closing services...",
                "[2026-10-17 23:55:01.000 DBG] InlineCode :: Unloading instance",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (logs / "log_20261018.log").write_text(
        "[2026-10-18 00:05:00.000 INF] SPIKE A 99999999 INFO after midnight\n", encoding="utf-8"
    )
    data = Path(root) / "data"
    data.mkdir()
    (data / "globals.db").write_text("SECRETVALUE", encoding="utf-8")
    return Path(root)


def write_trace(path):
    path.write_text(
        "\n".join(
            [
                "2026-10-17 09:00:00.000 SPIKE A aaaaaaaa INIT early",
                "2026-10-17 10:15:00.000 SPIKE A bbbbbbbb INFO late " + GUID,
                "2026-10-17 10:16:00.000 unrelated line without the marker word",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


class LiveEvidenceFullTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sb_dir = build_sb_dir(self.tmp.name)
        self.trace = write_trace(Path(self.tmp.name) / "da-spike-trace.log")

    def run_tool(self, *extra):
        argv = ["--sb-dir", str(self.sb_dir), "--no-process-check"] + list(extra)
        return run_main(live_evidence, argv)

    def test_segment_headers_and_cleanup_summaries_per_close(self):
        code, out = self.run_tool("--since", SINCE, "--trace", str(self.trace))
        self.assertEqual(code, 0, out)
        header0 = "== segment 0: before first close =="
        header1 = "== segment 1: close at %s ==" % CLOSE_1
        header2 = "== segment 2: close at %s ==" % CLOSE_2
        for header in (header0, header1, header2):
            self.assertIn(header, out)
        self.assertLess(out.index(header0), out.index(header1))
        self.assertLess(out.index(header1), out.index(header2))
        summaries = [line for line in out.splitlines() if line.startswith("summary ")]
        self.assertEqual(
            summaries,
            [
                "summary cleaned=no exited=no",
                "summary cleaned=yes exited=yes",
                "summary cleaned=no exited=no",
            ],
        )

    def test_segment_function_splits_at_each_close(self):
        lines = [
            "[2026-10-17 10:00:00.000 INF] SPIKE A 1a2b3c4d INIT",
            "[2026-10-17 10:30:00.000 INF] Closing services...",
            "[2026-10-17 10:30:02.000 INF] Cleaned up execute code instances",
            "[2026-10-17 10:30:03.000 INF] Streamer.bot exited",
        ]
        segments = live_evidence.segment(lines)
        self.assertEqual(len(segments), 2)
        self.assertFalse(segments[0]["cleaned"])
        self.assertTrue(segments[1]["cleaned"])
        self.assertTrue(segments[1]["exited"])

    def test_midnight_session_reads_both_day_logs_in_name_order(self):
        code, out = self.run_tool("--since", SINCE, "--trace", str(self.trace))
        self.assertEqual(code, 0, out)
        self.assertIn("SPIKE A 99999999 INFO after midnight", out)
        self.assertLess(out.index(CLOSE_2), out.index("after midnight"))
        self.assertNotIn("OLDDAY", out)

    def test_without_since_only_the_newest_log_is_read(self):
        code, out = self.run_tool("--trace", str(self.trace))
        self.assertEqual(code, 0, out)
        self.assertIn("after midnight", out)
        self.assertNotIn("1a2b3c4d", out)

    def test_data_folder_is_never_opened_or_printed(self):
        opened = []
        real_read = live_evidence.read_text

        def recording_read(path):
            opened.append(Path(path).resolve())
            return real_read(path)

        with mock.patch.object(live_evidence, "read_text", recording_read):
            code, out = self.run_tool("--since", SINCE, "--trace", str(self.trace))
        self.assertEqual(code, 0, out)
        self.assertNotIn("SECRETVALUE", out)
        self.assertTrue(opened)
        data_dir = (self.sb_dir / "data").resolve()
        for path in opened:
            self.assertNotIn(data_dir, path.parents)
            self.assertNotEqual(path.name, "globals.db")

    def test_pii_and_ids_stay_masked_in_sb_dir_mode(self):
        code, out = self.run_tool("--since", SINCE, "--trace", str(self.trace))
        self.assertEqual(code, 0, out)
        self.assertNotIn("someone@example.com", out)
        self.assertNotIn("SomeStreamer", out)
        self.assertNotIn(GUID, out)

    def test_trace_prints_spike_lines_after_since_only(self):
        code, out = self.run_tool("--since", SINCE, "--trace", str(self.trace))
        self.assertEqual(code, 0, out)
        self.assertIn("trace: 2026-10-17 10:15:00.000 SPIKE A bbbbbbbb INFO late <id>", out)
        self.assertNotIn("aaaaaaaa", out)
        self.assertNotIn("unrelated line", out)

    def test_missing_trace_file_prints_trace_missing_and_does_not_fail(self):
        code, out = self.run_tool("--since", SINCE, "--trace", str(Path(self.tmp.name) / "none.log"))
        self.assertEqual(code, 0, out)
        self.assertIn("trace: missing", out)

    def test_trace_collapses_long_heartbeat_runs(self):
        ticks = ["2026-10-17 10:%02d:00.000 SPIKE A bbbbbbbb BG-TICK n=%d" % (n, n) for n in range(10, 20)]
        self.trace.write_text("\n".join(ticks) + "\n", encoding="utf-8")
        code, out = self.run_tool("--since", SINCE, "--trace", str(self.trace))
        self.assertEqual(code, 0, out)
        self.assertIn("n=10", out)
        self.assertIn("n=19", out)
        self.assertNotIn("n=14", out)
        self.assertIn("8 BG-TICK lines omitted", out)

    def test_after_close_prints_only_the_last_segment(self):
        code, out = self.run_tool("--since", SINCE, "--after-close", "--trace", str(self.trace))
        self.assertEqual(code, 0, out)
        self.assertIn("== segment 2: close at %s ==" % CLOSE_2, out)
        self.assertNotIn("== segment 1:", out)
        self.assertNotIn("== segment 0:", out)

    def test_missing_sb_dir_or_logs_folder_exits_2(self):
        code, _ = run_main(live_evidence, ["--sb-dir", str(Path(self.tmp.name) / "nope"), "--no-process-check"])
        self.assertEqual(code, 2)
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        code, _ = run_main(live_evidence, ["--sb-dir", str(empty), "--no-process-check"])
        self.assertEqual(code, 2)

    def test_help_lists_the_documented_flags(self):
        code, out = run_main(live_evidence, ["--help"])
        self.assertEqual(code, 0)
        for flag in ("--sb-dir", "--log", "--since", "--after-close", "--trace", "--no-process-check"):
            self.assertIn(flag, out)


class ProcessCheckTests(unittest.TestCase):
    TASKLIST_PRESENT = b'"Streamer.bot.exe","1234","Console","1","200 000 K"\r\n"Streamer.bot.exe","5678","Console","1","9 000 K"\r\n'
    TASKLIST_ABSENT = "ИНФОРМАЦИЯ: задачи, соответствующие заданным критериям, не найдены.\r\n".encode("cp866")

    def completed(self, stdout):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=b"")

    def test_process_pids_parses_csv_without_depending_on_locale_text(self):
        with mock.patch.object(live_evidence.subprocess, "run", return_value=self.completed(self.TASKLIST_PRESENT)) as run:
            self.assertEqual(live_evidence.process_pids(), [1234, 5678])
        argv = run.call_args[0][0]
        self.assertEqual(argv[0], "tasklist")
        self.assertIn("IMAGENAME eq Streamer.bot.exe", argv)
        self.assertFalse(run.call_args[1].get("shell", False))
        with mock.patch.object(live_evidence.subprocess, "run", return_value=self.completed(self.TASKLIST_ABSENT)):
            self.assertEqual(live_evidence.process_pids(), [])

    def test_process_present_line_is_printed(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb_dir = build_sb_dir(tmp)
            with mock.patch.object(live_evidence, "process_pids", return_value=[4321]):
                code, out = run_main(live_evidence, ["--sb-dir", str(sb_dir), "--since", SINCE, "--trace", str(Path(tmp) / "x")])
        self.assertEqual(code, 0, out)
        self.assertIn("process: present pids=4321", out)

    def test_process_absent_line_is_printed(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb_dir = build_sb_dir(tmp)
            with mock.patch.object(live_evidence, "process_pids", return_value=[]):
                code, out = run_main(live_evidence, ["--sb-dir", str(sb_dir), "--trace", str(Path(tmp) / "x")])
        self.assertIn("process: absent", out)

    def test_after_close_polls_each_second_until_the_process_is_gone(self):
        answers = [[10], [10], []]
        sleeps = []
        result = live_evidence.wait_for_exit(
            query=lambda: answers.pop(0), sleep=sleeps.append, max_seconds=10
        )
        self.assertEqual(result, [])
        self.assertEqual(sleeps, [1, 1])

    def test_after_close_gives_up_after_ten_seconds(self):
        sleeps = []
        result = live_evidence.wait_for_exit(query=lambda: [10], sleep=sleeps.append, max_seconds=10)
        self.assertEqual(result, [10])
        self.assertEqual(len(sleeps), 10)

    def test_no_process_check_flag_never_calls_tasklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb_dir = build_sb_dir(tmp)
            with mock.patch.object(live_evidence.subprocess, "run") as run:
                code, out = run_main(
                    live_evidence,
                    ["--sb-dir", str(sb_dir), "--no-process-check", "--trace", str(Path(tmp) / "x")],
                )
        self.assertEqual(code, 0, out)
        run.assert_not_called()
        self.assertNotIn("process:", out)


if __name__ == "__main__":
    unittest.main()
