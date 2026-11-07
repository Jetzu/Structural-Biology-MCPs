---
name: attributes-and-defattr
title: Custom attributes with setattr and .defattr files (colour, select, list by attribute)
app: chimerax
description: Attach per-atom/residue/chain/model values (scores, conservation, categories) with setattr or .defattr files, colour/size/worm by attribute with palettes and ranges, select and list by attribute (info), export with save attrName, verify with residue_table
tags: attribute, defattr, setattr, byattribute, palette, range, info, conservation, custom data, select by attribute
---
Use for "colour by my scores / conservation / ddG", "load this per-residue CSV onto the structure",
"select residues with score > 2", "which attributes exist", "tag residues as core/loop". Built-in
numeric attributes (`bfactor`, `occupancy`, `area` from `measure sasa`, `mapvalue` from `measure
mapvalues`, `c_alpha_distance` from `alphafold match`, `overlap` from `clashes setAttrs true`) use the
same commands; B-factor/pLDDT recipes are in `representations-and-colouring` and
`alphafold-esmfold-predictions`; attribute-test spec syntax (`@@`, `::`, `//`, `##`) is in
`atom-spec-cheat-sheet`. Verified on ChimeraX 1.11.1.

## 1. One value for a set of items: `setattr`
`setattr spec level name value [create true] [type color|boolean|integer|float|string]`
Levels: `atoms`, `residues`, `chains`, `structures` (atomic models), `bonds`, `pseudobonds`, `groups`, `surfaces`, `models`.
```
setattr #1/A:50-60 residues myscore 8.0 create true     # new attribute: create true is mandatory
setattr #1/A:30-35 residues myscore 2.5                 # existing attribute: plain assignment
setattr #1/A:1-20 residues region core create true      # string (guess: name ends in color → colour; true/false → boolean; else int, float, string)
setattr #1 residues flagged false create true; setattr (ligand :< 5 & protein) residues flagged true
setattr #1/A chains chainlab main create true           # //chainlab=main
setattr #1 structures note "wild type" create true      # ##note="wild type"
setattr #1/A:1-10 atoms bfactor 99.5                    # overwrite a built-in (back it up first, section 5)
```
Names: letters, digits, underscores, no leading digit. Values with spaces need quotes. A new name
without `create true` fails: "Not creating attribute 'x'; use 'create true' to override".

## 2. Many values at once: a `.defattr` file
Format: whole-line `#` comments, control lines `key: value` (nothing else on the line), assignment
lines = TAB spec TAB value. ONE attribute per file, ONE value type per attribute.
```
# numeric per-residue scores, every line must match exactly one residue
attribute: myscore
recipient: residues
match mode: 1-to-1
none handling: None
	/A:1	0.1
	/A:2	0.5
	/A:3	9
	/A:41	none
```
```
# string categories; specs may match many residues (default match mode: any)
attribute: region
recipient: residues
	/A:1-20	core
	/A:21-40	loop
	:lys	"276"
```
Control lines: `attribute` (required; new or existing name), `recipient` = `atoms` (default) |
`residues` | `chains` | `structures` | `bonds` | `pseudobonds`, `match mode` = `any` (default) |
`non-zero` | `1-to-1` (a line matching 0 items, or 2+ items for 1-to-1, aborts the whole file),
`none handling` = `None` (default: the value `none`/`None` means unassigned) | `string` | `delete`.
Values: integer, float, `true`/`false`, string (quote strings that look numeric: `"276"`); a name ending
in `color` takes colour values. Any spec works (`#1/A:10-20`, `:lys`, `@CA`); model numbers in specs
are needed only when several models are open. Load it:
```
open ~/scores.defattr                                   # assigns values; opens no model
open ~/scores.defattr log true                          # one "Selector … matched …" line per assignment
open ~/scores.defattr format defattr models #2          # restrict to model #2; format when the suffix differs
```
(`defattr file` still works but logs a deprecation warning.) Write the file from a CSV/dict with the
`python` tool, then `open` it; the file is a shareable, reloadable record:
```python
import csv
rows = list(csv.DictReader(open("/path/scores.csv")))      # columns: chain,resnum,score
with open("/path/scores.defattr", "w") as f:
    f.write("attribute: myscore\nrecipient: residues\nmatch mode: 1-to-1\n")
    for r in rows:
        f.write("\t/%s:%s\t%s\n" % (r["chain"], r["resnum"], r["score"]))
run("open /path/scores.defattr")
result = {"written": len(rows)}
```
Computed values straight from Python (register first, otherwise the attribute is dropped from sessions):
```python
from chimerax.atomic import Residue, all_atomic_structures
Residue.register_attr(session, "dist_to_lig", "my-analysis", attr_type=float)
for r in all_atomic_structures(session)[0].residues:
    r.dist_to_lig = float(r.number) * 0.1                   # any per-residue number
```

## 3. Colour, size, worm by attribute
`color byattribute [a:|r:|c:|m:]name spec [target …] [palette p] [range lo,hi] [average residues] [noValueColor c] [transparency %]`
```
color byattribute myscore #1 palette bluered range 0,10 target c      # default palette bluered, default range full
color byattribute r:myscore #1 palette ^rdylbu-5 range 0,10 target acs  # prefix when a name exists at two levels
color byattribute myscore #1 palette 0,blue:5,white:10,red noValueColor gray   # value,colour pairs; unassigned → gray
color byattribute myscore #1 palette 0,blue:4.99,blue:5,red:10,red target c    # discrete bins (same colour per bin)
color byattribute charge_est #1 palette redblue range -0.5,0.5 target a average residues   # atom attribute, residue mean
key bluered :0 :5 :10 pos 0.05,0.05 size 0.3,0.04       # legend with the `key` command (labels-keys-and-measurements)
size byattribute myscore #1 min:1 max:3 style ball noValueRadius 1   # VDW radius from values (value:radius pairs)
worm myscore #1 min:0.25 max:2.0; ~worm                  # cartoon radius from values (= cartoon byattribute)
color ::region=loop gold target c; color ::flagged red   # string/boolean attributes: colour by spec test instead
```
Palettes: `palette list` (bluered, redblue, rainbow, grayscale, ColorBrewer `rdylbu-7`, `ylorrd-5`,
`^name` reverses, `c1:c2:c3`); an unknown name such as `viridis` triggers a web fetch that fails. Items
without a value keep their colour unless `noValueColor` is given. The log reports the real range
("134 residues, atom myscore range 0.1 to 9"): reuse it for `key` and for `range` on a second model.

## 4. Select and inspect by attribute
```
select ::myscore>5; select ::myscore>=2 & ::myscore<8    # residues; @@ atoms, // chains, ## models
select ::^myscore                                        # residues WITHOUT the attribute (unassigned)
select ::region=loop | ::region="core"; select ::flagged; select ##note="wild type"
info selection level residue attribute myscore           # values of the selection
info residues #1/A:1-10 attribute myscore                # "residue id /A:1 myscore 0.1 index 0"
info atoms #1/A:1 attribute charge_est; info chains #1 attribute chainlab; info models #1 attribute note
info resattr; info atomattr; info bondattr               # attribute names per level (custom ones included)
info residues #1 attribute myscore saveFile ~/vals.txt   # the same lines into a file
label #1/A:1-10 residues attribute myscore height 0.8    # show the values in 3D
```
Items holding the value `None` print `None`; items that never got the attribute (and a misspelt
attribute name) print nothing, without an error. `info` writes to the log, so read the `output`
field of `run`.

## 5. Save and restore
```
save ~/myscore.defattr attrName r:myscore models #1       # reloadable file (match mode 1-to-1 by default)
save ~/sel.defattr attrName myscore selectedOnly true matchMode any modelIds false
save ~/bfactor_backup.defattr attrName bfactor models #1  # before overwriting bfactor; `open` restores it
save ~/work.cxs                                           # sessions keep registered attributes (setattr/defattr/register_attr)
```
Writing scores into `bfactor` (`setattr … atoms bfactor v`, or a file with `attribute: bfactor`) makes
them travel in `save x.pdb` and show up as `b_mean` in `residue_table`.

## 6. Verify
- `run` output: "Assigned attribute 'myscore' to 11 residues using match mode: 1-to-1"; `setattr` →
  "Assigning myscore attribute to 3 items" ("… to 0 items" = spec matched nothing); `select` →
  "44 atoms, … 6 residues … selected" (0 or "Nothing selected" = wrong spec or misspelt name);
  `color byattribute` → the range line; `save … attrName` → "Saved attribute 'myscore' of 25
  residues using match mode: 1-to-1 to <path>".
- `selection_info("::myscore>5")` → the matching residues; `info residues … attribute` → exact values.
- `residue_table(spec="#1/A")` → `ribbon_rgb` / `atom_rgb` per residue must run from the low to the high
  palette colour in value order; unassigned residues keep the old colour (or `noValueColor`); `b_mean`
  holds the values only if they were written into `bfactor`. Custom attributes are not table columns.
- `render` → `palette` contains the palette end colours; `compare_renders` before/after → changed pixels.

## Pitfalls
- Assignment lines MUST start with a tab and separate spec and value by a tab; spaces give "Line N …
  is missing initial tab". Trailing `# comments` on control lines are read as part of the value
  ("Illegal control value"). With `match mode: 1-to-1` a line matching 0 or 2+ items aborts the file
  ("Selector (/A:999) on line 5 … matched nothing" / "… matched multiple residues"): fix the line
  and open it again.
- Several `attribute:` blocks in one file are broken in 1.11.1: the earlier blocks get assigned
  under the LAST block's attribute name and match mode. Write one file per attribute.
- Never mix strings and numbers in one attribute (a `loop` line in a numeric file, or `setattr …
  myscore abc` later: `setattr` does not type-check). The log says "Re-registration of attr …
  changes type information", then `::myscore>5` raises a TypeError and `color byattribute` says
  "No known/registered numeric attribute". Every `.defattr` load re-registers the type from that
  file's values, so reload a clean numeric file to repair it.
- `save … attrName` works for atom, residue and structure attributes; a chain attribute fails with
  a TypeError in 1.11.1 (store chain labels on residues instead if you need to export them).
- Colour-valued custom attributes (name ending in `color`, or `type color`) break `save x.cxs` in
  1.11.1 ("Unable to restore numpy.ndarray"): store a category string/number and colour by spec test.
- `color byattribute` needs int/float attributes; strings raise "No known/registered numeric
  attribute". The default `range` is computed per model and includes ligands/solvent carrying values.
- A `range` overrides value-based palettes (`alphafold`, `0,blue:10,red`): the colours are respread.
- `average residues` applies to atom attributes only; residue attributes already colour whole residues.
- `key true` on `color byattribute` runs `key <palette> :lo :mid :hi showTool true` for you (labels
  from `range` if given, else from the data range; in the GUI it also opens the Color Key panel).
  For your own labels, position or size run `key` yourself afterwards.
- Python attributes set without `register_attr` work in specs now but vanish after a session reload.
- `setattr` on `bfactor`/`occupancy`/`radius` overwrites real data for the session; keep a backup file.
