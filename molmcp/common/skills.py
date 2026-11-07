"""Skills: instruction files the agent can read on demand (how to render, align, make movies, ...).

Built-in skills live in ``molmcp/skills/<app>/*.md`` and ``molmcp/skills/shared/*.md``; users add or override
with files in ``$MOLMCP_HOME/skills/<app>/`` (or ``MOLMCP_SKILLS_DIR``).  Each file has YAML-ish front matter::

    ---
    name: publication-render
    title: Publication-quality rendering
    app: pymol
    description: one line shown in the index
    tags: rendering, figure
    ---
    body...
"""
from __future__ import annotations

import glob
import os
import re
from typing import Dict, List, Optional

from . import discovery

BUILTIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")


def user_skills_dir() -> str:
    return os.environ.get("MOLMCP_SKILLS_DIR") or os.path.join(discovery.molmcp_home(), "skills")


def _parse(path: str) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    meta: Dict[str, str] = {}
    body = text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
        body = text[m.end():]
    name = meta.get("name") or os.path.splitext(os.path.basename(path))[0]
    return {
        "name": name,
        "title": meta.get("title") or name.replace("-", " ").title(),
        "app": meta.get("app") or os.path.basename(os.path.dirname(path)),
        "description": meta.get("description", ""),
        "tags": [t.strip().strip("'\"") for t in meta.get("tags", "").strip().strip("[]").split(",") if t.strip().strip("'\"")],
        "path": path,
        "body": body.strip(),
        "source": "user" if path.startswith(os.path.abspath(user_skills_dir())) else "builtin",
    }


def list_skills(app: str) -> List[dict]:
    """Skills for ``app`` plus shared ones; user files override built-in ones with the same name."""
    out: Dict[str, dict] = {}
    for base in (BUILTIN_DIR, user_skills_dir()):
        for sub in ("shared", app):
            for path in sorted(glob.glob(os.path.join(base, sub, "*.md"))):
                s = _parse(os.path.abspath(path))
                if s:
                    out[s["name"]] = s
    return sorted(out.values(), key=lambda s: (s["app"] != app, s["name"]))


def get_skill(app: str, name: str) -> Optional[dict]:
    name = name.strip().lower()
    for s in list_skills(app):
        if s["name"].lower() == name:
            return s
    # fuzzy: substring / tag match
    for s in list_skills(app):
        if name in s["name"].lower() or name in s["title"].lower() or name in [t.lower() for t in s["tags"]]:
            return s
    return None


def index_text(app: str) -> str:
    skills = list_skills(app)
    if not skills:
        return "No skills installed. Add Markdown files under %s/%s/ (see docs)." % (user_skills_dir(), app)
    lines = ["Skills for %s (call `skill(name)` to read one; user files in %s override built-ins):" % (app, user_skills_dir())]
    for s in skills:
        tags = (" [%s]" % ", ".join(s["tags"])) if s["tags"] else ""
        src = "" if s["source"] == "builtin" else " (user)"
        lines.append("- %s: %s%s%s" % (s["name"], s["description"] or s["title"], tags, src))
    return "\n".join(lines)


def save_user_skill(app: str, name: str, content: str) -> str:
    """Create or overwrite a user skill; returns its path."""
    name = re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-") or "skill"
    d = os.path.join(user_skills_dir(), app)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name + ".md")
    if not content.lstrip().startswith("---"):
        content = "---\nname: %s\ntitle: %s\napp: %s\ndescription: user skill\ntags: user\n---\n%s" % (
            name, name.replace("-", " ").title(), app, content)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.rstrip() + "\n")
    return path
