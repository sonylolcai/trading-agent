# Partner Tools Runbook

This project should actively use two helper agents when work can be split or independently checked: Hermes and Antigravity.

## Hermes CLI

Use Hermes through the local CLI, not messaging platforms.

Default configuration verified on 2026-06-26:

- Provider: `deepseek`
- Model: `deepseek-v4-pro`
- Base URL: `https://api.deepseek.com/v1`

Preferred invocation from Codex:

```powershell
$hermes='C:\Users\Administrator\AppData\Local\hermes\hermes-agent\.venv\Scripts\hermes.exe'
& $hermes chat -Q -q "Task prompt here"
```

Guidelines:

- Do not pass `--provider` or `-m` by default. Let Hermes use its configured DeepSeek default.
- Keep `-Q` in Codex/non-interactive runs. Without `-Q`, Hermes may try to initialize a Windows interactive console and fail with `NoConsoleScreenBufferError`.
- Use Hermes for frontend work, refactors, review passes, and bounded implementation tasks.
- Treat Hermes output as a proposal until local files, diff, and tests confirm the result.

Known good smoke test:

```powershell
& $hermes chat -Q -q "Explain closures briefly"
```

## Antigravity

Use the local Antigravity bridge for PA_Agent work through the already-bound PA_Agent conversation.

Verified PA_Agent routing:

- Repository label: `rosemarycox5334-debug/PA_Agent`
- Workspace: `file:///s:/PA_Agent`
- Local directory: `S:\PA_Agent`
- Antigravity conversation ID: `bb8fc456-b257-4552-ac63-0cb277bb0124`
- Antigravity project ID: `f08698d5-df4a-47a3-a1d9-5dc7f72adba9`

Preferred MCP call shape:

```text
mcp__antigravity_bridge.ask_antigravity(
  directory="S:\\PA_Agent",
  conversation_id="bb8fc456-b257-4552-ac63-0cb277bb0124",
  prompt="ASCII-only task prompt here"
)
```

Guidelines:

- Include `rosemarycox5334-debug/PA_Agent` and `S:\PA_Agent` in the prompt for clarity.
- Use ASCII-only prompts when sending through fallback `send-message`; non-ASCII text previously failed with `string field contains invalid UTF-8`.
- Do not rely on `new-conversation` for PA_Agent right now. It currently fails with `project_id is required when providing project_env_config`.
- `sendMessage` means only that the message was delivered. It does not mean the task is complete.
- Require hard verification after every Antigravity task: inspect `git diff`, check touched files, and run the relevant tests.

Known good smoke test:

- Asked Antigravity to write `.codex/antigravity-pa-agent-smoke.txt`.
- Verified the file appeared with the expected content.

## Collaboration Policy

- Prefer using Hermes and Antigravity for parallelizable work, second opinions, and independent implementation slices.
- Keep tasks narrow and file-scoped.
- Give each helper explicit acceptance criteria and expected test commands.
- Never report helper work as complete until Codex has verified the actual workspace state.
