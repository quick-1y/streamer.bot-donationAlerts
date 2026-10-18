import base64
import contextlib
import gzip
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import build_sb

ACTION_ID = "11111111-1111-4111-8111-111111111111"
SUB_ID = "22222222-2222-4222-8222-222222222222"
CS_SOURCE = "public class CPHInline { public bool Execute() { return true; } }"


def make_model():
    byte_code = base64.b64encode(CS_SOURCE.encode("utf-8")).decode("ascii")
    return {
        "meta": {
            "name": "Synthetic",
            "author": None,
            "version": "1.0.0",
            "description": None,
            "autoRunAction": None,
            "minimumVersion": None,
        },
        "data": {
            "actions": [
                {
                    "id": ACTION_ID,
                    "queue": build_sb.NULL_GUID,
                    "enabled": True,
                    "excludeFromHistory": False,
                    "excludeFromPending": False,
                    "name": "GOLDEN | T",
                    "group": None,
                    "alwaysRun": False,
                    "randomAction": False,
                    "concurrent": False,
                    "triggers": [],
                    "subActions": [
                        {
                            "name": "Execute Code",
                            "description": None,
                            "references": [],
                            "byteCode": byte_code,
                            "precompile": False,
                            "delayStart": False,
                            "saveResultToVariable": False,
                            "saveToVariable": None,
                            "id": SUB_ID,
                            "weight": 0.0,
                            "type": 99999,
                            "parentId": build_sb.NULL_GUID,
                            "enabled": True,
                            "index": 0,
                        }
                    ],
                    "collapsedGroups": [],
                }
            ],
            "queues": [],
            "commands": [],
            "websocketServers": [],
            "websocketClients": [],
            "timers": [],
        },
        "version": 23,
        "exportedFrom": "1.0.4",
        "minimumVersion": "1.0.0-alpha.1",
    }


class CodecTests(unittest.TestCase):
    def test_pack_unpack_round_trip(self):
        model = make_model()
        self.assertEqual(build_sb.unpack(build_sb.pack(model)), model)

    def test_dump_uses_crlf_two_space_indent_no_trailing_newline_no_bom(self):
        raw = build_sb.dump({"a": {"b": 1}})
        self.assertEqual(raw, b'{\r\n  "a": {\r\n    "b": 1\r\n  }\r\n}')
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))

    def test_non_ascii_survives_unescaped(self):
        raw = build_sb.dump({"name": "тест"})
        self.assertIn("тест".encode("utf-8"), raw)
        self.assertNotIn(b"\\u", raw)
        self.assertEqual(build_sb.unpack(build_sb.pack({"name": "тест"})), {"name": "тест"})

    def test_pack_starts_with_base64_of_magic(self):
        self.assertTrue(base64.b64decode(build_sb.pack(make_model()))[:4] == b"SBAE")

    def test_decode_cli_pretty_shows_bytecode_source(self):
        model = make_model()
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "in.sb")
            out = os.path.join(tmp, "out.json")
            with open(src, "wb") as f:
                f.write(build_sb.pack(model))
            code = build_sb.main(["decode", src, "--pretty", "--out", out])
            self.assertEqual(code, 0)
            with open(out, "r", encoding="utf-8") as f:
                text = f.read()
        self.assertIn(CS_SOURCE, text)
        decoded = json.loads(text)
        self.assertEqual(decoded["data"]["actions"][0]["name"], "GOLDEN | T")

    def test_decode_cli_without_pretty_keeps_model_equal(self):
        model = make_model()
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "in.sb")
            with open(src, "wb") as f:
                f.write(build_sb.pack(model))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = build_sb.main(["decode", src])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buf.getvalue()), model)


OTHER_ID = "33333333-3333-4333-8333-333333333333"
STRANGER_ID = "99999999-9999-4999-8999-999999999999"


def payload_of(json_bytes, extra=b"", magic=build_sb.MAGIC):
    return base64.b64encode(magic + gzip.compress(json_bytes, mtime=0) + extra)


def write_file(directory, name, data):
    path = os.path.join(directory, name)
    with open(path, "wb") as handle:
        handle.write(data)
    return path


def run_cli(argv):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = build_sb.main(argv)
    return code, out.getvalue(), err.getvalue()


class LimitTests(unittest.TestCase):
    def setUp(self):
        self.json_bytes = build_sb.dump(make_model())

    def test_unpack_bytes_accepts_exact_cap(self):
        payload = payload_of(self.json_bytes)
        result = build_sb.unpack_bytes(payload, max_bytes=len(self.json_bytes))
        self.assertEqual(result, self.json_bytes)

    def test_unpack_bytes_rejects_one_byte_over_cap(self):
        payload = payload_of(self.json_bytes)
        with self.assertRaises(build_sb.SbFormatError):
            build_sb.unpack_bytes(payload, max_bytes=len(self.json_bytes) - 1)

    def test_unpack_bytes_rejects_trailing_data_after_gzip_member(self):
        with self.assertRaises(build_sb.SbFormatError):
            build_sb.unpack_bytes(payload_of(self.json_bytes, extra=b"x"))

    def test_unpack_bytes_rejects_truncated_stream(self):
        stream = gzip.compress(self.json_bytes, mtime=0)
        payload = base64.b64encode(build_sb.MAGIC + stream[: len(stream) // 2])
        with self.assertRaises(build_sb.SbFormatError):
            build_sb.unpack_bytes(payload)

    def test_unpack_bytes_rejects_missing_magic(self):
        with self.assertRaises(build_sb.SbFormatError):
            build_sb.unpack_bytes(payload_of(self.json_bytes, magic=b"XXXX"))

    def test_unpack_bytes_rejects_invalid_base64(self):
        with self.assertRaises(build_sb.SbFormatError):
            build_sb.unpack_bytes(b"!!!not base64!!!")

    def test_unpack_bytes_rejects_utf8_bom(self):
        with self.assertRaises(build_sb.SbFormatError):
            build_sb.unpack_bytes(payload_of(b"\xef\xbb\xbf" + self.json_bytes))

    def test_unpack_bytes_rejects_invalid_utf8(self):
        with self.assertRaises(build_sb.SbFormatError):
            build_sb.unpack_bytes(payload_of(b'{"a": "\xff"}'))

    def test_unpack_rejects_non_object_top_level(self):
        with self.assertRaises(build_sb.SbFormatError):
            build_sb.unpack(payload_of(b"[1, 2]"))

    def test_unpack_bytes_rejects_input_over_input_cap(self):
        payload = payload_of(self.json_bytes)
        with mock.patch.object(build_sb, "MAX_INPUT_BYTES", len(payload) - 1):
            with self.assertRaises(build_sb.SbFormatError):
                build_sb.unpack_bytes(payload)

    def test_read_sb_rejects_file_over_input_cap_before_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_file(tmp, "big.sb", payload_of(self.json_bytes))
            with mock.patch.object(build_sb, "MAX_INPUT_BYTES", 10):
                with self.assertRaises(build_sb.SbFormatError):
                    build_sb.read_sb(path)

    def test_cli_decode_and_check_exit_2_on_malformed_files(self):
        bad_inputs = {
            "magic.sb": payload_of(self.json_bytes, magic=b"XXXX"),
            "trailing.sb": payload_of(self.json_bytes, extra=b"x"),
            "bom.sb": payload_of(b"\xef\xbb\xbf" + self.json_bytes),
        }
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in bad_inputs.items():
                path = write_file(tmp, name, data)
                for command in ("decode", "check"):
                    code, _, err = run_cli([command, path])
                    self.assertEqual(code, 2, "%s %s" % (command, name))
                    self.assertTrue(err.startswith("ERROR "), err)


def check_model(model, raw_json=None):
    data = raw_json if raw_json is not None else build_sb.dump(model)
    with tempfile.TemporaryDirectory() as tmp:
        path = write_file(tmp, "m.sb", payload_of(data))
        return run_cli(["check", path])


class CheckTests(unittest.TestCase):
    def test_check_clean_model_passes(self):
        code, out, _ = check_model(make_model())
        self.assertEqual(code, 0, out)
        self.assertIn("PASS check:roundtrip", out)
        self.assertIn("check: 0 failed", out)

    def test_check_accepts_null_guid_references_and_resolving_references(self):
        model = make_model()
        model["data"]["actions"][0]["subActions"][0]["parentId"] = ACTION_ID
        code, out, _ = check_model(model)
        self.assertEqual(code, 0, out)

    def test_check_flags_non_canonical_json_round_trip(self):
        compact = json.dumps(make_model()).encode("utf-8")
        code, out, _ = check_model(None, raw_json=compact)
        self.assertEqual(code, 1)
        self.assertIn("FAIL check:roundtrip", out)

    def test_check_flags_duplicate_id(self):
        model = make_model()
        model["data"]["actions"][0]["subActions"][0]["id"] = ACTION_ID
        code, out, _ = check_model(model)
        self.assertEqual(code, 1)
        self.assertIn("FAIL check:ids-unique", out)

    def test_check_flags_malformed_and_uppercase_ids(self):
        for bad in ("not-a-guid", ACTION_ID.upper(), build_sb.NULL_GUID):
            model = make_model()
            model["data"]["actions"][0]["subActions"][0]["id"] = bad
            code, out, _ = check_model(model)
            self.assertEqual(code, 1, bad)
            self.assertIn("FAIL check:ids-format", out)

    def test_check_flags_dangling_guid_reference(self):
        model = make_model()
        model["data"]["actions"][0]["queue"] = STRANGER_ID
        code, out, _ = check_model(model)
        self.assertEqual(code, 1)
        self.assertIn("FAIL check:refs-resolve", out)
        self.assertIn("HARD check:refs-resolve", out)

    def test_check_flags_undecodable_bytecode(self):
        model = make_model()
        model["data"]["actions"][0]["subActions"][0]["byteCode"] = "***"
        code, out, _ = check_model(model)
        self.assertEqual(code, 1)
        self.assertIn("FAIL check:bytecode-utf8", out)

    def test_structural_findings_flags_bom_in_json_bytes(self):
        model = make_model()
        lines = build_sb.structural_findings(model, b"\xef\xbb\xbf" + build_sb.dump(model))
        self.assertTrue(any("check:utf8-no-bom" in line for line in lines), lines)

    def test_check_with_no_file_argument_is_a_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                build_sb.main(["check"])
        self.assertEqual(caught.exception.code, 2)


def with_trigger(model, trigger_id=OTHER_ID):
    model["data"]["actions"][0]["triggers"].append({"id": trigger_id, "type": 401, "enabled": True})
    return model


class DiffIdsTests(unittest.TestCase):
    def test_diff_ids_identical_models_give_only_same_lines(self):
        lines = build_sb.diff_ids(make_model(), make_model())
        self.assertIn("SAME action:GOLDEN | T", lines)
        self.assertIn("SAME sub:GOLDEN | T#0", lines)
        self.assertFalse([l for l in lines if l.startswith(("CHANGED", "ONLY-"))], lines)
        self.assertEqual(lines[-1], "diff-ids: same=2 changed=0 only_a=0 only_b=0")

    def test_diff_ids_reports_changed_action_id(self):
        changed = make_model()
        changed["data"]["actions"][0]["id"] = OTHER_ID
        lines = build_sb.diff_ids(make_model(), changed)
        self.assertIn("CHANGED action:GOLDEN | T %s -> %s" % (ACTION_ID, OTHER_ID), lines)
        self.assertEqual(lines[-1], "diff-ids: same=1 changed=1 only_a=0 only_b=0")

    def test_diff_ids_reports_only_a_and_only_b(self):
        extra = make_model()
        extra["data"]["queues"].append({"id": OTHER_ID, "name": "Q"})
        lines = build_sb.diff_ids(extra, make_model())
        self.assertIn("ONLY-A queue:Q", lines)
        lines = build_sb.diff_ids(make_model(), extra)
        self.assertIn("ONLY-B queue:Q", lines)

    def test_diff_ids_numbers_triggers_and_nested_sub_actions_depth_first(self):
        model = with_trigger(make_model())
        sub = model["data"]["actions"][0]["subActions"][0]
        nested = dict(sub, id=STRANGER_ID, index=0)
        sub["subActions"] = [nested]
        lines = build_sb.diff_ids(model, model)
        self.assertIn("SAME trigger:GOLDEN | T#0", lines)
        self.assertIn("SAME sub:GOLDEN | T#0", lines)
        self.assertIn("SAME sub:GOLDEN | T#1", lines)

    def test_diff_ids_cli_returns_0_and_prints_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write_file(tmp, "a.sb", build_sb.pack(make_model()))
            b = write_file(tmp, "b.sb", build_sb.pack(make_model()))
            code, out, _ = run_cli(["diff-ids", a, b])
        self.assertEqual(code, 0)
        self.assertIn("diff-ids: same=2 changed=0 only_a=0 only_b=0", out)

    def test_diff_ids_cli_returns_2_on_format_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write_file(tmp, "a.sb", build_sb.pack(make_model()))
            b = write_file(tmp, "b.sb", b"garbage!")
            code, _, err = run_cli(["diff-ids", a, b])
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("ERROR "))


if __name__ == "__main__":
    unittest.main()
