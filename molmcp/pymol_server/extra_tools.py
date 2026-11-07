"""Skills and structured helper tools for the PyMOL server (registered from server.py)."""
from typing import Optional

from molmcp.common import server_common as sc


def register(mcp, SESSION):

    @mcp.tool()
    def skills() -> str:
        """List the available skills (instruction files) for PyMOL: rendering, movies, surfaces, alignment, maps, ...
        Read one with `skill(name)` before starting a non-trivial task."""
        return sc.skills_index("pymol")

    @mcp.tool()
    def skill(name: str) -> str:
        """Return the full text of one PyMOL skill (see `skills` for names). Follow it step by step with `run`."""
        return sc.skill_text("pymol", name)

    @mcp.tool()
    def save_skill(name: str, content: str) -> str:
        """Store a reusable recipe as a user skill (Markdown; optional front matter). It appears in `skills` from now
        on and overrides a built-in skill with the same name. Files live under ~/.molmcp/skills/pymol/."""
        return sc.save_skill("pymol", name, content)

    @mcp.tool()
    def measure(kind: str, selection1: str, selection2: Optional[str] = None, selection3: Optional[str] = None,
                selection4: Optional[str] = None, name: Optional[str] = None) -> str:
        """Measure without clutter: kind = "distance" (two single-atom selections), "angle" (three), "dihedral" (four),
        "extent"/"center" (one selection: bounding box, size, centre of mass), "rmsd" (two selections with equal atom
        counts, in place, no fitting), "count" (atoms/residues/chains of selection1). `name` also draws the
        distance/angle/dihedral object."""
        code = PYMOL_MEASURE % dict(kind=kind, s1=selection1, s2=selection2, s3=selection3, s4=selection4, name=name)
        return sc.python_json(SESSION, code)

    @mcp.tool()
    def align(mobile: str, target: str, method: str = "align", cycles: int = 5, cutoff: float = 2.0,
              object_name: Optional[str] = None) -> str:
        """Superpose `mobile` onto `target` and report RMSD and atom counts. method: "align" (sequence-based, similar
        proteins), "super" (structure-based, low similarity), "cealign" (very different folds), "pair_fit" (explicit
        atom pairs). The mobile object is moved in place."""
        code = PYMOL_ALIGN % dict(method=method, mobile=mobile, target=target, cycles=int(cycles), cutoff=float(cutoff), obj=object_name)
        return sc.python_json(SESSION, code)

    @mcp.tool()
    def sequence(selection: str = "polymer") -> str:
        """One-letter sequence of every chain in the selection, with residue numbering ranges."""
        return sc.python_json(SESSION, PYMOL_SEQUENCE % dict(sel=selection))

    @mcp.tool()
    def contacts(selection1: str, selection2: str, cutoff: float = 4.0, polar_only: bool = False, max_pairs: int = 200) -> str:
        """Residue-level contacts between two selections within `cutoff` Å (default 4); polar_only keeps N/O pairs
        within 3.5 Å (approximate hydrogen bonds). Returns residue pairs with closest distance plus summaries."""
        return sc.python_json(SESSION, PYMOL_CONTACTS % dict(s1=selection1, s2=selection2, cut=float(cutoff), polar=bool(polar_only), n=int(max_pairs)))

    @mcp.tool()
    def residue_table(selection: str = "polymer", max_rows: int = 500, offset: int = 0) -> str:
        """Per-residue table for a selection: object, chain, resi, resn, secondary structure, mean B-factor (pLDDT
        for AlphaFold models), representations shown, dominant colour. Paged with max_rows/offset. Use it for
        "which residues have pLDDT < 50", "what is shown as sticks", "which residues are coloured red"."""
        return sc.python_json(SESSION, PYMOL_RESIDUE_TABLE % dict(sel=selection, n=int(max_rows), off=int(offset)))

    @mcp.tool()
    def save_file(path: str, selection: str = "all", format: Optional[str] = None, state: int = -1) -> str:
        """Save to disk: session (.pse/.pze), coordinates (.pdb/.cif/.mol2/.sdf/.xyz), sequence (.fasta), image
        (.png) or mesh (.obj/.wrl/.dae/.stl). Format from the extension unless given. Returns the absolute path."""
        return sc.python_json(SESSION, PYMOL_SAVE % dict(path=path, sel=selection, state=int(state), fmt=format))


PYMOL_MEASURE = r'''
kind = %(kind)r; sels = [x for x in [%(s1)r, %(s2)r, %(s3)r, %(s4)r] if x]
if kind == "distance":
    result = {"kind": kind, "value": round(cmd.get_distance(sels[0], sels[1]), 3), "unit": "A"}
elif kind == "angle":
    result = {"kind": kind, "value": round(cmd.get_angle(sels[0], sels[1], sels[2]), 2), "unit": "deg"}
elif kind == "dihedral":
    result = {"kind": kind, "value": round(cmd.get_dihedral(sels[0], sels[1], sels[2], sels[3]), 2), "unit": "deg"}
elif kind in ("extent", "center"):
    ext = cmd.get_extent(sels[0]); com = cmd.centerofmass(sels[0])
    result = {"kind": kind, "extent": [[round(x, 2) for x in ext[0]], [round(x, 2) for x in ext[1]]],
              "size": [round(ext[1][i] - ext[0][i], 2) for i in range(3)], "center_of_mass": [round(x, 2) for x in com]}
elif kind == "rmsd":
    result = {"kind": kind, "value": round(cmd.rms_cur(sels[0], sels[1], matchmaker=-1), 3), "unit": "A", "note": "in place, no fitting"}
elif kind == "count":
    res = set(); cmd.iterate(sels[0], "_r.add((model, chain, resi))", space={"_r": res})
    result = {"kind": kind, "atoms": cmd.count_atoms(sels[0]), "residues": len(res), "chains": cmd.get_chains(sels[0])}
else:
    raise ValueError("unknown kind " + kind)
name = %(name)r
if name and kind in ("distance", "angle", "dihedral"):
    getattr(cmd, kind)(name, *sels)
    result["object"] = name
'''

PYMOL_ALIGN = r'''
method = %(method)r
if method == "cealign":
    r = cmd.cealign(%(target)r, %(mobile)r, object=%(obj)r)
    result = {"method": method, "rmsd": round(r.get("RMSD", 0), 3), "aligned_atoms": r.get("alignment_length")}
elif method == "pair_fit":
    result = {"method": method, "rmsd": round(cmd.pair_fit(%(mobile)r, %(target)r), 3)}
else:
    fn = cmd.super if method == "super" else cmd.align
    r = fn(%(mobile)r, %(target)r, cycles=%(cycles)d, cutoff=%(cutoff)f, object=%(obj)r)
    result = {"method": method, "rmsd_after_refinement": round(r[0], 3), "atoms_after_refinement": r[1], "refinement_cycles": r[2],
              "rmsd_before_refinement": round(r[3], 3), "atoms_before_refinement": r[4], "alignment_score": round(r[5], 1), "residues_aligned": r[6]}
'''

PYMOL_SEQUENCE = r'''
sel = %(sel)r
out = {"selection": sel, "chains": []}
for obj in (cmd.get_object_list("(" + sel + ")") or []):
    for ch in cmd.get_chains("(" + sel + ") and %%" + obj):
        s = "((" + sel + ") and %%" + obj + " and chain '" + ch + "' and polymer)"
        seq = []; nums = []
        cmd.iterate(s + " and name CA+C1'", "_s.append(oneletter); _n.append(resv)", space={"_s": seq, "_n": nums})
        if seq:
            out["chains"].append({"object": obj, "chain": ch, "length": len(seq), "first": min(nums), "last": max(nums), "sequence": "".join(seq)})
result = out
'''

PYMOL_CONTACTS = r'''
s1, s2, cut, polar = %(s1)r, %(s2)r, %(cut)f, %(polar)r
if polar:
    s1 = "(" + s1 + ") and (elem N+O)"; s2 = "(" + s2 + ") and (elem N+O)"; cut = min(cut, 3.5)
near1 = "(" + s1 + ") within " + str(cut) + " of (" + s2 + ")"
near2 = "(" + s2 + ") within " + str(cut) + " of (" + s1 + ")"
pairs = cmd.find_pairs(near1, near2, cutoff=cut)
info = {}
cmd.iterate(near1, "_d[(model, index)] = (chain, resn, resi, name)", space={"_d": info})
cmd.iterate(near2, "_d[(model, index)] = (chain, resn, resi, name)", space={"_d": info})
best = {}
for (m1, i1), (m2, i2) in pairs:
    a, b = info.get((m1, i1)), info.get((m2, i2))
    if not a or not b:
        continue
    d = cmd.get_distance("%%s and index %%d" %% (m1, i1), "%%s and index %%d" %% (m2, i2))
    key = ("%%s/%%s/%%s%%s" %% (m1, a[0], a[1], a[2]), "%%s/%%s/%%s%%s" %% (m2, b[0], b[1], b[2]))
    if key not in best or d < best[key][0]:
        best[key] = (round(d, 2), a[3], b[3])
rows = sorted(({"res1": k[0], "res2": k[1], "min_distance": v[0], "atoms": [v[1], v[2]]} for k, v in best.items()), key=lambda r: r["min_distance"])
result = {"cutoff": cut, "polar_only": polar, "atom_pairs": len(pairs), "residue_pairs": len(rows),
          "residues1": sorted(set(r["res1"] for r in rows)), "residues2": sorted(set(r["res2"] for r in rows)), "pairs": rows[:%(n)d]}
'''

PYMOL_SAVE = r'''
import os
p = cmd.exp_path(%(path)r)
cmd.save(p, %(sel)r, state=%(state)d, format=%(fmt)r or "")
result = {"path": os.path.abspath(p), "bytes": os.path.getsize(p) if os.path.exists(p) else None}
'''


PYMOL_RESIDUE_TABLE = r'''
from collections import Counter, OrderedDict
REP = {0: "sticks", 1: "spheres", 2: "surface", 3: "labels", 4: "nb_spheres", 5: "cartoon", 6: "ribbon", 7: "lines", 8: "mesh", 9: "dots", 10: "dashes", 11: "nonbonded"}
acc = OrderedDict()
def _c(model, chain, resi, resn, ss, b, reps, color):
    k = (model, chain, resi)
    d = acc.get(k)
    if d is None:
        d = acc[k] = {"object": model, "chain": chain, "resi": resi, "resn": resn, "ss": ss or "L", "b": [], "reps": 0, "colors": Counter(), "atoms": 0}
    d["b"].append(b); d["reps"] |= reps; d["colors"][color] += 1; d["atoms"] += 1
cmd.iterate(%(sel)r, "_c(model, chain, resi, resn, ss, b, reps, color)", space={"_c": _c})
names = {i: n for n, i in cmd.get_color_indices()}
def _col(ci):
    if ci >= 0x40000000:
        return [(ci >> 16) & 255, (ci >> 8) & 255, ci & 255], "rgb"
    t = cmd.get_color_tuple(ci)
    return ([int(round(x * 255)) for x in t] if t else None), names.get(ci, "index_%%d" %% ci)
rows = []
for d in acc.values():
    ci, _ = d["colors"].most_common(1)[0]
    rgb, cname = _col(ci)
    rows.append({"object": d["object"], "chain": d["chain"], "resi": d["resi"], "resn": d["resn"], "ss": d["ss"],
                 "b_mean": round(sum(d["b"]) / len(d["b"]), 2), "atoms": d["atoms"],
                 "reps_shown": [REP[i] for i in REP if d["reps"] & (1 << i)], "color": cname, "rgb": rgb})
total = len(rows)
result = {"selection": %(sel)r, "total": total, "offset": %(off)d, "rows": rows[%(off)d:%(off)d + %(n)d]}
'''
