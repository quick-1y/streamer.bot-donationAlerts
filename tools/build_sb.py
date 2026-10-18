"""Streamer.bot .sb codec and safety tooling.

Format (observed on official 1.0.4 samples, see 01-RESEARCH.md Pattern 4):

    file text = base64(b"SBAE" + gzip(UTF-8 JSON, no BOM, CRLF, 2-space indent))

The user's golden export is the only schema authority for the fields inside the
JSON. Nothing in this module invents Streamer.bot fields; it only reads, checks
and re-serializes what a real export contains.

Standard library only. Run it as `python -I tools/build_sb.py <command>`.
"""

import argparse
import base64
import binascii
import copy
import gzip
import json
import re
import sys
import zlib
from pathlib import Path

MAGIC = b"SBAE"
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_DECODED_BYTES = 64 * 1024 * 1024
NULL_GUID = "00000000-0000-0000-0000-000000000000"
GUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
REPO_ROOT = Path(__file__).resolve().parent.parent

COMMON_SUBACTION_KEYS = {"id", "weight", "type", "parentId", "enabled", "index"}
KNOWN_KEYS = {}
DEFAULT_ALLOWED_PREFIXES = ("GOLDEN |", "SPIKE |")


class SbFormatError(ValueError):
    """The input is not a well-formed .sb payload."""


def dump(obj):
    """Canonical JSON bytes: CRLF, 2-space indent, `"key": value`, no BOM, no trailing newline."""
    text = json.dumps(obj, indent=2, ensure_ascii=False, separators=(',', ': '))
    return text.replace("\n", "\r\n").encode("utf-8")


def pack(obj):
    return base64.b64encode(MAGIC + gzip.compress(dump(obj), compresslevel=9, mtime=0))


def unpack_bytes(raw, max_bytes=MAX_DECODED_BYTES):
    """Return the decoded JSON bytes of a .sb payload."""
    try:
        payload = base64.b64decode(bytes(raw).strip(), validate=True)
    except (binascii.Error, ValueError) as e:
        raise SbFormatError("invalid base64") from e
    if payload[:4] != MAGIC:
        raise SbFormatError("missing SBAE magic")
    try:
        return gzip.decompress(payload[4:])
    except (OSError, EOFError, zlib.error) as e:
        raise SbFormatError("invalid gzip stream") from e


def unpack(raw):
    try:
        model = json.loads(unpack_bytes(raw).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise SbFormatError("payload is not valid UTF-8 JSON") from e
    if not isinstance(model, dict):
        raise SbFormatError("top-level JSON value is not an object")
    return model


def read_sb(path):
    """Return (model, decoded JSON bytes) for the .sb file at path."""
    raw = Path(path).read_bytes()
    json_bytes = unpack_bytes(raw)
    return unpack(raw), json_bytes


def decode_bytecode(value):
    """Decode a sub-action byteCode value (base64) to its UTF-8 source text."""
    try:
        return base64.b64decode(value, validate=True).decode("utf-8")
    except (binascii.Error, ValueError, TypeError) as e:
        raise SbFormatError("byteCode is not valid base64 UTF-8") from e


def iter_nodes(obj, path="$"):
    """Yield (json path, key or index, value) for every node below obj."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = "%s.%s" % (path, key)
            yield child, key, value
            yield from iter_nodes(value, child)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            child = "%s[%d]" % (path, index)
            yield child, index, value
            yield from iter_nodes(value, child)


def _pretty_copy(model):
    shown = copy.deepcopy(model)
    _replace_bytecode(shown)
    return shown


def _replace_bytecode(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "byteCode" and isinstance(value, str):
                node[key] = decode_bytecode(value)
            else:
                _replace_bytecode(value)
    elif isinstance(node, list):
        for item in node:
            _replace_bytecode(item)


def _configure_streams():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _cmd_decode(args):
    model, _ = read_sb(args.file)
    if args.pretty:
        model = _pretty_copy(model)
    text = json.dumps(model, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)
    return 0


def _build_parser():
    parser = argparse.ArgumentParser(prog="build_sb.py", description="Streamer.bot .sb codec and safety tooling")
    sub = parser.add_subparsers(dest="command", required=True)
    decode = sub.add_parser("decode", help="print the decoded JSON model")
    decode.add_argument("file")
    decode.add_argument("--pretty", action="store_true", help="replace each byteCode by its decoded source (display only)")
    decode.add_argument("--out", help="write the JSON to this path instead of stdout")
    decode.set_defaults(func=_cmd_decode)
    return parser


def main(argv=None):
    _configure_streams()
    args = _build_parser().parse_args(argv)
    try:
        return args.func(args)
    except SbFormatError as e:
        sys.stderr.write("ERROR %s\n" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
