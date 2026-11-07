# Feature coverage audit: can an agent reach everything in PyMOL and ChimeraX through molmcp?

Audited 2026-11-07 against the molmcp 0.1.0 working tree as it was at audit time (including the then-uncommitted
`extra_tools.py`, `common/skills.py`, `skills/`, chat-panel, `/model`, toolbar-button and window-naming changes, several of which landed while the audit ran), PyMOL 3.1.5.1
(`/Applications/PyMOL.app`, incentive build), UCSF ChimeraX 1.11.1 (`/Applications/ChimeraX-1.11.1.app`), Claude Code
2.1.319 (the VS Code extension's binary, which is the one the chat panel finds), Codex CLI 0.166.0-alpha.5.1 (the build
inside the ChatGPT desktop app) and the MCP Python SDK 2.3.0 in `.venv`.  A second pass later the same day re-ran the
headless checks and regenerated every count below; the PyMOL skill set had grown from 1 to 12 files in between
(section 7).  Everything marked *verified* was executed
headlessly during the audit (`pymol -cq script.py`, `ChimeraX --nogui --exit --script script.py`); no GUI was
launched, so GUI-specific statements come from reading the source and the shipped documentation.

> **Status after the audit (same day):** items 1, 2, 4 and 5 of section 6 are fixed in the code
> (`commands`/`help` import, `align` tuple handling, `run(json=True)` for structured ChimeraX output, a dangerous-command
> guard in `run` plus `confirm=True` on the `quit_*` tools), the three missing skills exist (PyMOL `alphafold-plddt`
> and `mutagenesis`, ChimeraX `ligand-binding-site`), all 27 skill bodies were reviewed against the installed
> programs, and `residue_table` (section 8, item 4) is implemented for both apps.  Second pass: items 5 (`mutate`,
> both apps), 7 (`map_info`, `set_isolevel`), 8 (`wait_for_jobs`), 9 (ChimeraX `set_view`) and 10 (`alignment_info`,
> both apps) are implemented too, plus PyMOL `measure(kind="sasa")`, `set_setting`, and one MCP prompt per skill
> (`/mcp__pymol__publication_rendering` style in Claude Code).

> **Red-team QA (same day):** 24 scenario testers (16 PyMOL on isolated headless instances, 8 ChimeraX) filed
> 113 reports (17 critical, 22 major, 74 minor). Fixed: a positional-argument slip in both servers' `run` wrapper
> (`allow_dangerous` landed in `timeout`, `json=True` bypassed the guard), guard bypass via `;` and command
> abbreviations, auto-launching a second window when a bridge was merely busy, silent fallback when the pinned
> window was gone, the ID-pass palette starting near black (background attributed to item 1) and ChimeraX items
> recolouring whole structures / resetting partial selections, headless PyMOL ignoring `transparent=False`, missing
> size limits (huge renders killed PyMOL), unvalidated `measure`/`mutate`/paging arguments, `swapaa preserve`
> syntax, `alignment_info` listing atoms instead of residue pairs, unordered ChimeraX residue tables, raw colour
> indices in `set_setting`, missing representation/movie changes in `changes`, loops excluded from secondary
> structure fractions, headless `log` empty, `compare_renders` failing in a fresh server process, ChimeraX
> `commands`/`help` import, volume statistics, duplicated python output, and more. Remaining minor items are
> documented in the tool docstrings (e.g. width/height 0 = window size).

> **Round 3 (restarted QA, same day):** the 9 scenarios and 2 skill writers lost in a session restart were re-run
> (2 agents at a time), the 24 earlier reports on `layout`/`render`/`mutate`/`save_file`/`set_setting` were
> regression-checked (19 fixed, 2 still open, 3 partial) and every new critical/major report was reproduced by an
> independent skeptic before fixing. Fixed: **PyMOL 3.1 undo bug** - once the undo history is active, `delete`
> + reloading the same object name leaves the live object unselectable after ~30 undoable commands (reproduced in
> plain GUI PyMOL too; headless sessions now keep undo disabled, the GUI bridge clears the undo cache whenever an
> agent command removed objects); headless command feedback (`Executive: RMSD = ...`) is written by PyMOL to the
> C-level stdout and is now captured per command; `render(width=0,height=0)` returned PyMOL's cached image (now
> the viewport size is passed explicitly); the licence banner an unlicensed/expired PyMOL burns into ray-traced
> frames is detected (gated on `pymol.licensing`) and excluded from `render`/`layout`/`compare_renders` with a
> `watermark` note; a single non-opaque pixel no longer flips the analysis into transparent mode; `layout` works
> with mesh/surface/map objects (coloured by name, per-item errors instead of a failed call); `scene` reports mesh
> colours and iso levels and survives a broken object; `changes` now include global settings, viewport, iso levels
> (PyMOL) and atom/cartoon style changes (ChimeraX); the `run` guard no longer refuses `rms`/`rms_cur`;
> `sequence` handles nucleotides and numbering ranges; `selection_info` keeps insertion codes; `residue_table`
> rejects invalid selections and leaves `ss` empty for non-polymer residues; `.pse` export with a bare `all` no
> longer writes an empty session; `set_setting` reads atom-level values back through `iterate`; `mutate` refuses
> `keep_original_as` names that already exist, restores the view on errors and undoes the wizard's side effects
> (lines, zeroed B-factors, `_pk*` selections); `events` pages oldest-first with `truncated`/`next_since` and
> carries error text; stale discovery files whose pid was reused are purged (process start time); fetched files
> go to `$MOLMCP_HOME/fetch` instead of the process cwd; ChimeraX `model_info` lists surface colours and
> transparency and the command echo is stripped even when ChimeraX normalises the text. The 18-chain ID pass of
> the earlier report now takes 1.2 s (3.7 s with occlusion). **Windows:** a GitHub Actions job on `windows-latest` now runs the installer, the 44 unit
> tests and the MCP stdio client end to end against `pymol-mcp`, which launches a headless open-source PyMOL on
> the runner (the stdio disconnect seen under Wine was a Wine artefact). ChimeraX on Windows remains untested
> (licence click-through). A second Windows job drives the **PyMOL GUI** (Qt window started by the server) through the
> bridge; it exposed two OpenGL-1.1 crashes (offscreen `draw`, `scene store` thumbnails) now avoided by a shader probe
> with a ray-tracer fallback and a scene-free ID pass.

## 1. Short answer

* **Reach is essentially complete for everything that has a command or a Python API.**  The `run` tool executes the
  full command language of each application (PyMOL: all 326 entries of `cmd.keyword`; ChimeraX: all 567 registered
  command names, 194 top-level words) and the `python` tool executes arbitrary Python inside the process (PyMOL:
  476 plain functions on `cmd` — 512 callables counting classes and `Shortcut` helpers — 206 of which have no
  command-line keyword; ChimeraX: the whole `chimerax.*` API through `session`).  Nothing that the applications can
  do non-interactively is blocked by molmcp.
* **What is not reachable is what is not programmable in the applications themselves:** mouse-driven operations
  (picking, dragging, map erasing, segmentation painting, marker placement by click), the *contents* of GUI panels
  and result tables, modal dialogs, VR/hardware devices, and screenshots of the application window (the `render`
  tools draw the 3D view only).  Section 4.3 and 5.3 list each item with its workaround.
* **Dedicated tools already exist for the things that benefit from structure:** state (`scene`, `object_info` /
  `model_info`, `selection_info`, `get_view`, `set_view` (PyMOL), `settings` (PyMOL)), verification (`render`,
  `layout`, `compare_renders`, `analyze_image`), activity (`events`, `log`), documentation (`help`, `commands`),
  lifecycle (`status`, `launch`, `connect`, `quit_*`), skills (`skills`, `skill`, `save_skill`, plus MCP resources
  and a `use_skill` prompt) and structured helpers (`measure`, `align`, `sequence`, `contacts`, `save_file`).
* **Defects found while auditing (section 6):** on ChimeraX 1.11.1 the `commands` tool and the "unknown command"
  branch of `help` fail with an `ImportError` (`registered_commands` moved to `chimerax.core.commands.cli`); the
  ChimeraX `align` tool raises `TypeError` for `method="align"` (its `matchmaker` branch was fixed while this audit
  was running and now returns RMSDs and atom counts, verified).  The dedicated `quit_*` tools do not confirm in code
  either: their descriptions tell the agent to ask the user first, the bridge op exits immediately.  Skill files:
  ChimeraX had 12 from the start and PyMOL only `publication-rendering` when the audit began; 11 further PyMOL files
  landed while it ran, so both apps now list 12 built-ins plus the shared one.  None of the 25 bodies was reviewed
  for command accuracy, ChimeraX still lacks the ligand-site skill that both servers' instructions advertise, and
  PyMOL has no mutagenesis or AlphaFold/pLDDT skill.
* **The biggest remaining value is not more reach but better structure and knowledge:** JSON return from ChimeraX
  `info`/`measure` commands (ChimeraX 1.11.1 already supports `run(..., return_json=True)`, verified), a handful of
  structured extraction tools (per-residue tables, mutation, map levels, alignment pairs, job waiting), a safety
  guard for destructive commands, and a review of the skill bodies.  Section 8 ranks these.

## 2. Method

**PyMOL.**  A headless script (`pymol -cq`) imported `pymol.cmd`, listed `cmd.keyword` (the command-line table,
326 names) and grouped the names by the module that defines the implementing function (`fn.__module__`, 32
modules), then listed every plain function on `cmd` (476; 512 callables when classes and `Shortcut` helpers are
counted) and subtracted the keyword table to find the API-only functions (206).  Representative commands of each area were then exercised headlessly to confirm they work through
the same `cmd` object the bridge uses (fab/peptide building, distances, SASA, mutagenesis wizard via API, movie
`mset`/`mview`, maps via `map_new` + `isomesh`, scenes, exports via `get_str` for pdb/cif/mol/sdf/mol2/xyz/pqr,
`get_povray`, session save).

**ChimeraX.**  The command documentation is not where the task text says: there is no
`Contents/Resources/docs/user/commands/index.html` in 1.11.1.  The user guide lives in
`/Applications/ChimeraX-1.11.1.app/Contents/share/docs/user/`; its `index.html` carries the categorised list of
all commands and tools, and `commands/` holds 145 HTML files (136 command pages plus 9 reference pages:
`atomspec`, `atomspec-diffsum`, `colornames`, `colortables`, `palettes`, `pointspec`, `seqspec`, `symbols`,
`usageconventions`); `tools/` holds 79 pages (71 tool pages plus toolbar/icon pages).  Titles of all of them were
extracted and the index text was dumped.  A `--nogui --exit --script` run (not the GUI) listed the registered
commands from `chimerax.core.commands.cli.registered_commands(multiword=True)`: 567 names (566 before `agent name`
was added), 194 top-level words including the 27 `~` negations and molmcp's own `agent`, `claude`, `codex`.  The bridge's own `ops.py` functions
were then called directly in that headless session (`op_run`, `op_help`, `op_commands`, `op_scene`,
`op_selection_info`) and the `CX_*` / `PYMOL_*` code templates of `extra_tools.py` were extracted with `ast` and
executed exactly as the tools send them, on two copies of PyMOL's bundled `1tii.pdb`.

**molmcp.**  The tool surface was taken from `molmcp/pymol_server/server.py`, `molmcp/chimerax_server/server.py`,
both `extra_tools.py`, `common/server_common.py`, `common/skills.py`; the bridge ops from
`inapp/pymol/molmcp_pymol_bridge/__init__.py` and `inapp/chimerax/.../agentbridge/ops.py`; the in-app chat from
`inapp/shared/agentcli.py`, `inapp/shared/agentchat_ui.py`, `chatpanel.py`, `tool.py`, `cmd.py`; registration from
`molmcp/install.py` and `install.py`.  No tool is named below that is not defined in those files.

**Reach legend used in the tables**

| code | meaning |
|---|---|
| `run` | reachable with the application's own command language through the `run` tool (per-command ok/output/error + `changes`) |
| `python` | reachable with the application's Python API through the `python` tool (set `result` to return JSON) |
| tool `name` | a dedicated structured MCP tool exists |
| chat | the in-app chat uses exactly the same tools (restrictions in 3.3) |
| GUI-only | no programmatic path; workaround given |

## 3. What exists today

### 3.1 MCP tool inventory (both servers unless noted)

| tool | bridge op | PyMOL | ChimeraX | notes |
|---|---|---|---|---|
| `status` | `ping` + discovery files | yes | yes | lists every open window with pid, user-given name (`agent_name …` in PyMOL, `agent name …` in ChimeraX, or `MOLMCP_<APP>_NAME`), loaded objects/models, whether it has focus, last activity; renders dir, `main_thread_busy` |
| `launch` | – | `gui` or `headless` (library mode via bundled Python) | `gui` or `nogui` (`--offscreen` added on Linux) | ChimeraX nogui cannot render on macOS |
| `connect` | – | yes | yes | pick a window by pid, port or name; without arguments the focused window, else the most recently used; `MOLMCP_<APP>_PID` pins the in-app chat; responses carry a one-line window note when several windows are open |
| `run` | `run` | yes | yes | output trimmed to 6000 chars per command; ChimeraX also returns the command's Python `value` |
| `python` | `python` | `cmd`, `pymol`, `stored` | `session`, `run(text)` | stdout + log captured; result > 60 000 chars is replaced by a message |
| `scene` | `scene` | objects, groups, selections, view, background, 39 curated settings, state/frame, scenes, wizard | models (atoms, chains, shown atoms/ribbons, styles, categories, surfaces, pseudobonds, Volume grid/levels/stats), selection, camera, clip planes, lighting, material, silhouettes | `detail="full"` adds per-chain details |
| `object_info` / `model_info` | `object_info` / `model_info` | yes | yes | full detail for one item |
| `selection_info` | `selection_info` | yes | yes (atom spec, default `sel`) | counts, residue ranges, names, elements, extent, centre |
| `get_view` | `get_view` | 18-value matrix decoded | position, direction, up, 3x4 matrix, fov, cofr, clip planes | |
| `set_view` | `set_view` | yes | **no** | ChimeraX: use `run` with `view matrix camera …` or named views |
| `render` | `render` | draw or `ray`, transparent | supersample, transparent | numerical analysis; PNG saved under `~/.molmcp/renders`; `return_image=True` sends the PNG |
| `layout` | `render_ids` | by object / chain / items | by model / chain / items | ID pass, occlusion option; state restored afterwards |
| `compare_renders`, `analyze_image` | – (server side) | yes | yes | pure numpy |
| `events`, `log` | `events`, `log` | feedback tee + fingerprint diff | log capture + triggers (`command started/finished/failed`, `add/remove models`, `selection changed`) | |
| `help` | `help` | `cmd.keyword[...]` docstring | `usage()` text | ChimeraX: fails for unknown names (section 6) |
| `commands` | `commands` | yes | **broken on 1.11.1** (section 6) | |
| `settings` | `settings` | yes (global or per object) | – | ChimeraX settings are in `scene.lighting` / `scene.camera` or via `python` |
| `quit_pymol` / `quit_chimerax` | `quit` | yes | yes | no confirmation in code: the tool description tells the agent to ask the user first; the op stops the bridge and exits at once (`cmd.quit()` / `exit`) |
| `skills`, `skill`, `save_skill` | – (server side files) | yes | yes | built-ins in `molmcp/skills/{shared,<app>}/*.md`, user files in `~/.molmcp/skills/<app>/` |
| `measure` | `python` | distance, angle, dihedral, extent/center, rmsd (in place), count | same plus `sasa` | verified |
| `align` | `python` | `align`, `super`, `cealign`, `pair_fit` (verified) | `matchmaker` (verified: full/final RMSD and atom counts), `align` (**raises**) | section 6 |
| `sequence` | `python` | per chain, one-letter + numbering | per chain + description | verified |
| `contacts` | `python` | residue pairs within cutoff, `polar_only` | same | verified (PyMOL: 36 residue pairs between 1tii chains A/C) |
| `save_file` | `python` | `cmd.save` (session, coordinates, images, meshes) | `save` command (session, coordinates, images, glb/stl/obj, maps) | verified (.pse, .cxs) |
| MCP resources `molmcp://<app>/skills`, `molmcp://<app>/skills/{name}`; prompt `use_skill` | – | yes | yes | registered through `MCPServer.resource` / `.prompt` (both exist in the installed SDK) |

Bridge ops without an MCP tool: `agent_ask` (lets a client trigger the in-app Claude/Codex run) – internal.

### 3.2 Properties of the generic path that limit coverage in practice

* **Everything runs on the application's main thread** (`cmd._call_in_gui_thread` / `session.ui.thread_safe`).
  A long command freezes the GUI until it returns, and while the application shows a modal dialog or is busy the
  bridge call times out with "is the app busy or showing a dialog?".  Timeouts: `run`, `python`, `render` 600 s,
  `layout` 900 s, other ops 120 s.  Long-running ChimeraX jobs (`blastprotein`, `alphafold predict`, `modeller`,
  `boltz`) are asynchronous inside ChimeraX, so `run` returns after submission; the agent must poll `events`,
  `scene` or `run taskman list`.
* **`changes` only sees what the fingerprint covers.**  PyMOL: object list, enabled flags, per-object representation
  bits, atom colours, selections, view, state/frame, scenes.  ChimeraX: model list/display, atom counts, shown
  atoms/ribbons, selected atoms, atom/ribbon colour hashes (plus the single colour of surfaces and other
  non-atomic models), camera, window size, background.  It does **not** detect setting changes (`set
  cartoon_transparency`, `lighting soft`), label *text* changes (showing labels is detected: as a representation
  change in PyMOL, as a new label model in ChimeraX), map level changes or per-vertex surface colouring (`color
  electrostatic`, `set surface_color`).  `compare_renders` or `settings` / `scene.lighting` are the way to confirm those.
* **Output size.**  `run` output is trimmed to 6000 characters per command (head and tail kept), `python` results
  to 60 000 characters.  Large listings (`info residues #1`, `iterate all, ...`) must be written to a file by the
  agent (via `python`) or summarised inside the application.
* **Headless differences.**  PyMOL headless (`launch mode="headless"`) is PyMOL as a library: no window, no Qt
  panels, `ray` renders only; `window`, `viewport`, `full_screen`, `volume_panel`, wizards with Qt panels are
  no-ops or print warnings.  ChimeraX `--nogui` has no tool panels; rendering only with `--offscreen` on Linux.

### 3.3 In-app chat (`claude …` / `codex …` inside the viewer)

The chat panel (PyMOL: dock widget, Plugin menu entry, `agent_chat` command (`agent_button` re-inserts the button), and an **Agent** button inserted into
the top toolbar next to **Builder** — the code uses `window.topToolBar.builderButton`, `TopToolBarButton` and
`_create_vert_line()`, all present in PyMOL 3.1.5's `pmg_qt/top_toolbar/top_panel_dialog.py`; ChimeraX: *Tools ▸
General ▸ Agent Chat*, `agent chat`, and a toolbar tab **Agent** declared through `Provider :: … :: toolbar`
classifiers whose syntax matches ChimeraX's own toolbar bundles) runs the user's own CLI non-interactively:

| | Claude Code | Codex |
|---|---|---|
| command | `claude -p <prompt> --output-format stream-json --verbose --include-partial-messages --allowedTools mcp__<app> --append-system-prompt <context> [--model m] [--effort e] [--resume id]` | `codex exec --json --approve-for-me --skip-git-repo-check [-m model] [-c model_reasoning_effort="e"] [resume id] <context + prompt>` |
| tools the agent may use | only the `pymol` / `chimerax` MCP server tools are pre-approved (`allow_shell=True` would add `Bash,Edit,Write`, but no caller sets it) | all MCP servers from `~/.codex/config.toml` plus shell commands under Codex's workspace-write sandbox with automatic review |
| file access | through the `python` tool only (it runs inside the viewer process with the user's permissions) | shell + `python` tool |
| skills | `skills` / `skill` are MCP tools, so they are always allowed; whether a `-p` run can invoke Claude Code's own `Skill` tool or MCP prompts (`/mcp__pymol__use_skill`) without listing them in `--allowedTools` was **not verified** here | molmcp skills via the MCP tools; Codex support for MCP prompts/resources **not verified** |
| images | `render return_image=True` returns the PNG; Claude Code can look at it | shown as `[image]` in the panel; Codex handling of MCP image content not verified |
| model / effort | `/model` menu and slash command; persisted per backend in `~/.molmcp/agent_settings.json` | same |

Consequences for coverage: the chat reaches everything the terminal agent reaches, *except* that in-app Claude
cannot read the user's files or run shell commands unless it does so through `python` inside the viewer.  Note the
reverse as well: the `--allowedTools mcp__<app>` restriction is **not a sandbox** — `run system ls ~` (PyMOL),
`run pip install …` (PyMOL's `pip`/`conda` commands), `run runscript …` (ChimeraX) and the `python` tool all give the
agent the user's full file-system and shell access from inside the application.

## 4. PyMOL

### 4.1 Coverage by area (326 `cmd.keyword` entries grouped by defining module)

| area (module) | n | representative commands | reach today | structured state today | would a dedicated tool or skill materially help? |
|---|---|---|---|---|---|
| importing | 7 | `load`, `fetch`, `load_traj`, `loadall`, `load_mtz`, `load_embedded`, `space` | `run` (`fetch 1abc, async=0`); API-only `read_pdbstr`, `load_coords`, `load_cgo`, `load_map`, `load_brick`, `load_callback` via `python` | `changes` reports `objects_added`; `scene` shows atoms/states/chains | no new tool; a skill line on `async=0`, `load_traj` state ranges and `fetch type=` suffices |
| exporting | 5 | `save`, `multisave`, `multifilesave`, `png`, `cache` | `run`; tool `save_file`; API-only `get_pdbstr`, `get_fastastr`, `get_str` (pdb/cif/mol/sdf/mol2/xyz/pqr, verified), `get_session`, `get_povray`, `get_gltf(filename)`, `get_collada`, `get_vrml`, `get_mtl_obj` via `python` | file path + size returned | covered |
| viewing | 46 | `show`/`hide`/`as`, `cartoon`, `color`, `spectrum`, `set_color`, `bg_color`, `label`, `zoom`/`orient`/`center`/`clip`/`turn`/`move`, `view`, `scene`, `scene_order`, `stereo`, `ray`, `draw`, `capture`, `rock`, `window`, `viewport`, `full_screen`, `rebuild`, `refresh`, `recolor`, `color_deep`, `load_png`, `meter_reset` | `run`; tools `render`, `layout`, `compare_renders`, `get_view`, `set_view` | reps, colours, view, scenes, background in `scene`; render analysis | **skill** "publication rendering" (ray settings, `ray_trace_mode`, lighting, `antialias`, transparent background, DPI) is high value: the knowledge, not the reach, is missing.  `window`/`viewport`/`full_screen` are GUI-window operations (no-ops headless) |
| creating | 20 | `create`, `extract`, `copy`, `group`/`ungroup`, `pseudoatom`, `fragment`, `symexp`, `map_new`, `isomesh`/`isosurface`/`isodot`/`isolevel`, `slice_new`, `volume`, `gradient`, `ramp_new`/`ramp_update`, `curve_new`, `join_states` | `run` (verified `map_new gaussian` + `isomesh`, `pseudoatom`, `load_cgo`) | map/mesh objects appear with type and setting overrides, but **no isolevel, map statistics or histogram** (`get_volume_histogram`, `get_volume_field` are `python`) | **tool `map_info`** (levels of each mesh/surface, map min/max/mean/sd, histogram) — medium value for density work |
| editing | 65 | `alter`/`iterate`/`alter_state`/`iterate_state`, `attach`, `bond`/`unbond`/`fuse`, `h_add`/`h_fill`/`h_fix`, `remove`, `rename`, `set_name`/`set_title`, `dss`, `rotate`/`translate`, `matrix_copy`/`matrix_reset`/`matrix_transfer`, `sculpt_*`, `set_dihedral`/`torsion`, `split_states`/`split_chains`, `symmetry_copy`/`set_symmetry`, `undo`/`redo`, `map_double`/`map_halve`/`map_trim`/`map_set`, `fix_chemistry`, `valence`, `protect`/`deprotect`/`flag`, `pbc_wrap`/`pbc_unwrap`, `mse2met`, `uniquify`, `update`, `smooth`, `sort`, `vdw_fit`, `reference`, `edit`/`unpick`/`remove_picked`/`drag`/`cycle_valence`/`invert`/`replace`, `look_at`, `alphatoall`, `copy_to` | `run`; pick-based editing (`attach`, `replace`, `cycle_valence`, `invert`, `remove_picked`) works after setting picks programmatically with `edit (sel1), (sel2)`; `undo`/`redo` present in 3.1 | atom counts and colours in `changes` | **tool `atom_table`/`residue_table`** (JSON from `iterate` for a selection: resn/resi/chain/name/b/q/ss/colour/formal charge, capped rows) — high value, the most common `python` snippet today.  **tool `mutate`** via the mutagenesis wizard API (see wizarding) |
| editor | 2 | `fab`, `fnab` | `run` (verified `fab ACDEFGHIK, ss=1`); `editor.attach_amino_acid`, `editor.build_peptide` via `python` | | covered; part of a "building" skill |
| fitting | 12 | `align`, `super`, `cealign`, `fit`, `pair_fit`, `rms`, `rms_cur`, `intra_fit`/`intra_rms`/`intra_rms_cur`, `extra_fit`, `alignto` | `run`; tool `align` (4 methods verified), `measure kind="rmsd"` | RMSD, atom counts, cycles, score, residues aligned | **tool `alignment_info`** (residue pairs of an alignment object via `get_raw_alignment`) would complete it — medium |
| querying | 26 | `distance`, `angle`, `dihedral`, `get_distance`/`get_angle`/`get_dihedral`, `get_area`, `get_extent`, `centerofmass`, `count_atoms`/`count_states`/`count_frames`/`count_discrete`, `get_chains`, `get_symmetry`, `get_title`/`get_type`/`get_version`, `identify`, `index`, `id_atom`, `overlap`, `phi_psi`, `pi_interactions`, `get_position`, `get_renderer` | `run`; tools `measure`, `contacts`; API-only `get_model`, `get_coords`, `get_coordset`, `get_phipsi`, `find_pairs`, `get_object_matrix`, `get_bonds` via `python` | | add `kind="sasa"` to PyMOL `measure` (`get_area` with `dot_solvent=1`, verified 1189 Å² for the test peptide) for parity with ChimeraX — trivial |
| selecting | 4 | `select`, `deselect`, `indicate`, `pop` | `run`; tool `selection_info` | selection names and atom counts in `scene` | covered; interactive picking is GUI-only (4.3) |
| setting | 7 | `set`, `get`, `unset`, `set_bond`, `get_bond`, `unset_bond`, `unset_deep` | `run`; tool `settings` (read, global or per object) | curated list in `scene.settings` | covered; a *write* path exists through `run set …` |
| controlling | 8 | `button`, `config_mouse`, `mouse`, `set_key`, `edit_mode`, `mask`/`unmask`, `order` | `run` | – | low value for an agent (configures the user's mouse/keys) |
| moving (movies) | 24 | `mset`, `mview`, `madd`/`mappend`/`minsert`/`mdelete`/`mcopy`/`mmove`, `mdo`, `mmatrix`, `mdump`, `frame`/`forward`/`backward`/`rewind`/`ending`/`middle`, `mplay`/`mstop`/`mtoggle`, `mpng`, `accept`/`decline` | `run` (verified `mset 1 x30`, `mview store`) | `scene.frames`, `scene.frame`, `scene.state` | **skill "movies"** (keyframes with `mview`, `set ray_trace_frames`, `mpng` + ffmpeg, scene transitions) — high value; encoding with `movie.produce` was not tested here |
| movie (`pymol.movie`) | 12 | `movie.produce`, `movie.load`, `movie.roll`/`rock`/`nutate`/`screw`/`sweep`/`zoom`/`tdroll`/`pause`, `util.mrock`/`mroll` | `run` | | same skill |
| morphing | 1 | `morph` | `run` | morph object appears as multi-state object | covered |
| wizarding | 3 | `wizard`, `replace_wizard`, `refresh_wizard` (30 wizard modules: mutagenesis, nucmutagenesis, measurement, pair_fit, density, sculpting, label, charge, filter, distance, box, annotation, demo, …) | `run wizard mutagenesis` opens the panel (GUI); the wizard *logic* is reachable with `python`: `cmd.wizard("mutagenesis"); w = cmd.get_wizard(); w.set_mode("ALA"); w.do_select("sele"); w.apply()` — **verified headless** (residue 3 became ALA; "no rotamers found in library" is normal for ALA) | `scene.wizard` names the active wizard | **tool `mutate`** (mode, selection, rotamer choice, clash report) and a "mutagenesis" skill — high value for protein design; wizard *buttons* are GUI-only |
| properties | 4 | `get_property`, `set_property`, `set_atom_property`, `get_property_list` | `run` / `python` | | covered |
| commanding | 11 | `alias`, `cls`, `delete`, `delete_states`, `log`/`log_open`/`log_close`, `quit`, `reinitialize`, `resume`, `splash` | `run` | | **safety**: `quit` and `reinitialize` through `run` exit / reset immediately (as does `quit_pymol`: no confirmation in code, only its description asks); see section 8 item 6 |
| externing | 7 | `cd`, `pwd`, `ls`, `dir`, `system`, `pip`, `conda` | `run` | | **safety**: `system` is a shell, `pip`/`conda` install into PyMOL's Python |
| helping | 20 | `help`, `help_setting`, `api`, plus the Python pass-through keywords (`if`, `for`, `def`, `import`, `python`, `embed`, `skip`, `assert`, …); `cmd.commands()` has no keyword | tool `help`, `commands`; Python via `python` | | covered |
| parsing | 3 | `run`, `spawn`, `fork` (run `.py`/`.pml` scripts) | `run` (`@file.pml`, `run file.py`) | | covered; in-app Claude writes script files through `python` |
| util | 16 | `util.cbc`/`cbaw`/`cbag`…, `util.chainbow`, `util.rainbow`, `util.cnc`, `util.ss`, `get_sasa_relative` | `run` | | covered |
| colorramping | 3 | `volume_color`, `volume_ramp_new`, `volume_panel` | `run` (`volume_panel` opens a GUI panel only) | | part of `map_info` / maps skill |
| computing / stereochemistry / experimenting / diagnosing / feedback / undo | 12 | `clean`, `assign_stereo`, `check`, `focal_blur`, `desaturate`, `callout`, `dump`, `mem`, `spheroid`, `diagnostics`, `feedback`, `undo_status` | `run` | | covered |
| internal / keyboard / misc | 8 | `_alt`, `_ctrl`, `_ctsh`, `_special`, `_quit`, `editing_ring`, `print` (module `pymol`), `obscure` (`epymol.comm.obscure`) | n/a | | n/a |

### 4.2 API-only functionality (206 `cmd` functions without a command keyword) — all reachable with `python`

Groups worth knowing: data access (`get_model`, `get_coords`, `get_coordset`, `get_pdbstr`, `get_fastastr`,
`get_str`, `get_bytes`, `get_session`, `get_names`, `get_object_list`, `get_object_matrix`, `get_object_ttt`,
`get_phipsi`, `get_raw_alignment`, `get_bonds`, `get_volume_field`, `get_volume_histogram`, `get_color_indices`,
`get_color_tuple`, `get_setting_*`, `get_scene_list`, `get_vis`, `get_wizard`); loaders (`read_pdbstr`,
`read_molstr`, `read_sdfstr`, `read_xplorstr`, `load_cgo`, `load_coords`, `load_coordset`, `load_map`,
`load_brick`, `load_raw`, `load_callback`); transforms (`transform_object`, `transform_selection`, `set_object_ttt`,
`translate_atom`, `set_object_color`, `set_vis`); undo control (`undo_*`); movie-maker timeline API (33
`timeline_*` functions of PyMOL 3's Movie Maker: keyframes, tracks, compositions — undocumented but callable); the
plugin system (`pymol.plugins.initialize/get_startup_path/set_startup_path/autoload`).

Plugins bundled with this PyMOL (`share/pymol/data/startup`): `align_gui`, `apbs_gui`, `excelexporter`,
`lightingsettings_gui`, `morph_gui`.  **APBS electrostatics** (`apbs_gui`, with the `apbs` binary in `Contents/bin`)
has a GUI-only dialog but the work is done by plain functions callable from `python` —
`apbs_gui.electrostatics.map_new_apbs(name, selection, grid, buffer, …)`, `apbs_gui.creating.pdb2pqr(name, selection,
ff, …)` and `apbs_gui.creating.prepwizard(name, selection, options, …)` (verified in the source; `import apbs_gui`
works once PyMOL's plugin system has initialised, i.e. in the GUI; headless needs the startup directory on
`sys.path`).  Added to the application's `pmg_tk/startup` directory after installation (not part of the PyMOL
distribution): **Caver3**, **ring_pymol** (GUI dialogs with Python back-ends) and a third-party
`pymol-mcp-socket-plugin` (an unrelated socket-based "PyMOL MCP" plugin, not part of molmcp).  All nine are registered
with autoload on (`pymol.plugins.initialize` lists them), so the socket plugin is loaded at every GUI start and may
open its own listener; it does not interfere with molmcp's HTTP bridge.  molmcp's own plugin lives in
`~/.pymol/startup/molmcp_pymol_bridge/` (the plugin path recorded in `~/.pymolpluginsrc.py`) and is byte-identical to
the repository copy.  (The stray `io.mc` file at the repository root is an APBS "MC-shell I/O capture" written
because APBS was run with the repository as working directory, and `1ubi.cif`, `2o6v.cif` there are test downloads —
`1ubq.cif` had already been removed at the second pass; none is part of molmcp.)

### 4.3 Not reachable in PyMOL, and workarounds

| not reachable | why | workaround |
|---|---|---|
| Mouse picking and dragging (pk1–pk4 picks, `drag`, sculpt dragging, rotating bonds by mouse, moving objects by mouse) | needs clicks in the 3D view | `edit (sel1), (sel2), (sel3), (sel4)` sets the same picks; `translate`/`rotate`/`set_dihedral`/`torsion`/`transform_selection` move things numerically; `sculpt_*` works without the mouse |
| Builder panel (clicking fragments into the scene) | GUI | `fragment`, `attach`, `fab`, `fnab`, `editor.attach_amino_acid`, `editor.build_peptide` (`python`), `h_add`, `bond`, `valence` |
| Wizard *panels* (buttons of Mutagenesis, Measurement, Density, Pair Fitting, Sculpting, Label, Charge, Filter, …) | GUI | the wizard objects' methods via `python` (verified for Mutagenesis); measurements via `distance`/`angle`/`dihedral`; density via `isomesh`/`isolevel`/`map_*`; pair fitting via `pair_fit` |
| Contents of panels and dialogs: Settings editor, Preferences, Plugin manager, APBS/Caver dialogs, Volume panel histogram, Movie panel / timeline, Properties inspector, Sequence viewer, Scene panel buttons | GUI state | every value they show maps to `set`/`get` (tool `settings`), `pymol.plugins` API, the plugin back-end functions, `get_volume_histogram`, `timeline_*`/`mview`, `get_property*`, `select` by residue, `scene` command; the *selection made in the sequence viewer* is just the `sele` selection (`selection_info sele`) |
| A screenshot of the PyMOL window (panels, menus, dialogs) | `render` draws the 3D view only | a terminal agent with shell access can take an OS screenshot (`screencapture` on macOS); the in-app Claude chat cannot |
| Interaction while a modal dialog is open (file dialogs, confirmation prompts) | main thread blocked | bridge calls time out; `status` shows `main_thread_busy`; the user must close the dialog.  Never needed for file I/O: `load`/`save` take paths |
| `window`, `viewport`, `full_screen`, `volume_panel`, Qt-based wizards in headless mode | no Qt window | use the GUI mode, or `ray`/`png` with explicit width/height |
| Movie *encoding* (`movie.produce`) | needs an encoder; not tested here | `mpng` writes frames; encode externally (terminal agent) |
| Confirmation before destructive commands | `run quit`, `run reinitialize`, `run delete all`, `run system …` execute immediately | nothing confirms in code: `quit_pymol` exits at once too (its description asks the agent to check with the user); see section 8 item 6 |

## 5. ChimeraX

### 5.1 Coverage by area (categories from the user-guide index; 136 command pages, 567 registered names)

| area | representative commands | reach today | structured state today | would a dedicated tool or skill materially help? |
|---|---|---|---|---|
| open / save / close / scripts | `open` (files, PDB/AlphaFold/EMDB fetch, `.cxc`/`.py` scripts), `save` (images, sessions, maps, coordinates, sequences, glTF/STL/OBJ/X3D…), `close`, `runscript`, `cd`, `pwd`, `log save`, `snapshot` | `run`; tool `save_file` (verified `.cxs`) | `changes`: `models_added/removed`; `scene` lists models | covered |
| display and style | `show`/`hide`, `style`, `cartoon`/`ribbon`/`worm`, `surface`, `size`, `transparency`, `color`/`rainbow`/`colordef`/`palette`, `nucleotides`, `preset`, `graphics`, `lighting`, `material`, `set bgColor`, `windowsize`, `camera`, `clip`, `view`, `turn`/`move`/`zoom`/`roll`/`rock`/`wobble`/`fly`, `cofr`, `tile`, `label`, `2dlabels`, `key`, `scalebar`, `struts`, `smoothlines`, `aniso`, `hkcage`, `shape` | `run`; tools `render`, `layout`, `compare_renders`, `get_view` | atoms/ribbons shown, styles, colours, camera, clip planes, lighting, material, silhouettes, background in `scene` | **tool `set_view`** for parity with PyMOL (apply the 3x4 camera matrix from `get_view`, or a named view) — small; **skill** "publication rendering" (`lighting soft/full`, `graphics silhouettes`, `set bgColor`, `save … width … supersample 3 transparentBackground true`) — high value |
| selection and specification | `select` (+ `up`/`down`/`clear`), `name`, `zone`, `define`, `info selection`, `~select` | `run`; tool `selection_info` (any spec, default `sel`) | selection summary in `scene` | covered; mouse selection is GUI-only (5.3) |
| structure analysis | `hbonds`, `clashes`/`contacts`, `interfaces`, `crosslinks`, `distance`, `angle`, `torsion`, `measure` (area, volume, sasa, buriedarea, blob, center, inertia, length, rotation, symmetry, mapstats, correlation, convexity, …), `rmsd`, `dssp`, `chirality`, `altlocs`, `crystalcontacts`, `unitcell`, `sym`, `kvfinder`, `mutationscores`, `coulombic`, `mlp`, `bumps`, `getcrd`, `info` (`models`, `chains`, `residues`, `atoms`, `polymers`, `selection`, `distmat`, `bounds`, `atomattr`/`resattr`/`bondattr`, `atomcolor`/`rescolor`, `path`, `notify`) | `run`: results arrive as the **log text** of each command (captured, trimmed at 6000 chars) plus the command's Python return value (e.g. `measure area #1` → 313.65, verified); tools `measure` (distance/angle/dihedral/extent/rmsd/count/sasa, verified), `contacts` | pseudobond groups created by `hbonds`/`clashes`/`distance` appear in `scene` with counts | **JSON return for `run`**: ChimeraX 1.11.1's `run(session, text, return_json=True)` returns a `JSONResult` whose `.json_value` is structured (verified for `info models`, `info chains`: per-chain `chain_id`, `sequence`, residue list).  The bridge does not use it.  Adding `json=True` to the `run` tool (or an `info` tool) is the single most valuable ChimeraX addition |
| structure editing | `build` (start / modify / replace / join peptide / join bond / invert), `bond`/`~bond`, `pbond`, `delete`, `addh`, `addcharge`, `swapaa`, `swapna`, `renumber`, `changechains`, `combine`, `split`, `rename`, `setattr`, `defattr`, `dockprep`, `minimize`, `tug` (OpenMM), `torsion`, `altlocs`, `mcopy`, `undo`/`redo` | `run` | atom counts in `changes` | **tool `mutate`** (`swapaa` with rotamer criteria, returns chosen rotamer and clash count) — medium-high; Build Structure / Rotamers *dialogs* are GUI-only but every function has a command |
| alignment, superposition, sequences | `matchmaker`/`mmaker`, `align`, `morph`, `rmsd`, `sequence` (chain, associate, header, align, search), `mseries`, `coordset`, `blastprotein`, `foldseek`, `similarstructures` | `run`; tools `align` (`matchmaker` verified, `method="align"` **raises**, section 6), `sequence` (verified) | `matchmaker` logs RMSD; result dicts (`"full RMSD"`, `"final RMSD"`, matched `Atoms`) are returned to Python | fix `align`'s `align` branch; **tool `alignment_info`** (matched residue pairs from `"final match atoms"`/`"final ref atoms"`, or `session.alignments`) — medium |
| maps and volumes | `volume` (level, style, step, region, threshold, gaussian, resample, mask, zone, erase, add/subtract/multiply, morph, splitbyzone, …), `molmap`, `fitmap`, `segmentation`/`segger`/`segmentations`, `vseries`, `measure mapstats`, `surface dust`/`zone`, `color zone`/`sample`/`electrostatic`, `topography`, `resfit`, `marker`, `bumps` | `run` (`volume erase` exists as a command, verified via `help`) | `scene` reports grid size, voxel size, origin, isosurface levels/colours/mesh, value range, min/max/mean/sd per Volume | **skill "cryo-EM / density maps"** (open, `volume level`, `fitmap`, `volume zone`, `surface dust`, `color zone`, `molmap` for comparison) — high value; state is already structured |
| predictions and external services | `alphafold` (fetch, match, predict, pae, contacts, dimers), `esmfold`, `boltz`, `modeller` (comparative, loops, refine, scores), `blastprotein`, `foldseek`, `similarstructures`, `taskman` | `run`; jobs run **in the background**, `run` returns after submission; results appear as new models (`events add_models`), log lines (`log`), and in GUI tables | | **tool `jobs` / `wait_for_jobs`** (poll `taskman` + model/log events until done, with timeout) — medium-high for prediction workflows; Modeller license key and Boltz/AlphaFold installs are one-time user actions (`boltz install`, `help modeller`) |
| movies and animation | `movie record`/`encode`/`stop`/`reset`, `crossfade`, `perframe`, `wait`, `roll`/`rock`/`turn … frames`, `coordset`, `morph`, `fly`, `scenes`, `vseries play`, `mseries` | `run` (ffmpeg is bundled; encoding not tested here) | | **skill "movies"** — high value |
| annotation | `label`, `2dlabels`, `key`, `scalebar` | `run` | labels are `ObjectLabels` models in `scene` | covered; placing by mouse is GUI-only |
| markers | `marker` (`marker #N position x,y,z` places one; subcommands `delete`, `link`, `segment`, `connected`, `fromMesh`, `change`) | `run` | `MarkerSet` models in `scene` | covered; mouse placement GUI-only |
| user interface, tools, preferences | `ui tool show/hide`, `tool show/hide`, `ui dockable`/`fullscreen`/`hideFloating`/`mousemode`/`statusbar`/`windowfill`, `functionkey`, `mousemode`, `buttonpanel`, `toolshed` (list/install/update), `alias`, `help`, `usage`, `version`, `registration status`, `exit`/`quit` | `run`; tools `help` (works for known names), `commands` (**broken**, section 6) | – | fix `commands`; the *contents* of tool panels are GUI-only (5.2) |
| Python and scripting | `runscript`, `open script.py`, `open script.cxc`, Shell tool (IPython) | tool `python`; `run open file.cxc` | | covered |
| remote control and devices | `remotecontrol rest/xmlrpc`, `mcp` (ChimeraX's own Claude Desktop bridge: `mcp setup`, `mcp start [port]`, `mcp info`, `mcp stop`; a REST server), `meeting`, `device vr`/`device xr`/`device snav`, `webcam`, `lookingglass` (both also as `device …`); *Send to Quest* is a tool without a command | `run` | | not useful to an agent; note that ChimeraX 1.11.1 ships its own `mcp` command (command execution over REST for Claude Desktop, no scene snapshots or render analysis); it uses a different port and transport than molmcp and the two were not tested side by side |
| medical imaging | `open` DICOM directories, `segmentations`, DICOM browser/metadata tools, `volume … orthoplanes xyz` and the Orthoplanes / Orthopick tools | `run` for commands; slice painting is mouse-driven | Volume state in `scene` | low priority for this project |

### 5.2 GUI tools (79 documentation pages) — what the agent can and cannot do with them

Every tool whose page names a command equivalent is covered by `run`: 2D Labels (`2dlabels`), Add Charges
(`addcharge`), Add Hydrogens (`addh`), Altloc Explorer (`altlocs`), Axes/Planes/Centroids (`define`), Blast Protein
(`blastprotein`), Boltz (`boltz`), Build Structure (`build`, `bond`, `torsion`, `swapaa`, `delete`), Cage Builder
(`sym`), Change Chain IDs (`changechains`), Clashes/Contacts (`clashes`, `contacts`), Color Actions (`color`), Color
Key (`key`), Color Zone (`color zone`, `volume splitbyzone`), Crystal Contacts (`crystalcontacts`), Distances
(`distance`), Dock Prep (`dockprep`), ESMFold/AlphaFold (`esmfold`, `alphafold`), Fit in Map (`fitmap`), Foldseek
(`foldseek`, `similarstructures`, `sequence search`), H-Bonds (`hbonds`), Hide Dust (`surface dust`), Map Eraser
(`volume erase`), Matchmaker (`matchmaker`), Measure and Color Blobs (`measure blob`), Measure Volume and Area
(`measure area/volume/sasa`), Modeller (`modeller comparative/loops/refine`), Render/Select by Attribute (`color
byattribute`, `size byattribute`, `cartoon byattribute`, `select … attribute`), Renumber (`renumber`), Rotamers
(`swapaa`), Scale Bar (`scalebar`), Scenes (`scenes`), Segment Map (`segger`, `segmentation`), Surface Zone (`surface
zone`), Unit Cell (`unitcell`), Volume Viewer (`volume`), Minimize (`minimize`), Model Panel (`info models`, `rename`,
`close`, `show`/`hide`), Log (`log`), Command Line (`run`), Shell (`python`), Task Manager (`taskman list/kill`), Side
View (`clip`, `view`), Toolbar (`ui tool show`, `mousemode`), Find Cavities (`kvfinder`), Angles/Torsions (`angle`,
`torsion`), Thermal Ellipsoids (`aniso`), Map Coordinates / Map Filter / Map Statistics (`volume … origin voxelSize`,
`volume gaussian/laplacian/…`, `measure mapstats`), Surface Color (`color electrostatic`, `color sample`, `coulombic`,
`mlp`), Marker Placement (`marker`), Sequence Viewer (`sequence chain`), Mutation Scores (`mutationscores`).

What remains GUI-only is the *state inside* a panel: result tables (Blast/Foldseek/Similar Structures hits, Rotamers
list, ViewDock table, Check Waters, Altloc Explorer, Mutation Scores plots, AlphaFold/ESMFold PAE plots), the Sequence
Viewer's region selection, Profile Grid, File History, the Selection Inspector, Registration, Orthopick/Orthoplanes
settings, Meeting/VR.  Workarounds: the commands log the same information (`log` tool), create models (`scene`),
or can save it (`blastprotein … log true` lists the hits in the log, `alphafold pae … plot false` loads the PAE data
without the plot; result tables such as Check Waters and Rotamers save as CSV/TSV only from their GUI context menu, not
through the `save` command); as a last
resort `python` can inspect tool instances (`[t for t in session.tools.list()]`) — an unsupported API surface.

### 5.3 Not reachable in ChimeraX, and workarounds

| not reachable | why | workaround |
|---|---|---|
| Mouse modes: rotate/translate by drag, ctrl-click selection, tug atoms, bond rotation by drag, place markers, erase map with the eraser sphere, segmentation painting, crop box, zone, pick blobs | mouse events | `turn`/`move`/`zoom`/`view`, `select <spec>`, `tug` command, `torsion`, `marker … position x,y,z`, `volume erase … center … radius …`, `segmentation`/`segger` commands, `volume region`, `zone`, `measure blob` |
| Contents of tool panels and result tables (5.2) | GUI widgets | log text, created models, saved files, `python` introspection |
| Modal prompts and dialogs (file browsers, "save changes?" style prompts) | main thread blocked | never needed for I/O (paths), bridge calls time out while one is open; the user closes it |
| Screenshot of the ChimeraX window | `render` draws the 3D view only (`view.image`) | OS screenshot from a terminal agent |
| Rendering in `--nogui` on macOS or Windows | no offscreen OpenGL | GUI mode, or Linux with `--offscreen` |
| Waiting for background jobs (`blastprotein`, `alphafold predict`, `modeller`, `boltz predict`) | `run` returns at submission | poll `events` (`add_models`), `log`, `run taskman list`; see section 8 item 8 |
| Listing commands / fuzzy help for unknown names | `commands` tool and the `help` fallback raise `ImportError` on 1.11.1 | `python`: `from chimerax.core.commands.cli import registered_commands; result = sorted(registered_commands(multiword=True))`; `help` works for exact names |
| Confirmation before destructive commands | `run exit`, `run close session`, `run close #*` execute immediately | nothing confirms in code: `quit_chimerax` exits at once too (its description asks the agent to check with the user); see section 8 item 6 |
| VR, Meeting, Space Navigator, webcam, Looking Glass, Quest | hardware | n/a |
| Preferences that exist only in the Settings dialog (startup commands, update checks, trackpad options) | dialog | mostly irrelevant to an agent; `set`, `graphics`, `ui`, `lighting` cover display preferences |

## 6. Defects found during the audit (verified)

1. **ChimeraX `commands` tool is broken on 1.11.1.**  `ops.op_commands` does `from chimerax.core.commands import
   registered_commands`; in 1.11.1 the function lives in `chimerax.core.commands.cli` (verified by calling
   `ops.op_commands(session, {"prefix": "col"})` in the installed bundle: `ImportError: cannot import name
   'registered_commands' from 'chimerax.core.commands'`).  `op_help` imports `usage` correctly from `cli` but its
   fallback for unknown names uses the same broken import, so `help("nosuchcmd")` returns an error instead of
   suggestions.  One-line fix: import from `chimerax.core.commands.cli` (with the old path as a fallback).
2. **ChimeraX `align` tool, `method="align"`.**  It runs `align #2@CA to #1@CA` and then `float(r[0])`; the
   command returns `(matched_atoms, matched_to_atoms, rmsd, full_rmsd, transform)`, so it raises `TypeError:
   float() argument must be a string or a real number, not 'Atoms'` (verified twice, before and after the
   concurrent edit of `extra_tools.py`).  Fix: `rmsd = r[2]`, `full_rmsd = r[3]`, pairs = `len(r[0])`.  The
   `matchmaker` branch originally looked for `full_rmsd`/`num_pairs` keys and returned only a raw `repr`; it was
   rewritten during the audit to scan the real keys (`"full RMSD"`, `"final RMSD"`, `"full match atoms"`, …) and
   now returns `full_rmsd`, `final_rmsd` and the four atom counts (verified on two copies of 1tii).
3. **Skills: PyMOL set was incomplete; bodies unreviewed.**  Both servers' instructions describe skills for
   publication rendering, movies, surfaces, alignment, maps, ligand sites.  When the audit began PyMOL had only
   `publication-rendering`; 11 further PyMOL files landed while it ran, and `skills()` now lists 13 entries on each
   server (12 app-specific plus the shared one, section 7).  What remains: ChimeraX has no ligand-site skill (PyMOL
   has `ligand-binding-site`), PyMOL has no mutagenesis or AlphaFold/pLDDT skill, and none of the 25 bodies has been
   checked against the command documentation.
4. **ChimeraX `info` results are text only** although the application can return JSON (section 5.1).
5. **Safety gap**: `run` executes `quit`/`exit`, `reinitialize`/`close session`, `delete all`/`close #*`, PyMOL
   `system`/`pip`/`conda` without confirmation, and the dedicated `quit_*` tools do not confirm in code either: their
   descriptions ("asks the user first") instruct the agent, while the `quit` op stops the bridge and exits at once.

## 7. Skills: what exists and how each CLI can use them

* **molmcp skills** (`common/skills.py`): Markdown files with front matter (`name`, `title`, `app`, `description`,
  `tags`) under `molmcp/skills/shared/` and `molmcp/skills/<app>/`; user overrides in `~/.molmcp/skills/<app>/`
  (or `MOLMCP_SKILLS_DIR`).  Exposed three ways: tools (`skills`, `skill`, `save_skill` — work with every MCP
  client, including the in-app chat whose Claude run only pre-approves MCP tools), MCP resources
  (`molmcp://<app>/skills`, `molmcp://<app>/skills/{name}`) and one generic MCP prompt (`use_skill(skill, task)`).
  The `/skills` slash command in the chat panel simply asks the agent to call the `skills` tool.
* **Claude Code** also has its own skills (`~/.claude/skills/<name>/SKILL.md`, project `.claude/skills/`, invoked
  with the `Skill` tool or `/name`) and lists MCP prompts as `/mcp__<server>__<prompt>` slash commands in
  interactive sessions.  Whether a `claude -p` run started from the viewer can use the `Skill` tool without adding
  it to `--allowedTools` was not verified; the MCP-tool route (`skill(name)`) is the one that is known to work in
  both the terminal and the in-app chat.
* **Codex** reads the `pymol`/`chimerax` MCP tools from `~/.codex/config.toml` (verified entries present) and can
  call `skills`/`skill`.  Codex's handling of MCP prompts and resources was not verified, which is another reason
  the skills are tools first.
* **Files present at the second pass** (all parse with `common/skills.py`; `skills()` lists 13 entries per app).
  Shared: `working-with-the-agent-tools`.  ChimeraX (12): `publication-rendering`, `representations-and-colouring`,
  `selection-and-zones`, `atom-spec-cheat-sheet`, `labels-keys-and-measurements`, `hbonds-contacts-clashes`,
  `structure-alignment`, `surfaces-and-electrostatics`, `maps-and-cryoem`, `movies`, `sessions-and-export`,
  `alphafold-esmfold-predictions`.  PyMOL (12; only `publication-rendering` existed when the audit began):
  `publication-rendering`, `representations-and-colouring`, `selection-cheat-sheet`, `labels-and-measurements`,
  `structure-alignment`, `surfaces-and-electrostatics`, `maps-and-density`, `movies-and-scenes`,
  `sessions-and-export`, `ligand-binding-site`, `styling-presets`, `sequence-view-and-stereo`.  No body was reviewed
  for command accuracy in this audit.
* Because the skill *content* is what agents lack, section 8 ranks reviewing these bodies above any new mechanism.
  Still missing: PyMOL `mutagenesis` (wizard API, section 4.1) and `alphafold` (colour by pLDDT with `spectrum b`,
  `fetch AF-…`), ChimeraX `ligand-binding-site` (the instructions of both servers advertise ligand sites).

## 8. The ten most valuable additions, ranked

1. **ChimeraX: structured `run` output (`json=True`) and the `commands`/`help` import fix.**  `info …`,
   `measure …`, `hbonds … log true` are the agent's primary data source; today they arrive as trimmed log text, and
   `run(..., return_json=True)` already exists in 1.11.1.  The import fix restores `commands` and fuzzy `help`.
2. **Fix the ChimeraX `align` tool's `align` branch** (section 6 item 2): a structured RMSD/pair count is exactly
   what the tool promises and `method="align"` still raises.
3. **Review the 25 skill bodies against the command docs and add the three missing topics** (section 7).  Reach is
   complete; what agents lack is *correct* non-obvious command sequences (`mview` keyframes, `ray` settings,
   `volume … level`, `fitmap`, `swapaa` criteria), and no skill body has been checked yet.
4. **`residue_table` / `atom_table`** (both apps): JSON rows for a selection (chain, resi, resn, ss, b/pLDDT, q,
   colour, shown reps), capped and pageable.  Replaces the most frequent ad-hoc `python` snippet and makes
   "colour by pLDDT, which residues are below 50" or "which residues lost their cartoon" one call.
5. **`mutate`** (PyMOL: mutagenesis wizard API, verified headless; ChimeraX: `swapaa … criteria`): returns the chosen
   rotamer, clash count and the resulting residue; a core protein-design action that is currently a multi-step
   `python` recipe.
6. **Safety guard in `run`**: refuse (or require `confirm=True` for) `quit`/`exit`, `reinitialize`/`close session`,
   `delete all`/`close #*`, PyMOL `system`/`pip`/`conda`, and `python` code that calls `os.remove`/`shutil.rmtree`
   outside the renders directory, routing quits to `quit_*` and giving `quit_*` a real `confirm=True` parameter
   (today only their description asks).  The chat's `--allowedTools mcp__<app>` is not a sandbox; the viewer process
   is.
7. **`map_info` for PyMOL** (isolevels per mesh/surface, map min/max/mean/sd via `get_volume_histogram`), mirroring
   what the ChimeraX `scene` already reports, plus a `set_isolevel` helper; density work is otherwise blind to levels.
8. **`jobs` / `wait_for_jobs` (ChimeraX)**: block (with timeout) until `blastprotein`, `alphafold predict`,
   `modeller`, `boltz` jobs finish, returning the models/files produced; today the agent must poll `events`/`taskman`.
9. **`set_view` for ChimeraX** (apply the matrix from `get_view`, or `view name`), so camera round-trips are
   symmetrical with PyMOL and figure reproduction does not depend on hand-typed `view matrix camera …` strings.
10. **`alignment_info`** (PyMOL `get_raw_alignment` of the alignment object; ChimeraX matchmaker's `"final match
    atoms"`/`"final ref atoms"` or `session.alignments`): the residue pairs behind an RMSD, needed for
    "which residues superpose / differ" questions.

Honourable mentions, lower value: `kind="sasa"` in PyMOL `measure` (one line); `gui_state` (which panels/docks are
open, open/close them with `ui tool show` / PyMOL `volume_panel`); registering one MCP prompt per skill so Claude
Code shows `/mcp__pymol__publication-render` style commands; `settings` write support (today via `run set …`).

## 9. Verification notes

Verified by execution during this audit: PyMOL keyword/module enumeration and API-only list; `fab`, `get_fastastr`,
`get_pdbstr`, `get_area` (molecular and SASA), `distance`/`get_distance`, mutagenesis wizard via API, `mset`/`mview`,
`get_session`, ray `png` bytes, `load_cgo`, `pseudoatom`, `map_new` + `isomesh`, `get_volume_histogram`, scenes,
`undo`/`redo` keywords, 33 `timeline_*` functions, 30 wizard modules, `get_sasa_relative`, `get_model`, `get_coords`,
`save` .pse/.cif, `get_str` formats, `get_povray`; all `PYMOL_*` templates of `extra_tools.py` (measure count/
distance/rmsd, align/super/cealign/pair_fit, sequence, contacts, save).  ChimeraX: registered command count,
`cli.registered_commands`/`cli.usage` import locations, `run()` signature with `return_json`, `JSONResult.json_value`
for `info models`/`info chains`, bridge ops `op_run` (value and log capture), `op_help` (known and unknown names),
`op_commands` failure, `op_scene`, `op_selection_info`; `CX_*` templates (measure count/sasa/distance OK, sequence OK,
contacts ran, save OK, `align` method `align` defective, `matchmaker` branch verified after its concurrent fix);
`volume erase`, `ui tool show`, `mcp` usage text; toolbar
`Provider` classifier syntax of ChimeraX's own bundles; PyMOL `pmg_qt` toolbar attributes used by the Agent button.
The second pass re-ran the ChimeraX console script (567 names; `align` branch still raising, `matchmaker` OK,
`measure sasa`/`count` OK, `JSONResult` for `info models`; the installed bundle's `op_commands` and the `op_help`
fallback raise the `ImportError`), diffed the installed copies against the repository (ChimeraX bundle in
`~/Library/Application Support/ChimeraX/1.11/lib/python/site-packages/chimerax/agentbridge/` and PyMOL plugin in
`~/.pymol/startup/molmcp_pymol_bridge/`: identical to the working tree), listed both servers through the MCP SDK (28
PyMOL tools, 26 ChimeraX tools, resource `molmcp://<app>/skills`, template `molmcp://<app>/skills/{name}`, prompt
`use_skill`), parsed the skill index (13 entries per app), checked every PyMOL name cited in section 4 against
`cmd.keyword`/`dir(cmd)` and every ChimeraX name cited in section 5 against the registered-command list, and checked
the CLI flags in `claude --help` / `codex exec --help` (`--include-partial-messages`, `--effort`,
`--append-system-prompt`, `--allowedTools`, `--resume`; `--json`, `--approve-for-me` = "route approval requests
through automatic review using the workspace-write sandbox", `--skip-git-repo-check`, `exec resume [SESSION_ID]
[PROMPT]`).

Not verified (no GUI was launched, no network, no model calls): behaviour of the chat panel, `/model`, the
toolbar buttons and the new window naming / focus-based `connect` selection at runtime; `claude -p` access to the `Skill` tool and MCP prompts; Codex handling of MCP prompts,
resources and image content; movie encoding (`movie.produce`, `movie encode`); `fetch`/`open <id>` network loads;
co-existence of molmcp with ChimeraX's built-in `mcp` REST server and with the third-party `pymol-mcp-socket-plugin`
found in PyMOL's startup directory; Windows and Linux behaviour (see the README matrix).
