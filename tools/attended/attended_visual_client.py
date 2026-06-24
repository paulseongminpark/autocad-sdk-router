import sys
import json
import time
import struct

pipe = sys.argv[1]
result_file = sys.argv[2]


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
res["echo"] = call("live.echo", message="W4X_VISUAL_PLOT_ATTENDED")
res["status"] = call("live.status")
res["plot_settings"] = call("plot.config.settings")
res["plot_run"] = call("plot.engine.run")
res["stop"] = call("live.stop")
fh.close()


def g(k):
    return res.get(k) or {}


checks = {
    "echo": g("echo").get("echo") == "W4X_VISUAL_PLOT_ATTENDED",
    "pump_running": g("status").get("pump") == "running",
    "host_full_autocad": g("status").get("host_mode") == "full_autocad",
    "plot_settings_ok": g("plot_settings").get("status") == "ok",
    "plot_settings_layout": "layout_name" in g("plot_settings").get("result", {}),
    "plot_engine_created": g("plot_run").get("status") == "ok" and g("plot_run").get("result", {}).get("engine_created") is True,
    "plot_engine_status_ok": g("plot_run").get("status") == "ok" and g("plot_run").get("result", {}).get("engine_status") == 0,
    "stop_ok": g("stop").get("stopped") is True,
}

allok = all(checks.values())
print("ATTENDED_CHECKS:", json.dumps(checks, ensure_ascii=False))
print("ATTENDED_PUMP_OK:", allok)

json.dump(
    {"checks": checks, "all_ok": allok, "responses": res},
    open(result_file, "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=2,
)

sys.exit(0 if allok else 2)
