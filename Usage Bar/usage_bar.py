"""Afaq's portable Codex Usage Bar. Standard library + already installed Pillow.

No login file is touched unless config.json explicitly enables authenticated usage.
Context percentages come from assistant-written status notes and are estimates.
"""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
import wave

ROOT = Path(__file__).resolve().parent
NOTIFICATIONS = ROOT.parent / "Notifications" / "afaq_notifications.py"
sys.path.insert(0, str(NOTIFICATIONS.parent))
from afaq_notifications import wave_bytes, play
HOME = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
u = ctypes.windll.user32
k = ctypes.windll.kernel32
_process_cache = {}
PTR = ctypes.c_ssize_t
u.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
u.GetWindowLongPtrW.restype = PTR
u.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, PTR]
u.SetWindowLongPtrW.restype = PTR
u.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
u.GetAncestor.restype = wintypes.HWND
u.GetForegroundWindow.restype = wintypes.HWND
u.IsIconic.argtypes = [wintypes.HWND]
u.IsWindowVisible.argtypes = [wintypes.HWND]
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                         ctypes.c_int, ctypes.c_int, wintypes.UINT]

WIN_EVENT_PROC = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD,
                                  wintypes.HWND, wintypes.LONG, wintypes.LONG,
                                  wintypes.DWORD, wintypes.DWORD)
u.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE,
                             WIN_EVENT_PROC, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
u.SetWinEventHook.restype = wintypes.HANDLE
u.UnhookWinEvent.argtypes = [wintypes.HANDLE]
u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
u.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
u.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
KEYBOARD_PROC = ctypes.WINFUNCTYPE(PTR, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
u.SetWindowsHookExW.argtypes = [ctypes.c_int, KEYBOARD_PROC, wintypes.HINSTANCE, wintypes.DWORD]
u.SetWindowsHookExW.restype = wintypes.HANDLE
u.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
u.CallNextHookEx.restype = PTR
u.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
k.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
k.GetModuleHandleW.restype = wintypes.HMODULE


class ForegroundVisibility:
    def __init__(self, overlays):
        self.overlays = overlays
        self.switching = False
        self.callback = WIN_EVENT_PROC(self.changed)
        self.keyboard_callback = KEYBOARD_PROC(self.key_changed)
        self.keyboard_hook = None
        self.key_switching = False
        self.hooks = []
        self.thread = None
        self.thread_id = None
        self.ready = threading.Event()
        self.error = None

    def start(self):
        self.thread = threading.Thread(target=self.listen, daemon=True)
        self.thread.start()
        self.ready.wait()
        if self.error:
            raise self.error

    def listen(self):
        self.thread_id = k.GetCurrentThreadId()
        try:
            # An independent Windows message loop keeps hiding responsive during rendering.
            for first, last in ((0x0003, 0x0003), (0x0014, 0x0015)):
                hook = u.SetWinEventHook(first, last, None, self.callback, 0, 0, 0)
                if not hook:
                    raise OSError("Unable to monitor foreground changes; Usage Bar stays hidden")
                self.hooks.append(hook)
            self.keyboard_hook = u.SetWindowsHookExW(13, self.keyboard_callback, k.GetModuleHandleW(None), 0)
            if not self.keyboard_hook:
                raise OSError("Unable to monitor window-switch shortcuts; Usage Bar stays hidden")
            self.ready.set()
            message = wintypes.MSG()
            while u.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                u.TranslateMessage(ctypes.byref(message))
                u.DispatchMessageW(ctypes.byref(message))
        except Exception as error:
            self.error = error
        finally:
            for hook in self.hooks:
                u.UnhookWinEvent(hook)
            self.hooks.clear()
            if self.keyboard_hook:
                u.UnhookWindowsHookEx(self.keyboard_hook)
                self.keyboard_hook = None
            self.ready.set()

    def allows(self, hwnd):
        return (not self.switching and not self.key_switching and self.error is None
                and u.GetForegroundWindow() == hwnd and not u.IsIconic(hwnd))

    def key_changed(self, code, message, address):
        if code >= 0:
            key = ctypes.cast(address, ctypes.POINTER(wintypes.DWORD))[0]
            if key == 9 and message in (0x100, 0x104):
                if (u.GetAsyncKeyState(0x12) | u.GetAsyncKeyState(0x11)) & 0x8000:
                    # Hide before Windows receives Alt/Ctrl+Tab; never record or consume keys.
                    self.key_switching = True
                    self.changed(None, 0, None, 0, 0, 0, 0)
            elif key in (9, 0x11, 0x12, 0xA2, 0xA3, 0xA4, 0xA5) and message in (0x101, 0x105):
                self.key_switching = False
        return u.CallNextHookEx(None, code, message, address)

    def changed(self, hook, event, hwnd, object_id, child_id, thread_id, timestamp):
        if event in (0x0014, 0x0015):
            self.switching = event == 0x0014
        # Read current focus, since queued events may describe an older window.
        for owner, data in list(self.overlays.items()):
            if not self.allows(owner):
                u.ShowWindow(data["native"], 0)

    def close(self):
        if self.thread and self.thread.is_alive():
            u.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)  # WM_QUIT
            self.thread.join(timeout=2)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path, default=None):
    try:
        if path.stat().st_size > 2_000_000:
            return default
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, UnicodeError):
        return default


def atomic_json(path, value):
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False,
                                   separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def valid_percent(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and 0 <= value <= 100)


def read_config():
    value = read_json(ROOT / "config.json", {})
    return value if isinstance(value, dict) else {}


def context_color(value, dark):
    if not valid_percent(value):
        return "#999da5" if dark else "#656971"
    if value >= 40:
        return "#ff7676" if dark else "#bd2020"
    if value >= 25:
        return "#ffd45b" if dark else "#997200"
    return "#6ad6a0" if dark else "#248454"


def status_path(name):
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")[:110]
    if not clean:
        raise ValueError("A chat name is required")
    return ROOT / ("status" + clean + ".json")


def report(name, project, context, state, handoff_state=None, next_step=None, read_files=None,
           job_id=None, started_at=None, event_id=None):
    if not valid_percent(context):
        raise ValueError("Context estimate must be between 0 and 100")
    path = status_path(name)
    old = read_json(path, {})
    if old and os.path.normcase(old.get("project_folder", "")) != os.path.normcase(project):
        raise ValueError("This chat name already belongs to another project; use a unique name")
    new_job = (not old.get("job_id") or (job_id and job_id != old.get("job_id"))
               or (state == "working" and old.get("state") == "done" and not job_id))
    received = started_at or (None if new_job else old.get("message_received_at")) or utc_now()
    start = datetime.fromisoformat(received.replace("Z", "+00:00"))
    if start.tzinfo is None or start.timestamp() > time.time() + 5:
        raise ValueError("Job start must be a timezone-aware timestamp, not in the future")
    if not event_id and not new_job and old.get("state") == state and state in ("waiting", "done"):
        event_id = old.get("event_id")
    note = {"chat_name": name, "project_folder": project, "context_percent": context,
            "context_estimated": True, "time": utc_now(), "state": state,
            "event_id": event_id or uuid.uuid4().hex,
            "job_id": job_id or (uuid.uuid4().hex if new_job else old["job_id"]),
            "message_received_at": received,
            "timing_source": "provided_start" if started_at else (
                "first_work_report" if new_job else old.get("timing_source")),
            "job_finished_at": ((old.get("job_finished_at") if not new_job and old.get("state") == "done" else None)
                                or utc_now()) if state == "done" else None}
    if state == "done":
        note["elapsed_seconds"] = max(0, int(datetime.fromisoformat(note["job_finished_at"]).timestamp() - start.timestamp()))
    last_done = old.get("last_done_time") or (old.get("time") if old.get("state") == "done" else None)
    if state == "done" or last_done:
        note["last_done_time"] = note["job_finished_at"] if state == "done" else last_done
    for key, value in (("handoff_state", handoff_state), ("next_step", next_step),
                       ("read_files", read_files)):
        if value is not None or key in old:
            note[key] = value if value is not None else old[key]
    atomic_json(path, note)
    if state in ("done", "waiting"):
        try:
            result = subprocess.run([sys.executable, "-B", str(NOTIFICATIONS), state,
                                     "--event-id", note["event_id"]],
                                    capture_output=True, timeout=45, creationflags=0x08000000)
            if result.returncode:
                raise RuntimeError("Notification process failed: " + result.stderr.decode(errors="replace")[-500:])
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            with (ROOT / "bar-errors.log").open("a", encoding="utf-8") as stream:
                stream.write(utc_now() + " notification error: " + str(error) + "\n")
            raise RuntimeError("Status saved, but notification delivery failed; check bar-errors.log") from error
    return path


def statuses():
    result = []
    for path in ROOT.glob("status*.json"):
        d = read_json(path)
        if (isinstance(d, dict) and isinstance(d.get("chat_name"), str)
                and isinstance(d.get("project_folder"), str)
                and valid_percent(d.get("context_percent"))):
            result.append(d)
    return result


def normalized(text):
    return " ".join(re.findall(r"\w+", text.casefold()))


def match_chat(text, notes):
    header = " " + normalized(text) + " "
    candidates = [n for n in notes if " " + normalized(n["chat_name"]) + " " in header]
    for note in sorted(candidates, key=lambda n: len(n["chat_name"]), reverse=True):
        rest = header.replace(" " + normalized(note["chat_name"]) + " ", " ", 1)
        if all(word in {"chatgpt", "share"} or len(word) == 1 for word in rest.split()):
            return note
    return None


def parse_usage(payload):
    if not isinstance(payload, dict):
        raise ValueError("Invalid usage response")
    result = {"five_hour": None, "weekly": None, "plan": None,
              "time": utc_now(), "source": "account"}
    plan = payload.get("plan_type", payload.get("planType"))
    if isinstance(plan, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,50}", plan):
        result["plan"] = plan
    limits = payload.get("rate_limit", payload.get("rateLimits", payload))
    if isinstance(limits, dict):
        for name in ("primary_window", "secondary_window", "primary", "secondary"):
            window = limits.get(name)
            if not isinstance(window, dict):
                continue
            seconds = window.get("limit_window_seconds")
            if seconds is None and isinstance(window.get("windowDurationMins"), (int, float)):
                seconds = window["windowDurationMins"] * 60
            pct = window.get("used_percent", window.get("usedPercent"))
            if not valid_percent(pct):
                continue
            if seconds == 18000:
                key = "five_hour"
            elif seconds == 604800:
                key = "weekly"
            else:
                continue
            result[key] = pct
            reset = window.get("reset_at", window.get("resetAt"))
            if reset is None and isinstance(window.get("reset_after_seconds"), (int, float)):
                reset = time.time() + window["reset_after_seconds"]
            if isinstance(reset, (str, int, float)) and not isinstance(reset, bool):
                result[key + "_reset"] = reset
    credits = payload.get("credits")
    if isinstance(credits, dict):
        balance = credits.get("balance")
        if isinstance(balance, (str, int, float)) and re.fullmatch(r"[\d., -]{1,30}", str(balance)):
            result["credits"] = str(balance)
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Redirect refused", headers, fp)


def fetch_usage(config):
    # This gate is checked before opening auth.json or constructing any request.
    if not isinstance(config, dict) or config.get("allow_authenticated_usage") is not True:
        return {"five_hour": None, "weekly": None, "plan": None, "source": "locked"}
    auth = read_json(HOME / "auth.json", {})
    tokens = auth.get("tokens") if isinstance(auth, dict) else None
    if not isinstance(tokens, dict) or not isinstance(tokens.get("access_token"), str):
        return {"source": "sign-in-unavailable"}
    headers = {"Authorization": "Bearer " + tokens["access_token"],
               "Accept": "application/json", "User-Agent": "AfaqUsageBar/1.0"}
    account = tokens.get("account_id")
    if isinstance(account, str) and "\r" not in account and "\n" not in account:
        headers["ChatGPT-Account-Id"] = account
    request = urllib.request.Request(USAGE_URL, headers=headers, method="GET")
    # No redirect, token refresh, telemetry, proxy, browser, or other endpoint.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=10) as response:
            payload = json.loads(response.read(1_000_001))
        return parse_usage(payload)
    except urllib.error.HTTPError as e:
        return {"source": "sign-in-expired" if e.code == 401 else "usage-unavailable",
                "http_status": e.code}
    except (OSError, ValueError, urllib.error.URLError) as error:
        reason = getattr(error, "reason", error)
        return {"source": "usage-unavailable", "reason": "connection-or-response-error",
                "error_type": type(reason).__name__, "error_code": getattr(reason, "errno", None)}


def codex_windows():
    result = {}
    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback
    def visit(hwnd, ignored):
        if not u.IsWindowVisible(hwnd):
            return True
        length = u.GetWindowTextLengthW(hwnd)
        text = ctypes.create_unicode_buffer(length + 1)
        u.GetWindowTextW(hwnd, text, length + 1)
        recognized = text.value == "ChatGPT" or text.value == "Codex" or text.value.endswith(" - Codex")
        if not recognized:
            cls = ctypes.create_unicode_buffer(100)
            u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
            u.GetClassNameW(hwnd, cls, 100)
            if cls.value == "Chrome_WidgetWin_1":
                pid = wintypes.DWORD()
                u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value not in _process_cache:
                    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
                    k.OpenProcess.restype = wintypes.HANDLE
                    k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                          wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
                    k.CloseHandle.argtypes = [wintypes.HANDLE]
                    ph = k.OpenProcess(0x1000, False, pid.value)
                    image = ctypes.create_unicode_buffer(2048)
                    size = wintypes.DWORD(2048)
                    ok = bool(ph and k.QueryFullProcessImageNameW(ph, 0, image, ctypes.byref(size)))
                    if ph:
                        k.CloseHandle(ph)
                    _process_cache[pid.value] = ok and Path(image.value).name.lower() == "chatgpt.exe"
                recognized = _process_cache[pid.value]
        if recognized:
            r = wintypes.RECT()
            u.GetWindowRect(hwnd, ctypes.byref(r))
            result[hwnd] = (r.left, r.top, r.right, r.bottom)
        return True

    u.EnumWindows(visit, 0)
    return result


def read_header(hwnd, rect):
    """OCR only the visible app header; never sends screenshots anywhere."""
    from PIL import ImageGrab
    left, top, right, bottom = rect
    image = ImageGrab.grab(bbox=(left + 50, top + 44, right - 60, top + 97), all_screens=True)
    temp = ROOT / "tmp" / ("header-" + str(hwnd) + ".png")
    temp.parent.mkdir(exist_ok=True)
    try:
        image.resize((image.width * 2, image.height * 2)).save(temp)
        powershell = os.path.join(os.environ["SystemRoot"], "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
        env = dict(os.environ, TEMP=str(ROOT / "tmp"), TMP=str(ROOT / "tmp"))
        process = subprocess.run([powershell, "-NoLogo", "-NoProfile", "-NonInteractive",
                                  "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "ocr-title.ps1"),
                                  "-Image", str(temp)], capture_output=True, timeout=8,
                                 creationflags=0x08000000, env=env)
        if process.returncode:
            return None, None
        # Sample the app's actual title bar to follow its light/dark appearance.
        # Sample outside the pill so its old theme cannot mask a theme switch.
        sample = ImageGrab.grab(bbox=(right - 120, top + 5, right - 115, top + 10), all_screens=True)
        rgb = sample.convert("RGB")
        pixels = list(rgb.get_flattened_data() if hasattr(rgb, "get_flattened_data") else rgb.getdata())
        dark = sum(sum(p) for p in pixels) / (3 * len(pixels)) < 128
        return process.stdout.decode("utf-8-sig", errors="replace").strip(), dark
    finally:
        temp.unlink(missing_ok=True)


def reset_label(value):
    try:
        if isinstance(value, (int, float)):
            stamp = datetime.fromtimestamp(value, timezone.utc)
        else:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        local = stamp.astimezone()
        now = datetime.now().astimezone()
        return "Resets " + local.strftime("%H:%M" if local.date() == now.date() else "%a %H:%M")
    except (ValueError, TypeError, AttributeError, OverflowError, OSError):
        return "Reset —"


def handoff_text(note):
    folder = note.get("project_folder")
    project = Path(folder) if folder else None
    files = note.get("read_files") or ([name for name in ("AGENTS.md", "CLAUDE.md", "PLAN.md", "HANDOFF.md")
                                       if (project / name).is_file()] if project else [])
    context = note.get("context_percent")
    context_text = f"~{context:g}% (estimate)" if valid_percent(context) else "Not yet reported"
    return ("Continue this project in a NEW chat.\n"
            f"Previous chat (reference only): {note['chat_name']}\n"
            "Before reporting: identify this NEW chat's actual title and estimate its own context. "
            "Do not reuse the previous chat title or context below.\n"
            f"Folder: {project or 'Not yet reported for this chat'}\n"
            f"Read: {', '.join(files) if files else 'No project .md files recorded'}\n"
            f"Current state: {note.get('handoff_state') or ('Last reported: ' + note.get('state', 'unknown'))}\n"
            f"Next step: {note.get('next_step') or 'Read the project handoff and resume the outstanding task.'}\n"
            f"Context: {context_text}; note updated {note.get('time', 'unknown')}.\n")


def copy_handoff(root, note):
    content = handoff_text(note)
    path = ROOT / (status_path(note["chat_name"]).stem.replace("status", "HANDOFF-", 1) + ".md")
    path.write_text(content, encoding="utf-8")
    root.clipboard_clear()
    root.clipboard_append(content)
    root.update_idletasks()
    return path


PILL_WIDTH, PILL_HEIGHT = 704, 44
BUTTON_LEFT = 620
CACHE_SECONDS = 30 * 60
FONT_DIR = ROOT / "fonts"
_fonts = {}


def job_duration(note, now=None):
    try:
        start = datetime.fromisoformat(note["message_received_at"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(note["job_finished_at"].replace("Z", "+00:00")) if note.get("job_finished_at") else None
        if start.tzinfo is None or (end and end.tzinfo is None):
            raise ValueError("Job timestamps need timezones")
        elapsed = int((end.timestamp() if end else (time.time() if now is None else now)) - start.timestamp())
        if elapsed < 0:
            raise ValueError("Job timestamps are reversed")
        minutes, seconds = divmod(elapsed, 60)
        return ("Took " if end else "") + f"{minutes}m {seconds}s"
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError, OSError):
        return "—"



def cache_status(note, now=None):
    # Heuristic from published GPT-5.6+ API lifetime; app cache expiry is not exposed.
    stamp = (note or {}).get("last_done_time")
    if not stamp and (note or {}).get("state") == "done":
        stamp = note.get("time")
    try:
        completed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if completed.tzinfo is None:
            raise ValueError("Completion timestamp needs a timezone")
        elapsed = (time.time() if now is None else now) - completed.timestamp()
        if elapsed < -5:
            raise ValueError("Completion timestamp is in the future")
    except (AttributeError, TypeError, ValueError, OverflowError, OSError):
        return "-", None, "unknown"
    remaining = max(0, min(CACHE_SECONDS, CACHE_SECONDS - elapsed))
    if remaining == 0:
        return "~cold", 0, "cold"
    phase = "low" if remaining <= CACHE_SECONDS * .2 else "warm"
    return f"~{math.ceil(remaining / 60)}m", remaining / CACHE_SECONDS, phase


def pill_image(usage, note, button="Handoff", dark=True, background=None):
    from PIL import Image, ImageDraw, ImageFont
    scale = 3
    width, height = PILL_WIDTH * scale, PILL_HEIGHT * scale
    background = background or ("#1f1f1f" if dark else "#fafafa")
    image = Image.new("RGBA", (width, height), background)
    draw = ImageDraw.Draw(image)

    def font(size, bold=False):
        key = (size, bold)
        if key not in _fonts:
            path = FONT_DIR / ("HelveticaNeueBold.otf" if bold else "HelveticaNeueMedium.otf")
            if not path.is_file():
                path = Path(os.environ["SystemRoot"]) / "Fonts" / ("segoeuib.ttf" if bold else "segoeui.ttf")
            _fonts[key] = ImageFont.truetype(str(path), size*scale)
        return _fonts[key]

    def text(x, y, value, size, color, bold=False, anchor="lm"):
        draw.text((x*scale, y*scale), value, font=font(size, bold), fill=color, anchor=anchor)

    fg, muted = ("#edf0f4", "#a9b0ba") if dark else ("#303740", "#727d8b")
    context = note.get("context_percent") if note else None
    metrics = [("5h", usage.get("five_hour"), reset_label(usage.get("five_hour_reset"))),
               ("Week", usage.get("weekly"), reset_label(usage.get("weekly_reset"))),
               ("Ctx", context, job_duration(note))]
    for index, (label, value, reset) in enumerate(metrics):
        x, end = ((16, 148), (170, 302), (324, 492))[index]
        pct = (("~" if index == 2 else "") + f"{value:g}%") if valid_percent(value) else "—"
        reset = reset.removeprefix("Resets ").replace("Reset —", "—")
        if index < 2 and not valid_percent(value) and usage.get("source") == "usage-unavailable":
            reset = "Offline"
        # Explicit middle anchors avoid Helvetica's unusual ascender offsets.
        text(x, 18, label, 14, fg)
        text(x+42, 18, pct, 14 if index == 2 else 16, fg, True)
        text(end, 18, reset, 9 if index == 2 else 11, muted, anchor="rm")
        draw.line((x*scale, 31*scale, end*scale, 31*scale),
                  fill="#555b62" if dark else "#ced6df", width=2*scale)
        if valid_percent(value) and value > 0:
            draw.line((x*scale, 31*scale, (x+(end-x)*value/100)*scale, 31*scale),
                      fill=context_color(value, dark), width=2*scale)
    cache_text, fraction, phase = cache_status(note)
    accent = (("#6ad6a0" if dark else "#248454") if phase == "warm" else
              ("#ffd45b" if dark else "#997200") if phase == "low" else muted)
    text(516, 18, "Cache", 14, fg)
    text(610, 18, cache_text, 16, accent, True, anchor="rm")
    draw.line((516*scale, 31*scale, 610*scale, 31*scale),
              fill="#555b62" if dark else "#ced6df", width=2*scale)
    if fraction:
        draw.line((516*scale, 31*scale, (516+94*fraction)*scale, 31*scale),
                  fill=accent, width=2*scale)
    text(660, 22, button, 14, fg, True, anchor="mm")
    return image.resize((PILL_WIDTH, PILL_HEIGHT), Image.Resampling.LANCZOS)


def draw_pill(canvas, usage, note, button="Handoff", dark=True, background=None):
    from PIL import ImageTk
    cache_text, fraction, phase = cache_status(note)
    key = (json.dumps(usage, sort_keys=True), note.get("context_percent") if note else None,
           cache_text, round(fraction or 0, 2), phase, job_duration(note), button, dark, background)
    if getattr(canvas, "pill_key", None) == key:
        return
    canvas.pill_key = key
    canvas.pill_photo = ImageTk.PhotoImage(pill_image(usage, note, button, dark, background), master=canvas)
    canvas.delete("all")
    canvas.create_image(0, 0, anchor="nw", image=canvas.pill_photo)


def unreported_note(header):
    name = re.sub(r"^(?:ChatGPT|Codex)\s+|\s+Share$", "", header.strip(), flags=re.I).strip()
    if not name or normalized(name) in ("chatgpt", "codex", "share"):
        raise ValueError("Current chat title could not be identified")
    return {"chat_name": name, "project_folder": None, "context_percent": None,
            "handoff_state": "No assistant work note has been saved for this chat yet.",
            "next_step": "Have the assistant record this chat's project folder, files, state and next action.",
            "time": utc_now()}


def sample_title_surface(hwnd, rect):
    """Only accept a uniform patch of the foreground app, left of our overlay."""
    if u.GetForegroundWindow() != hwnd:
        return None
    from PIL import ImageGrab
    left, top, right, bottom = rect
    image = ImageGrab.grab(bbox=(left+306, top+5, left+318, top+12), all_screens=True).convert("RGB")
    if u.GetForegroundWindow() != hwnd:
        return None
    from collections import Counter
    pixels = list(image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata())
    color, count = Counter(pixels).most_common(1)[0]
    if count < len(pixels) * .8:
        return None
    return "#" + "".join(f"{channel:02x}" for channel in color)


def stable_surface(data, color):
    if color is None:
        data["candidate_color"], data["candidate_count"] = None, 0
        return
    if data.get("candidate_color") == color:
        data["candidate_count"] = data.get("candidate_count", 0) + 1
    else:
        data["candidate_color"], data["candidate_count"] = color, 1
    if data["candidate_count"] >= 2:
        data["theme_color"] = color
        data["dark"] = sum(int(color[i:i+2], 16) for i in (1, 3, 5)) < 384


def run_ui():
    (ROOT / "tmp").mkdir(exist_ok=True)
    os.environ["TEMP"] = os.environ["TMP"] = str(ROOT / "tmp")
    import tkinter as tk
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except OSError:
        pass
    k.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    k.CreateMutexW.restype = wintypes.HANDLE
    # Global for this Windows session, even when another copy is launched.
    mutex_name = "Local\\AfaqUsageBar-SingleInstance"
    mutex = k.CreateMutexW(None, False, mutex_name)
    if k.GetLastError() == 183:
        return
    if not mutex:
        raise OSError("Unable to create Usage Bar instance lock")
    legacy_name = "Local\\AfaqUsageBar-" + hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]
    legacy_mutex = k.CreateMutexW(None, False, legacy_name)
    if k.GetLastError() == 183:
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle(legacy_mutex)
        k.CloseHandle(mutex)
        return
    root = tk.Tk()
    root.withdraw()

    def log_error(kind, error, tb):
        with (ROOT / "bar-errors.log").open("a", encoding="utf-8") as stream:
            stream.write(utc_now() + " UI error\n")
            traceback.print_exception(kind, error, tb, file=stream)

    root.report_callback_exception = log_error
    overlays = {}
    notes = statuses()
    results = queue.Queue()
    usage = {"source": "locked"}
    config = read_config()
    stop_file = ROOT / "stop.request"
    stop_file.unlink(missing_ok=True)
    last_usage = -100
    last_note_check = -100
    pending_usage = False
    last_health = -100

    def refresh_usage(snapshot):
        results.put(("usage", fetch_usage(snapshot)))

    def get_header(hwnd, rect):
        try:
            text, dark = read_header(hwnd, rect)
            results.put(("header", hwnd, rect, text, dark))
        except (OSError, ValueError, subprocess.TimeoutExpired):
            results.put(("header", hwnd, rect, None, None))

    def make_overlay(hwnd):
        window = tk.Toplevel(root)
        window.title("Afaq Usage Bar")
        window.withdraw()
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.attributes("-toolwindow", True)
        window.attributes("-alpha", 1.0)
        window.configure(bg="#010203")
        window.attributes("-transparentcolor", "#010203")
        canvas = tk.Canvas(window, width=PILL_WIDTH, height=PILL_HEIGHT,
                           bg="#010203", highlightthickness=0)
        canvas.pack()
        window.update_idletasks()
        native = u.GetAncestor(window.winfo_id(), 2)
        u.SetWindowLongPtrW(native, -20, u.GetWindowLongPtrW(native, -20) | 0x08000000)
        data = {"window": window, "native": native, "canvas": canvas, "note": None, "copied_until": 0,
                "header": None, "dark": None, "theme_color": None, "theme_checked": -100, "updated": -100, "pending": False,
                "rect": None, "offset": 0, "drag": None}

        def down(event):
            if u.GetAsyncKeyState(0x12) & 0x8000:
                data["drag"] = (event.x_root, data["offset"])
            elif event.x >= BUTTON_LEFT:
                try:
                    # Re-identify at click time so a recent chat switch cannot copy the old chat.
                    text, _ = read_header(hwnd, codex_windows()[hwnd])
                    note = match_chat(text or "", statuses())
                    if not note:
                        note = unreported_note(text or "")
                    copy_handoff(root, note)
                    data["button_error"] = None
                    data["copied_until"] = time.monotonic() + 2
                except (OSError, ValueError, tk.TclError, KeyError, subprocess.TimeoutExpired):
                    data["button_error"] = "Try again"
                    data["copied_until"] = time.monotonic() + 2

        def drag(event):
            if data["drag"]:
                data["offset"] = data["drag"][1] + event.x_root - data["drag"][0]

        def up(event):
            data["drag"] = None

        for widget in [canvas]:
            widget.bind("<ButtonPress-1>", down)
            widget.bind("<B1-Motion>", drag)
            widget.bind("<ButtonRelease-1>", up)
        return data

    def tick():
        nonlocal notes, usage, pending_usage, last_usage, last_note_check, last_health, config
        if stop_file.exists():
            stop_file.unlink(missing_ok=True)
            root.destroy()
            return
        now = time.monotonic()
        while True:
            try:
                result = results.get_nowait()
            except queue.Empty:
                break
            if result[0] == "usage":
                usage = result[1]
                pending_usage = False
                last_usage = now
                atomic_json(ROOT / "usage-cache.json", usage)
            elif result[1] in overlays:
                _, hwnd, oldrect, text, dark = result
                data = overlays[hwnd]
                data.update(header=text, updated=now, pending=False, rect=oldrect)
                # Header jobs may finish after another app becomes foreground.
                # Theme is sampled independently only from the active Codex window.
        if now - last_note_check >= .5:
            notes = statuses()
            last_note_check = now
        if now - last_usage >= 30 and not pending_usage:
            config = read_config()
            pending_usage = True
            threading.Thread(target=refresh_usage, args=(config,), daemon=True).start()
        windows = codex_windows()
        foreground = u.GetForegroundWindow()
        if now - last_health >= 2:
            atomic_json(ROOT / "bar-state.json", {
                "time": utc_now(), "pid": os.getpid(), "version": "integrated-5-foreground",
                "codex_windows": len(windows),
                "overlays": [{"native": d["native"], "client": d["window"].winfo_id(),
                              "visible": bool(u.IsWindowVisible(d["native"])),
                              "theme": d["theme_color"]} for d in overlays.values()],
                "codex_foreground": foreground in windows,
                "reason": "tracking-codex" if foreground in windows else "hidden-other-app-or-no-codex"})
            last_health = now
        for hwnd in list(overlays):
            if hwnd not in windows:
                overlays.pop(hwnd)["window"].destroy()
        for hwnd, rect in windows.items():
            if hwnd not in overlays:
                overlays[hwnd] = make_overlay(hwnd)
            data = overlays[hwnd]
            window = data["window"]
            left, top, right, bottom = rect
            available = right - left - 480
            if not visibility.allows(hwnd) or available < PILL_WIDTH:
                u.ShowWindow(data["native"], 0)
                continue
            if foreground == hwnd and now - data["theme_checked"] >= .5:
                stable_surface(data, sample_title_surface(hwnd, rect))
                data["theme_checked"] = now
            if data["theme_color"] is None:
                u.ShowWindow(data["native"], 0)
                continue
            if (now - data["updated"] >= 30 or data["rect"] != rect) and not data["pending"]:
                data["pending"] = True
                # A previous window-size capture is not used to guess another chat.
                if data["rect"] != rect:
                    data["header"] = None
                threading.Thread(target=get_header, args=(hwnd, rect), daemon=True).start()
            note = match_chat(data["header"] or "", notes)
            data["note"] = note
            button = (data.get("button_error") or "Copied") if now < data["copied_until"] else "Handoff"
            draw_pill(data["canvas"], usage, note, button, data["dark"], data["theme_color"])
            width, height = PILL_WIDTH, PILL_HEIGHT
            base_x = right - 150 - width
            x = max(left + 325, min(right - 145 - width, base_x + data["offset"]))
            y = top + 1
            # Only the Handoff hit area and Alt-drag accept pointer input.
            alt = bool(u.GetAsyncKeyState(0x12) & 0x8000)
            style = u.GetWindowLongPtrW(data["native"], -20)
            style |= 0x80000 | 0x80 | 0x08000000  # layered, tool window, no activation
            pointer = wintypes.POINT()
            u.GetCursorPos(ctypes.byref(pointer))
            over_button = x + BUTTON_LEFT <= pointer.x < x + width - 8 and y + 2 <= pointer.y < y + height - 2
            style = style & ~0x20 if alt or over_button else style | 0x20
            u.SetWindowLongPtrW(data["native"], -20, style)
            # Recheck after rendering: foreground may have changed during the tick.
            if not visibility.allows(hwnd):
                u.ShowWindow(data["native"], 0)
                continue
            window.geometry(f"{width}x{height}{x:+d}{y:+d}")
            window.state("normal")  # Unlike deiconify, do not explicitly raise/focus Tk's window.
            u.SetWindowPos(data["native"], wintypes.HWND(-1), x, y, width, height, 0x10 | 0x40)
            if not visibility.allows(hwnd):
                u.ShowWindow(data["native"], 0)
        root.after(100, tick)

    visibility = None
    try:
        visibility = ForegroundVisibility(overlays)
        visibility.start()
        tick()
        root.mainloop()
    finally:
        if visibility:
            visibility.close()
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle(mutex)
        k.CloseHandle(legacy_mutex)


def self_test():
    stamp = "2026-10-20T18:00:00+00:00"
    epoch = datetime.fromisoformat(stamp).timestamp()
    cache_note = {"last_done_time": stamp, "state": "working"}
    assert cache_status(cache_note, epoch) == ("~30m", 1, "warm")
    assert cache_status(cache_note, epoch + 1439)[2] == "warm"
    assert cache_status(cache_note, epoch + 1440) == ("~6m", .2, "low")
    assert cache_status(cache_note, epoch + 1799)[0] == "~1m"
    assert cache_status(cache_note, epoch + 1800) == ("~cold", 0, "cold")
    assert cache_status(cache_note, epoch - 60)[2] == "unknown"
    assert cache_status(None, epoch)[2] == "unknown"
    assert cache_status({"last_done_time": "bad"}, epoch)[2] == "unknown"
    assert cache_status({"last_done_time": stamp[:-6]}, epoch)[2] == "unknown"
    assert cache_status({"state": "done", "time": stamp}, epoch)[0] == "~30m"
    assert cache_status({"state": "waiting", "time": stamp}, epoch)[2] == "unknown"
    assert context_color(24, True) != context_color(25, True)
    assert context_color(25, True) != context_color(40, True)
    theme = {"theme_color": None}
    stable_surface(theme, "#1f1f1f")
    assert theme["theme_color"] is None
    stable_surface(theme, "#1f1f1f")
    assert theme["theme_color"] == "#1f1f1f" and theme["dark"]
    stable_surface(theme, "#fafafa")
    assert theme["dark"]
    stable_surface(theme, None)
    stable_surface(theme, "#fafafa")
    assert theme["dark"]
    stable_surface(theme, "#fafafa")
    assert not theme["dark"]
    assert not valid_percent(float("nan")) and not valid_percent(True)
    assert status_path("a/b:c").name == "statusa_b_c.json"
    notes = [{"chat_name": "Example", "project_folder": "G:\\test", "context_percent": 28}]
    assert match_chat("ChatGPT Example Share", notes) is notes[0]
    assert match_chat("ChatGPT Another Example Title Share", notes) is None
    assert match_chat("Other chat", notes) is None
    parsed = parse_usage({"plan_type": "plus", "rate_limit": {
        "primary_window": {"used_percent": 13, "limit_window_seconds": 18000},
        "secondary_window": {"used_percent": 44, "limit_window_seconds": 604800}}})
    assert parsed["five_hour"] == 13 and parsed["weekly"] == 44
    assert parse_usage({"rate_limit": {"primary_window": {"used_percent": 7,
           "limit_window_seconds": 3600}}})["five_hour"] is None
    assert fetch_usage({})["source"] == "locked"
    assert parse_usage({})["weekly"] is None
    resets = parse_usage({"rate_limit": {"primary_window": {"used_percent": 25,
        "limit_window_seconds": 18000, "reset_at": 1792512000},
        "secondary_window": {"used_percent": 40, "limit_window_seconds": 604800,
                             "reset_after_seconds": 60}}})
    assert resets["five_hour_reset"] == 1792512000
    assert 55 < resets["weekly_reset"] - time.time() <= 60
    assert reset_label(None) == "Reset —"
    assert reset_label("2026-10-21T12:00:00Z").startswith("Resets ")
    summary = handoff_text(dict(notes[0], handoff_state="UI complete", next_step="Review pill",
                               read_files=["PLAN.md", "HANDOFF.md"]))
    assert all(text in summary for text in ("Folder:", "PLAN.md, HANDOFF.md", "UI complete", "Review pill"))
    starter = unreported_note("ChatGPT Brand new chat Share")
    assert starter["chat_name"] == "Brand new chat"
    assert starter["project_folder"] is None and starter["context_percent"] is None
    assert "Not yet reported for this chat" in handoff_text(starter)
    assert "Not yet reported" in handoff_text(starter)
    for dark in (True, False):
        image = pill_image(parsed, notes[0], dark=dark)
        assert image.size == (704, 44) and image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 255
    for kind in ("done", "waiting"):
        with wave.open(io.BytesIO(wave_bytes(kind)), "rb") as w:
            assert w.getnchannels() == 1 and w.getframerate() == 24000
            assert w.getnframes() > 3000
    print("Self-check passed: thresholds, events, chat matching, quotas/resets, handoffs, light/dark rendering, offline gate, sound generation")


def startup_command():
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.is_file():
        raise RuntimeError("A windowless Python executable is required for automatic startup")
    return subprocess.list2cmdline([str(pythonw), "-B", str(ROOT / "usage_bar.py"), "ui"])


def startup(action):
    """Explicit one-time opt-in; only manages this tool's current-user Run value."""
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    name = "AfaqUsageBar"
    if action == "enable":
        command = startup_command()
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
        print("Automatic startup enabled for the current Windows user")
    elif action == "disable":
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                                winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
                existing, _ = winreg.QueryValueEx(key, name)
                if existing != startup_command():
                    print("Startup belongs to another installation; left unchanged")
                    return
                winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass
        print("Automatic startup disabled")
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, kind = winreg.QueryValueEx(key, name)
            print("Enabled for this folder" if value == startup_command() else "Enabled for another folder")
        except FileNotFoundError:
            print("Not enabled")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("ui")
    sub.add_parser("self-test")
    sub.add_parser("test-sounds")
    sub.add_parser("identify")
    sub.add_parser("stop")
    sub.add_parser("fetch-usage")
    p = sub.add_parser("startup")
    p.add_argument("action", choices=["enable", "disable", "status"])
    p = sub.add_parser("report")
    p.add_argument("--chat", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--context", required=True, type=float)
    p.add_argument("--handoff-state")
    p.add_argument("--next-step")
    p.add_argument("--read-files", nargs="+")
    p.add_argument("--state", choices=["working", "done", "waiting"], default="done")
    p.add_argument("--job-id")
    p.add_argument("--started-at")
    p.add_argument("--event-id")
    args = parser.parse_args()
    if args.command == "self-test":
        self_test()
    elif args.command == "startup":
        try:
            startup(args.action)
        except PermissionError:
            raise SystemExit("Windows denied access to the startup setting. Run the Enable/Disable Auto Start file normally outside the managed chat.")
    elif args.command == "report":
        print(report(args.chat, args.project, args.context, args.state, args.handoff_state, args.next_step,
                     args.read_files, args.job_id, args.started_at, args.event_id))
    elif args.command == "test-sounds":
        print("Completion chime, then a three-second pause, then the short UI ping", flush=True)
        play("done")
        time.sleep(3)
        play("waiting")
    elif args.command == "stop":
        (ROOT / "stop.request").touch()
    elif args.command == "fetch-usage":
        result = fetch_usage(read_config())
        atomic_json(ROOT / "usage-cache.json", result)
        print(json.dumps(result))
    elif args.command == "identify":
        hwnd = u.GetForegroundWindow()
        windows = codex_windows()
        if hwnd not in windows:
            raise SystemExit("Bring the Codex window to the foreground first.")
        print(read_header(hwnd, windows[hwnd])[0] or "Header could not be read")
    else:
        run_ui()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if len(sys.argv) > 1 and sys.argv[1] == "ui":
            with (ROOT / "bar-errors.log").open("a", encoding="utf-8") as stream:
                stream.write(utc_now() + " Startup error\n")
                traceback.print_exc(file=stream)
        raise
