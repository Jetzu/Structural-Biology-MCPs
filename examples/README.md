# Examples

| | |
|---|---|
| [prompts.md](prompts.md) | prompts to ask in Claude Code, Codex or the in-app chat, with the tools each one uses |
| [make_gallery.py](make_gallery.py) | regenerates the README images through the MCP servers, the same way an agent works |

`make_gallery.py` starts each server as an MCP client, launches the viewer, sends the `run` commands behind each
README prompt and saves the `render` / `layout` results to `docs/images/`, together with what the agent got back
(`docs/images/analysis/<name>.json`). It runs one viewer at a time and quits it at the end.

```bash
.venv/bin/python examples/make_gallery.py                 # everything
.venv/bin/python examples/make_gallery.py chimerax        # only the ChimeraX figures
.venv/bin/python examples/make_gallery.py layout biotin   # only these
```

For PyMOL figures without the evaluation banner that an unlicensed PyMOL prints into renders, point
`PYMOL_PYTHON` at a Python with open-source PyMOL; the PyMOL entries then run headless with it:

```bash
conda create -p ./pymol-os -c conda-forge python=3.11 pymol-open-source numpy pillow
PYMOL_PYTHON=./pymol-os/bin/python .venv/bin/python examples/make_gallery.py pymol
```
