# Release notes

## 0.1.0 preview

21 October foreground fix: a separate Windows event listener hides the bar when focus changes. Alt/Ctrl+Tab hides it before switching starts. Strict focus checks cover unknown or invisible foreground windows. The bar no longer uses Tk's explicit deiconify focus/raise behavior. Added six offline regression tests; live switching was checked against Explorer and Claude.

21 October reporting and notifications: per-job elapsed time appears beside context; completed notifications have durable receipts to prevent replay. Local WAV files can be selected without copying or modifying them. Unavailable account values show Offline. Assistant setup now documents exact thread-ID title lookup when foreground header reading fails, preventing missing reports when the app is behind another window.

First source release prepared for public review.

- Windows title-bar strip for optional five-hour and weekly usage, estimated chat context and estimated cache countdown.
- Per-chat Handoff button using assistant-reported project state.
- Independent waiting and completion sounds, with retry and local diagnostics.
- Explicit sign-in startup option and matching disable/stop controls.
- Account access disabled by default, system-font fallback and portable path resolution.
- Beginner setup, assistant instructions, privacy guidance and offline checks.

This preview requires an existing compatible Python environment. It is not a signed executable or an automatic installer. Account usage depends on an unofficial endpoint. Context and cache values are estimates. Desktop scaling, app layout changes and Windows OCR language availability can affect behavior.

See `docs/TESTING.md` for verified checks and remaining manual coverage.
