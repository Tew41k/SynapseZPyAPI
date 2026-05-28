from flask import Flask, jsonify, request
from flask_cors import CORS
from SynapseZAPI import SynapseZAPI, SynapseZAPI2
import threading
import time
import datetime

app = Flask(__name__)
CORS(app)

console_log = []
log_lock = threading.Lock()


def on_output(session, type_: int, output: str):
    labels = {0: "print", 1: "warn", 2: "error", 3: "system"}
    with log_lock:
        console_log.append({
            "type": labels.get(type_, "print"),
            "text": output,
            "pid": session.pid,
            "time": time.strftime("%H:%M:%S")
        })
        if len(console_log) > 200:
            console_log.pop(0)

def on_added(session):
    with log_lock:
        console_log.append({
            "type": "system",
            "text": f"Instance attached — PID {session.pid}",
            "pid": session.pid,
            "time": time.strftime("%H:%M:%S")
        })

def on_removed(session):
    with log_lock:
        console_log.append({
            "type": "system",
            "text": f"Instance detached — PID {session.pid}",
            "pid": 0,
            "time": time.strftime("%H:%M:%S")
        })

SynapseZAPI2.on_session_output(on_output)
SynapseZAPI2.on_session_added(on_added)
SynapseZAPI2.on_session_removed(on_removed)
SynapseZAPI2.start_instances_timer()


@app.route("/status")
def status():
    instances = SynapseZAPI2.get_instances()
    key = SynapseZAPI.get_account_key()
    return jsonify({
        "connected": len(instances) > 0,
        "instances": [{"pid": pid, "pipe": s.pipe_name} for pid, s in instances.items()],
        "has_key": bool(key),
        "key_preview": key[:8] + "..." if key else ""
    })

@app.route("/execute", methods=["POST"])
def execute():
    data = request.json or {}
    script = data.get("script", "")
    pid = int(data.get("pid", 0))
    use_pipe = data.get("use_pipe", True)

    if not script.strip():
        return jsonify({"ok": False, "error": "Empty script"})

    if use_pipe:
        SynapseZAPI2.execute(script, pid)
        return jsonify({"ok": True, "method": "pipe"})
    else:
        result = SynapseZAPI.execute(script, pid)
        errors = {1: "Bin folder not found", 2: "Scheduler folder not found", 3: "Write access denied"}
        if result == 0:
            return jsonify({"ok": True, "method": "scheduler"})
        return jsonify({"ok": False, "error": errors.get(result, "Unknown error")})

@app.route("/expire")
def expire():
    dt = SynapseZAPI.get_expire_date()
    if not dt:
        return jsonify({"ok": False, "error": SynapseZAPI.get_latest_error_message()})

    # Ensure dt is timezone-aware UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    now = datetime.datetime.now(datetime.timezone.utc)
    remaining_seconds = max(0, int((dt - now).total_seconds()))

    return jsonify({
        "ok": True,
        "expires_at": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),   # ISO 8601 UTC — машиночитаемый
        "expires_display": dt.strftime("%d.%m.%Y %H:%M UTC"),  # человекочитаемый
        "remaining_seconds": remaining_seconds,
        "active": remaining_seconds > 0
    })

@app.route("/redeem", methods=["POST"])
def redeem():
    data = request.json or {}
    key = data.get("key", "")
    result = SynapseZAPI.redeem(key)
    messages = {
        0:  ("ok",    "License activated successfully!"),
       -1:  ("error", "Account key not found"),
       -2:  ("error", SynapseZAPI.get_latest_error_message()),
       -3:  ("error", "Invalid or already used license")
    }
    status_str, msg = messages.get(result, ("error", "Unknown error"))
    return jsonify({"ok": result == 0, "status": status_str, "message": msg})

@app.route("/reset_hwid", methods=["POST"])
def reset_hwid():
    result = SynapseZAPI.reset_hwid()
    messages = {
        0:  (True,  "HWID reset successfully!"),
       -1:  (False, "Account key not found"),
       -2:  (False, SynapseZAPI.get_latest_error_message()),
       -3:  (False, "Cooldown active — try later"),
       -4:  (False, "Account is blacklisted")
    }
    ok, msg = messages.get(result, (False, "Unknown error"))
    return jsonify({"ok": ok, "message": msg})

@app.route("/logs")
def logs():
    with log_lock:
        return jsonify(list(console_log))

@app.route("/logs/clear", methods=["POST"])
def clear_logs():
    with log_lock:
        console_log.clear()
    return jsonify({"ok": True})

if __name__ == "__main__":
    print("RO-EXEC Server running → http://localhost:5000")
    print("Open ui.html in your browser.")
    app.run(host="localhost", port=5000, debug=False)
