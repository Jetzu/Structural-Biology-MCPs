"""Skills and structured helper tools for the ChimeraX server (registered from server.py)."""
from typing import Optional

from molmcp.common import server_common as sc


def register(mcp, SESSION):

    @mcp.tool()
    def skills() -> str:
        """List the available skills (instruction files) for ChimeraX: rendering, movies, maps, alignment, AlphaFold,
        hbonds/contacts, ... Read one with `skill(name)` before starting a non-trivial task."""
        return sc.skills_index("chimerax")

    @mcp.tool()
    def skill(name: str) -> str:
        """Return the full text of one ChimeraX skill (see `skills` for names). Follow it step by step with `run`."""
        return sc.skill_text("chimerax", name)

    @mcp.tool()
    def save_skill(name: str, content: str) -> str:
        """Store a reusable recipe as a user skill (Markdown; optional front matter). It appears in `skills` from now
        on and overrides a built-in skill with the same name. Files live under ~/.molmcp/skills/chimerax/."""
        return sc.save_skill("chimerax", name, content)

    @mcp.tool()
    def measure(kind: str, spec1: str, spec2: Optional[str] = None, spec3: Optional[str] = None, spec4: Optional[str] = None) -> str:
        """Measure: kind = "distance" (two single-atom specs), "angle" (three), "dihedral" (four), "extent"/"center"
        (one spec: bounding box, size, centroid), "rmsd" (two specs with equal atom counts, in place), "count"
        (atoms/residues/chains/models of spec1), "sasa" (solvent-accessible surface area of spec1 in Å^2)."""
        return sc.python_json(SESSION, CX_MEASURE % dict(kind=kind, s1=spec1, s2=spec2, s3=spec3, s4=spec4))

    @mcp.tool()
    def align(mobile: str, target: str, method: str = "matchmaker") -> str:
        """Superpose `mobile` onto `target`: method "matchmaker" (sequence + structure; proteins/nucleic acids) or
        "align" (two equal-size atom specs, e.g. "#2@CA" onto "#1@CA"). Reports RMSD and the number of pairs."""
        return sc.python_json(SESSION, CX_ALIGN % dict(method=method, mobile=mobile, target=target))

    @mcp.tool()
    def sequence(spec: str = "protein") -> str:
        """One-letter sequence of every chain in the spec, with residue numbering ranges and chain descriptions."""
        return sc.python_json(SESSION, CX_SEQUENCE % dict(spec=spec))

    @mcp.tool()
    def contacts(spec1: str, spec2: str, cutoff: float = 4.0, polar_only: bool = False, max_pairs: int = 200) -> str:
        """Residue-level contacts between two atom specs within `cutoff` Å (default 4); polar_only keeps N/O pairs
        within 3.5 Å (approximate hydrogen bonds). Returns residue pairs with closest distance plus summaries."""
        return sc.python_json(SESSION, CX_CONTACTS % dict(s1=spec1, s2=spec2, cut=float(cutoff), polar=bool(polar_only), n=int(max_pairs)))

    @mcp.tool()
    def residue_table(spec: str = "protein", max_rows: int = 500, offset: int = 0) -> str:
        """Per-residue table for a spec: model, chain, number, name, secondary structure, mean B-factor (pLDDT for
        AlphaFold models), ribbon shown, atoms shown, ribbon colour and dominant atom colour. Paged with
        max_rows/offset. Use it for questions like "which residues are below pLDDT 50" or "what lost its cartoon"."""
        return sc.python_json(SESSION, CX_RESIDUE_TABLE % dict(spec=spec, n=int(max_rows), off=int(offset)))

    @mcp.tool()
    def save_file(path: str, models: Optional[str] = None, format: Optional[str] = None, options: str = "") -> str:
        """Save with ChimeraX's `save`: session (.cxs), coordinates (.pdb/.cif/.mol2), images (.png/.jpg; options e.g.
        "width 1600 supersample 3 transparentBackground true"), 3D exports (.glb/.stl/.obj), maps (.mrc).
        `models` restricts what is saved. Returns the absolute path and the command used."""
        return sc.python_json(SESSION, CX_SAVE % dict(path=path, models=models, fmt=format, options=options))


CX_MEASURE = r'''
import numpy as np
from chimerax.core.commands import atomspec
kind = %(kind)r; specs = [x for x in [%(s1)r, %(s2)r, %(s3)r, %(s4)r] if x]
def objs(spec):
    return atomspec.AtomSpecArg.parse(spec, session)[0].evaluate(session)
def one(spec):
    a = objs(spec).atoms
    if len(a) != 1:
        raise ValueError("spec %%r matches %%d atoms, need exactly 1" %% (spec, len(a)))
    return a[0].scene_coord
if kind == "distance":
    result = {"kind": kind, "value": round(float(np.linalg.norm(one(specs[0]) - one(specs[1]))), 3), "unit": "A"}
elif kind in ("angle", "dihedral"):
    from chimerax.geometry import angle, dihedral
    pts = [one(s) for s in specs[:3 if kind == "angle" else 4]]
    result = {"kind": kind, "value": round(float(angle(*pts) if kind == "angle" else dihedral(*pts)), 2), "unit": "deg"}
elif kind in ("extent", "center"):
    xyz = objs(specs[0]).atoms.scene_coords
    result = {"kind": kind, "extent": [[round(float(x), 2) for x in xyz.min(axis=0)], [round(float(x), 2) for x in xyz.max(axis=0)]],
              "size": [round(float(x), 2) for x in (xyz.max(axis=0) - xyz.min(axis=0))], "centroid": [round(float(x), 2) for x in xyz.mean(axis=0)]}
elif kind == "rmsd":
    a, b = objs(specs[0]).atoms.scene_coords, objs(specs[1]).atoms.scene_coords
    if len(a) != len(b):
        raise ValueError("atom counts differ: %%d vs %%d" %% (len(a), len(b)))
    result = {"kind": kind, "value": round(float(np.sqrt(((a - b) ** 2).sum(axis=1).mean())), 3), "unit": "A", "atoms": int(len(a)), "note": "in place, no fitting"}
elif kind == "count":
    o = objs(specs[0])
    result = {"kind": kind, "atoms": o.num_atoms, "residues": len(o.residues), "chains": sorted(set(o.residues.chain_ids)), "models": ["#" + m.id_string for m in o.models]}
elif kind == "sasa":
    from chimerax.core.commands import run as _run
    val = _run(session, "measure sasa " + specs[0], log=False)
    result = {"kind": kind, "value": round(float(val), 1) if val is not None else None, "unit": "A^2"}
else:
    raise ValueError("unknown kind " + kind)
'''

CX_ALIGN = r'''
from chimerax.core.commands import run as _run
method = %(method)r
if method == "align":
    r = _run(session, "align %(mobile)s to %(target)s", log=False)
    # returns (matched_atoms, matched_to_atoms, rmsd, full_rmsd, transform)
    try:
        result = {"method": method, "rmsd": round(float(r[2]), 3), "full_rmsd": round(float(r[3]), 3), "pairs": int(len(r[0]))}
    except Exception:
        result = {"method": method, "raw": str(r)[:300]}
else:
    r = _run(session, "matchmaker %(mobile)s to %(target)s", log=False)
    res = r[0] if isinstance(r, (list, tuple)) and r else r
    out = {"method": "matchmaker"}
    if isinstance(res, dict):
        for k, v in res.items():
            kl = str(k).lower()
            if "rmsd" in kl and isinstance(v, (int, float)):
                out[kl.replace(" ", "_")] = round(float(v), 3)
            elif "atoms" in kl and hasattr(v, "__len__"):
                out[kl.replace(" ", "_").replace("atoms", "atom_count")] = int(len(v))
            elif isinstance(v, (int, float, str)) and "matrix" not in kl:
                out[kl.replace(" ", "_")] = v
    if len(out) == 1:
        out["raw"] = str(r)[:400]
    result = out
'''

CX_SEQUENCE = r'''
from chimerax.core.commands import atomspec
o = atomspec.AtomSpecArg.parse(%(spec)r, session)[0].evaluate(session)
out = {"spec": %(spec)r, "chains": []}
seen = set()
for s in o.atoms.unique_structures:
    for c in s.chains:
        key = (s.id_string, c.chain_id)
        if key in seen:
            continue
        seen.add(key)
        res = c.existing_residues
        if len(res) == 0:
            continue
        out["chains"].append({"model": "#" + s.id_string, "chain": c.chain_id, "length": len(c.characters), "first": int(res.numbers.min()),
                              "last": int(res.numbers.max()), "sequence": c.characters, "description": getattr(c, "description", None)})
result = out
'''

CX_CONTACTS = r'''
import numpy as np
from chimerax.core.commands import atomspec
s1, s2, cut, polar = %(s1)r, %(s2)r, %(cut)f, %(polar)r
a1 = atomspec.AtomSpecArg.parse(s1, session)[0].evaluate(session).atoms
a2 = atomspec.AtomSpecArg.parse(s2, session)[0].evaluate(session).atoms
if polar:
    a1 = a1.filter(np.isin(a1.element_names, ["N", "O"])); a2 = a2.filter(np.isin(a2.element_names, ["N", "O"])); cut = min(cut, 3.5)
from chimerax.geometry import find_close_points
i1, i2 = find_close_points(a1.scene_coords, a2.scene_coords, cut)
c1, c2 = a1.filter(i1), a2.filter(i2)
best = {}
if len(c1) and len(c2):
    d = np.linalg.norm(c1.scene_coords[:, None, :] - c2.scene_coords[None, :, :], axis=2)
    for i in range(len(c1)):
        for j in np.flatnonzero(d[i] <= cut):
            ra, rb = c1[i].residue, c2[j].residue
            key = ("#%%s/%%s:%%s%%d" %% (ra.structure.id_string, ra.chain_id, ra.name, ra.number), "#%%s/%%s:%%s%%d" %% (rb.structure.id_string, rb.chain_id, rb.name, rb.number))
            if key not in best or d[i, j] < best[key][0]:
                best[key] = (round(float(d[i, j]), 2), c1[i].name, c2[j].name)
rows = sorted(({"res1": k[0], "res2": k[1], "min_distance": v[0], "atoms": [v[1], v[2]]} for k, v in best.items()), key=lambda r: r["min_distance"])
result = {"cutoff": cut, "polar_only": polar, "residue_pairs": len(rows), "residues1": sorted(set(r["res1"] for r in rows)),
          "residues2": sorted(set(r["res2"] for r in rows)), "pairs": rows[:%(n)d]}
'''

CX_SAVE = r'''
import os
from chimerax.core.commands import run as _run
p = os.path.expanduser(%(path)r)
text = 'save "' + p + '"'
if %(fmt)r:
    text += " format " + %(fmt)r
if %(models)r:
    text += " models " + %(models)r
if %(options)r:
    text += " " + %(options)r
_run(session, text, log=False)
result = {"path": os.path.abspath(p), "bytes": os.path.getsize(p) if os.path.exists(p) else None, "command": text}
'''


CX_RESIDUE_TABLE = r'''
import numpy as np
from chimerax.core.commands import atomspec
o = atomspec.AtomSpecArg.parse(%(spec)r, session)[0].evaluate(session)
res = o.residues
rows = []
ss_names = {0: "coil", 1: "helix", 2: "strand"}
for r in res:
    atoms = r.atoms
    cols = atoms.colors[:, :3]
    if len(cols):
        vals, counts = np.unique(cols, axis=0, return_counts=True)
        dom = [int(x) for x in vals[counts.argmax()]]
    else:
        dom = None
    rows.append({"model": "#" + r.structure.id_string, "chain": r.chain_id, "number": int(r.number), "insertion_code": r.insertion_code or "",
                 "name": r.name, "ss": ss_names.get(int(r.ss_type), "?"), "polymer": int(r.polymer_type) != 0,
                 "b_mean": round(float(atoms.bfactors.mean()), 2) if len(atoms) else None,
                 "ribbon_shown": bool(r.ribbon_display), "atoms_shown": int(atoms.displays.sum()), "atoms": int(len(atoms)),
                 "ribbon_rgb": [int(x) for x in r.ribbon_color[:3]], "atom_rgb": dom})
total = len(rows)
rows = rows[%(off)d:%(off)d + %(n)d]
result = {"spec": %(spec)r, "total": total, "offset": %(off)d, "rows": rows}
'''
