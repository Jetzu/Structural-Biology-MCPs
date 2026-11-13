# Claude and Codex inside PyMOL and ChimeraX

A chat panel in each viewer that runs your installed Claude Code or Codex CLI against that very window.

## Opening it

| | PyMOL | ChimeraX |
|---|---|---|
| toolbar | **Agent** button next to *Builder...* in the top toolbar | **Agent** tab in the toolbar |
| menu | *Plugin > Agent Chat* | *Tools > General > Agent Chat* |
| command | `agent_chat` | `agent chat` |
| one-shot prompt | `claude <text>` / `codex <text>` | `claude <text>` / `codex <text>` |

```
PyMOL>  claude which chains are shown and how are they coloured?
PyMOL>  codex colour all carbons magenta and zoom on the ligand
ChimeraX: claude colour the ribbon of chain A hot pink
```

## What it looks like

```
✻ Welcome to Agent Chat for PyMOL
> colour the helices marine and the strands yellow, then say what you changed
⏺ I'll update the colours in the current PyMOL session.
⏺ pymol/scene({"detail": "summary"})
  ⎿  {"app": "pymol", "gui": true, "viewport": [1230, 1404], "objects": [{"name": "1ubq", ...
⏺ pymol/run({"commands": ["color marine, ss H", "color yellow, ss S"]})
  ⎿  {"results": [{"command": "color marine, ss H", "ok": true, ...
⏺ I coloured the helices marine and the strands yellow in the current PyMOL session.
✓ codex · 22.9s · 328 output tokens
```

The panel follows Claude Code's terminal style: the agent's text streams in, each tool call shows the commands or
scripts it ran in a code window with a collapsed `⎿` result, and time, tokens and cost appear when it is done.

## Controls

* **Model switcher** (bottom right, or `/model`): provider (Claude Code / Codex), model and effort, like `/model`
  in Claude Code. Providers whose CLI is not installed are greyed out, so a Claude-only or Codex-only setup just
  works. The choice is stored in `~/.molmcp/agent_settings.json`.
* Slash commands: `/model`, `/clear`, `/claude`, `/codex`, `/skills`, `/stop`, `/help`.
* Keys: Enter sends, Shift+Enter inserts a newline, Esc interrupts, Up/Down browse the history, Tab accepts a
  suggestion.

## How it runs

The panel spawns `claude -p ... --output-format stream-json --allowedTools mcp__<app>` or
`codex exec --json --approve-for-me ...` from inside the application with `MOLMCP_<APP>_PID` set, so the MCP server
the CLI starts attaches to this exact viewer process, even with several windows open.

* The CLI is found on `PATH`, in the VS Code / Cursor Claude Code extension, in `~/.claude/local`, or (Codex) in the
  ChatGPT desktop app. Override with `MOLMCP_CLAUDE_EXE` / `MOLMCP_CODEX_EXE`. Each candidate is checked with
  `--version`, so a stale or wrong-architecture install is skipped.
* The viewer's own interpreter settings (`PYTHONHOME`, `PYTHONEXECUTABLE`, `DYLD_*`, `QT_*`, ...) are stripped from
  the CLI's environment so the server's Python starts cleanly.
* Both CLIs run with your own accounts and use your own subscription or usage.
