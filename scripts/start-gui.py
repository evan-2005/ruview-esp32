#!/usr/bin/env python3
"""RuView laptop GUI launcher.

Starts everything needed for the browser dashboard with only the Python
standard library (plus the `websockets` + `numpy` deps of the sensing
server):

  1. The Python sensing WebSocket server (archive/v1) on ws://localhost:8765
     - auto-detects an ESP32 CSI stream on UDP :5005,
     - falls back to live laptop WiFi RSSI (netsh / /proc), then simulation.
  2. A static file server for ui/ on http://localhost:8080
     - sends `Cache-Control: no-cache` so edits show up on reload
       (plain `python -m http.server` lets browsers cache stale files).
  3. Opens the dashboard in the default browser.

Usage:
    python scripts/start-gui.py [--no-browser] [--http-port 8080]

Stop with Ctrl+C — both servers shut down together.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import signal
import socket
import subprocess
import sys
import threading
import webbrowser

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_DIR = os.path.join(REPO_ROOT, "ui")
ARCHIVE_DIR = os.path.join(REPO_ROOT, "archive")
DEFAULT_HTTP_PORT = 8080  # ui/ maps :8080 -> sensing WS :8765 (sensing.service.js)


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    """Static file handler that forbids stale caching of UI assets."""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # keep the console readable; errors still surface via stderr


def sensing_server_running(port: int = 8765) -> bool:
    """True if something already listens on the sensing WebSocket port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def start_sensing_server() -> subprocess.Popen | None:
    """Launch the archive/v1 sensing WebSocket server as a child process.

    Returns None if a sensing server is already running on :8765 —
    the GUI just attaches to the existing one.
    """
    if sensing_server_running():
        print("Sensing server already running on ws://localhost:8765 — reusing it.")
        return None
    return subprocess.Popen(
        [sys.executable, "-m", "v1.src.sensing.ws_server"],
        cwd=ARCHIVE_DIR,
    )


def serve_ui(port: int) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(NoCacheHandler, directory=UI_DIR)
    return http.server.ThreadingHTTPServer(("0.0.0.0", port), handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the RuView laptop GUI")
    parser.add_argument("--http-port", type=int, default=DEFAULT_HTTP_PORT,
                        help="UI port (default 8080; keep 8080 unless you also "
                             "change the WS port mapping in ui/services/sensing.service.js)")
    parser.add_argument("--no-browser", action="store_true",
                        help="Don't open the browser automatically")
    args = parser.parse_args()

    if not os.path.isdir(UI_DIR):
        print(f"ERROR: UI directory not found: {UI_DIR}", file=sys.stderr)
        return 1

    sensing_proc = start_sensing_server()

    try:
        httpd = serve_ui(args.http_port)
    except OSError as exc:
        print(f"ERROR: cannot bind UI port {args.http_port}: {exc}", file=sys.stderr)
        if sensing_proc is not None:
            sensing_proc.terminate()
        return 1

    url = f"http://localhost:{args.http_port}/index.html"
    print()
    print("  RuView GUI")
    print(f"    Dashboard : {url}")
    print("    Sensing WS: ws://localhost:8765  (ESP32 UDP :5005 auto-detected)")
    print("    Stop with Ctrl+C")
    print()

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    if not args.no_browser:
        webbrowser.open(url)

    stop = threading.Event()

    def _shutdown(signum, frame) -> None:
        stop.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while not stop.is_set():
            if sensing_proc is not None and sensing_proc.poll() is not None:
                print("Sensing server exited — shutting down GUI.", file=sys.stderr)
                break
            stop.wait(1.0)
    finally:
        httpd.shutdown()
        if sensing_proc is not None and sensing_proc.poll() is None:
            sensing_proc.terminate()
            try:
                sensing_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                sensing_proc.kill()

    print("Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
