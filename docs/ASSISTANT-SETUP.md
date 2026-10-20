# Assistant setup

The bar does not read your transcript or measure token usage. Your assistant must write a small status note for the active chat. Copy the instructions below into the assistant's project instructions or AGENTS.md, adapting paths to your extracted package and existing Python.

Use absolute paths and quote paths containing spaces. The paths below are placeholders, not files supplied by the project. `D:\Tools\usage-bar` represents your chosen extraction folder.

## Instructions to give the assistant

In a new continuation, a pasted `Continue chat:` title belongs to the previous conversation. Establish the new chat's own visible title before reporting; do not inherit the handoff's title or context percentage. Keep this new title stable when the user views other chats. Until its first completed reply, Cache is unknown; working/waiting reports do not start the timer.

Use the local Usage Bar reporting tool with the actual current chat title. Start with a working report and keep its handoff metadata current. Do not guess or substitute another chat's title. You may run `usage_bar.py identify` while the app is foreground to read the visible header; remove app chrome/icons from the title, and retain a title already confirmed for the current task. If identification fails, save a project handoff and explain that matching data is unavailable.

Use a best context estimate from 0 to 100 and clearly label it as estimated. Report waiting immediately before asking the user a question or deliberately requesting permission. Report done just before the final reply. Report working when resuming work. Working and waiting preserve the last completion timestamp.

Example in PowerShell, with your own Python and package paths:

```powershell
& 'D:\Python\python.exe' -B 'D:\Tools\usage-bar\Usage Bar\usage_bar.py' report `
  --chat 'Actual chat title' `
  --project 'D:\Projects\Example' `
  --context 12 --state working `
  --handoff-state 'Current work and decisions' `
  --next-step 'Concrete next action' `
  --read-files 'D:\Projects\Example\AGENTS.md' 'D:\Projects\Example\HANDOFF.md'
```

Change `--state` to `waiting` or `done` when appropriate. You may omit handoff fields in later reports; previous values are retained. Update them whenever the work or next step changes. Use `--state done` only for an actual completed reply; it begins the estimated cache countdown.

At about 25% estimated context, save the project's current decisions and handoff, update its report, and visibly recommend a fresh chat with a short continuation. Ask once per chat, and continue authorized work rather than abandoning it. This is a workflow preference, not an OpenAI context limit.

## Sounds and native permission prompts

Waiting and done reports invoke the sibling `Notifications/afaq_notifications.py` directly. Keep both folders together. No visual helper needs to be running for these sounds. The tool retries playback failures, but cannot override muted speakers or guarantee audibility.

A waiting report can cue the user before a permission prompt only if the assistant reports first. This does not monitor or intercept unexpected native dialogs.

## Chat matching

Match the complete visible title. If you rename a chat, report the new title deliberately; do not mix another task's state into it. Duplicate titles in different projects are rejected by the reporting command: choose unique titles or separate installations. OCR errors and future header layouts can prevent matching. Ctx and Cache then show dashes.

The Handoff button rechecks the title before copying. It writes a local `HANDOFF-<chat>.md` alongside the tool and copies the continuation text to your clipboard. It does not start a new chat or upload a transcript.
