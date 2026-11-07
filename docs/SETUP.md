# molmcp setup guide

This guide takes you from a bare machine to Claude Code or Codex driving your PyMOL and/or ChimeraX
session. It is written for structural biologists who have never configured an MCP server. Every
molmcp command, flag, file path and environment variable below is taken from the code in this repository; the
install commands for the agent CLIs themselves (§2.3) come from the vendors' documentation.

**You do not need both agents.** Claude Code *or* Codex is enough; both is fine too. You also do not need
both viewers: PyMOL only or ChimeraX only works.

Contents

1. [What you are installing](#1-what-you-are-installing)
2. [Prerequisites](#2-prerequisites)
3. [Install molmcp](#3-install-molmcp)
4. [What the installer touches](#4-what-the-installer-touches)
5. [Verify each piece](#5-verify-each-piece)
6. [Using it](#6-using-it)
7. [Headless use and environment variables](#7-headless-use-and-environment-variables)
8. [Several viewer windows at once](#8-several-viewer-windows-at-once)
9. [Where renders go](#9-where-renders-go)
10. [Security model](#10-security-model)
11. [Troubleshooting](#11-troubleshooting)
12. [Uninstalling](#12-uninstalling)
13. [Docker verification images](#13-docker-verification-images)
14. [Appendix: manual registration and file map](#14-appendix-manual-registration-and-file-map)

---

## 1. What you are installing

molmcp has three parts:

```
Claude Code / Codex / Claude Desktop            (the agent, your own account)
        │  stdio (MCP)
        ▼
<repo>/.venv/bin/pymol-mcp    or    <repo>/.venv/bin/chimerax-mcp     (the MCP server, Python ≥ 3.10)
        │  HTTP on 127.0.0.1, random port, secret token
        ▼
a bridge thread inside the running PyMOL / ChimeraX process         (plugin / bundle, auto-starts)
```

* **The MCP servers** (`pymol-mcp`, `chimerax-mcp`) are ordinary programs in a virtual environment in the
  cloned repository. The agent starts one whenever it needs it and talks to it over stdin/stdout.
* **The in-app bridges** are a PyMOL plugin (`molmcp_pymol_bridge`) and a ChimeraX bundle
  (`ChimeraX-AgentBridge`). They start a tiny HTTP server inside the viewer when the viewer starts and write
  a discovery file so the MCP server can find them. They add commands to the viewers (`agent_status`,
  `claude ...`, `codex ...`, an *Agent Chat* panel and a toolbar button).
* **The installer** (`install.py`) creates the virtual environment, installs the plugin and bundle, and
  registers the two servers with Claude Code, Codex and Claude Desktop.

Nothing is installed system-wide and nothing needs administrator rights. Everything lives in the cloned
repository, in your viewer's own plugin directories, in your agent's own config files and in `~/.molmcp`.

---

## 2. Prerequisites

### 2.1 Python 3.10 or newer (for the MCP servers)

The servers run in their own virtual environment, so this Python is separate from the one inside PyMOL or
ChimeraX. Check what you have:

| OS | check | if missing |
|---|---|---|
| macOS | `python3 --version` | `brew install python` (Homebrew) or the installer from python.org |
| Linux | `python3 --version` and `python3 -m venv --help` | Debian/Ubuntu: `sudo apt install python3 python3-venv python3-pip`; Fedora: `sudo dnf install python3` |
| Windows | `py -3 --version` (or `python --version`) | installer from python.org; tick "Add python.exe to PATH" |

**Optional: `uv`.** If `uv` is on your `PATH` the installer uses it to create the virtual environment and
install packages (faster, and it can supply a Python ≥ 3.10 even when your default `python3` is older):
`pip install uv`, `brew install uv`, or `curl -LsSf https://astral.sh/uv/install.sh | sh`. The installer
runs `uv venv --python ">=3.10" <repo>/.venv` and `uv pip install --python <venv python> -e <repo>` when it
finds `uv`; otherwise it uses `python -m venv` and `pip`.

### 2.2 PyMOL and/or ChimeraX

Install the viewer(s) you use. The installer looks for them in this order (from `molmcp/common/discovery.py`):

1. the environment variables `PYMOL_EXE` / `CHIMERAX_EXE` (full path to the executable);
2. anything on `PATH` named `pymol`, `PyMOL`, `pymol.exe`, `PyMOLWin.exe` / `chimerax`, `ChimeraX`,
   `ChimeraX.exe`, `chimerax-daily`, `ChimeraX-daily`;
3. the usual install locations:

| | PyMOL | ChimeraX |
|---|---|---|
| macOS | `/Applications/PyMOL.app/Contents/bin/pymol`, `/Applications/PyMOL*.app/...`, `~/Applications/PyMOL*.app/...`, Homebrew `/opt/homebrew/bin/pymol`, `/usr/local/bin/pymol`, conda envs under `~/miniconda3`, `~/anaconda3`, `~/miniforge3`, `/opt/anaconda3` | `/Applications/ChimeraX.app/Contents/bin/ChimeraX`, `/Applications/ChimeraX-*.app/...`, `~/Applications/ChimeraX*.app/...` |
| Linux | `/usr/bin/pymol`, `/usr/local/bin/pymol`, `/opt/pymol*/`, `~/pymol/`, conda/mamba envs (`~/miniconda3`, `~/anaconda3`, `~/miniforge3`, `~/mambaforge`, `/opt/conda`), `~/.local/bin/pymol`, `/snap/bin/pymol`, Flatpak exports | `/usr/bin/chimerax`, `/usr/local/bin/chimerax`, `/opt/UCSF/ChimeraX*/bin/ChimeraX`, `/opt/chimerax*/bin/ChimeraX`, `~/chimerax*/bin/ChimeraX`, `~/ChimeraX*/bin/ChimeraX`, `~/.local/bin/chimerax`, Flatpak exports, `/snap/bin/chimerax` |
| Windows | `C:\Program Files\Schrodinger\PyMOL2\PyMOLWin.exe`, `C:\Program Files\PyMOL*\PyMOLWin.exe`, `%LOCALAPPDATA%\Programs\PyMOL*\`, `%LOCALAPPDATA%\Schrodinger\PyMOL*\`, conda `%USERPROFILE%\miniconda3\...\Scripts\pymol.exe` | `C:\Program Files\ChimeraX\bin\ChimeraX.exe`, `C:\Program Files\ChimeraX*\bin\`, `C:\Program Files\UCSF\ChimeraX*\bin\`, `%LOCALAPPDATA%\Programs\ChimeraX*\bin\`, `%USERPROFILE%\ChimeraX*\bin\` |

If your viewer lives somewhere else, set the variable before running the installer, e.g.

```bash
# macOS / Linux
export PYMOL_EXE=/path/to/pymol
export CHIMERAX_EXE=/path/to/ChimeraX
```

```powershell
# Windows (PowerShell, current session)
$env:PYMOL_EXE = "C:\path\to\PyMOLWin.exe"
$env:CHIMERAX_EXE = "C:\path\to\ChimeraX.exe"
```

Open-source PyMOL from conda-forge (`conda install -c conda-forge pymol-open-source`) works; the installer
finds the conda env automatically or you point `PYMOL_EXE` at `<env>/bin/pymol`.

### 2.3 An agent CLI: Claude Code **or** Codex

You need at least one. Each uses **your own account and your own usage/billing**; molmcp never talks to
Anthropic or OpenAI itself.

#### Claude Code

Install (pick one; see Anthropic's Claude Code documentation for the current recommended method):

| OS | command |
|---|---|
| macOS / Linux | `curl -fsSL https://claude.ai/install.sh \| bash` |
| Windows (PowerShell) | `irm https://claude.ai/install.ps1 \| iex` |
| any, via npm | `npm install -g @anthropic-ai/claude-code` |
| macOS, Homebrew | `brew install --cask claude-code` |

The VS Code extension *Claude Code* also ships the CLI binary (under
`~/.vscode/extensions/anthropic.claude-code-<version>-<platform>/resources/native-binary/claude`); molmcp
finds that binary too, so an extension-only install is enough for the in-app chat.

Log in and check:

```bash
claude --version          # e.g. "2.1.319 (Claude Code)"
claude auth login         # browser login with your Claude subscription (default, --claudeai)
                          # --console  = Anthropic Console / API billing instead;  --sso = force SSO
claude auth status
```

(You can also start `claude` and type `/login`.)

#### Codex

Install (pick one; see OpenAI's Codex documentation for the current recommended method):

| OS | command |
|---|---|
| any, via npm | `npm install -g @openai/codex` |
| macOS, Homebrew | `brew install --cask codex` |
| macOS, ChatGPT desktop app | the app bundles the CLI at `/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex`; molmcp finds it there without any PATH change |

Log in and check:

```bash
codex --version           # e.g. "codex-cli 0.167.0"
codex login               # browser login with your ChatGPT account
codex login --device-auth # for a machine without a browser
printenv OPENAI_API_KEY | codex login --with-api-key    # API-key login instead
codex login status        # "Logged in using ChatGPT"
```

#### The two one-agent paths

| | Claude-only | Codex-only |
|---|---|---|
| install + login | Claude Code (above) | Codex (above) |
| run the installer | `python install.py --pymol --chimerax --claude` | `python install.py --pymol --chimerax --codex` |
| verify registration | `claude mcp list` | `codex mcp list` |
| use from a terminal | `claude` then ask | `codex` then ask |
| use inside the viewer | `claude <text>`, the *Agent Chat* panel | `codex <text>`, the *Agent Chat* panel |

Drop `--pymol` or `--chimerax` if you only have one viewer. Running plain `python install.py` with no flags
also works for a one-agent setup: the step for the agent you do not have only writes a config file that
nothing reads (`~/.codex/config.toml` and `~/.claude.json` are created if missing; an existing
`~/.claude.json` that does not parse as JSON is left untouched). The *Agent Chat* panel inside the viewers
detects which CLIs are installed and uses the one it finds; the missing one is shown greyed out as
"(not installed)".

---

## 3. Install molmcp

### 3.1 Clone

```bash
git clone https://github.com/Jetzu/Structural-Biology-MCPs.git mol-mcp
cd mol-mcp
```

Keep the clone where it is: the MCP configs point at `<repo>/.venv/bin/pymol-mcp`, so moving or deleting
the folder breaks the registration (re-run the installer after moving, see §11).

### 3.2 Run the installer

```bash
# macOS / Linux
python3 install.py

# Windows (PowerShell or cmd)
py -3 install.py          # or: python install.py
```

What `install.py` (the bootstrap script at the repository root) does, in order:

1. creates `<repo>/.venv` (with `uv` if available, else `python -m venv`); exits with
   "Python 3.10+ is required" if the Python you used is too old and `uv` is not there;
2. installs the `molmcp` package into it in editable mode (`pip install -e .`), which also installs the
   dependencies `mcp>=1.10`, `numpy>=1.24`, `pillow>=10` and creates the console scripts `pymol-mcp`,
   `chimerax-mcp` and `molmcp-install`;
3. runs `.venv/bin/python -m molmcp.install` with every flag you passed.

`molmcp.install` always prints a summary first (the same as `--check`) and then runs the steps.

### 3.3 Every flag

```
python install.py [--pymol] [--chimerax] [--claude] [--codex] [--claude-desktop]
                  [--uninstall] [--dry-run] [--check] [--help]
```

| flag | meaning |
|---|---|
| *(no flags)* | do everything that applies: PyMOL plugin, ChimeraX bundle, Claude Code, Codex and (only if its config file already exists) Claude Desktop |
| `--pymol` | install the PyMOL plugin (auto-starts the bridge in PyMOL) |
| `--chimerax` | build + install the ChimeraX bundle (auto-starts the bridge in ChimeraX) |
| `--claude` | register the `pymol` and `chimerax` servers with Claude Code (user scope, `~/.claude.json`) |
| `--codex` | register them with Codex (`~/.codex/config.toml`) |
| `--claude-desktop` | register them with Claude Desktop (only if `claude_desktop_config.json` exists) |
| `--uninstall` | remove instead of install; combine with the flags above to remove only some pieces, alone removes everything |
| `--dry-run` | print what would be done, change nothing |
| `--check` | only print what was found (Python, PyMOL, ChimeraX, server commands, state directory) and exit |
| `--help`, `-h` | show the bootstrap help and, if the venv exists, the full `molmcp.install` help |

Selecting one or more step flags runs *only* those steps. All steps are idempotent: re-running the
installer (for example after `git pull`) is the normal way to update.

Inside the venv the same program is available as `.venv/bin/molmcp-install` (Windows:
`.venv\Scripts\molmcp-install.exe`) or `.venv/bin/python -m molmcp.install`.

### 3.4 After installing

Restart PyMOL and ChimeraX if they were open (the bridge starts with the application). Restart any running
Claude Code session so it re-reads `~/.claude.json`; Codex reads `~/.codex/config.toml` at start as well.

---

## 4. What the installer touches

Everything below is written by `molmcp/install.py`; nothing else on the machine is changed.

### 4.1 Repository

* `<repo>/.venv/` – the virtual environment. Server commands: `.venv/bin/pymol-mcp`,
  `.venv/bin/chimerax-mcp`, `.venv/bin/molmcp-install` (Windows: `.venv\Scripts\pymol-mcp.exe`,
  `chimerax-mcp.exe`, `molmcp-install.exe`).
* `molmcp/inapp/shared/{bridgecore,agentcli,agentchat_ui}.py` are copied into
  `molmcp/inapp/pymol/molmcp_pymol_bridge/` and
  `molmcp/inapp/chimerax/chimerax_agentbridge/chimerax/agentbridge/` so that both in-app packages carry
  the same code (they are tracked in the repository already; the copy keeps them in sync).

### 4.2 PyMOL plugin (`--pymol`)

The installer runs PyMOL headless with a small script:

```
<PyMOL's own python> -m pymol -cq -k <temporary script>.py      # preferred
<pymol executable> -cq -k <temporary script>.py                  # fallback
```

(`-c` = no GUI, `-q` = quiet, `-k` = do not read pymolrc/plugins; `MOLMCP_PYMOL_AUTOSTART=0` is set so no
bridge starts during installation.) The script uses PyMOL's own plugin API
(`pymol.plugins`, `pymol.plugins.installation`) to:

1. pick the first writable directory in PyMOL's plugin startup path, or PyMOL's default user plugin
   directory if none is writable (creating it):

   | OS | default user plugin directory |
   |---|---|
   | macOS, Linux | `~/.pymol/startup/` |
   | Windows | `%APPDATA%\pymol\startup\` (i.e. `C:\Users\<you>\AppData\Roaming\pymol\startup\`) |

2. copy `molmcp/inapp/pymol/molmcp_pymol_bridge/` to `<that directory>/molmcp_pymol_bridge/`
   (replacing an older copy);
3. add the directory to the startup path if needed, set `autoload["molmcp_pymol_bridge"] = True` and save
   PyMOL's plugin preferences to **`~/.pymolpluginsrc.py`** (PyMOL's own autogenerated file).

The installer prints `installed plugin: <path>` on success.

**Fallback.** If PyMOL is not found, or the headless run does not report success, the installer instead
appends a block to your pymolrc:

```
# >>> molmcp bridge >>>
run /path/to/mol-mcp/molmcp/inapp/pymol/molmcp_pymol_launch.py
# <<< molmcp bridge <<<
```

It reuses an existing `~/.pymolrc`, `~/.pymolrc.pml`, `~/pymolrc.pml` or `~/pymolrc`; otherwise it creates
`~/.pymolrc` (macOS/Linux) or `~/pymolrc.pml` (Windows). The block is replaced, not duplicated, on re-runs
and removed on uninstall. The launcher registers the commands (`agent_*`, `claude`, `codex`, `agent_chat`,
`agent_button`) but not the Plugin-menu entries or the toolbar button; type `agent_button` to add the button.

### 4.3 ChimeraX bundle (`--chimerax`)

1. A wheel is built without any build tools:
   `$MOLMCP_HOME/build/ChimeraX_AgentBridge-0.1.0-py3-none-any.whl` (default
   `~/.molmcp/build/...`). It contains `chimerax/agentbridge/*.py` and the toolbar icon `agent_chat.png`.
2. ChimeraX is run headless: `ChimeraX --nogui --exit --silent --script <temporary script>.py`
   (on Windows `ChimeraX-console.exe` next to `ChimeraX.exe` is used so output can be captured;
   `MOLMCP_CHIMERAX_AUTOSTART=0` is set). The script runs ChimeraX's own commands
   `toolshed uninstall "ChimeraX-AgentBridge"` and then `toolshed install "<wheel>" reinstall true`.

ChimeraX installs user bundles into its per-user, per-version directory:

| OS | ChimeraX per-user directory |
|---|---|
| macOS | `~/Library/Application Support/ChimeraX/<version>/lib/python/site-packages/chimerax/agentbridge/` (verified on 1.11) |
| Linux | `~/.local/share/ChimeraX/<version>/...` |
| Windows | `%LOCALAPPDATA%\UCSF\ChimeraX\<version>\...` |

The bundle registers the commands `agent start`, `agent stop`, `agent status`, `agent info`, `agent chat`,
`agent name`, `claude`, `codex`, the tool *Tools ▸ General ▸ Agent Chat* and a toolbar tab **Agent** (after *Markers*)
with an *Agent Chat* button. Because the install is per ChimeraX version, re-run `python install.py
--chimerax` after upgrading ChimeraX.

**Fallback.** If ChimeraX is not found the installer prints the manual alternative: inside ChimeraX run
`open /path/to/mol-mcp/molmcp/inapp/chimerax/molmcp_chimerax_launch.py`, or start ChimeraX with
`--script /path/to/mol-mcp/molmcp/inapp/chimerax/molmcp_chimerax_launch.py`. That starts the bridge and
registers the commands for that session only.

### 4.4 Claude Code (`--claude`)

File: **`~/.claude.json`** (user scope, so the servers are available in every project). The installer
reads it, adds or replaces `mcpServers.pymol` and `mcpServers.chimerax`, and writes it back:

```json
"mcpServers": {
  "pymol":    {"type": "stdio", "command": "/path/to/mol-mcp/.venv/bin/pymol-mcp",    "args": [], "env": {}},
  "chimerax": {"type": "stdio", "command": "/path/to/mol-mcp/.venv/bin/chimerax-mcp", "args": [], "env": {}}
}
```

If the console script is missing the command falls back to `<venv python> -m molmcp.pymol_server.server`.
A copy of the previous file is saved as **`~/.claude.json.molmcp-backup`** before writing. If
`~/.claude.json` exists but does not parse as JSON, the installer leaves it alone and says so.

### 4.5 Codex (`--codex`)

File: **`~/.codex/config.toml`** (the directory is created if needed). Two sections are added or
replaced in place:

```toml
[mcp_servers.pymol]
command = "/path/to/mol-mcp/.venv/bin/pymol-mcp"
args = []

[mcp_servers.chimerax]
command = "/path/to/mol-mcp/.venv/bin/chimerax-mcp"
args = []
```

Backup: **`~/.codex/config.toml.molmcp-backup`**. On Python 3.11+ the installer re-parses the file
afterwards and warns if it is no longer valid TOML (restore the backup in that case).

### 4.6 Claude Desktop (`--claude-desktop`, automatic when the file exists)

| OS | file |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

Entries `pymol` and `chimerax` of the form `{"command": "...", "args": []}` are added. If you already have
a server called `pymol` that is not molmcp's, yours is kept and molmcp's is added as `pymol-molmcp`
(likewise `chimerax-molmcp`). Backup: `claude_desktop_config.json.molmcp-backup`. Restart Claude Desktop
afterwards.

### 4.7 State directory `~/.molmcp` (`MOLMCP_HOME`)

Created on demand (`build/` by the installer, the rest by the servers, bridges and the in-app chat):

| path | content |
|---|---|
| `instances/<app>-<pid>.json` | one discovery file per running bridge (host, port, token, pid, version, cwd; mode 0600) |
| `renders/` | PNGs written by the `render` and `layout` tools |
| `build/` | the ChimeraX wheel |
| `skills/<app>/*.md` | your own skill files (see §6.5) |
| `agent_settings.json` | provider/model/effort chosen in the in-app chat (see §6.4); always under `~/.molmcp`, even when `MOLMCP_HOME` is set |

---

## 5. Verify each piece

### 5.1 The installer's view

```bash
python3 install.py --check        # Windows: py -3 install.py --check
```

```
== molmcp 0.1.0 ==
python:   /path/to/mol-mcp/.venv/bin/python
pymol:    /Applications/PyMOL.app/Contents/bin/pymol
chimerax: /Applications/ChimeraX-1.11.1.app/Contents/bin/ChimeraX
pymol     server: /path/to/mol-mcp/.venv/bin/pymol-mcp
chimerax  server: /path/to/mol-mcp/.venv/bin/chimerax-mcp
home:     /Users/you/.molmcp
```

`NOT FOUND (set PYMOL_EXE)` means the viewer was not discovered; set the variable (§2.2) and re-run.

### 5.2 PyMOL

Start PyMOL normally. In the PyMOL command line:

```
PyMOL> agent_status
 Agent bridge: running on http://127.0.0.1:50885  pid 26360  events 3  (connection file: /Users/you/.molmcp/instances/pymol-26360.json)
```

If it says `Agent bridge: not running (use agent_start)`, type `agent_start`. You should also see, in the
**Plugin** menu, *Agent Chat (Claude / Codex)*, *Agent Bridge (MCP): Start / Status / Stop*, and an
**Agent** button in the top toolbar next to *Builder* (PyMOL 3 Qt GUI; type `agent_button` to add it if it
is missing).

Note: the plugin loads only in the Qt GUI. `pymol -c` (headless) does not load plugins; headless use goes
through the launcher scripts, see §7.

### 5.3 ChimeraX

Start ChimeraX normally. In the ChimeraX command line:

```
agent status
```

The log shows `molmcp agent bridge: running on http://127.0.0.1:<port>  pid <pid>  events <n>
(connection file: ...)`. If it says `not running (use 'agent start')`, run `agent start`. Check also
*Tools ▸ General ▸ Agent Chat* and the **Agent** toolbar tab. `usage claude` prints the synopsis of the
`claude` command.

ChimeraX 1.11 also ships its *own* `mcp` command (`mcp setup`, `mcp start`, ...) for Claude Desktop. That is
UCSF's separate implementation and has nothing to do with molmcp; molmcp's commands all start with `agent`.

### 5.4 Claude Code

```bash
claude mcp list
```

```
Checking MCP server health…
pymol: /path/to/mol-mcp/.venv/bin/pymol-mcp  - ✔ Connected
chimerax: /path/to/mol-mcp/.venv/bin/chimerax-mcp  - ✔ Connected
```

`claude mcp get pymol` shows the scope (`User config`), type, command and status. Inside an interactive
`claude` session, `/mcp` lists the servers and their tools. "Connected" only means the server program
starts; it does not need a running viewer for that.

### 5.5 Codex

```bash
codex mcp list            # table (Name, Command, Args, Env, Cwd, Status, Auth); pymol and chimerax show "enabled"
codex mcp get pymol       # enabled: true, transport: stdio, command: ...
```

### 5.6 A first prompt

With PyMOL or ChimeraX open (or not: the agent can start it), from a terminal:

```bash
# Claude Code, interactive
claude
> Use the pymol MCP server: call status, then scene, and tell me what is loaded and how it is shown.

# Claude Code, one-shot
claude -p "Use the pymol MCP server: call status and summarise it." --allowedTools mcp__pymol

# Codex, interactive
codex
> Use the chimerax MCP server: call status, then scene, and describe the models.

# Codex, one-shot
codex exec "Use the chimerax MCP server: call status and summarise it."
```

And inside the viewer:

```
PyMOL>  claude what is loaded and how is it coloured?
ChimeraX: codex colour chain A hot pink and zoom on it
```

The first call from each agent may take a few seconds: the MCP server starts, finds the bridge's discovery
file and connects.

---

## 6. Using it

### 6.1 From Claude Code

Open `claude` anywhere (terminal or the VS Code extension) and ask in plain language; it picks the `pymol`
or `chimerax` server by itself. The tool names, as the agent sees them, are `mcp__pymol__<tool>` and
`mcp__chimerax__<tool>`.

Tools on both servers:

| tool | purpose |
|---|---|
| `status`, `launch`, `connect` | find / start / pick a viewer process. `launch(mode="gui"\|"headless")` for PyMOL, `mode="gui"\|"nogui"` for ChimeraX; `connect(pid=...)`, `connect(port=...)` or `connect(name=...)` |
| `run` | execute viewer commands (list, or one string with one command per line); per-command ok/output/error plus a `changes` list |
| `python` | run Python inside the viewer (`cmd`, `pymol`, `stored` in PyMOL; `session`, `run()` in ChimeraX); assign `result` |
| `scene` | structured snapshot (`detail="summary"` or `"full"`; `objects=[...]` / `models=[...]`) |
| `object_info` (PyMOL) / `model_info` (ChimeraX) | everything about one object / model |
| `selection_info` | what a selection / atom spec matches |
| `get_view`, `set_view` (PyMOL only) | camera |
| `render` | render + numerical analysis; `width`, `height`, `ray` (PyMOL) / `supersample` (ChimeraX), `transparent`, `path`, `return_image`, `grid` |
| `layout` | ID-pass render: which objects/chains are where; `by="object"\|"chain"\|"items"` (ChimeraX: `"model"\|"chain"\|"items"`), `occlusion` |
| `compare_renders`, `analyze_image` | diff two renders; analyse any PNG |
| `events`, `log` | what happened since the last call; viewer log |
| `help`, `commands` | viewer command documentation / list |
| `settings` (PyMOL only) | read settings globally or per object |
| `skills`, `skill`, `save_skill` | instruction files (§6.5) |
| `measure`, `align`, `sequence`, `contacts`, `save_file` | structured helpers (§6.6) |
| `quit_pymol` / `quit_chimerax` | terminate the viewer |

Permissions: in an interactive Claude Code session the first use of each MCP tool asks for approval unless
you allow it; for one-shot runs pass `--allowedTools mcp__pymol` (or `mcp__chimerax`, or both separated by a
comma) as in §5.6.

### 6.2 From Codex

Start `codex` in a terminal and ask for the `pymol` or `chimerax` server by name the first time ("use the
pymol server to ..."). Codex's sandbox applies to shell commands it runs, not to MCP tool calls: the viewer
commands the agent sends through `run`/`python` execute inside PyMOL/ChimeraX with your user's rights.

### 6.3 Inside PyMOL and ChimeraX

| what | PyMOL | ChimeraX |
|---|---|---|
| ask Claude Code | `claude <text>` | `claude <text>` |
| ask Codex | `codex <text>` | `codex <text>` |
| open the chat panel | `agent_chat`, *Plugin ▸ Agent Chat (Claude / Codex)*, or the **Agent** toolbar button (toggles the dock) | `agent chat`, *Tools ▸ General ▸ Agent Chat*, or the **Agent** toolbar tab ▸ *Agent Chat* |
| add the toolbar button if missing | `agent_button` | (provided by the bundle) |
| bridge control | `agent_start [port]`, `agent_stop`, `agent_status`, `agent_info` | `agent start [port N]`, `agent stop`, `agent status`, `agent info` |
| name this window (see §8) | `agent_name <name>` | `agent name <name>` |

`claude ...` / `codex ...` open the panel (in the GUI) and submit the text; the agent is pinned to **that**
viewer window, so it reads and changes exactly what you see. Without a GUI (headless PyMOL, `chimerax
--nogui`) the agent's text and tool calls are printed to the log instead. In PyMOL, commas in your text are
preserved (the command re-joins its arguments).

**The panel** mirrors the Claude Code terminal UI:

* `>` your prompt, `⏺` assistant text, `⏺ pymol/run(...)` tool calls with the commands or Python script
  shown in a numbered code window, `⎿` a collapsed preview of the result, a spinner line while it works
  and a closing line such as `✓ claude code · opus · high · 12.3s · $0.12 · 328 output tokens` (provider ·
  model · effort · time; the dollar figure is the API-price estimate Claude Code reports — a subscription login
  is not billed per request — and Codex reports tokens only).
* Keys: **Enter** sends, **Shift+Enter** inserts a newline, **Esc** interrupts the running agent,
  **↑ / ↓** recall previous prompts, **Tab** accepts a slash-command suggestion (a list pops up when the
  prompt starts with `/`).
* Slash commands:

  | command | effect |
  |---|---|
  | `/model` | show the current provider · model · effort and the usage line |
  | `/model [claude\|codex] [<model>\|default] [effort]` | set them, e.g. `/model claude opus high`, `/model codex gpt-5-codex`, `/model default` |
  | `/claude`, `/codex` | switch provider (optionally followed by a prompt: `/codex what is shown?`) |
  | `/clear` | start a fresh conversation with the current provider |
  | `/skills` | ask the agent to list its skill files |
  | `/stop` | interrupt |
  | `/help` (or `/?`) | this list |

* The **model button** at the bottom right (`claude code · default ▾`) opens a menu with one submenu per
  provider: *Model* (Claude: default, fable, opus, sonnet, haiku; Codex: default, gpt-5-codex, gpt-5, o3,
  gpt-6-sol — any other name can be typed with `/model <name>`), *Effort* (Claude: default, low, medium,
  high, xhigh, max; Codex: default, minimal, low, medium, high, xhigh) and, for the provider not currently in
  use, *Use Claude Code* / *Use Codex*.
  A provider whose CLI is not installed is greyed out as "(not installed)".
* Conversations continue across turns per provider (Claude Code via `--resume <session id>`, Codex via
  `codex exec resume <thread id>`); `/clear` forgets the session.

**What runs under the hood.** Each prompt spawns your own CLI non-interactively from inside the viewer:

```
claude -p "<prompt>" --output-format stream-json --verbose --include-partial-messages \
       --allowedTools mcp__pymol --append-system-prompt "<context>" [--model M] [--effort E] [--resume <id>]

codex exec --json --approve-for-me --skip-git-repo-check [-m M] [-c model_reasoning_effort="E"] "<prompt>"
codex exec resume --json --approve-for-me --skip-git-repo-check [...] <thread id> "<prompt>"
```

with `MOLMCP_PYMOL_PID` / `MOLMCP_CHIMERAX_PID` set to the viewer's process id, so the MCP server the CLI
starts attaches to this exact process. Claude Code is restricted to the viewer's MCP tools
(`--allowedTools mcp__<app>`: no Bash, Edit or Write). The CLI is searched on `PATH`, in the VS Code / Cursor
Claude Code extension, in `~/.claude/local`, in `~/.npm-global/bin`, `/usr/local/bin`, `/opt/homebrew/bin`,
on Windows in `%APPDATA%\npm` and `%LOCALAPPDATA%\Programs`, and for Codex also in the ChatGPT desktop app;
override with `MOLMCP_CLAUDE_EXE` / `MOLMCP_CODEX_EXE` (used as given). Every candidate found by searching must
pass `<exe> --version`.
Variables the viewer sets for its own bundled Python/Qt (`PYTHONHOME`, `PYTHONPATH`, `PYTHONEXECUTABLE`,
`DYLD_*`, `LD_LIBRARY_PATH`, `QT_*`, `PYMOL_PATH`, `SSL_CERT_FILE`, ...) are stripped from the CLI's
environment, and the usual user bin directories are appended to `PATH`.

### 6.4 Provider, model and effort settings

Choices made with `/model` or the model button are saved to **`~/.molmcp/agent_settings.json`** (or the
file named by `MOLMCP_AGENT_SETTINGS`; this path does not follow `MOLMCP_HOME`) and apply to every later run
from either viewer:

```json
{
 "default_backend": "claude",
 "claude": {"model": "opus", "effort": "high"},
 "codex": {"model": "", "effort": "medium"}
}
```

An empty model means the CLI's default (for Codex: whatever `~/.codex/config.toml` says). When the panel
opens it uses `default_backend` if that CLI is installed, otherwise the first installed CLI.

### 6.5 Skills: instructions the agent reads on demand

A skill is a Markdown file with a short front matter. The agent lists them with the `skills` tool, reads
one with `skill(name)` and can store its own recipe with `save_skill(name, content)`. They are also exposed
as MCP resources `molmcp://<app>/skills` and `molmcp://<app>/skills/<name>` and as the MCP prompt
`use_skill(skill, task)` for clients that support those.

| location | role |
|---|---|
| `<repo>/molmcp/skills/shared/*.md`, `<repo>/molmcp/skills/pymol/*.md`, `<repo>/molmcp/skills/chimerax/*.md` | built-in |
| `~/.molmcp/skills/shared/`, `~/.molmcp/skills/pymol/`, `~/.molmcp/skills/chimerax/` (or `$MOLMCP_SKILLS_DIR/<app>/`) | yours; a user file with the same `name` overrides the built-in one |

File format:

```markdown
---
name: publication-render
title: Publication-quality rendering
app: pymol
description: one line shown in the index
tags: rendering, figure
---
1. `scene` first, then ...
```

`save_skill` normalises the name to lowercase letters, digits and dashes, adds the front matter if you
omit it, and writes `~/.molmcp/skills/<app>/<name>.md`. Edit these files with any editor; no restart is
needed.

### 6.6 Structured helper tools

Both servers add convenience tools that run small scripts inside the viewer and return JSON:

| tool | PyMOL | ChimeraX |
|---|---|---|
| `measure` | `kind` = distance / angle / dihedral / extent / center / rmsd / count, with `selection1..4`, optional `name` to draw the measurement | the same `kind`s plus `sasa`, with `spec1..4` |
| `align` | `mobile`, `target`, `method` = align / super / cealign / pair_fit, `cycles`, `cutoff`, `object_name` | `mobile`, `target`, `method` = matchmaker (default) / align |
| `sequence` | `selection` (default `polymer`) | `spec` (default `protein`) |
| `contacts` | `selection1`, `selection2`, `cutoff` (4 Å), `polar_only`, `max_pairs` | `spec1`, `spec2`, `cutoff`, `polar_only`, `max_pairs` |
| `save_file` | `path`, `selection`, `format`, `state` | `path`, `models`, `format`, `options` |

---


> Added after the guide was written: `residue_table` (per-residue table: secondary structure, B-factor/pLDDT, shown
> representations, colours), `run(json=True)` in ChimeraX for structured command output, `allow_dangerous=True`
> required for commands that quit/reset the session or run shell/package managers, and `confirm=True` required
> by `quit_pymol` / `quit_chimerax`.  PyMOL now ships 14 skills (incl. `alphafold-plddt`, `mutagenesis`) and
> ChimeraX 13 (incl. `ligand-binding-site`).

## 7. Headless use and environment variables

### 7.1 Headless PyMOL

`launch(mode="headless")` starts PyMOL *as a library* inside PyMOL's own bundled Python:

```
<PyMOL python> <repo>/molmcp/inapp/pymol/molmcp_pymol_headless.py [--port N]
```

The Python is found via `PYMOL_PYTHON`, or next to the PyMOL executable (`.../bin/python`,
`.../MacOS/python`, the shebang of a conda launcher script, ...), and must be able to `import pymol, pymol2`.
If no such Python is found the server falls back to `pymol -cq -r molmcp_pymol_launch.py` with
`MOLMCP_KEEPALIVE=1` (the launcher then keeps the process alive serving the bridge). Renders in headless
mode are ray-traced. You can start it yourself, e.g. on macOS:

```bash
/Applications/PyMOL.app/Contents/bin/python /path/to/mol-mcp/molmcp/inapp/pymol/molmcp_pymol_headless.py --port 5555
```

The process stays alive until the `quit_pymol` tool is called or you terminate it.

### 7.2 Headless ChimeraX

`launch(mode="nogui")` (or `"headless"`) runs

```
ChimeraX --nogui [--offscreen] --script <repo>/molmcp/inapp/chimerax/molmcp_chimerax_launch.py
```

`--offscreen` is added on Linux only: it is the only platform where ChimeraX can render without a window.
On macOS and Windows a `--nogui` ChimeraX can execute commands, report `scene`, etc., but `render` and
`layout` fail ("ChimeraX returned no image"). Windows uses `ChimeraX-console.exe` so output is visible. To
start it yourself on Linux:

```bash
chimerax --nogui --offscreen --script /path/to/mol-mcp/molmcp/inapp/chimerax/molmcp_chimerax_launch.py
```

### 7.3 Environment variables

Two different processes read these: the **MCP server** (started by Claude Code/Codex) and the **viewer**
(started by you, or by the server's `launch` tool, which passes its own environment on).

| variable | read by | meaning |
|---|---|---|
| `MOLMCP_HOME` | server and viewer | state directory (default `~/.molmcp`): discovery files, renders, build, skills. Both sides must agree, see §11 |
| `MOLMCP_OUTPUT_DIR` | server | where `render`/`layout` PNGs go (default `$MOLMCP_HOME/renders`) |
| `MOLMCP_AUTOLAUNCH=0` | server | never start a viewer automatically when a tool is called and no bridge is running (the explicit `launch` tool still works) |
| `MOLMCP_APP_CWD` | server | working directory for viewers started by `launch` (default: your home directory) |
| `MOLMCP_PYMOL_PID`, `MOLMCP_CHIMERAX_PID` | server | attach to this viewer process id instead of the newest bridge (set automatically by the in-app chat) |
| `PYMOL_EXE`, `CHIMERAX_EXE` | server, installer | explicit viewer executables |
| `PYMOL_PYTHON` | server, installer | explicit Python that can `import pymol` (headless library mode, plugin installation) |
| `MOLMCP_PYMOL_PORT`, `MOLMCP_CHIMERAX_PORT` | viewer | fixed bridge port (default: a random free port; if the fixed port is busy the next 19 ports are tried) |
| `MOLMCP_PYMOL_NAME`, `MOLMCP_CHIMERAX_NAME` | viewer | initial window name for `connect(name=...)`, same as `agent_name` / `agent name` (§8) |
| `MOLMCP_PYMOL_AUTOSTART=0`, `MOLMCP_CHIMERAX_AUTOSTART=0` | viewer | do not start the bridge when the application starts (`agent_start` / `agent start` still work) |
| `MOLMCP_KEEPALIVE=1` | viewer (PyMOL `-c`) | keep a `pymol -cq -r molmcp_pymol_launch.py` process alive serving the bridge |
| `MOLMCP_CLAUDE_EXE`, `MOLMCP_CODEX_EXE` (also `CLAUDE_CLI`, `CODEX_CLI`) | viewer (in-app chat) | explicit CLI executables |
| `MOLMCP_SKILLS_DIR` | server | user skills directory (default `$MOLMCP_HOME/skills`) |
| `MOLMCP_AGENT_SETTINGS` | viewer (in-app chat) | settings file (default `~/.molmcp/agent_settings.json`, independent of `MOLMCP_HOME`) |

How to set them:

* **For the MCP server, permanently:** put them in the server's config entry. Claude Code:
  `"env": {"MOLMCP_OUTPUT_DIR": "/data/renders"}` in `~/.claude.json`; Codex: an `env` table under the
  section, e.g.

  ```toml
  [mcp_servers.pymol]
  command = "/path/to/mol-mcp/.venv/bin/pymol-mcp"
  args = []
  env = { MOLMCP_OUTPUT_DIR = "/data/renders" }
  ```

  Otherwise the server simply inherits the environment of the shell you started `claude`/`codex` from
  (`export VAR=value` on macOS/Linux; `$env:VAR = "value"` in PowerShell; `setx VAR value` for a
  persistent Windows user variable, effective in new terminals).
* **For the viewer:** a viewer started from the Dock, Finder, Start menu or a desktop launcher gets a
  minimal environment. Start it from a terminal with the variable set
  (`MOLMCP_PYMOL_PORT=5555 pymol`), or use the in-app commands (`agent_start 5555`, `agent start port 5555`)
  instead of variables.

---

## 8. Several viewer windows at once

Every bridge writes its own discovery file `$MOLMCP_HOME/instances/<app>-<pid>.json`; files whose process
is gone are deleted automatically. One bridge per viewer process; `agent_start` in a process that already
has one just reports the port.

* `status` lists every live bridge of that app under `windows` (pid, name, loaded items, whether the window
  has focus, gui, last activity, start time, cwd) and says which one is connected (`connected_pid`).
* Without instructions the server connects to the window that **has keyboard focus**, else the most recently
  used one, else the newest. `connect(pid=26360)`, `connect(port=50885)` or `connect(name="mywork")` switches
  to a specific one for the rest of the session; name a window with `agent_name mywork` (PyMOL) or
  `agent name mywork` (ChimeraX). With several windows open, every `run`/`scene`/`events` reply names the
  window it acted on, and `events` points out when you are typing in a different one.
* The in-app chat always pins to its own window via `MOLMCP_<APP>_PID`; if that process disappears the
  server falls back to the newest bridge.
* PyMOL and ChimeraX are independent servers; you can drive both in the same conversation.

---

## 9. Where renders go

`render` and `layout` return numbers, not pictures, but every image is also saved so you can open it:

* default directory `~/.molmcp/renders/` (`MOLMCP_OUTPUT_DIR` or `$MOLMCP_HOME/renders` overrides);
  the `status` tool reports it as `renders_dir`;
* file names `<app>_render_<YYYYMMDD_HHMMSS_mmm>.png` and `<app>_layout_<...>.png`
  (e.g. `pymol_render_20261107_100923_565.png`);
* `render(path="/some/file.png")` writes to that file instead (`.png` is appended if missing);
* the server remembers the last 30 renders, so `compare_renders()` with no arguments diffs the last two;
* `return_image=True` additionally sends a thumbnail (max 1024 px) to the agent, which is the only case in
  which image data leaves the MCP server.

Images the *agent* makes with viewer commands (`png`, `save`, `save_file`) go wherever it says, relative to
the viewer's working directory (shown in the chat panel's welcome box and in `status` → `cwd`).

---

## 10. Security model

* **Localhost only.** Each bridge binds `127.0.0.1` on a random free port (or `MOLMCP_<APP>_PORT`). It
  never listens on a network interface.
* **Token.** Every bridge generates a fresh secret (`secrets.token_urlsafe(24)`) at start. All operations
  (`POST /call`) require it as `Authorization: Bearer <token>` (or `X-MolMCP-Token`); anything else gets
  HTTP 401. The only unauthenticated endpoint is `GET /ping`, which returns the app name, pid, version
  and uptime.
* **Discovery files** `~/.molmcp/instances/<app>-<pid>.json` contain the token and are written with mode
  `0600` (owner read/write only). They are the only place the token is stored and are removed when the
  bridge stops or when its process is found dead. If `MOLMCP_HOME` points to a shared or network file
  system, other people who can read it can control your viewer.
* **What leaves the machine:** molmcp itself makes no network connections (the only other process it
  talks to is the viewer on localhost). Claude Code and Codex send your prompts and everything the tools
  return — scene snapshots, command output, render analyses, thumbnails if `return_image=True` — to
  Anthropic / OpenAI under your own account. The viewers download structures (`fetch 1abc`, `open 1abc`)
  from the PDB as they always do.
* **What the agent can do:** `run` and `python` execute arbitrary viewer commands and Python inside
  PyMOL/ChimeraX with your user's rights — reading, writing and deleting files included. The in-app chat
  limits Claude Code to the viewer's MCP tools (`--allowedTools mcp__<app>`), and Codex is started with
  `--approve-for-me` (its shell commands run in the workspace-write sandbox), but the viewer-side
  execution is by design unsandboxed. Review what the panel shows in its code windows; use `quit_pymol` /
  `quit_chimerax` only when you mean it (they terminate the viewer).
* **Config edits** are limited to the files listed in §4, each backed up as `*.molmcp-backup` first.

---

## 11. Troubleshooting

**`No running pymol bridge found` / `no running chimerax bridge found`**

1. Is the viewer running? In it, run `agent_status` (PyMOL) or `agent status` (ChimeraX). `not running` →
   `agent_start` / `agent start`. If the commands do not exist, the plugin/bundle is not installed in this
   viewer: re-run `python install.py --pymol` / `--chimerax` and restart the viewer, or load it for this
   session with `run /path/to/mol-mcp/molmcp/inapp/pymol/molmcp_pymol_launch.py` (PyMOL) or
   `open /path/to/mol-mcp/molmcp/inapp/chimerax/molmcp_chimerax_launch.py` (ChimeraX).
2. Does `~/.molmcp/instances/` contain a `<app>-<pid>.json` whose pid is the running viewer? If the viewer
   writes to a different `MOLMCP_HOME` (set in one environment but not the other; Flatpak/Snap sandboxes
   with their own `HOME`) the server cannot see it. Make both sides use the same directory.
3. `MOLMCP_PYMOL_AUTOSTART=0` / `MOLMCP_CHIMERAX_AUTOSTART=0` in the viewer's environment disables
   autostart; `pymol -k` disables PyMOL plugins altogether.
4. Autolaunch may have been disabled with `MOLMCP_AUTOLAUNCH=0`; call `launch` explicitly.

**Stale instance files.** Files for dead processes are removed automatically on every discovery (pid
check). After a crash on Windows a reused pid can in rare cases keep a stale file alive; delete
`~/.molmcp/instances/*.json` and run `agent_start` / `agent start` again. `bridge rejected token;
reconnecting on next call` means the viewer restarted: just call the tool again.

**`launched pymol (...) but no bridge appeared within 120s`.** The executable that started is not the
one you expected (set `PYMOL_EXE` / `CHIMERAX_EXE`), the application needs longer to start (pass
`wait_seconds`), or it exited (the message then shows the exit code; start it from a terminal with the
same arguments to see why).

**`<app> bridge timed out after Ns on op 'run' (is the app busy or showing a dialog?)`.** A modal dialog
(file chooser, licence prompt, "save changes?") blocks the viewer's main thread; dismiss it. Very long
ray-traces also hit the timeout.

**`Claude Code CLI not found. Install it or set MOLMCP_CLAUDE_EXE` (or Codex).** The viewer searched the
locations in §6.3 and found nothing that passes `--version`. Find the binary (`which claude`, `which codex`
on macOS/Linux; `where claude` on Windows) and set `MOLMCP_CLAUDE_EXE` / `MOLMCP_CODEX_EXE` to its full
path in the viewer's environment. A binary that exists but fails `--version` — typically a stale npm
install or the wrong CPU architecture (an x86_64 build on Apple silicon or vice versa) — is skipped on
purpose: reinstall it. GUI apps started from the Dock/Start menu do not see your shell's `PATH`; the chat
adds `~/.local/bin`, `~/.npm-global/bin`, `~/.claude/local`, `/opt/homebrew/bin`, `/usr/local/bin` itself.

**The agent starts but the server does not (`connection closed`, `claude exited with code 1`, Python
tracebacks about `encodings` or `site`).** The server's Python was started with the viewer's interpreter
settings. The chat strips `PYTHONHOME`, `PYTHONPATH`, `PYTHONEXECUTABLE`, `DYLD_*`, `LD_LIBRARY_PATH`,
`QT_*` and friends automatically; if you set any of these yourself (e.g. in `~/.zshrc`, or a conda
`activate` that exports `PYTHONHOME`), unset them for the viewer and for the terminal you start the CLI
from. Also check that `<repo>/.venv/bin/pymol-mcp` still exists.

**`claude mcp list` shows `✘ Failed to connect` / Codex says the server failed.** The command path in the
config no longer exists (repository moved or `.venv` deleted) → re-run `python install.py --claude --codex`
from the new location (it rewrites the paths). Test the server by hand:
`/path/to/mol-mcp/.venv/bin/pymol-mcp` should start silently and wait for input (Ctrl-C to stop); a
traceback means the venv is broken → delete `.venv` and re-run `python install.py`. The end-to-end test
`.venv/bin/python tests/e2e_mcp_client.py pymol --launch` exercises the whole chain.

**`WARNING: ~/.codex/config.toml does not parse as TOML after edit`.** Restore
`~/.codex/config.toml.molmcp-backup` and add the two sections from §4.5 by hand (or with
`codex mcp add pymol -- /path/to/mol-mcp/.venv/bin/pymol-mcp`).

**`headless PyMOL plugin install failed; output was: ...`** The headless PyMOL run did not complete (a licence
dialog, a PyMOL build without `-c`, a Python that imports `pymol` but cannot run it). The installer then
falls back to the pymolrc block (§4.2), which works just as well. Alternatively zip the folder
`molmcp/inapp/pymol/molmcp_pymol_bridge` and install it through *Plugin ▸ Plugin Manager ▸ Install New
Plugin* in PyMOL.

**`bundle install failed; ChimeraX output: ...`** Run ChimeraX, then in its command line
`toolshed install "/Users/you/.molmcp/build/ChimeraX_AgentBridge-0.1.0-py3-none-any.whl" reinstall true`
and read the log. `toolshed list` shows installed bundles. After a ChimeraX upgrade the bundle must be
installed again for the new version.

**ChimeraX as root on Linux.** ChimeraX does not use a real per-user data directory for root, so the
bundle ends up where ChimeraX will not look and autostart never happens. Run ChimeraX (and the installer)
as a normal user — the Docker image does exactly that with a `tester` user.

**ChimeraX headless on macOS/Windows cannot render.** Expected: offscreen rendering (`--offscreen`) exists
on Linux only. Use the GUI, or a Linux machine/container for batch rendering.

**`claude`/`codex` show no panel in `chimerax --nogui` or `pymol -c`.** They work: without a GUI the answer
is written to the log as `Claude Code: ...` (ChimeraX) or ` claude: ...` (PyMOL) lines instead.

**Claude Desktop does not show the servers.** The installer only edits the config if the file already
exists; create it by opening Claude Desktop's developer settings once, then re-run
`python install.py --claude-desktop` and restart Claude Desktop. If your config already had a `pymol`
server of your own, molmcp's is called `pymol-molmcp`.

**Windows notes.** Use `py -3` if `python` opens the Microsoft Store. The server commands are
`.venv\Scripts\pymol-mcp.exe` and `chimerax-mcp.exe`; in `~/.claude.json` backslashes are escaped
(`"C:\\Users\\you\\mol-mcp\\.venv\\Scripts\\pymol-mcp.exe"`). The PyMOL plugin goes to
`%APPDATA%\pymol\startup`, the pymolrc fallback to `%USERPROFILE%\pymolrc.pml`. Scripted ChimeraX runs use
`ChimeraX-console.exe`; the in-app chat starts the CLI without a console window. Windows paths and process
handling are covered by the platform-simulation tests and the Wine image (§13) but have not yet been run
on a physical Windows machine — please report what you see.

**The agent claims it changed something but the view did not change.** Ask it to call `events` or
`compare_renders`; `run` stops at the first failing command (`stop_on_error=True`) and reports it.

---

## 12. Uninstalling

```bash
python3 install.py --uninstall                      # everything
python3 install.py --uninstall --pymol              # only the PyMOL plugin (+ pymolrc block)
python3 install.py --uninstall --chimerax           # only the ChimeraX bundle
python3 install.py --uninstall --claude --codex     # only the registrations
python3 install.py --uninstall --dry-run            # show what would be removed
```

What is removed:

| piece | action |
|---|---|
| PyMOL plugin | headless PyMOL deletes `molmcp_pymol_bridge` from every directory in its plugin startup path, drops the autoload entry and saves `~/.pymolpluginsrc.py`; the `# >>> molmcp bridge >>>` block is removed from your pymolrc |
| ChimeraX bundle | headless ChimeraX runs `toolshed uninstall "ChimeraX-AgentBridge"` |
| Claude Code | `mcpServers.pymol` / `.chimerax` are removed from `~/.claude.json` only if they point at `pymol-mcp` / `chimerax-mcp` (or `-m molmcp...`) |
| Codex | the `[mcp_servers.pymol]` / `[mcp_servers.chimerax]` sections are removed from `~/.codex/config.toml` |
| Claude Desktop | `pymol`, `pymol-molmcp`, `chimerax`, `chimerax-molmcp` entries that are molmcp's are removed |

Not removed, delete by hand if you want: the repository with its `.venv`, `~/.molmcp` (renders, skills,
settings, build), and the `*.molmcp-backup` files. Equivalent manual commands:
`claude mcp remove pymol -s user`, `claude mcp remove chimerax -s user`, `codex mcp remove pymol`,
`codex mcp remove chimerax`.

---

## 13. Docker verification images

`tests/docker/` holds the images used to verify the Linux and Windows code paths without a second machine.
You do not need them to use molmcp; they are for checking a change or reproducing a platform problem. All
build commands run from the repository root and copy the current checkout into the image.

| image | what it checks | build / run |
|---|---|---|
| `Dockerfile.pymol-linux` | open-source PyMOL from conda-forge (micromamba, Python 3.11), no display: installer (`--pymol --claude --codex` on Linux paths), unit tests, full MCP end-to-end with headless library-mode launch, `quit_pymol` | `docker build --platform linux/amd64 -f tests/docker/Dockerfile.pymol-linux -t molmcp-pymol-linux .`<br>`docker run --rm --platform linux/amd64 molmcp-pymol-linux` |
| `Dockerfile.chimerax-official` | UCSF's official headless image `ucsfrbvi/chimerax` (multi-arch, no licence click-through), run as the normal user `tester`: bundle install, `--nogui --offscreen` launch via MCP, run / scene / offscreen render / layout / events / compare, `quit_chimerax` | `docker build -f tests/docker/Dockerfile.chimerax-official -t molmcp-chimerax-official .`<br>`docker run --rm molmcp-chimerax-official`<br>bundle autostart + `agent status` + `usage claude` check: `docker run --rm molmcp-chimerax-official bash /home/tester/work/mol-mcp/tests/docker/linux_bundle_check_chimerax.sh` |
| `Dockerfile.chimerax-linux` | same checks with a release `.deb`: download the Ubuntu 24.04 package for your CPU from https://www.rbvi.ucsf.edu/chimerax/download.html and save it as `tests/docker/chimerax.deb` first | `docker build -f tests/docker/Dockerfile.chimerax-linux -t molmcp-chimerax-linux .`<br>`docker run --rm molmcp-chimerax-linux` |
| `Dockerfile.chimerax-flatpak` | ChimeraX from Flathub inside the container, exposed as `/usr/local/bin/chimerax` with `MOLMCP_HOME` and `MOLMCP_CHIMERAX_AUTOSTART` passed into the sandbox | `docker build -f tests/docker/Dockerfile.chimerax-flatpak -t molmcp-chimerax-flatpak .`<br>`docker run --rm --privileged molmcp-chimerax-flatpak` (bubblewrap needs `--privileged`) |
| `Dockerfile.windows-wine` | the Windows code paths (`sys.platform == "win32"`) without Windows: the official Windows CPython 3.11 (NuGet package) and the open-source PyMOL Windows wheel under Wine; `install.py` on win32 (`.venv\Scripts\*.exe`, `%APPDATA%\pymol\startup`, Windows config paths), unit tests, MCP e2e with a headless Windows PyMOL. `PYMOL_PYTHON='C:\Py311\python.exe'`; `wine-constraints.txt` pins `numpy<2`, `pillow<11` because Wine 9 lacks a C-runtime symbol numpy 2 needs | `docker build --platform linux/amd64 -f tests/docker/Dockerfile.windows-wine -t molmcp-windows-wine .`<br>`docker run --rm --platform linux/amd64 molmcp-windows-wine` |

Scripts the images run (usable on any Linux box with the venv set up):

| script | purpose |
|---|---|
| `linux_smoke_pymol.sh` | installer → unit tests → `MOLMCP_PYMOL_LAUNCH_MODE=headless .venv/bin/python tests/e2e_mcp_client.py pymol --launch` → quit |
| `linux_smoke_chimerax.sh` | installer → `MOLMCP_CHIMERAX_LAUNCH_MODE=nogui .venv/bin/python tests/e2e_mcp_client.py chimerax --launch` → quit |
| `linux_bundle_check_chimerax.sh` | plain `ChimeraX --nogui --exit --cmd "agent status ; usage claude"` to prove the bundle autostarts and registers its commands |
| `linux_diag_chimerax.sh` | step-by-step bridge probes (`ping`, `log`, `run`, `scene`, `render`) against a `--nogui --offscreen --script` ChimeraX, with the ChimeraX log tail |
| `wine_smoke_pymol.sh` | the Windows run described above |
| `wine_rpc_probe.py` | raw JSON-RPC probe of a stdio server (`initialize`, `tools/list`, `tools/call`), prints the server's stderr so crashes are visible |

The end-to-end client itself: `.venv/bin/python tests/e2e_mcp_client.py pymol|chimerax [--launch]`; the
environment variables `MOLMCP_PYMOL_LAUNCH_MODE` / `MOLMCP_CHIMERAX_LAUNCH_MODE` (`gui`, `headless`,
`nogui`) choose how `--launch` starts the viewer and `MOLMCP_E2E_ERRLOG` redirects the server's stderr to
a file. Unit tests: `.venv/bin/python -m unittest discover -s tests`.

---

## 14. Appendix: manual registration and file map

### Any MCP client

Register a stdio server with command `<repo>/.venv/bin/pymol-mcp` or `<repo>/.venv/bin/chimerax-mcp`
(Windows `<repo>\.venv\Scripts\pymol-mcp.exe` / `chimerax-mcp.exe`), no arguments. Equivalent commands:

```bash
claude mcp add pymol    -s user -- /path/to/mol-mcp/.venv/bin/pymol-mcp
claude mcp add chimerax -s user -- /path/to/mol-mcp/.venv/bin/chimerax-mcp
codex  mcp add pymol    -- /path/to/mol-mcp/.venv/bin/pymol-mcp
codex  mcp add chimerax -- /path/to/mol-mcp/.venv/bin/chimerax-mcp
```

### Files, by location

| location | file | written by |
|---|---|---|
| repository | `.venv/` | `install.py` |
| | `molmcp/inapp/pymol/molmcp_pymol_bridge/{bridgecore,agentcli,agentchat_ui}.py` (copies of `molmcp/inapp/shared/`) | installer |
| home | `~/.pymol/startup/molmcp_pymol_bridge/` (Windows `%APPDATA%\pymol\startup\...`) | installer via PyMOL |
| | `~/.pymolpluginsrc.py` | PyMOL (plugin prefs) |
| | `~/.pymolrc` or `~/pymolrc.pml` (fallback only) | installer |
| | ChimeraX per-user dir `.../ChimeraX/<ver>/lib/python/site-packages/chimerax/agentbridge/` | ChimeraX toolshed |
| | `~/.claude.json` (+ `.molmcp-backup`) | installer |
| | `~/.codex/config.toml` (+ `.molmcp-backup`) | installer |
| | `claude_desktop_config.json` (+ `.molmcp-backup`), see §4.6 | installer |
| `~/.molmcp` | `instances/<app>-<pid>.json` | bridges |
| | `renders/*.png` | servers |
| | `build/ChimeraX_AgentBridge-0.1.0-py3-none-any.whl` | installer |
| | `skills/<app>/*.md` | you / `save_skill` |
| | `agent_settings.json` (always `~/.molmcp`, see §6.4) | in-app chat |
