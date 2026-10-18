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
        for bad in ("not-a-guid", "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA", build_sb.NULL_GUID):
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


def audit_model(model, extra_args=()):
    with tempfile.TemporaryDirectory() as tmp:
        path = write_file(tmp, "m.sb", build_sb.pack(model))
        return run_cli(["audit", path] + list(extra_args))


def b64_text(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


PLANTED = {
    "jwt": "eyJhbGciOiJIUzI1NiJ9.e30.abc",
    "bearer": "Bearer zzTopSecretValue",
    "client_secret": "my client_secret value",
    "access_token": "my access_token value",
    "refresh_token": "my refresh_token value",
    "oauth-token": "oauth:qwertyuiop",
    "email": "streamer.person@example.org",
    "user-profile-path": "C:\\Users\\someone\\Documents\\notes.txt",
    "long-token": "0123456789abcdef0123456789abcdef01234567",
}


class AuditTests(unittest.TestCase):
    def test_audit_clean_model_has_no_hard_findings(self):
        code, out, _ = audit_model(make_model())
        self.assertEqual(code, 0, out)
        self.assertNotIn("HARD ", out)
        self.assertIn("audit: 0 hard,", out)

    def test_audit_planted_patterns_are_hard_and_never_echoed(self):
        for rule, planted in PLANTED.items():
            model = make_model()
            model["meta"]["description"] = planted
            code, out, _ = audit_model(model)
            self.assertEqual(code, 1, rule)
            self.assertIn("HARD secret:%s $.meta.description" % rule, out)
            self.assertNotIn(planted, out, rule)
        for rule in ("jwt", "email", "long-token", "oauth-token"):
            model = make_model()
            model["meta"]["description"] = PLANTED[rule]
            _, out, _ = audit_model(model)
            self.assertNotIn(PLANTED[rule][:8], out, rule)

    def test_audit_ignores_guids_and_reference_dll_paths(self):
        model = make_model()
        sub = model["data"]["actions"][0]["subActions"][0]
        sub["references"] = [
            "C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\mscorlib.dll",
            "C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\System.dll",
            ".\\Newtonsoft.Json.dll",
        ]
        code, out, _ = audit_model(model)
        self.assertEqual(code, 0, out)

    def test_audit_flags_secret_inside_decoded_bytecode_but_not_raw_base64(self):
        model = make_model()
        sub = model["data"]["actions"][0]["subActions"][0]
        sub["byteCode"] = b64_text('class CPHInline { string h = "Bearer abc"; }')
        code, out, _ = audit_model(model)
        self.assertEqual(code, 1)
        self.assertIn("HARD secret:bearer", out)
        self.assertIn("byteCode", out)
        self.assertNotIn("Bearer abc", out)

    def test_audit_does_not_scan_raw_bytecode_base64_as_long_token(self):
        model = make_model()
        sub = model["data"]["actions"][0]["subActions"][0]
        sub["byteCode"] = b64_text("public class CPHInline { public bool Execute() { return true; } } // padding padding")
        self.assertGreaterEqual(len(sub["byteCode"]), 32)
        code, out, _ = audit_model(model)
        self.assertEqual(code, 0, out)

    def test_audit_flags_undecodable_bytecode(self):
        model = make_model()
        model["data"]["actions"][0]["subActions"][0]["byteCode"] = "***"
        code, out, _ = audit_model(model)
        self.assertEqual(code, 1)
        self.assertIn("HARD structure:bytecode-undecodable", out)

    def test_audit_flags_non_empty_forbidden_collections(self):
        for key in ("commands", "websocketServers", "websocketClients", "timers"):
            model = make_model()
            model["data"][key] = [{"name": "x"}]
            code, out, _ = audit_model(model)
            self.assertEqual(code, 1, key)
            self.assertIn("HARD structure:non-empty-%s" % key, out)

    def test_audit_flags_action_name_outside_allowed_prefixes(self):
        model = make_model()
        model["data"]["actions"][0]["name"] = "Other | X"
        code, out, _ = audit_model(model)
        self.assertEqual(code, 1)
        self.assertIn("HARD structure:action-prefix", out)

    def test_audit_allow_prefix_option_extends_allowed_prefixes(self):
        model = make_model()
        model["data"]["actions"][0]["name"] = "Other | X"
        code, out, _ = audit_model(model, ["--allow-prefix", "Other |"])
        self.assertEqual(code, 0, out)

    def test_audit_unknown_key_is_review_only(self):
        model = make_model()
        model["data"]["actions"][0]["mystery"] = 1
        model["data"]["actions"][0]["subActions"][0]["extraThing"] = 2
        code, out, _ = audit_model(model)
        self.assertEqual(code, 0, out)
        self.assertIn("REVIEW unknown-key action mystery", out)
        self.assertIn("REVIEW unknown-key subaction:99999 extraThing", out)

    def test_audit_reports_author_queue_and_inventory_lines(self):
        model = make_model()
        model["meta"]["author"] = "Some Author"
        model["data"]["queues"].append({"id": OTHER_ID, "name": "Q"})
        model["data"]["actions"][0]["triggers"].append({"id": STRANGER_ID, "type": 401})
        code, out, _ = audit_model(model)
        self.assertEqual(code, 0, out)
        self.assertIn("REVIEW meta.author=Some Author", out)
        self.assertIn("REVIEW queue=Q", out)
        self.assertIn("INFO version=23 exportedFrom=1.0.4 minimumVersion=1.0.0-alpha.1", out)
        self.assertIn("INFO meta.name=Synthetic", out)
        self.assertIn("INFO actions=1 GOLDEN | T", out)
        self.assertIn("INFO subActionTypes=99999", out)
        self.assertIn("INFO triggerTypes=401", out)

    def test_audit_output_order_is_info_review_hard_summary(self):
        model = make_model()
        model["meta"]["description"] = PLANTED["email"]
        model["data"]["actions"][0]["mystery"] = 1
        _, out, _ = audit_model(model)
        lines = out.splitlines()
        first = {tag: next(i for i, l in enumerate(lines) if l.startswith(tag)) for tag in ("INFO", "REVIEW", "HARD", "audit:")}
        self.assertLess(first["INFO"], first["REVIEW"])
        self.assertLess(first["REVIEW"], first["HARD"])
        self.assertLess(first["HARD"], first["audit:"])

    def test_audit_review_lines_do_not_echo_secret_looking_values(self):
        model = make_model()
        model["meta"]["author"] = PLANTED["email"]
        _, out, _ = audit_model(model)
        self.assertNotIn(PLANTED["email"], out)

    def test_audit_findings_returns_hard_review_info_lists(self):
        hard, review, info = build_sb.audit_findings(make_model(), build_sb.DEFAULT_ALLOWED_PREFIXES)
        self.assertEqual(hard, [])
        self.assertTrue(any(line.startswith("INFO ") for line in info))
        self.assertTrue(all(line.startswith("REVIEW ") for line in review))

    def test_audit_exit_2_on_malformed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_file(tmp, "bad.sb", payload_of(b"{}", extra=b"x"))
            code, _, err = run_cli(["audit", path])
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("ERROR "))

    def test_audit_help_mentions_allow_prefix(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as caught:
                build_sb.main(["audit", "--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("--allow-prefix", out.getvalue())


GOLDEN_PATH = build_sb.REPO_ROOT / "tools" / "golden" / "golden-1.0.7.sb"


class BuildTests(unittest.TestCase):
    """The builder against the real 1.0.7 golden and the real spike manifest."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = build_sb.load_manifest("spike")
        cls.golden_model, cls.golden_json = build_sb.read_sb(GOLDEN_PATH)
        cls.templates = build_sb.Templates(cls.golden_model)
        cls.skipped = []
        cls.model, cls.expected_ids = build_sb.build_model(cls.manifest, cls.templates, cls.skipped)
        cls.json_bytes = build_sb.dump(cls.model)

    def written(self):
        """What read_sb returns for the written file: (model, decoded json bytes)."""
        packed = build_sb.pack(self.model)
        return build_sb.unpack(packed), build_sb.unpack_bytes(packed)

    def verify(self, model, json_bytes, manifest=None):
        return build_sb.verify_built(model, json_bytes, manifest or self.manifest, self.templates, self.expected_ids)

    @staticmethod
    def names(findings):
        return {finding.split(":", 1)[0] for finding in findings}

    def test_golden_fidelity_dump_reproduces_golden_json(self):
        reparsed = json.loads(self.golden_json.decode("utf-8"))
        self.assertEqual(build_sb.dump(reparsed), self.golden_json)

    def test_golden_fidelity_numeric_tokens_keep_their_form(self):
        self.assertIn(b'"weight": 0.0,', self.golden_json)
        self.assertIn(b'"weight": 0.0,', self.json_bytes)
        self.assertEqual(build_sb.unpack_bytes(build_sb.pack(self.golden_model)), self.golden_json)

    def test_two_builds_pack_to_identical_bytes_and_ids(self):
        model, ids = build_sb.build_model(self.manifest, self.templates)
        self.assertEqual(build_sb.pack(model), build_sb.pack(self.model))
        self.assertEqual(ids, self.expected_ids)

    def test_ids_are_uuid5_of_the_stable_name(self):
        namespace = self.manifest["namespace"]
        info = next(a for a in self.model["data"]["actions"] if a["name"] == "SPIKE | Info")
        self.assertEqual(info["id"], str(build_sb.uuid.uuid5(build_sb.uuid.UUID(namespace), "spike/action/SPIKE | Info")))
        self.assertEqual(self.expected_ids["spike/code/a"], build_sb.stable_id(namespace, "spike", "code", "a"))
        other = dict(self.manifest, namespace="00000000-0000-4000-8000-000000000001")
        other_model, _ = build_sb.build_model(other, self.templates)
        self.assertNotEqual(other_model["data"]["actions"][0]["id"], self.model["data"]["actions"][0]["id"])

    def test_fresh_build_has_no_findings(self):
        model, json_bytes = self.written()
        self.assertEqual(self.verify(model, json_bytes), [])

    def test_every_action_is_a_spike_action_and_exiting_is_skipped_only_when_golden_lacks_it(self):
        actions = self.model["data"]["actions"]
        self.assertTrue(all(a["name"].startswith("SPIKE |") for a in actions))
        has_exiting = 707 in self.templates.triggers
        self.assertEqual(len(actions), 26 if has_exiting else 25)
        if not has_exiting:
            self.assertEqual(self.skipped, ["SKIP SPIKE | On exiting: golden lacks trigger:707"])

    def test_code_references_equal_the_golden_code_template(self):
        template = self.templates.code(self.manifest["templates"])
        subs = build_sb._code_subs(self.model, self.manifest)
        self.assertEqual(len(subs), 2)
        for sub in subs:
            self.assertEqual(sub["references"], template["references"])

    def test_embedded_sources_are_exactly_the_manifest_sources(self):
        decoded = {sub["name"]: build_sb.decode_bytecode(sub["byteCode"]) for sub in build_sb._code_subs(self.model, self.manifest)}
        wanted = {c["name"]: build_sb.normalize_source(build_sb.source_path(c)) for c in self.manifest["codes"]}
        self.assertEqual(decoded, wanted)
        for text in decoded.values():
            self.assertNotIn("﻿", text)
            self.assertNotIn("\n", text.replace("\r\n", ""))

    def test_whole_action_copies_remap_every_golden_id_and_keep_parent_links(self):
        golden_ids = {v for _, k, v in build_sb.iter_nodes(self.golden_model) if k == "id"}
        emitted = {v for _, k, v in build_sb.iter_nodes(self.model) if k == "id"}
        self.assertFalse(golden_ids & emitted)
        copy_action = next(a for a in self.model["data"]["actions"] if a["name"] == "SPIKE | On event (json)")
        if_sub = next(s for s in copy_action["subActions"] if s["type"] == 120)
        for branch in if_sub["subActions"]:
            for child in branch["subActions"]:
                self.assertEqual(child["parentId"], branch["id"])
        queue = self.model["data"]["queues"][0]
        self.assertEqual(copy_action["queue"], queue["id"])

    def test_appended_method_continues_the_golden_index_sequence(self):
        copy_action = next(a for a in self.model["data"]["actions"] if a["name"] == "SPIKE | On event (dict)")
        golden_action = self.templates.action("SPIKE | On event (dict)")
        appended = copy_action["subActions"][-1]
        self.assertEqual(appended["index"], len(golden_action["subActions"]))
        self.assertEqual(appended["method"], "SpikeDumpArgs")

    def test_normalize_source_strips_bom_and_unifies_line_endings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_file(tmp, "x.cs", b"\xef\xbb\xbfa\nb\r\nc\n")
            self.assertEqual(build_sb.normalize_source(path), "a\r\nb\r\nc\r\n")

    # Mutation tests: each defect must be reported under the check that owns it.

    def test_mutation_flipped_byte_gives_roundtrip_finding(self):
        model, json_bytes = self.written()
        position = json_bytes.index(b"\r")
        flipped = json_bytes[:position] + b" " + json_bytes[position + 1:]
        self.assertEqual(len(flipped), len(json_bytes))
        self.assertIn("roundtrip", self.names(self.verify(model, flipped)))

    def test_mutation_changed_field_value_gives_model_finding(self):
        model, json_bytes = self.written()
        model["data"]["actions"][2]["name"] = "SPIKE | Info changed"
        self.assertIn("model", self.names(self.verify(model, json_bytes)))

    def test_mutation_written_file_differing_from_a_fresh_build_gives_deterministic_finding(self):
        model, _ = self.written()
        model["data"]["actions"][2]["name"] = "SPIKE | Info changed"
        self.assertIn("deterministic", self.names(self.verify(model, build_sb.dump(model))))

    def test_mutation_unstable_packing_gives_deterministic_finding(self):
        model, json_bytes = self.written()
        with mock.patch.object(build_sb, "pack", side_effect=[b"first", b"second"]):
            findings = self.verify(model, json_bytes)
        self.assertIn("deterministic", self.names(findings))

    def test_mutation_duplicated_id_gives_ids_finding(self):
        model, json_bytes = self.written()
        model["data"]["actions"][1]["id"] = model["data"]["actions"][0]["id"]
        self.assertIn("ids", self.names(self.verify(model, json_bytes)))

    def test_mutation_changed_id_gives_ids_finding(self):
        model, json_bytes = self.written()
        model["data"]["actions"][0]["id"] = "99999999-9999-4999-8999-999999999999"
        self.assertIn("ids", self.names(self.verify(model, json_bytes)))

    def test_keyset_mutation_added_key_gives_keysets_finding_for_every_object_kind(self):
        def action_with_key(model):
            model["data"]["actions"][0]["bogus"] = 1

        def trigger_with_key(model):
            next(a for a in model["data"]["actions"] if a["name"] == "SPIKE | On started")["triggers"][0]["bogus"] = 1

        def sub_with_key(model):
            model["data"]["actions"][2]["subActions"][0]["bogus"] = 1

        def queue_with_key(model):
            model["data"]["queues"][0]["bogus"] = 1

        def copied_nested_with_key(model):
            copy_action = next(a for a in model["data"]["actions"] if a["name"] == "SPIKE | On event (dict)")
            copy_action["subActions"][1]["subActions"][0]["subActions"][0]["bogus"] = 1

        for mutate in (action_with_key, trigger_with_key, sub_with_key, queue_with_key, copied_nested_with_key):
            with self.subTest(mutation=mutate.__name__):
                model, json_bytes = self.written()
                mutate(model)
                self.assertIn("keysets", self.names(self.verify(model, json_bytes)))

    def test_keyset_mutation_reordered_keys_gives_keysets_finding(self):
        model, json_bytes = self.written()
        action = model["data"]["actions"][0]
        model["data"]["actions"][0] = dict(reversed(list(action.items())))
        self.assertIn("keysets", self.names(self.verify(model, json_bytes)))

    def test_misspelled_method_in_manifest_copy_gives_methods_exist_finding(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["actions"][2]["subActions"][0]["method"] = "SpikeInfx"
        model, json_bytes = self.written()
        self.assertIn("methods-exist", self.names(self.verify(model, json_bytes, manifest)))

    def test_mutation_changed_byte_code_gives_bytecode_finding(self):
        model, json_bytes = self.written()
        sub = build_sb._code_subs(model, self.manifest)[0]
        sub["byteCode"] = build_sb.embed_source("class Other { }\r\n")
        self.assertIn("bytecode", self.names(self.verify(model, json_bytes)))

    def test_mutation_bom_in_byte_code_gives_no_bom_finding(self):
        model, json_bytes = self.written()
        sub = build_sb._code_subs(model, self.manifest)[0]
        sub["byteCode"] = base64.b64encode(build_sb.BOM + build_sb.decode_bytecode(sub["byteCode"]).encode("utf-8")).decode("ascii")
        self.assertIn("no-bom", self.names(self.verify(model, json_bytes)))

    def test_mutation_dangling_reference_gives_refs_finding(self):
        model, json_bytes = self.written()
        model["data"]["actions"][2]["subActions"][0]["executeCodeId"] = "12345678-1234-4234-8234-123456789abc"
        self.assertIn("refs", self.names(self.verify(model, json_bytes)))

    def test_mutation_golden_id_left_in_output_gives_refs_finding(self):
        model, json_bytes = self.written()
        golden_id = self.golden_model["data"]["actions"][0]["id"]
        model["data"]["actions"][2]["subActions"][0]["parentId"] = golden_id
        self.assertIn("refs", self.names(self.verify(model, json_bytes)))

    # Template handling.

    def test_missing_template_kind_stops_the_build_and_names_the_kind(self):
        golden = json.loads(json.dumps(self.golden_model))
        for action in golden["data"]["actions"]:
            action["triggers"] = [t for t in action["triggers"] if t["type"] != 706]
        templates = build_sb.Templates(golden)
        with self.assertRaises(build_sb.MissingTemplateError) as caught:
            build_sb.build_model(self.manifest, templates)
        self.assertEqual(caught.exception.kind, "trigger:706")
        self.assertIn("trigger:706", str(caught.exception))
        self.assertIn("RECIPE.md", str(caught.exception))

    def test_only_optional_actions_are_skipped_when_a_template_kind_is_missing(self):
        golden = json.loads(json.dumps(self.golden_model))
        for action in golden["data"]["actions"]:
            action["triggers"] = [t for t in action["triggers"] if t["type"] != 706]
        manifest = json.loads(json.dumps(self.manifest))
        next(a for a in manifest["actions"] if a["name"] == "SPIKE | On started")["optional"] = True
        skipped = []
        model, ids = build_sb.build_model(manifest, build_sb.Templates(golden), skipped)
        self.assertIn("SKIP SPIKE | On started: golden lacks trigger:706", skipped)
        self.assertNotIn("SPIKE | On started", [a["name"] for a in model["data"]["actions"]])
        self.assertFalse([name for name in ids if "SPIKE | On started" in name])

    def test_override_of_a_key_the_golden_template_lacks_is_refused(self):
        manifest = json.loads(json.dumps(self.manifest))
        next(a for a in manifest["actions"] if a["name"] == "SPIKE | On event (json)")["trigger_override"]["bogus"] = "x"
        with self.assertRaises(build_sb.SbFormatError) as caught:
            build_sb.build_model(manifest, self.templates)
        self.assertIn("no invented fields", str(caught.exception))
        with self.assertRaises(build_sb.SbFormatError):
            build_sb.set_existing({"a": 1}, "b", 2, "action")

    def test_manifest_source_outside_the_repository_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = write_file(tmp, "outside.cs", b"class X { }")
            for source in ("../outside.cs", "../../../outside.cs", outside):
                manifest = json.loads(json.dumps(self.manifest))
                manifest["codes"][0]["source"] = source
                with self.subTest(source=source):
                    with self.assertRaises(build_sb.SbFormatError):
                        build_sb.validate_manifest(manifest, "spike")

    def test_manifest_with_unknown_action_key_or_duplicate_name_is_rejected(self):
        for mutate in (
            lambda m: m["actions"][0].update(bogus=1),
            lambda m: m["actions"][1].update(name=m["actions"][0]["name"]),
            lambda m: m["actions"][0]["subActions"].append({"kind": "code", "code": "a"}),
            lambda m: m.update(namespace="not-a-uuid"),
            lambda m: m.update(out="elsewhere/spike.sb"),
        ):
            manifest = json.loads(json.dumps(self.manifest))
            mutate(manifest)
            with self.assertRaises(build_sb.SbFormatError):
                build_sb.validate_manifest(manifest, "spike")

    def test_load_manifest_rejects_path_like_package_names(self):
        for name in ("../spike", "spike/../spike", "", "Spike"):
            with self.assertRaises(build_sb.SbFormatError):
                build_sb.load_manifest(name)

    # Command line.

    def test_cli_build_check_writes_output_and_prints_every_pass_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "out", "spike.sb")
            code, out, err = run_cli(["build", "spike", "--check", "--out", target])
            self.assertEqual((code, err), (0, ""))
            self.assertTrue(os.path.getsize(target) > 0)
            self.assertEqual(build_sb.read_sb(target)[1], self.json_bytes)
        for name in build_sb.BUILD_CHECK_NAMES:
            self.assertIn("PASS build-check:%s\n" % name, out)
        self.assertNotIn("FAIL", out)
        self.assertRegex(out, r"built .+ actions=\d+ sha256-json=[0-9a-f]{64}")

    def test_cli_build_with_a_golden_lacking_a_required_kind_exits_1_naming_the_kind(self):
        golden = json.loads(json.dumps(self.golden_model))
        for action in golden["data"]["actions"]:
            action["triggers"] = [t for t in action["triggers"] if t["type"] != 706]
        with tempfile.TemporaryDirectory() as tmp:
            golden_file = write_file(tmp, "golden.sb", build_sb.pack(golden))
            target = os.path.join(tmp, "spike.sb")
            code, _, err = run_cli(["build", "spike", "--golden", golden_file, "--out", target])
            self.assertEqual(code, 1)
            self.assertIn("trigger:706", err)
            self.assertFalse(os.path.exists(target))

    def test_cli_build_unknown_package_exits_2(self):
        code, _, err = run_cli(["build", "no-such-package"])
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("ERROR "))


if __name__ == "__main__":
    unittest.main()
