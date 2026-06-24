import sys
import json
import time
import struct

pipe = sys.argv[1]
result_file = sys.argv[2]

FIXTURE_HANDLE = "119F5"


def frame(op, **kw):
    body = json.dumps({"op": op, **kw}).encode("utf-8")
    return struct.pack("<I", len(body)) + body


def _readn(f, n):
    buf = b""
    while len(buf) < n:
        c = f.read(n - len(buf))
        if not c:
            return None
        buf += c
    return buf


def rd(f):
    h = _readn(f, 4)
    if h is None:
        return None
    n = struct.unpack("<I", h)[0]
    body = _readn(f, n)
    return json.loads(body.decode("utf-8")) if body is not None else None


fh = None
for _ in range(60):
    try:
        fh = open(pipe, "r+b", buffering=0)
        break
    except OSError:
        time.sleep(0.5)

if fh is None:
    print("CLIENT: could not connect")
    sys.exit(1)


def call(op, **kw):
    fh.write(frame(op, **kw))
    fh.flush()
    r = rd(fh)
    print(op, "->", json.dumps(r, ensure_ascii=False))
    return r


res = {}
res["echo"] = call("live.echo", message="W4X_LIVE_UI_ATTENDED")
res["status"] = call("live.status")
res["tool_execute"] = call(
    "editor.toolpalette.tool_execute",
    execute=1,
    palette_name="ARIADNE_PALETTE",
    tool_name="ARIADNE_STATUS",
)
res["sub_highlight"] = call(
    "ui.subentity.highlight",
    handle=FIXTURE_HANDLE,
    subent_type="edge",
    subent_index=1,
    execute=1,
)
res["sub_clear"] = call(
    "ui.subentity.highlight",
    handle=FIXTURE_HANDLE,
    subent_type="edge",
    subent_index=1,
    execute=1,
    clear=1,
)
res["stop"] = call("live.stop")
fh.close()


def g(k):
    return res.get(k) or {}


tool = g("tool_execute").get("result", {})
sub_hl = g("sub_highlight").get("result", {})
sub_clr = g("sub_clear").get("result", {})
checks = {
    "echo": g("echo").get("echo") == "W4X_LIVE_UI_ATTENDED",
    "pump_running": g("status").get("pump") == "running",
    "host_full_autocad": g("status").get("host_mode") == "full_autocad",
    "tool_execute_status_ok": g("tool_execute").get("status") == "ok",
    "tool_execute_safe_status_only": tool.get("tool_execute_invoked") is False and tool.get("safe_status_only") is True,
    "tool_execute_no_raw_command_surface": tool.get("raw_command_agent_surface") is False,
    "sub_highlight_status_ok": g("sub_highlight").get("status") == "ok",
    "sub_highlight_real": sub_hl.get("attended_editor_present") is True and sub_hl.get("highlight_status") == 0 and sub_hl.get("display_flush") is True,
    "sub_highlight_marker_count": int(sub_hl.get("marker_count") or 0) >= 1,
    "sub_clear_real": g("sub_clear").get("status") == "ok" and sub_clr.get("highlight_status") == 0,
    "stop_ok": g("stop").get("stopped") is True,
}

allok = all(checks.values())
print("ATTENDED_CHECKS:", json.dumps(checks, ensure_ascii=False))
print("ATTENDED_LIVE_UI_OK:", allok)

json.dump(
    {
        "fixture": {
            "handle": FIXTURE_HANDLE,
            "subent_type": "edge",
            "subent_index": 1,
        },
        "checks": checks,
        "all_ok": allok,
        "responses": res,
    },
    open(result_file, "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=2,
)

sys.exit(0 if allok else 2)
