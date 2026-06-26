"""Launch Sky Order Converter as a native desktop window."""

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_server(port: int, timeout: float = 45.0) -> bool:
    url = f"http://127.0.0.1:{port}/"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(0.4)
    return False


def start_streamlit(base: Path, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["SKY_DESKTOP"] = "1"
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"

    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(base / "app.py"),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
            "--server.port",
            str(port),
            "--server.address",
            "127.0.0.1",
        ],
        cwd=base,
        env=env,
    )


def main() -> None:
    base = app_dir()
    os.chdir(base)
    port = free_port()
    proc = start_streamlit(base, port)

    try:
        if not wait_for_server(port):
            raise RuntimeError("Sky Order Converter failed to start.")

        url = f"http://127.0.0.1:{port}"
        try:
            import webview

            webview.create_window(
                "Sky Order Converter",
                url,
                width=1100,
                height=820,
                min_size=(800, 600),
            )
            webview.start()
        except ImportError:
            import webbrowser

            webbrowser.open(url)
            proc.wait()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
