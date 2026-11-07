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
        counts, in place, no fitting), "count" (atoms/residues/chains of selection1), "sasa" (solvent-accessible
        surface area of selection1 in Å^2). `name` also draws the distance/angle/dihedral object."""
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
need = {"distance": 2, "angle": 3, "dihedral": 4, "extent": 1, "center": 1, "rmsd": 2, "count": 1, "sasa": 1}
if kind not in need:
    raise ValueError("unknown kind %%r; use one of %%s" %% (kind, sorted(need)))
if len(sels) < need[kind]:
    raise ValueError("kind %%r needs %%d selection(s), got %%d" %% (kind, need[kind], len(sels)))
for s_ in sels[:need[kind]]:
    if cmd.count_atoms(s_) == 0:
        raise ValueError("selection %%r matches no atoms" %% s_)
if kind in ("distance", "angle", "dihedral"):
    for s_ in sels[:need[kind]]:
        if cmd.count_atoms(s_) != 1:
            raise ValueError("selection %%r must match exactly one atom for kind %%r (matches %%d)" %% (s_, kind, cmd.count_atoms(s_)))
if kind == "rmsd" and cmd.count_atoms(sels[0]) != cmd.count_atoms(sels[1]):
    raise ValueError("rmsd needs equal atom counts: %%d vs %%d" %% (cmd.count_atoms(sels[0]), cmd.count_atoms(sels[1])))
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
    by_obj = {}
    for o in (cmd.get_object_list("(" + sels[0] + ")") or []):
        by_obj[o] = cmd.get_chains("(" + sels[0] + ") and %%" + o)
    result = {"kind": kind, "atoms": cmd.count_atoms(sels[0]), "residues": len(res),
              "chains": sorted({c for cs in by_obj.values() for c in cs}), "chains_by_object": by_obj}
elif kind == "sasa":
    old = cmd.get("dot_solvent"); old_dd = cmd.get("dot_density"); cmd.set("dot_solvent", 1); cmd.set("dot_density", 3)
    try:
        area = cmd.get_area(sels[0])
    finally:
        cmd.set("dot_solvent", old); cmd.set("dot_density", old_dd)
    result = {"kind": kind, "value": round(float(area), 1), "unit": "A^2", "note": "solvent-accessible area via get_area with dot_solvent=1"}
name = %(name)r
if name and kind in ("distance", "angle", "dihedral"):
    getattr(cmd, kind)(name, *sels)
    result["object"] = name
'''

PYMOL_ALIGN = r'''
method = %(method)r
if method not in ("align", "super", "cealign", "pair_fit"):
    raise ValueError("method must be align, super, cealign or pair_fit")
for s_ in (%(mobile)r, %(target)r):
    if cmd.count_atoms(s_) == 0:
        raise ValueError("selection %%r matches no atoms" %% s_)
if method == "cealign":
    r = cmd.cealign(%(target)r, %(mobile)r, object=%(obj)r)
    result = {"method": method, "rmsd": round(r.get("RMSD", 0), 3), "aligned_atoms": r.get("alignment_length"),
              "note": "cealign ignores cycles/cutoff"}
elif method == "pair_fit":
    n1, n2 = cmd.count_atoms(%(mobile)r), cmd.count_atoms(%(target)r)
    if n1 != n2:
        raise ValueError("pair_fit needs selections with equal atom counts (got %%d vs %%d); pick matching atoms, e.g. 'name CA'" %% (n1, n2))
    result = {"method": method, "rmsd": round(cmd.pair_fit(%(mobile)r, %(target)r), 3), "atoms": n1,
              "note": "pair_fit matches atoms by order; it creates no alignment object (object_name ignored) and ignores cycles/cutoff"}
else:
    fn = cmd.super if method == "super" else cmd.align
    r = fn(%(mobile)r, %(target)r, cycles=%(cycles)d, cutoff=%(cutoff)f, object=%(obj)r)
    result = {"method": method, "rmsd_after_refinement": round(r[0], 3), "atoms_after_refinement": r[1], "refinement_cycles": r[2],
              "rmsd_before_refinement": round(r[3], 3), "atoms_before_refinement": r[4], "alignment_score": round(r[5], 1), "residues_aligned": r[6]}
'''

PYMOL_SEQUENCE = r'''
sel = %(sel)r
if cmd.count_atoms(sel) == 0:
    raise ValueError("selection %%r matches no atoms" %% sel)
NUC = {"DA": "A", "DC": "C", "DG": "G", "DT": "T", "DU": "U", "DI": "I", "A": "A", "C": "C", "G": "G", "U": "U", "I": "I",
       "T": "T", "N": "N", "DN": "N"}
def _ranges(vals):
    vals = sorted(set(vals)); out_ = []; start = prev = None
    for v in vals:
        if start is None:
            start = prev = v
        elif v == prev + 1:
            prev = v
        else:
            out_.append("%%d" %% start if start == prev else "%%d-%%d" %% (start, prev)); start = prev = v
    if start is not None:
        out_.append("%%d" %% start if start == prev else "%%d-%%d" %% (start, prev))
    return out_
out = {"selection": sel, "chains": []}
polymer_atoms = cmd.count_atoms("(" + sel + ") and polymer")
for obj in (cmd.get_object_list("(" + sel + ")") or []):
    for ch in cmd.get_chains("(" + sel + ") and %%" + obj):
        s = "((" + sel + ") and %%" + obj + " and chain '" + ch + "' and polymer)"
        rows = []
        cmd.iterate(s + " and name CA+C1'", "_r.append((resv, resi, resn, oneletter))", space={"_r": rows})
        if rows:
            rows.sort(key=lambda r_: r_[0])
            seq = []
            for resv, resi, resn, one in rows:
                if one in ("X", "", None) and resn.strip() in NUC:
                    one = NUC[resn.strip()]
                seq.append(one or "X")
            nums = [r_[0] for r_ in rows]
            kind = "nucleic" if any(r_[2].strip() in NUC for r_ in rows) else "protein"
            out["chains"].append({"object": obj, "chain": ch, "type": kind, "length": len(seq), "first": min(nums), "last": max(nums),
                                  "ranges": _ranges(nums), "sequence": "".join(seq)})
if not out["chains"]:
    out["note"] = ("the selection has %%d atoms but no polymer residues with a CA (protein) or C1' (nucleic acid) atom; "
                   "solvent, ligands and CA-less selections have no sequence" %% cmd.count_atoms(sel)) if polymer_atoms == 0 else \
                  "polymer atoms matched but none of them is a CA/C1' atom; select whole residues (byres ...)"
result = out
'''

PYMOL_CONTACTS = r'''
s1, s2, cut, polar = %(s1)r, %(s2)r, %(cut)f, %(polar)r
for s_ in (s1, s2):
    if cmd.count_atoms(s_) == 0:
        raise ValueError("selection %%r matches no atoms" %% s_)
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
if cmd.count_atoms(%(sel)r) == 0 and not p.lower().endswith((".pse", ".pze", ".png")):
    raise ValueError("selection %%r matches no atoms" %% %(sel)r)
st = %(state)d
if st > 0:
    mx = max([cmd.count_states(o) for o in (cmd.get_object_list("(" + %(sel)r + ")") or [])] or [0])
    if st > mx:
        raise ValueError("state %%d does not exist (objects in the selection have at most %%d states)" %% (st, mx))
d = os.path.dirname(p)
if d and not os.path.isdir(d):
    raise ValueError("directory does not exist: %%s" %% d)
sel_ = %(sel)r
fmt_ = (%(fmt)r or "").lower() or p.lower().rsplit(".", 1)[-1]
if fmt_ in ("pse", "pze", "psw"):
    # PyMOL treats a bare "all" / "" as a partial-session object list and writes an empty session
    if sel_.strip().strip("()").strip().lower() in ("all", "", "*", "visible", "enabled"):
        cmd.save(p, "(all)", state=st, format=%(fmt)r or "", partial=0)
    else:
        cmd.save(p, sel_, state=st, format=%(fmt)r or "", partial=1)
else:
    cmd.save(p, sel_, state=st, format=%(fmt)r or "")
result = {"path": os.path.abspath(p), "bytes": os.path.getsize(p) if os.path.exists(p) else None}
if fmt_ in ("pse", "pze", "psw") and result["bytes"] is not None and result["bytes"] < 2000 and cmd.count_atoms("all") > 0:
    raise RuntimeError("the session file is suspiciously small (%%d bytes) although %%d atoms are loaded" %% (result["bytes"], cmd.count_atoms("all")))
'''


PYMOL_RESIDUE_TABLE = r'''
from collections import Counter, OrderedDict
REP = {0: "sticks", 1: "spheres", 2: "surface", 3: "labels", 4: "nb_spheres", 5: "cartoon", 6: "ribbon", 7: "lines", 8: "mesh", 9: "dots", 10: "dashes", 11: "nonbonded"}
off, n = %(off)d, %(n)d
if off < 0 or n < 1:
    raise ValueError("offset must be >= 0 and max_rows >= 1 (max_rows is capped at 2000; page with offset)")
cmd.count_atoms(%(sel)r)          # raises for invalid selection names instead of returning an empty table
acc = OrderedDict()
def _c(model, chain, resi, resn, ss, b, reps, color):
    k = (model, chain, resi)
    d = acc.get(k)
    if d is None:
        d = acc[k] = {"object": model, "chain": chain, "resi": resi, "resn": resn, "ss": ss, "b": [], "reps": 0, "colors": Counter(), "atoms": 0, "polymer": False}
    d["b"].append(b); d["reps"] |= reps; d["colors"][color] += 1; d["atoms"] += 1
cmd.iterate(%(sel)r, "_c(model, chain, resi, resn, ss, b, reps, color)", space={"_c": _c})
poly = set(); cmd.iterate("(" + %(sel)r + ") and polymer", "_p.add((model, chain, resi))", space={"_p": poly})
for k_, d_ in acc.items():
    d_["polymer"] = k_ in poly
    d_["ss"] = (d_["ss"] or "L") if d_["polymer"] else ""
names = {i: n for n, i in cmd.get_color_indices(all=1)}
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
n = min(n, 2000)
result = {"selection": %(sel)r, "total": total, "offset": off, "max_rows": n, "rows": rows[off:off + n], "truncated": off + n < total,
          "note": "ss is '' for non-polymer residues (ligands, water, ions); reps_shown lists enabled representation flags, "
                  "some of which draw nothing for a given residue (e.g. lines for a single-atom water)"}
'''


def register_more(mcp, SESSION):
    """Second wave of structured tools (audit items 5, 7, 10 and honourable mentions)."""

    @mcp.tool()
    def mutate(selection: str, residue: str, rotamer: int = 0, keep_original_as: Optional[str] = None) -> str:
        """Point mutation with PyMOL's mutagenesis wizard (headless-safe). `selection` must match exactly one
        residue (e.g. "1ubq and chain A and resi 48"); `residue` is a three-letter code (ALA, PHE, ...).
        rotamer=0 picks the rotamer with the lowest clash score, otherwise the 1-based rotamer index.
        keep_original_as copies the object first (e.g. "wt"). Returns rotamer scores and close contacts."""
        return sc.python_json(SESSION, PYMOL_MUTATE % dict(sel=selection, res=residue.upper(), rot=int(rotamer), keep=keep_original_as))

    @mcp.tool()
    def map_info(name: Optional[str] = None) -> str:
        """Density maps and their isosurfaces: for every map object the grid size and min/max/mean/sd; for every
        mesh/surface/volume object its current isolevel. Use set_isolevel to change a level."""
        return sc.python_json(SESSION, PYMOL_MAP_INFO % dict(name=name))

    @mcp.tool()
    def set_isolevel(name: str, level: float) -> str:
        """Change the contour level of an existing mesh/surface/volume object (PyMOL `isolevel`)."""
        return sc.python_json(SESSION, "cmd.isolevel(%r, %f)\nresult = {'object': %r, 'level': %f}" % (name, float(level), name, float(level)))

    @mcp.tool()
    def alignment_info(alignment_object: str, max_pairs: int = 400) -> str:
        """Residue pairs behind an alignment object created by `align`/`super`/`cealign` with object_name=...:
        which residues superpose, with their per-pair CA distance. Use after `align(..., object_name="aln")`."""
        return sc.python_json(SESSION, PYMOL_ALIGNMENT_INFO % dict(aln=alignment_object, n=int(max_pairs)))

    @mcp.tool()
    def set_setting(name: str, value: str, selection: Optional[str] = None) -> str:
        """Set a PyMOL setting (global, or for an object/selection). Values are parsed like the `set` command
        ("0.5", "on", "[1,0,0]", "marine"). Returns the old and new value."""
        return sc.python_json(SESSION, PYMOL_SET_SETTING % dict(name=name, value=value, sel=selection))


PYMOL_MUTATE = r'''
sel, res, rot, keep = %(sel)r, %(res)r, %(rot)d, %(keep)r
AA = {"ALA","ARG","ASN","ASP","CYS","GLN","GLU","GLY","HIS","ILE","LEU","LYS","MET","PHE","PRO","SER","THR","TRP","TYR","VAL","HID","HIE","HIP"}
if res not in AA:
    raise ValueError("residue must be a three-letter amino-acid code, got %%r" %% res)
if rot < 0:
    raise ValueError("rotamer must be >= 0")
ids = set(); cmd.iterate(sel, "_i.add((model, chain, resi))", space={"_i": ids})
if len(ids) != 1:
    raise ValueError("selection must match exactly one residue, matched %%d: %%s" %% (len(ids), sorted(ids)[:5]))
model, chain, resi = next(iter(ids))
if keep:
    if keep == model:
        raise ValueError("keep_original_as must differ from the object being mutated (%%r)" %% model)
    if keep in cmd.get_names("all"):
        raise ValueError("an object or selection named %%r already exists; cmd.create would merge into it - choose a new name or delete it first" %% keep)
    cmd.create(keep, model)
mut = "/%%s//%%s/%%s/" %% (model, chain, resi)
before = []
cmd.iterate(sel, "_b.append(resn)", space={"_b": before})
b_before = {}
cmd.iterate(mut, "_bb[name] = b", space={"_bb": b_before})
lines_before = cmd.count_atoms("(%%s) and rep lines" %% mut)
view0 = cmd.get_view()
try:
    cmd.wizard("mutagenesis"); cmd.do("refresh_wizard")
    w = cmd.get_wizard()
    w.set_mode(res)
    w.do_select(mut)
    scores = [float(x) for x in getattr(w, "bump_scores", []) or []]
    n_rot = cmd.count_states("mutation") if "mutation" in cmd.get_names("all") else len(scores)
    if rot > max(n_rot, 1):
        raise ValueError("rotamer %%d out of range (1-%%d)" %% (rot, max(n_rot, 1)))
    chosen = rot if rot > 0 else ((scores.index(min(scores)) + 1) if scores else 1)
    cmd.frame(chosen)
    w.apply()
finally:
    cmd.set_wizard()
    for s_ in cmd.get_names("selections"):
        if s_.startswith("_pk"):
            cmd.delete(s_)
    cmd.set_view(view0)
# the wizard shows the residue as lines and zeroes its B-factors: undo both
if lines_before == 0:
    cmd.hide("lines", mut)
if b_before:
    mean_b = sum(b_before.values()) / len(b_before)
    cmd.alter(mut, "b = _bb.get(name, _mb)", space={"_bb": b_before, "_mb": mean_b})
after = []
cmd.iterate(mut, "_a.append(resn)", space={"_a": after})
others = "(%%s) and not hydro and not (byres (%%s)) and not ((neighbor (%%s)) extend 2)" %% (model, mut, mut)
close = cmd.find_pairs("(%%s) and not hydro and not name N+C+O+CA" %% mut, others, cutoff=2.5)
result = {"object": model, "chain": chain, "resi": resi, "from": before[0] if before else None, "to": after[0] if after else None,
          "rotamers": n_rot, "chosen_rotamer": chosen, "bump_scores": [round(s, 2) for s in scores][:20],
          "heavy_atom_contacts_below_2.5A": len(close), "kept_original_as": keep,
          "note": "camera, representations and B-factors of the residue were restored (new side-chain atoms get the "
                  "residue's mean B); side-chain contacts exclude bonded/adjacent backbone atoms"}
'''

PYMOL_MAP_INFO = r'''
name = %(name)r
if name and name not in cmd.get_names("public_objects"):
    raise ValueError("no object named %%r (have: %%s)" %% (name, ", ".join(cmd.get_names("public_objects"))))
out = {"maps": [], "isosurfaces": []}
for o in cmd.get_names("public_objects"):
    if name and o != name:
        continue
    t = cmd.get_type(o)
    if t == "object:map":
        d = {"name": o, "type": "map"}
        try:
            h = cmd.get_volume_histogram(o)
            d["min"], d["max"], d["mean"], d["sd"] = [round(float(x), 4) for x in h[:4]]
        except Exception as e:
            d["error"] = str(e)
        try:
            f = cmd.get_volume_field(o, copy=0)
            d["grid_size"] = [int(x) for x in f.shape]
        except Exception:
            pass
        try:
            ext = cmd.get_extent(o); d["extent"] = [[round(x, 1) for x in ext[0]], [round(x, 1) for x in ext[1]]]
        except Exception:
            pass
        out["maps"].append(d)
    elif t in ("object:mesh", "object:surface", "object:volume", "object:slice"):
        d = {"name": o, "type": t.split(":")[1]}
        try:
            d["level"] = round(float(cmd.isolevel(o, 0.0, query=1)), 4)
        except Exception as e:
            d["level_error"] = str(e)[:120]
        out["isosurfaces"].append(d)
result = out
'''

PYMOL_ALIGNMENT_INFO = r'''
aln, n = %(aln)r, %(n)d
if aln not in cmd.get_names("all"):
    raise ValueError("no alignment object %%r; run align/super/cealign with object_name first" %% aln)
raw = cmd.get_raw_alignment(aln)
info = {}
objs = set()
for pair in raw:
    for model, idx in pair:
        objs.add(model)
for m in objs:
    cmd.iterate("%%" + m, "_d[(model, index)] = (chain, resn, resi, name)", space={"_d": info})
seen = {}
atom_pairs_total = 0
for pair in raw:
    if len(pair) < 2:
        continue
    (m1, i1), (m2, i2) = pair[0], pair[1]
    a, b = info.get((m1, i1)), info.get((m2, i2))
    if not a or not b:
        continue
    atom_pairs_total += 1
    key = ("%%s/%%s/%%s%%s" %% (m1, a[0], a[1], a[2]), "%%s/%%s/%%s%%s" %% (m2, b[0], b[1], b[2]))
    is_ca = a[3] == "CA" and b[3] == "CA"
    if key in seen and (seen[key]["atom"] == "CA" or not is_ca):
        continue
    try:
        d = cmd.get_distance("%%s and index %%d" %% (m1, i1), "%%s and index %%d" %% (m2, i2))
    except Exception:
        d = None
    seen[key] = {"a": key[0], "b": key[1], "atom": "CA" if is_ca else a[3], "distance": round(d, 2) if d is not None else None}
pairs = list(seen.values())
ca_pairs = [p for p in pairs if p["atom"] == "CA"]
result = {"alignment": aln, "objects": sorted(objs), "atom_pairs_total": atom_pairs_total,
          "residue_pairs_total": len(pairs), "ca_pairs": len(ca_pairs), "pairs": pairs[:n],
          "worst_pairs": sorted([p for p in ca_pairs if p["distance"] is not None], key=lambda p: -p["distance"])[:10],
          "note": "distances are CA-CA where both residues have a CA in the alignment; residue_pairs_total can differ from "
                  "align's residues_aligned because the alignment object stores atom pairs after refinement"}
'''

PYMOL_SET_SETTING = r'''
name, value, sel = %(name)r, %(value)r, %(sel)r
try:
    cmd.get_setting_tuple(name)
except Exception:
    raise ValueError("unknown setting %%r" %% name)
names_ = {i: n for n, i in cmd.get_color_indices(all=1)}
def _dec(v):
    if isinstance(v, (list, tuple)) and len(v) == 1:
        v = v[0]
    if (name.endswith("color") or name == "bg_rgb") and isinstance(v, int):
        if v >= 0x40000000:
            return {"name": "rgb", "rgb": [(v >> 16) & 255, (v >> 8) & 255, v & 255]}
        if v >= 0:
            t = cmd.get_color_tuple(v)
            return {"name": names_.get(v, "index_%%d" %% v), "rgb": [int(round(x * 255)) for x in t] if t else None}
        return {"name": "default", "rgb": None}
    if isinstance(v, (list, tuple)) and len(v) == 3 and all(isinstance(x, float) for x in v) and (name.endswith("color") or name == "bg_rgb"):
        return {"name": "rgb", "rgb": [int(round(x * 255)) for x in v]}
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, (list, tuple)):
        return [round(x, 4) if isinstance(x, float) else x for x in v]
    return v
obj_names = set(cmd.get_names("objects"))
bare = sel.strip().lstrip("%%").strip() if sel else ""
scope = "global" if not sel else ("object" if bare in obj_names else "atoms")
def _read():
    if scope == "global":
        return cmd.get_setting_tuple(name)[1]
    if scope == "object":
        return cmd.get_setting_tuple(name, bare)[1]
    vals = []
    cmd.iterate(sel, "_v.append(getattr(s, _n, None))", space={"_v": vals, "_n": name})
    uniq = []
    for v in vals:
        if v not in uniq:
            uniq.append(v)
    return uniq
try:
    old = _read()
except Exception:
    old = None
if scope == "global":
    cmd.set(name, value)
elif scope == "object":
    cmd.set(name, value, bare)
else:
    n_atoms = cmd.count_atoms(sel)
    if n_atoms == 0:
        raise ValueError("selection %%r matches no atoms" %% sel)
    cmd.set(name, value, sel)
try:
    new = _read()
except Exception:
    new = None
if scope == "atoms":
    result = {"setting": name, "selection": sel, "scope": "atoms", "atoms": cmd.count_atoms(sel),
              "old_values": [_dec(v) for v in (old or [])][:10], "new_values": [_dec(v) for v in (new or [])][:10],
              "note": "atom-level values (unique per atom); None means the atom inherits the object/global value"}
else:
    result = {"setting": name, "selection": sel, "scope": scope, "old": _dec(old), "new": _dec(new)}
'''
