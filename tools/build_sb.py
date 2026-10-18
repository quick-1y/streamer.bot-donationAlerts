"""Streamer.bot .sb codec and safety tooling (RED skeleton, behavior not implemented yet)."""

import sys
from pathlib import Path

MAGIC = b"SBAE"
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_DECODED_BYTES = 64 * 1024 * 1024
NULL_GUID = "00000000-0000-0000-0000-000000000000"
REPO_ROOT = Path(__file__).resolve().parent.parent


class SbFormatError(ValueError):
    pass


def dump(obj):
    raise NotImplementedError


def pack(obj):
    raise NotImplementedError


def unpack_bytes(raw, max_bytes=MAX_DECODED_BYTES):
    raise NotImplementedError


def unpack(raw):
    raise NotImplementedError


def main(argv=None):
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main())
