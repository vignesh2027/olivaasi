"""Drive a private headless Chrome over the DevTools protocol (development tool only).

Used by scripts/a11y_check.py and scripts/screenshots.py. Starts its own
Chrome with its own profile folder and debugging port, and closes it after.

    OLIVAASI_CHROME   path to the Chrome binary
    OLIVAASI_CDP_PORT debugging port (default 9530)
    OLIVAASI_PROFILE  profile folder (default: a fresh temporary folder)
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket

CHROME = os.environ.get("OLIVAASI_CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


class Browser:
    def __init__(self, width: int = 1280, height: int = 900, scale: float = 1.0) -> None:
        self.port = int(os.environ.get("OLIVAASI_CDP_PORT", "9530"))
        profile = os.environ.get("OLIVAASI_PROFILE") or tempfile.mkdtemp(prefix="olivaasi-cdp-")
        Path(profile).mkdir(parents=True, exist_ok=True)
        self.proc = subprocess.Popen(
            [CHROME, "--headless=new", f"--remote-debugging-port={self.port}", f"--user-data-dir={profile}",
             "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "--mute-audio",
             "--autoplay-policy=no-user-gesture-required", f"--window-size={width},{height}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        ws_url = None
        for _ in range(100):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=1) as r:
                    pages = [p for p in json.load(r) if p["type"] == "page"]
                if pages:
                    ws_url = pages[0]["webSocketDebuggerUrl"]
                    break
            except OSError:
                pass
            time.sleep(0.1)
        if ws_url is None:
            self.close()
            raise RuntimeError("Chrome did not start")
        self.ws = websocket.create_connection(ws_url, timeout=60)
        self._id = 0
        self.send("Page.enable")
        self.send("Runtime.enable")
        self.send("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=scale, mobile=False)

    def send(self, method: str, **params):
        self._id += 1
        my = self._id
        self.ws.send(json.dumps({"id": my, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == my:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def goto(self, url: str, wait: float = 0.5) -> None:
        self.send("Page.navigate", url=url)
        deadline = time.time() + 30
        while time.time() < deadline:
            if self.eval("document.readyState") == "complete":
                break
            time.sleep(0.1)
        time.sleep(wait)

    def eval(self, expr: str, await_promise: bool = False):
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=await_promise)
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description", "script error"))
        return r.get("result", {}).get("value")

    def key(self, key: str, code: str | None = None, shift: bool = False) -> None:
        mods = 8 if shift else 0
        vk = {"Tab": 9, "Enter": 13, " ": 32}.get(key, 0)
        for t in ("keyDown", "keyUp"):
            self.send("Input.dispatchKeyEvent", type=t, key=key, code=code or key, modifiers=mods, windowsVirtualKeyCode=vk)

    def screenshot(self, path: Path, full: bool = False) -> None:
        params = {"format": "png"}
        if full:
            params["captureBeyondViewport"] = True
            h = self.eval("Math.ceil(document.documentElement.scrollHeight)")
            w = self.eval("document.documentElement.clientWidth")
            params["clip"] = {"x": 0, "y": 0, "width": w, "height": h, "scale": 1}
        data = self.send("Page.captureScreenshot", **params)["data"]
        path.write_bytes(base64.b64decode(data))

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
