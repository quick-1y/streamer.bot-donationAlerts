import base64
import contextlib
import io
import json
import os
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
