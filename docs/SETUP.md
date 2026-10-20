# Setup

## Before you start

Use Windows desktop with the ChatGPT/Codex application. The bar uses Windows window APIs, Tk, local Windows OCR and Segoe UI. It is designed for a wide window: less than roughly 1,184 pixels of window width can hide it. Display scaling and future app layouts may affect placement.

You need an existing Python 3.10+ installation with Tk, `pythonw.exe` and Pillow 10+. If those are missing, obtain Python from [python.org](https://www.python.org/downloads/windows/). Pillow is listed in `requirements.txt`. This project does not bundle or automatically download Python, fonts or dependencies.

If you choose to install Pillow yourself, run `python -m pip install -r requirements.txt` from the package's top folder using your chosen Python. Choose your installation and cache locations according to your own machine policy. You do not need Node, a browser extension or an API key.

## First run

1. Extract everything. Running inside the ZIP will not work reliably. Keep the two tool folders together.
2. Keep the folder in a permanent location that your Windows account can write to. Avoid a protected installation folder or a shared folder readable by strangers: chat titles and project paths are saved locally.
3. Open `Usage Bar` and run **Check Setup.cmd**. It checks dependencies without changing startup or reading your account.
4. Run **Test Offline.cmd** for the local regression checks and Windows OCR check. It does not contact a usage endpoint or play sounds.
5. Run **Start Usage Bar.cmd** and bring ChatGPT/Codex to the foreground. A helper window is not shown while other apps are active. Account values initially show dashes.
6. Add the [assistant instructions](ASSISTANT-SETUP.md). Use the exact current chat title. Context should then appear after OCR refresh, within about 30 seconds. Cache starts after the first matching done report.
7. Optionally run **Test Sounds.cmd**. It plays a completion chime, pauses three seconds, then plays the waiting cue.

The launchers prefer `USAGE_BAR_PYTHON` if you explicitly set it, then `Usage Bar/runtime/python.exe` if you provide a compatible runtime, then the first `python.exe` on PATH. The runtime must include Tk, Pillow and `pythonw.exe`. Windows Store aliases or incomplete embeddable Python distributions may fail the dependency check. Nothing is bundled in `runtime`.

## Automatic availability with your normal app icon

Run **Enable Auto Start.cmd** once after choosing a permanent folder. This writes the current user's `AfaqUsageBar` value under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` and starts the helper. It does not need administrator access or change the ChatGPT shortcut.

At each Windows sign-in the helper starts, waits for the app, and follows its foreground window. Closing ChatGPT leaves the helper ready for the next launch. Restarting Windows signs you in again and starts the helper again. If you manually stop it or it crashes, run **Start Usage Bar.cmd** again. This is sign-in startup, not a hook installed into ChatGPT's own launch process.

Enable startup again after moving the folder or changing Python. Only one installation should own the startup entry at a time. **Restart Usage Bar.cmd** stops and restarts the helper from its own folder; it cannot replace a copy running from a different folder.

## Turn off or uninstall

1. Run **Disable Auto Start.cmd** from the enabled installation. It removes this tool's startup value, leaving other startup entries alone.
2. Run **Stop Usage Bar.cmd** and wait a few seconds.
3. Remove the reporting instructions from your assistant settings or AGENTS.md.
4. Delete the extracted package if you no longer need it. It includes your local reports, handoffs and diagnostic logs, so back up anything you want to keep first.

Your ChatGPT account, chats and Python installation are unaffected. Disabling automatic startup does not stop an already running helper.
