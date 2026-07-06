#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wave-R -- Get-NativeJobOpSet / Test-NativeP1CadJobOperation must never
silently misroute a native op.

Bug (root-caused live before this fix): Get-NativeJobOpSet builds its op set
from config/operations.v2.json (the SoT for which ops route to the native
ObjectARX .crx/.dbx job lane) and cached it per-process. On ANY read/parse
failure -- or if the file simply did not exist -- it silently swallowed the
error and cached an EMPTY set forever. Test-NativeP1CadJobOperation then
treated "empty set" as "registry unreadable" and fell back to a hardcoded
legacy op-id list that was missing newer write ops (write.dimstyle.create,
write.linetype.create, write.textstyle.create, and everything else added
since that list was last hand-maintained). A transient failed read (e.g.
while another process is writing operations.v2.json) would therefore
silently misroute those ops to the managed CadJobRunner.cs lane, which
throws "Unsupported CAD job operation" -- an intermittent, confusing
failure with no indication the registry read ever failed.

Fix: Get-NativeJobOpSet now retries briefly (3 attempts, ~200ms apart) on
any read/parse failure (including a missing file) and then FAILS LOUD
(throws, naming the registry path). The per-process cache is invalidated
whenever the registry file's mtime or size changes. The hardcoded legacy
op-id list is deleted entirely from Test-NativeP1CadJobOperation -- there is
no longer any fallback path, silent or otherwise.

These tests exercise the two PowerShell functions directly and in isolation.
Dot-sourcing/running the full router script always executes its trailing
`switch ($Action) { ... }` dispatch (PowerShell runs a script top-to-bottom
regardless of dot-sourcing), whose default 'status' action live-probes every
CAD route (slow) and whose 'run' action can launch the real accoreconsole
engine (well beyond what a fast unit test of two plain functions should do,
and this repo's own discipline is "no live CAD runs beyond -Action status" --
see AUTO_CAD_ROUTER_AGENT_CONTRACT.md). So each test here takes only the
router source up to (excluding) that trailing switch block -- the param()
block plus function definitions, which have no side effects on their own --
and appends a small driver tail that calls the functions directly against a
real or synthetic -RouterHome and prints the result as JSON.

This file touches no DWG and never spawns AutoCAD/accoreconsole.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

_THIS = Path(__file__).resolve()
_REPO = _THIS.parents[2]
_ROUTER = _REPO / "tools" / "autocad-router.ps1"

_MAIN_MARKER = "# ---- main ----"

_GETSET_START = "function Get-NativeJobOpSet {"
_TESTOP_START = "function Test-NativeP1CadJobOperation {"
_NEXT_FN_START = "function Test-NativeAcadModules {"


def _router_functions_prefix() -> str:
    """Return the router source up to (excluding) the "# ---- main ----"
    marker, i.e. param() + all function definitions only.

    Cutting here (rather than at the trailing `switch ($Action) { ... }`
    itself) also excludes the unconditional top-level
    `$capabilities = Read-JsonFile -Path $ConfigPath` load that immediately
    precedes the switch -- that line requires
    config/autocad_router_capabilities.json to exist under -RouterHome, which
    these tests' synthetic RouterHome directories deliberately do not
    provide (they only need config/operations.v2.json; Get-NativeJobOpSet
    and Test-NativeP1CadJobOperation do not touch $capabilities at all)."""
    text = _ROUTER.read_text(encoding="utf-8")
    idx = text.index(_MAIN_MARKER)
    return text[:idx]


def _run_ps1(body: str, router_home: str, timeout: int = 60):
    """Write `_router_functions_prefix() + body` to a temp .ps1 and run it
    with -RouterHome pinned to `router_home`. Returns (returncode, stdout,
    stderr)."""
    script = _router_functions_prefix() + "\n" + body + "\n"
    with tempfile.NamedTemporaryFile(
        "w", suffix=".ps1", delete=False, encoding="utf-8"
    ) as f:
        f.write(script)
        path = f.name
    try:
        proc = subprocess.run(
            [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", path, "-RouterHome", router_home,
            ],
            cwd=str(_REPO),
            capture_output=True,
            timeout=timeout,
        )
        # Windows PowerShell 5.1's own native error formatting (e.g. an
        # uncaught exception from a script bug) is localized on this
        # Korean-locale machine and written in the console's OEM codepage,
        # not UTF-8 -- decode leniently so a genuine script bug surfaces as
        # a readable assertion message instead of an opaque
        # UnicodeDecodeError from the test harness itself.
        out = proc.stdout.decode("utf-8", errors="replace")
        err = proc.stderr.decode("utf-8", errors="replace")
        return proc.returncode, out, err
    finally:
        Path(path).unlink(missing_ok=True)


_CALL_ONE_OP = r"""
$result = [ordered]@{}
try {
  $r = Test-NativeP1CadJobOperation -OperationName '__OPNAME__'
  $result.ok = $true
  $result.value = $r
} catch {
  $result.ok = $false
  $result.error = $_.Exception.Message
}
$result | ConvertTo-Json -Compress
"""

_CALL_ONE_OP_TIMED = r"""
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$result = [ordered]@{}
try {
  $r = Test-NativeP1CadJobOperation -OperationName '__OPNAME__'
  $result.ok = $true
  $result.value = $r
} catch {
  $result.ok = $false
  $result.error = $_.Exception.Message
}
$sw.Stop()
$result.elapsed_ms = $sw.ElapsedMilliseconds
$result | ConvertTo-Json -Compress
"""


class TestGetNativeJobOpSetBehavior(unittest.TestCase):
    """Behavioral tests: real registry, synthetic registry, missing/malformed
    registry, and cache invalidation on file change."""

    def test_real_registry_dimstyle_create_routes_native(self):
        """write.dimstyle.create is a real, already-registered ARIADNE_NATIVE_JOB
        op in this repo's live config/operations.v2.json (landed by the
        DIMSTYLE wave). This is the exact op the ticket calls out as silently
        misrouted whenever the old empty-set-triggers-hardcoded-fallback bug
        fired, since the legacy list never had it."""
        rc, out, err = _run_ps1(
            _CALL_ONE_OP.replace("__OPNAME__", "write.dimstyle.create"),
            router_home=str(_REPO),
        )
        self.assertEqual(rc, 0, err)
        payload = json.loads(out)
        self.assertTrue(payload["ok"], payload)
        self.assertTrue(payload["value"], "write.dimstyle.create must route native")

    def test_synthetic_registry_new_write_ops_route_native(self):
        """write.linetype.create / write.textstyle.create are the other two
        ops the ticket names -- at this commit they may not yet exist in the
        live registry (LINETYPE/TEXTSTYLE waves land concurrently), so this
        proves the *general* mechanism against a synthetic registry: any op
        id the registry marks ARIADNE_NATIVE_JOB routes native, and anything
        else does not -- with zero dependence on a hardcoded name list."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / "config"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "operations.v2.json").write_text(
                json.dumps({
                    "operations": [
                        {"id": "write.linetype.create",
                         "handler": {"router_lane": "ARIADNE_NATIVE_JOB"}},
                        {"id": "write.textstyle.create",
                         "handler": {"router_lane": "ARIADNE_NATIVE_JOB"}},
                        {"id": "write.some.managed_only_op",
                         "handler": {"router_lane": "ARIADNE_CAD_JOB"}},
                    ]
                }),
                encoding="utf-8",
            )
            body = r"""
$results = [ordered]@{}
foreach ($op in @('write.linetype.create', 'write.textstyle.create', 'write.some.managed_only_op')) {
  try {
    $results[$op] = Test-NativeP1CadJobOperation -OperationName $op
  } catch {
    $results[$op] = "ERROR: $($_.Exception.Message)"
  }
}
$results | ConvertTo-Json -Compress
"""
            rc, out, err = _run_ps1(body, router_home=tmp)
            self.assertEqual(rc, 0, err)
            payload = json.loads(out)
            self.assertTrue(payload["write.linetype.create"])
            self.assertTrue(payload["write.textstyle.create"])
            self.assertFalse(payload["write.some.managed_only_op"])

    def test_missing_registry_fails_loud_not_silent_empty_set(self):
        """No config/ subdirectory at all -- the OLD code silently returned an
        empty set (no exception, Test-Path just false) and then silently
        served the stale hardcoded list. The fix must throw, naming the
        registry path, instead of returning any value at all. The >= 350ms
        floor is evidence the 3-attempt/~200ms-apart retry loop actually ran
        (2 sleeps of 200ms) rather than failing on the first try -- a
        deterministic, non-flaky proxy for "the retry logic executed" that
        does not require racing a background writer thread."""
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, err = _run_ps1(
                _CALL_ONE_OP_TIMED.replace("__OPNAME__", "write.dimstyle.create"),
                router_home=tmp,
            )
            self.assertEqual(rc, 0, err)
            payload = json.loads(out)
            self.assertFalse(payload["ok"], payload)
            self.assertIn("operations.v2.json", payload["error"])
            self.assertGreaterEqual(
                payload["elapsed_ms"], 350,
                "expected the 3-attempt retry loop (~400ms of sleeps) to have run",
            )

    def test_malformed_json_registry_fails_loud(self):
        """A registry file that exists but fails to parse (e.g. truncated by
        a concurrent writer) must also retry-then-throw, never silently
        fall back to an empty/stale set."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / "config"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "operations.v2.json").write_text(
                "{ this is not valid json !!!", encoding="utf-8"
            )
            rc, out, err = _run_ps1(
                _CALL_ONE_OP_TIMED.replace("__OPNAME__", "write.dimstyle.create"),
                router_home=tmp,
            )
            self.assertEqual(rc, 0, err)
            payload = json.loads(out)
            self.assertFalse(payload["ok"], payload)
            self.assertIn("operations.v2.json", payload["error"])
            self.assertGreaterEqual(payload["elapsed_ms"], 350)

    def test_cache_invalidated_on_registry_mtime_change(self):
        """Same process, two calls: the first sees the op as native (registry
        v-A), then the registry is rewritten (op removed) with a forced,
        unambiguously-later mtime, then the second call -- in the SAME
        process, so this only proves anything if caching is real -- must see
        the update. If the cache were still keyed only on "have I ever read
        this file" (the old `$null -ne $script:_NativeJobOpSet` check with no
        mtime/size component), the second call would wrongly keep returning
        the first (stale) answer."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / "config"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            reg_path = cfg_dir / "operations.v2.json"
            reg_path.write_text(
                json.dumps({"operations": [
                    {"id": "probe.cache.op",
                     "handler": {"router_lane": "ARIADNE_NATIVE_JOB"}},
                ]}),
                encoding="utf-8",
            )
            body = r"""
$results = @()
try {
  $r1 = Test-NativeP1CadJobOperation -OperationName 'probe.cache.op'
  $results += [ordered]@{ ok = $true; value = $r1 }
} catch {
  $results += [ordered]@{ ok = $false; error = $_.Exception.Message }
}

$regPath = Join-Path $RouterHome 'config\operations.v2.json'
$newContent = @'
{"operations":[{"id":"probe.cache.op","handler":{"router_lane":"ARIADNE_CAD_JOB"}}]}
'@
Set-Content -LiteralPath $regPath -Value $newContent -Encoding UTF8
[System.IO.File]::SetLastWriteTimeUtc($regPath, [DateTime]::UtcNow.AddSeconds(5))

try {
  $r2 = Test-NativeP1CadJobOperation -OperationName 'probe.cache.op'
  $results += [ordered]@{ ok = $true; value = $r2 }
} catch {
  $results += [ordered]@{ ok = $false; error = $_.Exception.Message }
}
$results | ConvertTo-Json -Compress
"""
            rc, out, err = _run_ps1(body, router_home=tmp)
            self.assertEqual(rc, 0, err)
            payload = json.loads(out)
            self.assertEqual(len(payload), 2)
            self.assertTrue(payload[0]["ok"])
            self.assertTrue(payload[0]["value"], "v-A: probe.cache.op should be native")
            self.assertTrue(payload[1]["ok"])
            self.assertFalse(
                payload[1]["value"],
                "v-B (after mtime-bumped rewrite) must not serve the v-A cached answer",
            )


class TestLegacyFallbackRemovedFromSource(unittest.TestCase):
    """Static/tripwire checks on the router source itself: the hardcoded
    legacy op list and the emptiness gate that triggered it must be gone,
    and the fail-loud machinery must be present. These are honest tripwires
    -- they prove the specific anti-pattern cannot silently regress, not that
    every possible future bug is impossible."""

    def setUp(self):
        self.text = _ROUTER.read_text(encoding="utf-8")

    def test_legacy_fallback_comment_and_literals_gone(self):
        self.assertNotIn("Legacy explicit fallback", self.text)
        # NOTE: 'live.jig.point_probe' is deliberately NOT checked here -- unlike
        # the other three, it legitimately reappears elsewhere in the router
        # (Invoke-CadJobRoute / the full-AutoCAD jig-wait path compare
        # $jobOperation against it directly for real jig-handling logic, see
        # around line ~850 and ~936), so its presence is expected and correct.
        for legacy_literal in (
            "'inspect.protocol.queryx'",
            "'extend.customobject.create'",
            "'inspect.jig.host_support'",
        ):
            self.assertNotIn(
                legacy_literal, self.text,
                f"{legacy_literal} should no longer appear anywhere in the router "
                "-- it was only ever present as part of the deleted hardcoded list",
            )

    def test_get_native_job_opset_fails_loud_with_mtime_cache(self):
        start = self.text.index(_GETSET_START)
        end = self.text.index(_TESTOP_START)
        body = self.text[start:end]
        self.assertNotIn("catch { }", body, "no more bare error-swallowing catch")
        self.assertIn("throw", body, "must fail loud on unrecoverable read/parse failure")
        self.assertIn("Start-Sleep", body, "must retry before giving up")
        self.assertIn("LastWriteTimeUtc", body, "cache key must include file mtime")

    def test_test_native_p1_cad_job_operation_has_no_fallback_gate(self):
        start = self.text.index(_TESTOP_START)
        end = self.text.index(_NEXT_FN_START)
        body = self.text[start:end]
        self.assertNotIn("$set.Count -gt 0", body, "emptiness must no longer gate a fallback")
        self.assertNotIn("-contains $OperationName", body, "hardcoded array fallback must be gone")


if __name__ == "__main__":
    unittest.main()
