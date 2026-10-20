"""Independent, on-demand Afaq notifications. No bar, account, network or startup service."""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import io
import json
import math
import os
from pathlib import Path
import struct
import time
import uuid
import wave
import winsound

ROOT = Path(__file__).resolve().parent

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def atomic_json(path, value):
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False,
                                   separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def wave_bytes(kind):
    rate = 24000
    if kind == "done":
        duration = .65
        notes = [(0, 659.25, .36, .17), (.13, 987.77, .42, .15)]
    else:
        duration = .16
        notes = [(0, 1174.66, .16, .24)]
    volume = .25 if kind == "done" else .708
    data = bytearray()
    for i in range(int(rate * duration)):
        t = i / rate
        value = 0.0
        for start, freq, length, gain in notes:
            x = t - start
            if 0 <= x < length:
                if kind == "done":
                    env = min(1, x / .012) * math.exp(-x * 9) * min(1, (length - x) / .04)
                    harmonic = .15
                else:
                    env = (1 - math.exp(-x / .003)) * math.exp(-x / .026) * min(1, (length - x) / .015)
                    harmonic = .06
                value += gain * env * (math.sin(2 * math.pi * freq * x)
                                      + harmonic * math.sin(4 * math.pi * freq * x))
        data.extend(struct.pack("<h", max(-32767, min(32767, round(value * volume * 32767)))))
    output = io.BytesIO()
    with wave.open(output, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data)
    return output.getvalue()


def play(kind):
    winsound.PlaySound(wave_bytes(kind), winsound.SND_MEMORY | winsound.SND_NODEFAULT)


def deliver_sound(event):
    result = {"kind": event["kind"], "event_id": event.get("event_id"), "time": utc_now()}
    for attempt in range(3):
        try:
            play(event["kind"])
            result.update(playback="completed", attempts=attempt + 1)
            result.pop("error", None)
            break
        except (RuntimeError, OSError) as error:
            result.update(playback="failed", attempts=attempt + 1, error=str(error))
            if attempt < 2:
                time.sleep(.2 * (attempt + 1))
    atomic_json(ROOT / "last-notification.json", result)
    with (ROOT / "notification-history.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(result) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("waiting", "done"))
    parser.add_argument("--event-id", default=None)
    args = parser.parse_args()
    kernel = ctypes.windll.kernel32
    kernel.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    mutex = kernel.CreateMutexW(None, False, r"Local\AfaqNotificationsPlayback")
    if not mutex:
        raise ctypes.WinError()
    acquired = False
    try:
        acquired = kernel.WaitForSingleObject(mutex, 10000) in (0, 0x80)
        if not acquired:
            raise RuntimeError("Notification playback queue timed out")
        result = deliver_sound({"kind": args.kind, "event_id": args.event_id or uuid.uuid4().hex})
        print(json.dumps(result))
        return 0 if result["playback"] == "completed" else 1
    finally:
        if acquired:
            kernel.ReleaseMutex(mutex)
        kernel.CloseHandle(mutex)


if __name__ == "__main__":
    raise SystemExit(main())
