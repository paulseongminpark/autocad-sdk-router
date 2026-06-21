#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CADOS M06 tests -- visual, batch, golden, performance, review reports."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _write_json(path: str | Path, obj: dict) -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _fixture_pair(tmp: str):
    import ir_builder

    pre = ir_builder.make_fixture_ir()
    post = json.loads(json.dumps(pre))
    handle = "M06A"
    post["entities"].append({
        "handle": handle,
        "class": "AcDbLine",
        "dxf_name": "LINE",
        "owner_handle": "1F",
        "space": "model",
        "layer": "0",
        "bbox": [0, 0, 0, 10, 0, 0],
        "geometry": {"kind": "line", "start": [0, 0, 0], "end": [10, 0, 0]},
    })
    post["diagnostics"]["entity_count"] = len(post["entities"])
    diff = {
        "schema": "ariadne.cad_diff.v1",
        "diff_id": "m06-test-diff",
        "changed_handles": [{"handle": handle, "change": "added", "dxf_name": "LINE", "layer": "0"}],
        "summary": {"added": 1, "removed": 0, "modified": 0, "created_count": 1,
                    "deleted_count": 0, "modified_count": 0},
        "diagnostics": {"comparison_basis": "handle", "warnings": [], "errors": []},
    }
    pre_path = _write_json(Path(tmp) / "pre.json", pre)
    post_path = _write_json(Path(tmp) / "post.json", post)
    diff_path = _write_json(Path(tmp) / "diff.json", diff)
    return pre_path, post_path, diff_path, handle, post


class TestM06VisualVerification(unittest.TestCase):
    def test_visual_verification_writes_required_artifacts_and_manifest(self):
        import cados_m06

        with tempfile.TemporaryDirectory(prefix="m06_visual_") as tmp:
            pre_path, post_path, diff_path, handle, _ = _fixture_pair(tmp)
            out_dir = os.path.join(tmp, "visual")

            result = cados_m06.build_visual_verification(
                pre_path, post_path, diff_path, out_dir=out_dir)

            self.assertEqual(result["schema"], "ariadne.cad_os.m06.visual_verification.v1")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["render_status"], "ok")
            self.assertIn(handle, result["handles_highlighted"])
            roles = {a["role"] for a in result["artifacts"]}
            self.assertGreaterEqual(roles, {"before", "after", "overlay", "visual_diff"})
            for artifact in result["artifacts"]:
                self.assertTrue(os.path.isfile(artifact["ref"]), artifact)
                self.assertGreater(artifact.get("byte_size", 0), 0)
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "visual_verification.json")))


class TestM06BatchRunner(unittest.TestCase):
    def test_batch_runner_validates_successes_and_quarantines_failures(self):
        import cados_m06

        with tempfile.TemporaryDirectory(prefix="m06_batch_") as tmp:
            pre_path, _, _, _, _ = _fixture_pair(tmp)
            manifest = {
                "schema": "ariadne.cad_os.m06.batch_manifest.v1",
                "fixtures": [
                    {"id": "small", "kind": "ir_validate", "ir_path": pre_path},
                    {"id": "missing", "kind": "ir_validate", "ir_path": os.path.join(tmp, "missing.json")},
                ],
            }
            manifest_path = _write_json(Path(tmp) / "manifest.json", manifest)

            result = cados_m06.run_batch_manifest(manifest_path, out_dir=os.path.join(tmp, "batch"))

            self.assertEqual(result["schema"], "ariadne.cad_os.m06.batch_result.v1")
            self.assertEqual(result["status"], "PARTIAL_PASS")
            self.assertEqual(result["successes"], 1)
            self.assertEqual(result["failures"], 1)
            self.assertEqual([q["id"] for q in result["quarantine"]], ["missing"])
            self.assertTrue(os.path.isfile(os.path.join(tmp, "batch", "batch_summary.json")))


class TestM06GoldenPerformanceAndReports(unittest.TestCase):
    def test_golden_regression_passes_expected_counts(self):
        import cados_m06

        with tempfile.TemporaryDirectory(prefix="m06_golden_") as tmp:
            pre_path, _, _, _, post = _fixture_pair(tmp)
            expected = {
                "schema": "ariadne.cad_os.expected_counts.v1",
                "modelspace_total": len(json.loads(Path(pre_path).read_text(encoding="utf-8"))["entities"]),
                "by_type": {"LINE": 1, "CIRCLE": 1, "INSERT": 1},
            }
            expected_path = _write_json(Path(tmp) / "expected_counts.json", expected)
            manifest = {"schema": "ariadne.cad_os.golden_manifest.v1",
                        "fixtures": [{"id": "small", "ir_path": pre_path}]}
            manifest_path = _write_json(Path(tmp) / "golden_manifest.json", manifest)

            result = cados_m06.run_golden_regression(
                manifest_path, expected_path, out_dir=os.path.join(tmp, "golden"))

            self.assertEqual(result["schema"], "ariadne.cad_os.m06.golden_regression.v1")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["fixtures"][0]["status"], "PASS")
            self.assertEqual(result["fixtures"][0]["entity_count"], expected["modelspace_total"])

    def test_performance_report_records_duration_size_and_threshold(self):
        import cados_m06

        with tempfile.TemporaryDirectory(prefix="m06_perf_") as tmp:
            pre_path, _, _, _, _ = _fixture_pair(tmp)

            result = cados_m06.build_performance_report(
                [{"id": "small", "kind": "ir", "path": pre_path}],
                out_dir=os.path.join(tmp, "perf"),
                thresholds={"small": {"max_duration_ms": 10_000}},
            )

            self.assertEqual(result["schema"], "ariadne.cad_os.m06.performance_report.v1")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["artifacts"][0]["id"], "small")
            self.assertGreaterEqual(result["artifacts"][0]["duration_ms"], 0)
            self.assertGreater(result["artifacts"][0]["byte_size"], 0)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "perf", "performance_report.json")))

    def test_review_report_writes_markdown_and_html(self):
        import cados_m06

        with tempfile.TemporaryDirectory(prefix="m06_review_") as tmp:
            summary = {
                "visual": {"status": "PASS", "artifacts": [{"role": "before", "ref": "before.svg"}]},
                "batch": {"status": "PASS", "successes": 1, "failures": 0},
                "golden": {"status": "PASS", "fixtures": [{"id": "small", "status": "PASS"}]},
                "performance": {"status": "PASS", "artifacts": [{"id": "small", "duration_ms": 1}]},
            }

            result = cados_m06.build_review_report(summary, out_dir=tmp)

            self.assertEqual(result["schema"], "ariadne.cad_os.m06.review_report.v1")
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(os.path.isfile(result["markdown_ref"]))
            self.assertTrue(os.path.isfile(result["html_ref"]))
            self.assertIn("Visual", Path(result["markdown_ref"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
