---
name: working-with-the-agent-tools
title: How to work with the molmcp tools
app: both
description: Recommended loop for any task: inspect, act in batches, verify numerically, report
tags: workflow, verification
---
1. `status` once, then `scene` (detail="summary") before assuming anything about what is loaded or shown.
2. Act with `run`, batching several commands per call. Read the `changes` list in the response: it says what
   really changed (objects/models added or removed, representations, colours, camera). If nothing changed when
   you expected a change, re-check the selection / atom spec with `selection_info` and the command syntax with `help`.
3. Verify visually without looking at pixels: `render` returns coverage, bounding box, clipping of the frame edges,
   free margins, named colours and an ASCII map. Use `layout` (by object/model or chain) to learn which items are
   visible where and how much of each is hidden; use `compare_renders` to prove that a change had an effect.
4. Before a final figure: no `clipped_edges`, margins of at least ~5%, the intended colours in `palette`, and a
   contrast ratio above ~3 against the background.
5. Keep the user informed in one or two sentences: what you changed and what the render analysis says.
6. If the user may be working in the window at the same time, call `events` to see what they typed since your
   last call before changing the scene.
7. Prefer the app's command language over `python`; use `python` for data extraction or when no command exists.
