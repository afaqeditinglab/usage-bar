# Verification

## Automated checks

Run `Usage Bar/Test Offline.cmd`. The release checks cover:

- Context thresholds; quota and reset parsing; missing values; chat-title matching.
- Cache boundaries, expiration, missing or invalid completion timestamps, and working/waiting preservation of completion time.
- Dark/light native renderer with system fonts and the expected 704 by 44 pixel output.
- Account access locked by default, including invalid configuration; config deletion and revocation.
- Handoff text/file/clipboard calls using a fake clipboard, with synthetic chat information.
- Independent notification dispatch, unique event IDs, retry recovery and failure logging, with audio mocked.
- Startup enable/status/disable and another installation's startup ownership, using an in-memory registry.
- Windows OCR against a generated sample image, including a path with spaces.

Release preparation passed on Windows with Python 3.13.14 and Pillow 12.2.0. Check Setup.py and the full offline suite passed both in the prepared source tree and after clean ZIP extraction into a folder with spaces. CMD launcher resolution passed with an explicitly selected Python and with PATH fallback. The archive contains 32 allowlisted files; included SHA-256 checksums verified after extraction. No private configuration or runtime history is included.

## Manual coverage and limits

The original installation's foreground overlay, matching title-bar surface, Alt-drag/click-through and independent sounds were exercised during development. Those results do not prove compatibility on every other Windows machine.

A fresh Windows sign-in, startup after relocating the new package, actual app light/dark theme switching, different display scaling and minimum Python/Pillow versions still need independent user testing. Startup registration is mocked by the automated release checks; those tests do not change the developer's live startup entry. The release helper was not launched over the developer's working helper.

No live account endpoint, DNS or credential test is performed by these checks. The account feature is opt-in and experimental. Sound tests verify generated waveforms and dispatch; physical speaker audibility and OS mute state cannot be asserted.

This is a preview release. Report reproducible failures with sanitized details.

21 October foreground regression: six offline tests cover focus changes, null/invisible focus, multiple owners, stale events, switcher suppression, shortcut pass-through and hook cleanup/failure. Live tests: 10 Alt+Tab switches each from Codex to Claude and Explorer, then 10 Ctrl+Tab presses. A 100-second native sampler recorded 25,881 samples, including 14,526 visible-bar samples, with zero final overlay-over-other-foreground violations. This is observed coverage, not a guarantee for every Windows scheduling condition.

Job timing and sound receipts: repeated pending/completed reports reuse event IDs; completed sound events do not replay; failed playback retries and interrupted playback stays explicitly ambiguous. Four offline tests cover timer boundaries, job lifecycles, event receipts and direct file playback. Personal sound-files.json and original WAVs are excluded from the package.
