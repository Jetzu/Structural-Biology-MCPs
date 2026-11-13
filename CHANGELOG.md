# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

- README rewritten around a gallery of PyMOL and ChimeraX renders made through the servers, each with what the
  agent got back instead of a picture; reference material moved to `docs/detailed.md`, the in-app chat to
  `docs/agent-chat.md`; `examples/make_gallery.py` regenerates the images, `examples/prompts.md` lists prompts.
- Installer detects which viewers (PyMOL, ChimeraX) and AI clients (Claude Code, Codex, Claude Desktop) are
  installed and sets up only those; `--pymol`, `--chimerax`, `--claude`, `--codex`, `--claude-desktop` narrow the
  choice, `--no-<name>` skips one.
- PyMOL GUI renders and ID passes work on OpenGL contexts without shader support (VMs, remote desktops, CI): the
  bridge falls back to the ray tracer and saves and restores state without scenes.
- CI on GitHub Actions: Linux unit tests; Windows installer, unit tests, headless PyMOL end-to-end run and
  ChimeraX server checks; a Windows job that drives the PyMOL GUI.

## 0.1.0 - 2026-11-07

First release: `pymol-mcp` and `chimerax-mcp`, MCP servers that give Claude Code, Codex and other MCP clients a
live connection to PyMOL and UCSF ChimeraX.

### Added
- In-app bridges (PyMOL plugin, ChimeraX bundle) that start with the application and serve commands over an
  authenticated localhost connection on the application's main thread.
- Scene snapshots, per-command change lists and an event stream of GUI activity.
- Render analysis without a vision model (coverage, framing, clipped edges, named colours, contrast, ASCII map),
  ID-pass layout with screen share, 2D contacts and occlusion, and render diffs; detection and masking of the
  evaluation banner of unlicensed PyMOL.
- Structured tools: `measure`, `align`, `alignment_info`, `sequence`, `contacts`, `residue_table`, `mutate`,
  `save_file`, `map_info`, `set_isolevel`, `set_setting`, `set_view`, `wait_for_jobs`.
- 43 reviewed skills, user skills under `~/.molmcp/skills`, MCP resources and one MCP prompt per skill.
- Agent Chat panel inside PyMOL and ChimeraX for Claude Code and Codex, with a model switcher and toolbar buttons.
- Several viewer windows at once, each its own session.
- Cross-platform installer (macOS, Linux, Windows) and headless PyMOL in library mode.

### Fixed
- Two red-team QA rounds (24 scenario agents, then a restarted round with regression checks); every critical or
  major report was reproduced before fixing. Notable: a PyMOL 3.1 undo bug that made reloaded objects
  unselectable, missing headless command feedback, stale renders at viewport size, `.pse` export of a bare `all`,
  and `layout` failing with mesh objects. See `docs/FEATURE_COVERAGE.md`.
