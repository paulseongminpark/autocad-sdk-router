#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""anchor_ops -- semantic anchor (CAD OS Layer, Wave 5 / Lane W5-ANCHOR) TESTS.

Intent (WHY):
  anchor_ops adds no new native op: it composes the ALREADY live-certified
  set_entity_xdata_by_handle write (native modify.entity.xdata) with a
  Python-side JSON-chunking encode/decode. The pure logic (chunking, envelope
  schema, size guard, malformed-input tolerance, IR-side lookup) is unit
  tested here with synthetic data -- no accoreconsole, no AutoCAD, ever (same
  discipline test_op_roundtrip_probe.py already established for its own
  injected-fake-apply_staged suite).

  The genuine end-to-end proof -- a real anchor written to a real staged DWG,
  reopened in a FRESH accoreconsole process, and read back byte-identical --
  is a separate CADOS_LIVE=1 (+ tests/fixtures/native_sample.dwg present)
  smoke at the bottom of this file, skipped by default with an explicit
  reason (same convention test_attended_lane.py already established for its
  own live leg). Its findings are also recorded in build_log.md, section
  "Lane W5-ANCHOR".

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib
only for the non-live tests.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import anchor_ops  # noqa: E402


# ========================================================================== #
# 1. Chunking primitives -- pure, no I/O.
# ========================================================================== #

class TestUtf8Chunking(unittest.TestCase):
    def test_empty_text_yields_one_empty_chunk(self):
        self.assertEqual(anchor_ops._utf8_chunks("", 250), [""])

    def test_short_ascii_is_one_chunk(self):
        self.assertEqual(anchor_ops._utf8_chunks("hello", 250), ["hello"])

    def test_reassembly_is_lossless_for_ascii(self):
        text = "x" * 1000
        chunks = anchor_ops._utf8_chunks(text, 250)
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(c.encode("utf-8")) <= 250 for c in chunks))

    def test_255_byte_boundary_ascii(self):
        """A run of exactly 255 ASCII bytes must split at the 250-byte cap
        (250 + 5), never producing an oversized chunk."""
        text = "a" * 255
        chunks = anchor_ops._utf8_chunks(text, 250)
        self.assertEqual([len(c.encode("utf-8")) for c in chunks], [250, 5])
        self.assertEqual("".join(chunks), text)

    def test_exactly_max_bytes_is_a_single_chunk(self):
        text = "a" * 250
        chunks = anchor_ops._utf8_chunks(text, 250)
        self.assertEqual(chunks, [text])

    def test_one_byte_over_max_splits_into_two(self):
        text = "a" * 251
        chunks = anchor_ops._utf8_chunks(text, 250)
        self.assertEqual(len(chunks), 2)
        self.assertEqual("".join(chunks), text)

    def test_korean_text_never_splits_a_multibyte_char(self):
        """Korean syllables are 3 bytes each in UTF-8. A naive byte-offset cut
        would slice a character in half and corrupt it; the chunker must back
        off to the nearest character boundary instead."""
        # "평면도(기본형)" repeated so the byte length crosses several
        # chunk boundaries at non-multiple-of-3 offsets.
        text = "평면도(기본형)테스트" * 20
        for max_bytes in (250, 249, 248, 10, 7, 4, 3):
            with self.subTest(max_bytes=max_bytes):
                chunks = anchor_ops._utf8_chunks(text, max_bytes)
                # every chunk must itself be valid, round-trippable UTF-8
                for c in chunks:
                    self.assertEqual(c.encode("utf-8").decode("utf-8"), c)
                self.assertEqual("".join(chunks), text)
                for c in chunks:
                    self.assertLessEqual(len(c.encode("utf-8")), max_bytes)

    def test_max_bytes_too_small_for_one_codepoint_raises(self):
        # A single Korean syllable is 3 UTF-8 bytes; max_bytes=2 cannot hold one.
        with self.assertRaises(anchor_ops.AnchorError):
            anchor_ops._utf8_chunks("가", 2)


# ========================================================================== #
# 2. Envelope construction + validation.
# ========================================================================== #

class TestEncodeAnchorEnvelope(unittest.TestCase):
    def test_builds_expected_fields(self):
        env = anchor_ops.encode_anchor_envelope(
            {"k": "v"}, author_agent="agent-1", tags=["t1", "t2"])
        self.assertEqual(env["schema_version"], anchor_ops.SCHEMA_VERSION)
        self.assertEqual(env["author_agent"], "agent-1")
        self.assertEqual(env["tags"], ["t1", "t2"])
        self.assertEqual(env["body"], {"k": "v"})
        self.assertFalse(env["tombstone"])
        self.assertIn("timestamp", env)

    def test_missing_author_agent_raises(self):
        with self.assertRaises(anchor_ops.AnchorError):
            anchor_ops.encode_anchor_envelope({}, author_agent="")

    def test_non_dict_body_raises(self):
        with self.assertRaises(anchor_ops.AnchorError):
            anchor_ops.encode_anchor_envelope(["not", "a", "dict"], author_agent="a")

    def test_non_list_tags_raises(self):
        with self.assertRaises(anchor_ops.AnchorError):
            anchor_ops.encode_anchor_envelope({}, author_agent="a", tags="not-a-list")

    def test_tombstone_flag_is_carried(self):
        env = anchor_ops.encode_anchor_envelope({}, author_agent="a", tombstone=True)
        self.assertTrue(env["tombstone"])


# ========================================================================== #
# 3. encode_anchor_values / decode_anchor_values round trip.
# ========================================================================== #

class TestValuesRoundTrip(unittest.TestCase):
    def _values_to_items(self, values):
        """values (as sent to modify.entity.xdata) already ARE the
        {"code","value"} item shape the IR's entity.xdata[].items carries --
        this helper exists only to name that equivalence at the test call site."""
        return values

    def test_ascii_roundtrip(self):
        env = anchor_ops.encode_anchor_envelope({"a": 1, "b": [1, 2, 3]}, author_agent="a1")
        values = anchor_ops.encode_anchor_values(env)
        items = self._values_to_items(values)
        out = anchor_ops.decode_anchor_values(items)
        self.assertEqual(out, env)

    def test_korean_and_nested_json_roundtrip(self):
        body = {
            "note": "한국어 텍스트 확인 완전체",
            "nested": {
                "층": "1층",
                "list": [1, 2, {"평면도(기본형)": True}],
                "unicode_mix": "Line-A 평면도 テスト 混合",
            },
        }
        env = anchor_ops.encode_anchor_envelope(
            body, author_agent="claude-w5-anchor", tags=["load_bearing", "검증됨"])
        values = anchor_ops.encode_anchor_values(env, max_chunk_bytes=32)  # force many chunks
        self.assertGreater(len(values), 5, "expected several chunks at a tiny max_chunk_bytes")
        out = anchor_ops.decode_anchor_values(values)
        self.assertEqual(out, env)
        self.assertEqual(out["body"]["note"], "한국어 텍스트 확인 완전체")

    def test_values_shape_is_header_plus_base64_chunks(self):
        """The wire format must never put a literal '{'/'}'/'"' on the wire
        (the native job's item-boundary scanner corrupts on those -- see
        encode_anchor_values' docstring): header is a plain 'ANCHOR1|...'
        string, chunks are pure base64 alphabet."""
        env = anchor_ops.encode_anchor_envelope({"x": 1}, author_agent="a1")
        values = anchor_ops.encode_anchor_values(env)
        self.assertTrue(all(v["code"] == 1000 for v in values))
        for v in values:
            self.assertNotIn("{", v["value"])
            self.assertNotIn("}", v["value"])
            self.assertNotIn('"', v["value"])
        header_raw = values[0]["value"]
        self.assertTrue(header_raw.startswith("ANCHOR1|"))
        fields = dict(p.split("=", 1) for p in header_raw.split("|")[1:])
        n, declared_len, sha = int(fields["n"]), int(fields["len"]), fields["sha256"]
        self.assertEqual(n, len(values) - 1)
        b64_joined = "".join(v["value"] for v in values[1:])
        payload_bytes = base64.b64decode(b64_joined)
        self.assertEqual(len(payload_bytes), declared_len)
        self.assertEqual(hashlib.sha256(payload_bytes).hexdigest(), sha)
        self.assertEqual(json.loads(payload_bytes.decode("utf-8")), env)

    def test_255_byte_boundary_end_to_end(self):
        """A body whose serialized JSON lands right at a chunk boundary still
        round-trips exactly (regression guard for off-by-one errors)."""
        body = {"pad": "p" * 255}
        env = anchor_ops.encode_anchor_envelope(body, author_agent="a1")
        values = anchor_ops.encode_anchor_values(env, max_chunk_bytes=250)
        out = anchor_ops.decode_anchor_values(values)
        self.assertEqual(out, env)


# ========================================================================== #
# 4. Size guard.
# ========================================================================== #

class TestSizeGuard(unittest.TestCase):
    def test_oversized_payload_is_rejected(self):
        env = anchor_ops.encode_anchor_envelope({"blob": "z" * 100}, author_agent="a1")
        with self.assertRaises(anchor_ops.AnchorError):
            anchor_ops.encode_anchor_values(env, max_total_bytes=10)

    def test_payload_at_exactly_the_cap_is_accepted(self):
        # Build a body whose envelope serializes to EXACTLY max_total_bytes.
        probe_env = anchor_ops.encode_anchor_envelope({"pad": ""}, author_agent="a1")
        base_len = len(json.dumps(probe_env, ensure_ascii=False,
                                  separators=(",", ":"), sort_keys=True).encode("utf-8"))
        cap = base_len + 50
        env = anchor_ops.encode_anchor_envelope(
            {"pad": "p" * (cap - base_len)}, author_agent="a1")
        exact_len = len(json.dumps(env, ensure_ascii=False,
                                   separators=(",", ":"), sort_keys=True).encode("utf-8"))
        values = anchor_ops.encode_anchor_values(env, max_total_bytes=exact_len)
        self.assertTrue(values)

    def test_build_anchor_set_patch_propagates_size_guard(self):
        with self.assertRaises(anchor_ops.AnchorError):
            big_body = {"blob": "z" * (anchor_ops.MAX_ANCHOR_BYTES * 2)}
            anchor_ops.build_anchor_set_patch("1A2", big_body, author_agent="a1")


# ========================================================================== #
# 5. Malformed-anchor tolerance on read (decode_anchor_values).
# ========================================================================== #

class TestMalformedTolerance(unittest.TestCase):
    def test_empty_items_raises(self):
        with self.assertRaises(anchor_ops.AnchorError):
            anchor_ops.decode_anchor_values([])

    def test_header_not_recognized_raises(self):
        with self.assertRaises(anchor_ops.AnchorError):
            anchor_ops.decode_anchor_values([{"code": 1000, "value": "not-a-header"}])

    def test_header_wrong_version_prefix_raises(self):
        header = "ANCHOR2|n=0|len=0|sha256="
        with self.assertRaises(anchor_ops.AnchorError):
            anchor_ops.decode_anchor_values([{"code": 1000, "value": header}])

    def test_header_missing_field_raises(self):
        header = "ANCHOR1|n=1|sha256=abc"  # missing 'len'
        with self.assertRaises(anchor_ops.AnchorError):
            anchor_ops.decode_anchor_values(
                [{"code": 1000, "value": header}, {"code": 1000, "value": "eA=="}])

    def test_truncated_chunk_set_raises(self):
        env = anchor_ops.encode_anchor_envelope({"k": "v" * 500}, author_agent="a1")
        values = anchor_ops.encode_anchor_values(env, max_chunk_bytes=32)
        self.assertGreater(len(values), 3)
        truncated = values[:-1]  # drop the last chunk; header still claims the old n
        with self.assertRaises(anchor_ops.AnchorError):
            anchor_ops.decode_anchor_values(truncated)

    def test_tampered_chunk_fails_sha256_check(self):
        env = anchor_ops.encode_anchor_envelope({"k": "v"}, author_agent="a1")
        values = anchor_ops.encode_anchor_values(env)
        tampered = [dict(v) for v in values]
        tampered[1]["value"] = tampered[1]["value"] + "TAMPERED"
        with self.assertRaises(anchor_ops.AnchorError):
            anchor_ops.decode_anchor_values(tampered)

    def test_wrong_chunk_count_header_raises(self):
        env = anchor_ops.encode_anchor_envelope({"k": "v"}, author_agent="a1")
        values = anchor_ops.encode_anchor_values(env)
        header_raw = values[0]["value"]
        fields = dict(p.split("=", 1) for p in header_raw.split("|")[1:])
        bumped_n = int(fields["n"]) + 5  # claim more chunks than are present
        tampered_header = "ANCHOR1|n=%d|len=%s|sha256=%s" % (
            bumped_n, fields["len"], fields["sha256"])
        tampered = [{"code": 1000, "value": tampered_header}] + values[1:]
        with self.assertRaises(anchor_ops.AnchorError):
            anchor_ops.decode_anchor_values(tampered)

    def test_body_schema_version_mismatch_raises(self):
        # A well-formed chunk set whose INNER envelope has a bad schema_version.
        bad_envelope_json = json.dumps({"schema_version": 999, "author_agent": "x",
                                        "timestamp": "t", "tags": [], "body": {},
                                        "tombstone": False},
                                       ensure_ascii=False, separators=(",", ":"))
        payload_bytes = bad_envelope_json.encode("utf-8")
        b64 = base64.b64encode(payload_bytes).decode("ascii")
        header = "ANCHOR1|n=1|len=%d|sha256=%s" % (
            len(payload_bytes), hashlib.sha256(payload_bytes).hexdigest())
        items = [{"code": 1000, "value": header}, {"code": 1000, "value": b64}]
        with self.assertRaises(anchor_ops.AnchorError):
            anchor_ops.decode_anchor_values(items)


# ========================================================================== #
# 6. IR-side lookup helpers (find_anchor_xdata_items / get_anchor_from_ir /
#    list_anchors_from_ir) against synthetic dwg_graph_ir.v1-shaped dicts --
#    no accoreconsole involved.
# ========================================================================== #

def _entity_with_anchor(handle, body, *, author_agent="a1", tombstone=False, cls="AcDbLine"):
    env = anchor_ops.encode_anchor_envelope(body, author_agent=author_agent, tombstone=tombstone)
    values = anchor_ops.encode_anchor_values(env)
    return {
        "handle": handle,
        "class": cls,
        "xdata": [{"app": anchor_ops.APP_NAME, "items": values}],
    }


class TestFindAnchorXdataItems(unittest.TestCase):
    def test_no_xdata_returns_none(self):
        self.assertIsNone(anchor_ops.find_anchor_xdata_items({"handle": "1A2"}))

    def test_other_apps_xdata_is_ignored(self):
        entity = {"handle": "1A2", "xdata": [{"app": "SOME_OTHER_APP", "items": [{"code": 1000, "value": "x"}]}]}
        self.assertIsNone(anchor_ops.find_anchor_xdata_items(entity))

    def test_finds_our_app_block_among_others(self):
        ours = {"app": anchor_ops.APP_NAME, "items": [{"code": 1000, "value": "hi"}]}
        entity = {"handle": "1A2", "xdata": [{"app": "OTHER", "items": []}, ours]}
        self.assertEqual(anchor_ops.find_anchor_xdata_items(entity), [{"code": 1000, "value": "hi"}])


class TestGetAnchorFromIr(unittest.TestCase):
    def test_handle_not_in_ir_is_not_found(self):
        ir = {"entities": []}
        out = anchor_ops.get_anchor_from_ir(ir, "1A2")
        self.assertEqual(out["status"], "not_found")

    def test_entity_without_anchor_is_not_found(self):
        ir = {"entities": [{"handle": "1A2", "class": "AcDbLine"}]}
        out = anchor_ops.get_anchor_from_ir(ir, "1A2")
        self.assertEqual(out["status"], "not_found")

    def test_live_anchor_is_returned_ok(self):
        entity = _entity_with_anchor("1A2", {"note": "평면도 test"}, author_agent="a1")
        ir = {"entities": [entity]}
        out = anchor_ops.get_anchor_from_ir(ir, "1A2")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["anchor"]["body"], {"note": "평면도 test"})

    def test_tombstoned_anchor_is_not_found(self):
        entity = _entity_with_anchor("1A2", {}, author_agent="a1", tombstone=True)
        ir = {"entities": [entity]}
        out = anchor_ops.get_anchor_from_ir(ir, "1A2")
        self.assertEqual(out["status"], "not_found")
        self.assertIn("tombstone", out["reason"])

    def test_malformed_xdata_is_reported_not_swallowed(self):
        entity = {"handle": "1A2", "xdata": [{"app": anchor_ops.APP_NAME,
                                              "items": [{"code": 1000, "value": "not-json"}]}]}
        ir = {"entities": [entity]}
        out = anchor_ops.get_anchor_from_ir(ir, "1A2")
        self.assertEqual(out["status"], "malformed")
        self.assertIn("reason", out)


class TestListAnchorsFromIr(unittest.TestCase):
    def test_lists_only_live_anchors(self):
        live = _entity_with_anchor("1A2", {"k": "v"}, author_agent="a1")
        cleared = _entity_with_anchor("2B3", {}, author_agent="a1", tombstone=True)
        plain = {"handle": "3C4", "class": "AcDbCircle"}
        ir = {"entities": [live, cleared, plain]}
        out = anchor_ops.list_anchors_from_ir(ir)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["anchors"][0]["handle"], "1A2")

    def test_malformed_anchor_is_reported_separately(self):
        bad = {"handle": "9F9", "xdata": [{"app": anchor_ops.APP_NAME,
                                          "items": [{"code": 1000, "value": "not-json"}]}]}
        ir = {"entities": [bad]}
        out = anchor_ops.list_anchors_from_ir(ir)
        self.assertEqual(out["count"], 0)
        self.assertEqual(out["malformed_count"], 1)
        self.assertEqual(out["malformed"][0]["handle"], "9F9")


# ========================================================================== #
# 7. Patch builders -- shape of the cad_patch.v1 handed to patch_engine.
# ========================================================================== #

class TestBuildAnchorSetPatch(unittest.TestCase):
    def test_reuses_the_existing_set_entity_xdata_by_handle_op(self):
        patch = anchor_ops.build_anchor_set_patch(
            "1A2", {"k": "v"}, author_agent="a1")
        self.assertEqual(patch["schema"], "ariadne.cad_patch.v1")
        ops = patch["operations"]
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0]["operation"], "set_entity_xdata_by_handle")
        args = ops[0]["args"]
        self.assertEqual(args["handle"], "1A2")
        self.assertEqual(args["app_name"], anchor_ops.APP_NAME)
        self.assertTrue(args["values"])

    def test_missing_handle_raises(self):
        with self.assertRaises(anchor_ops.AnchorError):
            anchor_ops.build_anchor_set_patch("", {"k": "v"}, author_agent="a1")

    def test_patch_op_is_declared_in_native_write_op_map(self):
        """The patch op this builder emits must already have a live native
        handler wired (tools/patch_ops/entities.py's WRITE_OP_MAP) -- this is
        NOT a new native op, just reuse."""
        import patch_ops  # sibling package (tools/patch_ops/__init__.py)
        self.assertEqual(
            patch_ops.NATIVE_WRITE_OP_MAP.get("set_entity_xdata_by_handle"),
            "modify.entity.xdata")


class TestBuildAnchorClearPatch(unittest.TestCase):
    def test_writes_a_tombstone_envelope(self):
        patch = anchor_ops.build_anchor_clear_patch("1A2", author_agent="a1")
        args = patch["operations"][0]["args"]
        envelope = anchor_ops.decode_anchor_values(args["values"])
        self.assertTrue(envelope["tombstone"])
        self.assertEqual(envelope["body"], {})

    def test_missing_handle_raises(self):
        with self.assertRaises(anchor_ops.AnchorError):
            anchor_ops.build_anchor_clear_patch("", author_agent="a1")

    def test_get_anchor_from_ir_treats_clear_patch_output_as_absent(self):
        """End-to-end at the pure-Python level (no DWG): what build_anchor_
        clear_patch would write, if placed straight into an entity's xdata,
        anchor.get reports as not_found."""
        patch = anchor_ops.build_anchor_clear_patch("1A2", author_agent="a1")
        values = patch["operations"][0]["args"]["values"]
        entity = {"handle": "1A2", "xdata": [{"app": anchor_ops.APP_NAME, "items": values}]}
        out = anchor_ops.get_anchor_from_ir({"entities": [entity]}, "1A2")
        self.assertEqual(out["status"], "not_found")


# ========================================================================== #
# 8. Genuine end-to-end proof -- CADOS_LIVE=1 + AutoCAD-capable router only.
#    Skipped by default with an explicit reason; never a silent/fake pass.
#    See build_log.md, section "Lane W5-ANCHOR", for the recorded numbers.
# ========================================================================== #

_FIXTURE = os.path.join(_REPO, "tests", "fixtures", "native_sample.dwg")


def _live_available() -> bool:
    return os.environ.get("CADOS_LIVE") == "1" and os.path.isfile(_FIXTURE)


def _live_skip_reason() -> str:
    reasons = []
    if os.environ.get("CADOS_LIVE") != "1":
        reasons.append("CADOS_LIVE!=1")
    if not os.path.isfile(_FIXTURE):
        reasons.append("fixture not found: %s" % _FIXTURE)
    return "SKIPPED_LIVE: " + ", ".join(reasons)


@unittest.skipUnless(_live_available(), _live_skip_reason())
class TestAnchorLiveCert(unittest.TestCase):
    """Real anchor.set -> independent fresh-process reopen -> anchor.get/list
    -> anchor.clear -> independent fresh-process reopen -> anchor.get/list,
    against a STAGED copy of tests/fixtures/native_sample.dwg. The original
    fixture's sha256 is verified unchanged at the end. Every step's own
    original_unchanged proof (from patch_engine.apply_staged) is asserted too.
    """

    @classmethod
    def setUpClass(cls):
        import patch_engine
        import cadctl
        import run_job
        import ir_builder
        cls.patch_engine = patch_engine
        cls.cad = cadctl.Cad()
        cls.run_job = run_job
        cls.ir_builder = ir_builder
        cls.run_dir = os.path.join(
            _REPO, "runs", "w5_anchor_live_cert_%s"
            % __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.makedirs(cls.run_dir, exist_ok=True)

    def _sha256(self, path):
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def _fresh_reopen_ir(self, staged_dwg_path, tag):
        """Independent fresh-process reopen: a NEW accoreconsole invocation
        (run_job.run_router_cad_job), decoupled from whatever process wrote
        staged_dwg_path, reusing patch_engine's own native_full IR builder --
        the same production code path apply_staged uses for its pre/post
        inspects, just called a second, independent time here."""
        out_dir = os.path.join(self.run_dir, "reopen_%s" % tag)
        run_res = self.run_job.run_router_cad_job(
            staged_dwg_path, out_dir, "inspect.database.graph", write_mode="read")
        ir_path = os.path.join(out_dir, "dwg_graph_ir.json")
        result = self.patch_engine._native_full_ir(
            self.ir_builder, run_res, staged_dwg_path, staged_dwg_path, ir_path, tag)
        self.assertTrue(result["ok"], "fresh reopen (%s) failed: %r" % (tag, result))
        return result["ir_path"]

    def test_full_lifecycle(self):
        sha_before = self._sha256(_FIXTURE)

        # --- discover a real, pre-existing entity handle to anchor onto ---
        discover_dir = os.path.join(self.run_dir, "discover")
        discover = self.cad.inspect(_FIXTURE, discover_dir, mode="graph", include_rich=True)
        self.assertEqual(discover.get("status"), "ok",
                         "discovery inspect failed: %r" % discover)
        ir_path = discover.get("dwg_graph_ir")
        self.assertTrue(ir_path and os.path.isfile(ir_path), "no IR produced by discovery inspect")
        with open(ir_path, "r", encoding="utf-8-sig") as fh:
            discover_ir = json.load(fh)
        entities = discover_ir.get("entities") or []
        self.assertTrue(entities, "native_sample.dwg produced no entities to anchor onto")
        target_handle = entities[0]["handle"]

        body = {
            "note": "한국어 텍스트 확인 완전체 -- Lane W5-ANCHOR live cert",
            "nested": {"층": "1층", "list": [1, 2, {"ok": True}],
                      "layer_ref": entities[0].get("layer")},
        }
        author_agent = "claude-w5-anchor-live-cert"

        # --- anchor.set on a STAGED copy (original untouched) ---
        set_dir = os.path.join(self.run_dir, "set")
        set_result = self.cad.anchor_set(
            _FIXTURE, target_handle, body, set_dir,
            author_agent=author_agent, tags=["live_cert", "검증됨"])
        self.assertEqual(set_result.get("status"), "ok",
                         "anchor_set did not succeed: %r" % set_result)
        patch_result = set_result["patch_result"]
        self.assertTrue(patch_result["original_unchanged"]["unchanged"],
                        "anchor_set's own original_unchanged proof failed")
        staged_after_set = patch_result["staged_output"]

        # --- independent fresh-process reopen #1 ---
        reopened_ir_1 = self._fresh_reopen_ir(staged_after_set, "after_set")
        get_1 = self.cad.anchor_get(reopened_ir_1, target_handle)
        self.assertEqual(get_1.get("status"), "ok", "anchor_get after set: %r" % get_1)
        self.assertEqual(get_1["anchor"]["body"], body,
                         "reassembled anchor body is not byte-identical to what was written")
        self.assertEqual(get_1["anchor"]["author_agent"], author_agent)

        list_1 = self.cad.anchor_list(reopened_ir_1)
        self.assertEqual(list_1.get("status"), "ok")
        self.assertIn(target_handle, [a["handle"] for a in list_1["anchors"]],
                     "anchor_list did not find the freshly-set anchor")

        # --- anchor.clear on the SAME (already-anchored) staged output ---
        clear_dir = os.path.join(self.run_dir, "clear")
        clear_result = self.cad.anchor_clear(
            staged_after_set, target_handle, clear_dir, author_agent=author_agent)
        self.assertEqual(clear_result.get("status"), "ok",
                         "anchor_clear did not succeed: %r" % clear_result)
        staged_after_clear = clear_result["patch_result"]["staged_output"]

        # --- independent fresh-process reopen #2 ---
        reopened_ir_2 = self._fresh_reopen_ir(staged_after_clear, "after_clear")
        get_2 = self.cad.anchor_get(reopened_ir_2, target_handle)
        self.assertEqual(get_2.get("status"), "not_found",
                         "anchor_get after clear should report not_found: %r" % get_2)
        list_2 = self.cad.anchor_list(reopened_ir_2)
        self.assertNotIn(target_handle, [a["handle"] for a in list_2["anchors"]],
                         "cleared anchor still present in anchor_list")

        # --- the pristine fixture was NEVER touched ---
        sha_after = self._sha256(_FIXTURE)
        self.assertEqual(sha_before, sha_after,
                         "tests/fixtures/native_sample.dwg changed during the live cert")


if __name__ == "__main__":
    unittest.main(verbosity=2)
