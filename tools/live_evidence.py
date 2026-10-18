"""Privacy-preserving evidence extractor for the Phase 1 live spikes.

Privacy contract (enforced by tests that plant PII and a data-folder secret):

- Only timestamped Streamer.bot log lines that match the fixed MARKER_PATTERNS are
  ever printed. Every other line, and every continuation line, is dropped.
- GUIDs, runs of 32 or more hex characters and e-mail addresses are masked as
  <id> / <email> before printing.
- Only logs/log_*.log files (or the one file given with --log) and the spike trace
  file are read. Nothing under the Streamer.bot data folder (globals.db and
  friends) is ever opened, listed or printed.
- The only subprocess is a read-only `tasklist` query with a fixed argument list.

Usage:
    python -I tools/live_evidence.py --sb-dir DIR [--since "YYYY-MM-DD HH:MM"] [--after-close]
    python -I tools/live_evidence.py --log FILE   [--since "YYYY-MM-DD HH:MM"]
Options: --trace PATH, --no-process-check.

Output modes:
- With --since or --after-close the marker lines are split into segments at each
  "Closing services" line: "== segment <k>: close at <ts> ==" followed by the
  segment's marker lines and "summary cleaned=<yes|no> exited=<yes|no>". Segment 0
  holds everything before the first close. --after-close prints only the last
  segment and polls tasklist once a second for up to 10 seconds.
- Without them the filtered lines are printed flat.
- The spike trace file (default %TEMP%/da-spike-trace.log) is printed as
  "trace: <line>" lines when --trace or --since is given; a missing file prints
  "trace: missing". Long BG-TICK runs are collapsed to first line, last line and
  an omitted-count line.
- Unless --no-process-check is given, one line "process: present pids=<...>",
  "process: absent" or "process: unknown" is printed.

Known limit: the marker allow-list is line based. A chat line that happens to
contain the word SPIKE or GOLDEN in capitals would pass it. Nothing in the spike
or golden packages logs chat content.

Exit codes: 0 ok, 2 the log or the Streamer.bot folder is missing.
Standard library only; the script imports nothing from its own folder.
"""

import argparse
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# Marker allow-list. The clean-shutdown strings are constants on purpose: finding F9
# confirms them live, and one edit here fixes them everywhere.
CLOSING_MARKER = r"Closing services"
CLEANED_MARKER = r"Cleaned up execute code instances"
EXITED_MARKER = r"Streamer\.bot exited"
MARKER_PATTERNS = [
    CLOSING_MARKER,
    r"InlineCode :: (Cleaning|Cleaned|Unloading|Creating)",
    CLEANED_MARKER,
    EXITED_MARKER,
    r"\bSPIKE\b",
    r"\bGOLDEN\b",
]
MARKER_RE = re.compile("|".join("(?:%s)" % pattern for pattern in MARKER_PATTERNS))
CLOSING_RE = re.compile(CLOSING_MARKER)
CLEANED_RE = re.compile(CLEANED_MARKER)
EXITED_RE = re.compile(EXITED_MARKER)

TS_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.\d{3} [A-Z]{3}\]")
TS_FORMAT = "%Y-%m-%d %H:%M:%S"
TRACE_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.\d{3} ")
LOG_NAME_RE = re.compile(r"^log_(\d{8})\.log$")

GUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
HEX_RUN_RE = re.compile(r"\b[0-9a-fA-F]{32,}\b")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

TASKLIST_ARGV = ["tasklist", "/FI", "IMAGENAME eq Streamer.bot.exe", "/FO", "CSV", "/NH"]
PID_RE = re.compile(r'^"Streamer\.bot\.exe","(\d+)"', re.IGNORECASE | re.MULTILINE)
PROCESS_POLL_SECONDS = 10
TICK_MARKER = " BG-TICK "


def mask(line):
    """Mask GUIDs, long hex runs and e-mail addresses."""
    line = GUID_RE.sub("<id>", line)
    line = HEX_RUN_RE.sub("<id>", line)
    return EMAIL_RE.sub("<email>", line)


def parse_since(text):
    """Parse 'YYYY-MM-DD', 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD HH:MM:SS'."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    raise ValueError("bad --since value (use 'YYYY-MM-DD HH:MM')")


def filter_lines(lines, since=None):
    """Keep only timestamped marker lines at or after `since`; return them masked."""
    if isinstance(since, str):
        since = parse_since(since)
    kept = []
    for raw in lines:
        line = raw.rstrip("\r\n")
        match = TS_RE.match(line)
        if not match:
            continue
        if since is not None and datetime.strptime(match.group(1), TS_FORMAT) < since:
            continue
        if not MARKER_RE.search(line):
            continue
        kept.append(mask(line))
    return kept


def segment(lines):
    """Split filtered lines at each 'Closing services' line.

    Segment 0 is everything before the first close. Every other segment starts with
    its own close line. Each segment is a dict: index, ts, lines, cleaned, exited.
    """
    segments = [{"index": 0, "ts": None, "lines": []}]
    for line in lines:
        if CLOSING_RE.search(line):
            match = TS_RE.match(line)
            segments.append(
                {"index": len(segments), "ts": match.group(1) if match else "unknown", "lines": []}
            )
        segments[-1]["lines"].append(line)
    for item in segments:
        item["cleaned"] = any(CLEANED_RE.search(line) for line in item["lines"])
        item["exited"] = any(EXITED_RE.search(line) for line in item["lines"])
    return segments


def format_segment(item):
    if item["index"] == 0:
        header = "== segment 0: before first close =="
    else:
        header = "== segment %d: close at %s ==" % (item["index"], item["ts"])
    summary = "summary cleaned=%s exited=%s" % (
        "yes" if item["cleaned"] else "no",
        "yes" if item["exited"] else "no",
    )
    return [header] + item["lines"] + [summary]


def read_text(path):
    """The only place a file is opened for reading."""
    return Path(path).read_text(encoding="utf-8", errors="replace")


def select_log_files(sb_dir, since):
    """Pick logs/log_*.log files by name only. Never touches anything else."""
    logs = Path(sb_dir) / "logs"
    if not logs.is_dir():
        return []
    logs_resolved = logs.resolve()
    found = []
    for path in logs.glob("log_*.log"):
        match = LOG_NAME_RE.match(path.name)
        if match and path.is_file() and path.resolve().parent == logs_resolved:
            found.append((match.group(1), path))
    found.sort(key=lambda item: item[1].name)
    if since is None:
        return [path for _, path in found[-1:]]
    cutoff = since.strftime("%Y%m%d")
    return [path for day, path in found if day >= cutoff]


def collapse_ticks(lines):
    """Keep first and last line of each BG-TICK run longer than two lines."""
    out = []
    run = []

    def flush():
        if len(run) > 2:
            out.extend([run[0], "... %d BG-TICK lines omitted" % (len(run) - 2), run[-1]])
        else:
            out.extend(run)
        del run[:]

    for line in lines:
        if TICK_MARKER in line:
            run.append(line)
        else:
            flush()
            out.append(line)
    flush()
    return out


def trace_lines(path, since=None):
    """Return 'trace: ...' lines from the spike trace file, or ['trace: missing']."""
    path = Path(path)
    if not path.is_file():
        return ["trace: missing"]
    kept = []
    for raw in read_text(path).splitlines():
        match = TRACE_TS_RE.match(raw)
        if not match or "SPIKE" not in raw:
            continue
        if since is not None and datetime.strptime(match.group(1), TS_FORMAT) < since:
            continue
        kept.append(mask(raw.rstrip("\r\n")))
    return ["trace: " + line for line in collapse_ticks(kept)]


def process_pids():
    """PIDs of Streamer.bot.exe, or None when tasklist cannot be run.

    The PID is parsed from the CSV line, which is locale-independent; the
    "no tasks" sentence is localized and never inspected.
    """
    try:
        completed = subprocess.run(TASKLIST_ARGV, capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    text = completed.stdout.decode("utf-8", errors="replace")
    return [int(pid) for pid in PID_RE.findall(text)]


def wait_for_exit(query=None, sleep=time.sleep, max_seconds=PROCESS_POLL_SECONDS):
    """Poll once a second until the process is gone or max_seconds have passed."""
    query = query or process_pids
    pids = query()
    waited = 0
    while pids and waited < max_seconds:
        sleep(1)
        waited += 1
        pids = query()
    return pids


def process_line(pids):
    if pids is None:
        return "process: unknown"
    if not pids:
        return "process: absent"
    return "process: present pids=" + ",".join(str(pid) for pid in pids)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Print only fixed marker lines from Streamer.bot logs, with ids masked."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--sb-dir", metavar="DIR", help="Streamer.bot folder (only its logs folder is read)")
    source.add_argument("--log", metavar="FILE", help="one Streamer.bot log file")
    parser.add_argument("--since", metavar="YYYY-MM-DD[ HH:MM]", help="ignore lines before this local time")
    parser.add_argument(
        "--after-close",
        action="store_true",
        help="print only the segment after the last 'Closing services' line and poll for Streamer.bot.exe",
    )
    parser.add_argument(
        "--trace",
        metavar="PATH",
        help="spike trace file (default: da-spike-trace.log in the temp folder); printed when given or with --since",
    )
    parser.add_argument("--no-process-check", action="store_true", help="do not run tasklist")
    return parser


def main(argv):
    args = build_parser().parse_args(argv)
    since = None
    if args.since:
        try:
            since = parse_since(args.since)
        except ValueError as exc:
            print("ERROR %s" % exc)
            return 2

    if args.sb_dir:
        sb_dir = Path(args.sb_dir)
        if not sb_dir.is_dir():
            print("ERROR Streamer.bot folder not found")
            return 2
        log_files = select_log_files(sb_dir, since)
        if not log_files:
            print("ERROR no logs/log_*.log files for the requested time")
            return 2
    else:
        log_path = Path(args.log)
        if not log_path.is_file():
            print("ERROR log file not found")
            return 2
        log_files = [log_path]

    all_lines = []
    for log_file in log_files:
        all_lines.extend(read_text(log_file).splitlines())
    marker_lines = filter_lines(all_lines, since)

    if since is not None or args.after_close:
        segments = segment(marker_lines)
        if args.after_close:
            if len(segments) > 1:
                segments = segments[-1:]
            else:
                print("== no close found in the selected logs ==")
                segments = []
        for item in segments:
            for line in format_segment(item):
                print(line)
    else:
        for line in marker_lines:
            print(line)

    if args.trace is not None or since is not None:
        trace_path = Path(args.trace) if args.trace else Path(tempfile.gettempdir()) / "da-spike-trace.log"
        for line in trace_lines(trace_path, since):
            print(line)

    if not args.no_process_check:
        if args.after_close:
            started = time.monotonic()
            pids = wait_for_exit()
            print(process_line(pids))
            print("process: polled=%ds" % int(time.monotonic() - started))
        else:
            print(process_line(process_pids()))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
