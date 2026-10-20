"""Offline release checks; never starts the helper, reads credentials or plays audio."""
from contextlib import nullcontext
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import types
from unittest.mock import Mock, patch

import usage_bar as bar
import test_notifications


def main():
    (bar.ROOT / "tmp").mkdir(exist_ok=True)
    bar.self_test()
    test_notifications.run()
    with tempfile.TemporaryDirectory(dir=bar.ROOT / "tmp", prefix="release- Unicode-") as folder:
        folder = Path(folder)
        with patch.object(bar, "ROOT", folder):
            config = folder / "config.json"
            config.write_text('{"allow_authenticated_usage":true}', encoding="utf-8")
            assert bar.read_config()["allow_authenticated_usage"] is True
            config.write_text('{"allow_authenticated_usage":false}', encoding="utf-8")
            assert bar.read_config()["allow_authenticated_usage"] is False
            config.unlink()
            assert bar.read_config() == {}
            for text in ("[]", "null", "broken", '"true"'):
                config.write_text(text, encoding="utf-8")
                assert bar.read_config() == {}
            with patch.object(bar, "read_json", side_effect=AssertionError("Credential read")):
                with patch.object(bar.urllib.request, "build_opener",
                                  side_effect=AssertionError("Network access")):
                    for value in ({}, {"allow_authenticated_usage": False},
                                  {"allow_authenticated_usage": "true"}, [], None):
                        assert bar.fetch_usage(value)["source"] == "locked"
            clipboard = Mock()
            note = {"chat_name": "Release example", "project_folder": str(folder),
                    "context_percent": 12, "read_files": ["PLAN.md"],
                    "handoff_state": "Example only", "next_step": "Continue"}
            copied = bar.copy_handoff(clipboard, note)
            assert "Example only" in copied.read_text(encoding="utf-8")
            assert clipboard.clipboard_append.call_args.args[0] == copied.read_text(encoding="utf-8")
            assert "Previous chat (reference only): Release example" in copied.read_text(encoding="utf-8")
            assert "Do not reuse the previous chat title or context below." in copied.read_text(encoding="utf-8")

            # A continuation must never inherit the old chat's context or completion.
            with patch.object(bar.subprocess, "run", return_value=Mock(returncode=0)):
                bar.report("Previous conversation", str(folder), 57, "done", "Old state", "Old step")
                old_path = bar.status_path("Previous conversation")
                old_bytes = old_path.read_bytes()
                assert bar.match_chat("ChatGPT Fresh conversation Share", bar.statuses()) is None
                bar.report("Fresh conversation", str(folder), 3, "working", "New state", "New step")
                fresh = bar.match_chat("ChatGPT Fresh conversation Share", bar.statuses())
                assert fresh["context_percent"] == 3 and fresh["handoff_state"] == "New state"
                assert bar.cache_status(fresh)[2] == "unknown"
                bar.report("Fresh conversation", str(folder), 4, "waiting")
                assert bar.cache_status(bar.read_json(bar.status_path("Fresh conversation")))[2] == "unknown"
                bar.report("Fresh conversation", str(folder), 5, "done")
                fresh = bar.read_json(bar.status_path("Fresh conversation"))
                assert bar.cache_status(fresh)[2] == "warm"
                completed = fresh["last_done_time"]
                bar.report("Fresh conversation", str(folder), 6, "working")
                assert bar.read_json(bar.status_path("Fresh conversation"))["last_done_time"] == completed
                assert old_path.read_bytes() == old_bytes

        # Real startup registration is never touched. Verify ownership and quoted paths in memory.
        registry = {}
        fake = types.ModuleType("winreg")
        fake.HKEY_CURRENT_USER, fake.REG_SZ = 1, 1
        fake.KEY_QUERY_VALUE, fake.KEY_SET_VALUE = 1, 2
        fake.CreateKeyEx = fake.OpenKey = lambda *args: nullcontext("key")
        fake.SetValueEx = lambda key, name, reserved, kind, value: registry.update({name: value})
        def query(key, name):
            if name not in registry:
                raise FileNotFoundError(name)
            return registry[name], fake.REG_SZ
        fake.QueryValueEx = query
        fake.DeleteValue = lambda key, name: registry.pop(name)
        with patch.dict(sys.modules, {"winreg": fake}):
            bar.startup("enable")
            expected = bar.startup_command()
            assert registry["AfaqUsageBar"] == expected
            assert str(bar.ROOT / "usage_bar.py") in expected
            bar.startup("status")
            registry["AfaqUsageBar"] = "another installation"
            bar.startup("disable")
            assert registry["AfaqUsageBar"] == "another installation"
            registry["AfaqUsageBar"] = expected
            bar.startup("disable")
            assert "AfaqUsageBar" not in registry
            bar.startup("disable")

        # Exercise Windows OCR with a generated fixture, never the user's screen.
        from PIL import Image, ImageDraw, ImageFont
        image = Image.new("RGB", (1100, 110), "white")
        font = ImageFont.truetype(str(Path(os.environ["SystemRoot"]) / "Fonts" / "segoeui.ttf"), 42)
        ImageDraw.Draw(image).text((15, 15), "Release Setup Check", font=font, fill="black")
        fixture = folder / "OCR sample.png"
        image.save(fixture)
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        result = subprocess.run([str(powershell), "-NoProfile", "-NonInteractive",
                                 "-ExecutionPolicy", "Bypass", "-File", str(bar.ROOT / "ocr-title.ps1"),
                                 "-Image", str(fixture)], capture_output=True, timeout=20,
                                creationflags=0x08000000,
                                env=dict(os.environ, TEMP=str(folder), TMP=str(folder)))
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        assert "release setup check" in result.stdout.decode("utf-8-sig").strip().lower()
    print("Passed: config revocation/default lock, handoff round-trip, startup ownership/quoting, Windows OCR fixture")
    print("No live usage requests, real startup changes, helper replacement or audio playback.")


if __name__ == "__main__":
    main()
