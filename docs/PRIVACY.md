# Privacy and optional account usage

## Local features

With the default configuration, Usage Bar makes no account requests and does not open your sign-in file. Context, handoffs and sounds work from local assistant reports. There is no product analytics or update checker.

To match a chat, it captures the visible app header locally and runs Windows OCR through the included PowerShell helper. The temporary header image is deleted after the attempt; an abrupt process termination can leave a file in `Usage Bar/tmp`. Nothing uploads those images.

Local data includes chat titles, project paths, context estimates, work summaries, next steps, handoff files and notification timestamps. Handoff also copies its content to the Windows clipboard, where clipboard history or syncing may retain it according to your settings. Keep this folder private. Do not publish it after using it.

## Optional account usage

Account reads are off by default. If you understand and authorize them for your own account:

1. Copy `Usage Bar/config.example.json` to `Usage Bar/config.json`.
2. Change `allow_authenticated_usage` from `false` to `true`.
3. Confirm you have a compatible existing Codex sign-in. The helper looks under `CODEX_HOME`, or your user's `.codex` folder when that variable is unset. Do not send anyone your `auth.json`.

When explicitly enabled, the tool reads the existing access token in memory and sends a read-only HTTPS GET to `https://chatgpt.com/backend-api/wham/usage`. A compatible account ID is included in the request when present. The endpoint and response format are unofficial and may stop working. Browser-only login does not necessarily provide a compatible local sign-in.

The visual helper attempts the read about every 30 seconds. It does not follow redirects, refresh tokens, open a login page or change account settings. It bypasses configured HTTP proxies; some managed networks will therefore block it. Its own cache stores parsed usage/reset information, not token contents. The tool does not copy credentials into reports, images or handoffs.

To revoke access, set `allow_authenticated_usage` to `false` or remove `config.json`. The helper checks configuration on each polling cycle. An already-started request may finish; previously displayed values may remain briefly until the next update. Restart the helper if you want to clear the display immediately.

Network restrictions, expired tokens and unsupported plans may leave dashes. Do not weaken your machine's security policy or share credentials to troubleshoot this. No public API key is required.

## Sharing a bug report

Remove chat titles, project paths, account details and private text from logs and screenshots. Never attach `auth.json`, actual configuration, status reports, handoff files, usage caches or notification history. Share only the minimum diagnostic information needed to reproduce the issue.
