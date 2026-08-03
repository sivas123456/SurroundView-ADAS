from __future__ import annotations

import random
import threading
import time
from datetime import datetime
from typing import Any

from flask import Flask, jsonify, render_template

app = Flask(__name__)

state_lock = threading.Lock()
stop_event = threading.Event()
runner_thread: threading.Thread | None = None

state: dict[str, Any] = {
    "devices": [
        {"ip": "192.168.43.1", "status": "Active", "detected_at": "", "is_new": False},
        {"ip": "192.168.43.20", "status": "Completed", "detected_at": "", "is_new": False},
    ],
    "ml": {"decision": "LOW", "network_load": 22, "latency": 14},
    "system_state": "Idle",
    "progress": 0,
    "logs": [],
}


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(level: str, message: str) -> None:
    with state_lock:
        state["logs"].append({"time": ts(), "level": level, "message": message})
        state["logs"] = state["logs"][-250:]


def normalize_new_flags() -> None:
    with state_lock:
        for device in state["devices"]:
            device["is_new"] = False


def scan_network() -> None:
    normalize_new_flags()
    device_count = random.randint(3, 7)
    devices: list[dict[str, Any]] = []
    for i in range(device_count):
        ip = f"192.168.43.{10 + i}"
        devices.append(
            {
                "ip": ip,
                "status": random.choice(["Active", "Provisioning", "Completed"]),
                "detected_at": ts(),
                "is_new": i >= max(0, device_count - 2),
            }
        )

    with state_lock:
        state["devices"] = devices
    log("INFO", f"Network scan completed. {len(devices)} devices discovered.")


def run_provisioning() -> None:
    global runner_thread
    stop_event.clear()
    with state_lock:
        state["system_state"] = "Running"
        state["progress"] = 3
    log("INFO", "Provisioning run started from dashboard.")

    scan_network()
    for step in range(1, 11):
        if stop_event.is_set():
            with state_lock:
                state["system_state"] = "Idle"
            log("ERROR", "Provisioning interrupted by user.")
            runner_thread = None
            return

        time.sleep(0.8)
        with state_lock:
            state["progress"] = min(100, step * 10)
            state["ml"] = {
                "decision": random.choice(["LOW", "MEDIUM", "HIGH"]),
                "network_load": random.randint(18, 95),
                "latency": random.randint(8, 140),
            }
            for device in state["devices"]:
                device["status"] = random.choice(["Active", "Provisioning", "Completed"])
        log("INFO", f"Automation stage {step}/10 completed.")

    with state_lock:
        state["system_state"] = "Completed"
        state["progress"] = 100
    log("SUCCESS", "Provisioning workflow completed successfully.")
    runner_thread = None


@app.route("/")
def dashboard() -> str:
    return render_template("dashboard.html")


@app.route("/status")
def status() -> Any:
    with state_lock:
        return jsonify(state)


@app.route("/run")
def run() -> Any:
    global runner_thread
    if runner_thread and runner_thread.is_alive():
        return jsonify({"ok": False, "message": "Run already in progress"})
    runner_thread = threading.Thread(target=run_provisioning, daemon=True)
    runner_thread.start()
    return jsonify({"ok": True, "message": "Provisioning started"})


@app.route("/scan")
def scan() -> Any:
    scan_network()
    return jsonify({"ok": True, "message": "Scan completed"})


@app.route("/stop")
def stop() -> Any:
    stop_event.set()
    return jsonify({"ok": True, "message": "Stop signal sent"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
