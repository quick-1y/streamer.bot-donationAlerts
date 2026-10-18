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
BOM = b"\xef\xbb\xbf"
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_DECODED_BYTES = 64 * 1024 * 1024
NULL_GUID = "00000000-0000-0000-0000-000000000000"
GUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
REPO_ROOT = Path(__file__).resolve().parent.parent

COMMON_SUBACTION_KEYS = {"id", "weight", "type", "parentId", "enabled", "index"}
# Key sets seen in the official 1.0.4 samples (01-RESEARCH.md Pattern 4). Keys outside them are
# only listed as REVIEW lines; the explicit allow-listing is a human decision (01-03 checkpoint).
KNOWN_KEYS = {
    "top": {"meta", "data", "version", "exportedFrom", "minimumVersion"},
    "meta": {"name", "author", "version", "description", "autoRunAction", "minimumVersion"},
    "data": {"actions", "queues", "commands", "websocketServers", "websocketClients", "timers"},
    "action": {
        "id", "queue", "enabled", "excludeFromHistory", "excludeFromPending", "name", "group",
        "alwaysRun", "randomAction", "concurrent", "triggers", "subActions", "collapsedGroups",
    },
    "subaction:99999": {
        "name", "description", "references", "byteCode", "precompile", "delayStart",
        "saveResultToVariable", "saveToVariable",
    } | COMMON_SUBACTION_KEYS,
    "subaction:120": {"input", "operation", "value", "autoType", "subActions"} | COMMON_SUBACTION_KEYS,
    "subaction:99900": {"name", "color", "random", "subActions"} | COMMON_SUBACTION_KEYS,
}
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
    """Return the decoded JSON bytes of a .sb payload, enforcing hard limits.

    Rejects: input over MAX_INPUT_BYTES, invalid base64, a missing SBAE magic,
    output over max_bytes (exactly max_bytes is accepted), a truncated gzip
    stream, data after the gzip member, a UTF-8 BOM and invalid UTF-8.
    """
    raw = bytes(raw)
    if len(raw) > MAX_INPUT_BYTES:
        raise SbFormatError("input is larger than %d bytes" % MAX_INPUT_BYTES)
    try:
        payload = base64.b64decode(b"".join(raw.split()), validate=True)
    except (binascii.Error, ValueError) as e:
        raise SbFormatError("invalid base64") from e
    if payload[:4] != MAGIC:
        raise SbFormatError("missing SBAE magic")
    decompressor = zlib.decompressobj(31)
    try:
        out = decompressor.decompress(payload[4:], max_bytes + 1)
    except zlib.error as e:
        raise SbFormatError("invalid gzip stream") from e
    if len(out) > max_bytes or decompressor.unconsumed_tail:
        raise SbFormatError("decompressed size exceeds %d bytes" % max_bytes)
    if not decompressor.eof:
        raise SbFormatError("truncated gzip stream")
    if decompressor.unused_data:
        raise SbFormatError("trailing data after the gzip member")
    if out.startswith(BOM):
        raise SbFormatError("JSON starts with a UTF-8 BOM")
    try:
        out.decode("utf-8")
    except UnicodeDecodeError as e:
        raise SbFormatError("payload is not valid UTF-8") from e
    return out


def unpack(raw):
    """Return the model (a dict) of a .sb payload."""
    json_bytes = unpack_bytes(raw)
    try:
        model = json.loads(json_bytes.decode("utf-8"))
    except (json.JSONDecodeError, RecursionError) as e:
        raise SbFormatError("payload is not valid JSON") from e
    if not isinstance(model, dict):
        raise SbFormatError("top-level JSON value is not an object")
    return model


def read_sb(path):
    """Return (model, decoded JSON bytes) for the .sb file at path."""
    path = Path(path)
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise SbFormatError("file is larger than %d bytes" % MAX_INPUT_BYTES)
    raw = path.read_bytes()
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


CHECK_NAMES = ("roundtrip", "utf8-no-bom", "ids-format", "ids-unique", "refs-resolve", "bytecode-utf8")


def _hard(name, path, reason):
    return "HARD check:%s %s: %s" % (name, path, reason)


def _check_roundtrip(model, json_bytes):
    try:
        reparsed = json.loads(json_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        return [_hard("roundtrip", "$", "decoded bytes are not valid JSON")]
    if dump(reparsed) != json_bytes:
        return [_hard("roundtrip", "$", "decoded bytes differ from the canonical serialization")]
    return []


def _check_utf8_no_bom(model, json_bytes):
    findings = []
    if json_bytes.startswith(BOM):
        findings.append(_hard("utf8-no-bom", "$", "JSON starts with a UTF-8 BOM"))
    try:
        json_bytes.decode("utf-8")
    except UnicodeDecodeError:
        findings.append(_hard("utf8-no-bom", "$", "JSON is not valid UTF-8"))
    return findings


def _id_nodes(model):
    return [(path, value) for path, key, value in iter_nodes(model) if key == "id"]


def _check_ids_format(model, json_bytes):
    findings = []
    for path, value in _id_nodes(model):
        if not isinstance(value, str) or not GUID_RE.match(value):
            findings.append(_hard("ids-format", path, "id is not a lowercase 8-4-4-4-12 GUID string"))
        elif value == NULL_GUID:
            findings.append(_hard("ids-format", path, "id is the null GUID"))
    return findings


def _check_ids_unique(model, json_bytes):
    seen = {}
    findings = []
    for path, value in _id_nodes(model):
        if not isinstance(value, str):
            continue
        if value in seen:
            findings.append(_hard("ids-unique", path, "duplicate id (first seen at %s)" % seen[value]))
        else:
            seen[value] = path
    return findings


def _check_refs_resolve(model, json_bytes):
    ids = {value for _, value in _id_nodes(model) if isinstance(value, str)}
    findings = []
    for path, key, value in iter_nodes(model):
        if key == "id" or not isinstance(value, str) or not GUID_RE.match(value):
            continue
        if value != NULL_GUID and value not in ids:
            findings.append(_hard("refs-resolve", path, "GUID does not resolve to an id in this file"))
    return findings


def _check_bytecode_utf8(model, json_bytes):
    findings = []
    for path, key, value in iter_nodes(model):
        if key != "byteCode" or value is None:
            continue
        try:
            if not isinstance(value, str):
                raise SbFormatError("byteCode is not a string")
            decode_bytecode(value)
        except SbFormatError:
            findings.append(_hard("bytecode-utf8", path, "byteCode is not valid base64 UTF-8"))
    return findings


_CHECKS = (
    ("roundtrip", _check_roundtrip),
    ("utf8-no-bom", _check_utf8_no_bom),
    ("ids-format", _check_ids_format),
    ("ids-unique", _check_ids_unique),
    ("refs-resolve", _check_refs_resolve),
    ("bytecode-utf8", _check_bytecode_utf8),
)


def structural_findings(model, json_bytes):
    """HARD lines for the generic structural checks; empty when the model is clean."""
    findings = []
    for _, check in _CHECKS:
        findings.extend(check(model, json_bytes))
    return findings


def _index_objects(model):
    """Map diff keys (action:, queue:, sub:, trigger:) to the object id."""
    index = {}

    def put(key, obj):
        unique = key
        copy_number = 1
        while unique in index:
            copy_number += 1
            unique = "%s~%d" % (key, copy_number)
        index[unique] = obj.get("id")

    def walk_subs(subs, action_name, counter):
        for sub in subs or []:
            if not isinstance(sub, dict):
                continue
            put("sub:%s#%d" % (action_name, counter[0]), sub)
            counter[0] += 1
            walk_subs(sub.get("subActions"), action_name, counter)

    data = model.get("data") if isinstance(model.get("data"), dict) else {}
    for queue in data.get("queues") or []:
        if isinstance(queue, dict):
            put("queue:%s" % queue.get("name"), queue)
    for action in data.get("actions") or []:
        if not isinstance(action, dict):
            continue
        name = action.get("name")
        put("action:%s" % name, action)
        for position, trigger in enumerate(action.get("triggers") or []):
            if isinstance(trigger, dict):
                put("trigger:%s#%d" % (name, position), trigger)
        walk_subs(action.get("subActions"), name, [0])
    return index


def diff_ids(model_a, model_b):
    """Compare object ids between two models; the last line is the summary."""
    a = _index_objects(model_a)
    b = _index_objects(model_b)
    lines = []
    counts = {"same": 0, "changed": 0, "only_a": 0, "only_b": 0}
    for key, id_a in a.items():
        if key not in b:
            lines.append("ONLY-A %s" % key)
            counts["only_a"] += 1
        elif b[key] == id_a:
            lines.append("SAME %s" % key)
            counts["same"] += 1
        else:
            lines.append("CHANGED %s %s -> %s" % (key, id_a, b[key]))
            counts["changed"] += 1
    for key in b:
        if key not in a:
            lines.append("ONLY-B %s" % key)
            counts["only_b"] += 1
    lines.append("diff-ids: same=%(same)d changed=%(changed)d only_a=%(only_a)d only_b=%(only_b)d" % counts)
    return lines


FORBIDDEN_COLLECTIONS = ("commands", "websocketServers", "websocketClients", "timers")

_SECRET_RULES = (
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.")),
    ("bearer", re.compile(r"Bearer\s")),
    ("client_secret", re.compile(r"client_secret", re.IGNORECASE)),
    ("access_token", re.compile(r"access_token", re.IGNORECASE)),
    ("refresh_token", re.compile(r"refresh_token", re.IGNORECASE)),
    ("oauth-token", re.compile(r"oauth:")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("user-profile-path", re.compile(r"[A-Za-z]:[\\/]+Users[\\/]", re.IGNORECASE)),
)
_ANY_GUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
_LONG_TOKEN_RE = re.compile(r"[A-Za-z0-9+/=_-]{32,}")


def _mask(match_text):
    """First 3 characters plus the length; never the whole match."""
    return "%s…len=%d" % (match_text[:3], len(match_text))


def _scan_text(text):
    """Return [(rule, masked preview)] with at most one entry per rule."""
    hits = []
    for rule, pattern in _SECRET_RULES:
        found = pattern.search(text)
        if found:
            hits.append((rule, _mask(found.group(0))))
    without_guids = _ANY_GUID_RE.sub(" ", text)
    for found in _LONG_TOKEN_RE.finditer(without_guids):
        if len(set(found.group(0))) > 2:
            hits.append(("long-token", _mask(found.group(0))))
            break
    return hits


def _safe(value):
    """Display text for REVIEW/INFO lines: redacted when it looks like a secret, shortened otherwise."""
    text = str(value).replace("\r", " ").replace("\n", " ")
    if _scan_text(text):
        return "<redacted: matches a secret rule>"
    return text if len(text) <= 80 else text[:77] + "..."


def _walk_sub_actions(subs):
    for sub in subs or []:
        if isinstance(sub, dict):
            yield sub
            yield from _walk_sub_actions(sub.get("subActions"))


def _type_set(values):
    return ",".join(str(v) for v in sorted(values, key=lambda v: (not isinstance(v, int), v if isinstance(v, int) else str(v))))


def audit_findings(model, allowed_prefixes):
    """Return (hard, review, info) line lists for the secret and shape audit."""
    hard, review, info = [], [], []
    prefixes = tuple(allowed_prefixes)
    data = model.get("data") if isinstance(model.get("data"), dict) else {}
    meta = model.get("meta") if isinstance(model.get("meta"), dict) else {}
    actions = [a for a in (data.get("actions") or []) if isinstance(a, dict)]
    queues = [q for q in (data.get("queues") or []) if isinstance(q, dict)]

    for key in FORBIDDEN_COLLECTIONS:
        value = data.get(key)
        if value:
            size = len(value) if hasattr(value, "__len__") else 1
            hard.append("HARD structure:non-empty-%s $.data.%s: %d item(s)" % (key, key, size))
    for index, action in enumerate(data.get("actions") or []):
        name = action.get("name") if isinstance(action, dict) else None
        if not isinstance(name, str) or not name.startswith(prefixes):
            hard.append("HARD structure:action-prefix $.data.actions[%d].name: %s" % (index, _safe(name)))

    for path, key, value in iter_nodes(model):
        if not isinstance(value, str):
            continue
        shown_path = path
        text = value
        if key == "byteCode":
            try:
                text = decode_bytecode(value)
            except SbFormatError:
                hard.append("HARD structure:bytecode-undecodable %s: byteCode cannot be decoded, so it cannot be audited" % path)
                continue
            shown_path = path + "(decoded)"
        for rule, masked in _scan_text(text):
            hard.append("HARD secret:%s %s: %s" % (rule, shown_path, masked))

    review.append("REVIEW meta.author=%s" % _safe(meta.get("author")))
    for queue in queues:
        review.append("REVIEW queue=%s" % _safe(queue.get("name")))

    def unknown(kind, obj):
        known = KNOWN_KEYS.get(kind, set())
        for key in obj:
            if key not in known:
                review.append("REVIEW unknown-key %s %s" % (kind, _safe(key)))

    unknown("top", model)
    unknown("meta", meta)
    unknown("data", data)
    for queue in queues:
        unknown("queue", queue)
    sub_types, trigger_types = set(), set()
    for action in actions:
        unknown("action", action)
        for trigger in action.get("triggers") or []:
            if isinstance(trigger, dict):
                trigger_types.add(trigger.get("type"))
                unknown("trigger:%s" % trigger.get("type"), trigger)
        for sub in _walk_sub_actions(action.get("subActions")):
            sub_types.add(sub.get("type"))
            unknown("subaction:%s" % sub.get("type"), sub)

    info.append("INFO version=%s exportedFrom=%s minimumVersion=%s" % (
        _safe(model.get("version")), _safe(model.get("exportedFrom")), _safe(model.get("minimumVersion"))))
    info.append("INFO meta.name=%s" % _safe(meta.get("name")))
    info.append("INFO actions=%d %s" % (len(actions), "; ".join(_safe(a.get("name")) for a in actions)))
    info.append("INFO subActionTypes=%s" % _type_set(sub_types))
    info.append("INFO triggerTypes=%s" % _type_set(trigger_types))
    return hard, review, info


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


def _cmd_check(args):
    model, json_bytes = read_sb(args.file)
    failed = 0
    hard_lines = []
    for name, check in _CHECKS:
        found = check(model, json_bytes)
        print("%s check:%s" % ("FAIL" if found else "PASS", name))
        failed += 1 if found else 0
        hard_lines.extend(found)
    for line in hard_lines:
        print(line)
    print("check: %d failed" % failed)
    return 1 if failed else 0


def _cmd_diff_ids(args):
    model_a, _ = read_sb(args.a)
    model_b, _ = read_sb(args.b)
    for line in diff_ids(model_a, model_b):
        print(line)
    return 0


def _cmd_audit(args):
    model, _ = read_sb(args.file)
    prefixes = DEFAULT_ALLOWED_PREFIXES + tuple(args.allow_prefix or ())
    hard, review, info = audit_findings(model, prefixes)
    for line in info + review + hard:
        print(line)
    print("audit: %d hard, %d review" % (len(hard), len(review)))
    return 1 if hard else 0


def _build_parser():
    parser = argparse.ArgumentParser(prog="build_sb.py", description="Streamer.bot .sb codec and safety tooling")
    sub = parser.add_subparsers(dest="command", required=True)
    decode = sub.add_parser("decode", help="print the decoded JSON model")
    decode.add_argument("file")
    decode.add_argument("--pretty", action="store_true", help="replace each byteCode by its decoded source (display only)")
    decode.add_argument("--out", help="write the JSON to this path instead of stdout")
    decode.set_defaults(func=_cmd_decode)
    check = sub.add_parser("check", help="generic structural checks (canonical form, ids, references)")
    check.add_argument("file")
    check.set_defaults(func=_cmd_check)
    diff = sub.add_parser("diff-ids", help="compare object ids between two .sb files (informational)")
    diff.add_argument("a")
    diff.add_argument("b")
    diff.set_defaults(func=_cmd_diff_ids)
    audit = sub.add_parser("audit", help="secret and shape audit; findings are masked, never the full value")
    audit.add_argument("file")
    audit.add_argument("--allow-prefix", action="append", metavar="PREFIX",
                       help="additional allowed action-name prefix (defaults: %s)" % ", ".join(DEFAULT_ALLOWED_PREFIXES))
    audit.set_defaults(func=_cmd_audit)
    return parser


def main(argv=None):
    _configure_streams()
    args = _build_parser().parse_args(argv)
    try:
        return args.func(args)
    except SbFormatError as e:
        sys.stderr.write("ERROR %s\n" % e)
        return 2
    except OSError as e:
        sys.stderr.write("ERROR cannot read file: %s\n" % e.strerror)
        return 2


if __name__ == "__main__":
    sys.exit(main())
