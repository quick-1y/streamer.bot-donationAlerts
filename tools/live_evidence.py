"""Privacy-preserving evidence extractor for the Phase 1 live spikes.

Privacy contract (enforced by tests that plant PII and a data-folder secret):

- Only timestamped Streamer.bot log lines that match the fixed MARKER_PATTERNS are
  ever printed. Every other line, and every continuation line, is dropped.
- GUIDs, runs of 32 or more hex characters and e-mail addresses are masked as
  <id> / <email> before printing.
- Only log files are read. Nothing under the Streamer.bot data folder is ever
  opened, listed or printed.

Usage:
    python -I tools/live_evidence.py --log FILE [--since "YYYY-MM-DD HH:MM"]

Exit codes: 0 ok, 2 the log is missing.
Standard library only; the script imports nothing from its own folder.
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

# Marker allow-list. The clean-shutdown strings are constants on purpose: finding F9
# confirms them live, and one edit here fixes them everywhere.
MARKER_PATTERNS = [
    r"Closing services",
    r"InlineCode :: (Cleaning|Cleaned|Unloading|Creating)",
    r"Cleaned up execute code instances",
    r"Streamer\.bot exited",
    r"\bSPIKE\b",
    r"\bGOLDEN\b",
]
MARKER_RE = re.compile("|".join("(?:%s)" % pattern for pattern in MARKER_PATTERNS))

TS_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.\d{3} [A-Z]{3}\]")
TS_FORMAT = "%Y-%m-%d %H:%M:%S"

GUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
HEX_RUN_RE = re.compile(r"\b[0-9a-fA-F]{32,}\b")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


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


def read_text(path):
    """The only place a file is opened for reading."""
    return Path(path).read_text(encoding="utf-8", errors="replace")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Print only fixed marker lines from a Streamer.bot log, with ids masked."
    )
    parser.add_argument("--log", required=True, metavar="FILE", help="one Streamer.bot log file")
    parser.add_argument("--since", metavar="YYYY-MM-DD[ HH:MM]", help="ignore lines before this local time")
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
    log_path = Path(args.log)
    if not log_path.is_file():
        print("ERROR log file not found")
        return 2
    for line in filter_lines(read_text(log_path).splitlines(), since):
        print(line)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
