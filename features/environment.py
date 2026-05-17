import atexit
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests

from features.locators.api_locators import Defaults, Endpoints, StatusCodes


APP_PROCESS = None


def _port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def _stop_app():
    global APP_PROCESS
    if APP_PROCESS and APP_PROCESS.poll() is None:
        APP_PROCESS.terminate()
        try:
            APP_PROCESS.wait(timeout=5)
        except subprocess.TimeoutExpired:
            APP_PROCESS.kill()
    APP_PROCESS = None


def before_all(context):
    os.makedirs("reports", exist_ok=True)
    os.makedirs("tests", exist_ok=True)

    port = 8000 if _port_is_free(8000) else 8001
    os.environ["BASE_URL"] = f"http://localhost:{port}"

    global APP_PROCESS
    APP_PROCESS = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    atexit.register(_stop_app)

    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            response = requests.get(Endpoints.HEALTH, timeout=1)
            if response.status_code == StatusCodes.OK:
                context.base_url = os.environ["BASE_URL"]
                print("App started")
                return
        except requests.ConnectionError:
            time.sleep(0.5)
    _stop_app()
    raise RuntimeError("FastAPI app failed to start within 10 seconds")


def before_scenario(context, scenario):
    context.start_time = time.time()
    context.last_endpoint = ""


def after_scenario(context, scenario):
    duration_ms = (time.time() - context.start_time) * 1000
    log_file = os.getenv("LOG_FILE", Defaults.LOG_FILE)
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scenario": scenario.name,
        "feature": scenario.feature.name,
        "tags": list(scenario.tags),
        "status": "passed" if scenario.status.name == "passed" else "failed",
        "duration_ms": duration_ms,
        "endpoint": context.last_endpoint,
        "commit_sha": os.getenv(Defaults.COMMIT_SHA_ENV, ""),
        "changed_files": os.getenv(Defaults.CHANGED_FILES_ENV, ""),
    }
    with open(log_file, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def after_all(context):
    _stop_app()
    print("App stopped")
