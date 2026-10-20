# Troubleshooting

| Symptom | What to check |
| --- | --- |
| Nothing appears | Bring ChatGPT/Codex forward, widen the window, run Check Setup.cmd, then Start Usage Bar.cmd. It hides behind other apps and while minimized. |
| A second copy will not start | One helper is allowed per Windows session. Stop the original installation from its own folder first. |
| 5h and Week are dashes | Account access defaults off. Read PRIVACY.md before opting in. Existing sign-in, network access and compatible usage data are required. |
| Ctx or Cache are dashes | Confirm the assistant wrote a report for this exact chat title. Allow about 30 seconds for header refresh. Cache needs a completed reply report first. |
| Wrong or missing chat match | Windows needs an installed OCR language. Header icons, duplicate titles, display scaling and app layout changes can affect OCR. Run Test Offline.cmd. |
| No sound | Check Windows output/mute settings and run Test Sounds.cmd. Confirm the assistant actually reported waiting/done. Unexpected permission prompts do not trigger sounds automatically. |
| Handoff has incomplete information | Have the assistant report project, files, work state and next step. No matching note produces an explicit starter. |
| It stopped appearing after a folder move | Run Enable Auto Start.cmd from the new permanent location and stop the old installation. |
| Automatic startup is denied | Run the launcher normally outside a managed assistant environment. Your organization may restrict startup. Do not bypass its policy. |
| Python is missing or an app store opens | Use a compatible installed Python on PATH, provide a compatible runtime, or explicitly set USAGE_BAR_PYTHON. |

Check Setup.cmd verifies local prerequisites. Test Offline.cmd runs checks without using your credentials or the network. Logs such as `bar-errors.log` can help, but remove private information before sharing them. A successful automated test does not guarantee every desktop layout or future app version works.
