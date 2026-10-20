"""Read-only prerequisite checks. No installs, account access or startup changes."""
from pathlib import Path
import os
import sys


def main():
    if sys.platform != "win32":
        raise SystemExit("Usage Bar supports Windows desktop only.")
    if sys.version_info < (3, 10):
        raise SystemExit("Python 3.10 or newer is required. Read docs/SETUP.md.")
    try:
        import tkinter
        from PIL import Image, ImageFont
    except ImportError as error:
        raise SystemExit(f"Missing prerequisite: {error.name}. Read docs/SETUP.md.")
    root = Path(__file__).resolve().parent
    required = (root / "ocr-title.ps1", root.parent / "Notifications" / "afaq_notifications.py",
                Path(sys.executable).with_name("pythonw.exe"))
    for path in required:
        if not path.is_file():
            raise SystemExit(f"Missing required file: {path}")
    font = Path(os.environ["SystemRoot"]) / "Fonts" / "segoeui.ttf"
    ImageFont.truetype(str(font), 14)
    print("Ready: Windows, Python, Tk, Pillow, system font, pythonw and package files.")
    print("Windows OCR language availability is checked by Test Offline.cmd.")
    print("No files installed, no account read and no startup setting changed.")


if __name__ == "__main__":
    main()
