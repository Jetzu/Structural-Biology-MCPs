---
name: sequence-viewer-and-blast
title: Sequence viewer, alignments and BLAST
app: chimerax
description: Show chain sequences (sequence chain), make or open alignments (sequence align / Clustal Omega, MUSCLE, FASTA, UniProt), associate structures with alignments, superimpose from an alignment (sequence match), colour by conservation / RMSD / identity (color byattribute seq_conservation), run blastprotein searches, wait with wait_for_jobs and load the hits
tags: sequence, alignment, blast, blastprotein, conservation, seq_conservation, uniprot, clustal, muscle, jobs, wait_for_jobs
---
Use for "show the sequence", "align these sequences", "colour by conservation", "find homologues /
templates with BLAST", "which residues are conserved". Web services (Clustal, MUSCLE, BLAST, UniProt)
need internet. Syntax verified against the ChimeraX 1.11.1 docs, source and headless runs.
Structure-based superposition itself is in `structure-alignment`; AlphaFold/ESMFold DB searches in
`alphafold-esmfold-predictions`; colour keys in `labels-keys-and-measurements`.

## 1. Sequences and alignment identifiers
```
sequence chain #1/A                       # Sequence Viewer panel for one chain (GUI); one chain per command
sequence chain #1/A viewer false          # data only, no panel (several chains only if their sequences are identical)
```
Every alignment gets an identifier, logged as an info line "Alignment identifier is X" (it is in the
`run` output). `sequence chain #1/A` → `1/A`; `sequence align` and `matchmaker … showAlignment true`
share one counter → `1`, `2`, …; a file → its file name with extension (`fam.aln`) unless `ident` is
given; UniProt → the identifier you typed. A sequence inside an alignment is `ID:name` or `ID:index`
(`fam:1`, `fam:-1`); use the index when names contain spaces (`1ubq, chain A` from matchmaker) and
drop the `ID:` part only when a single alignment is open. The viewer is a GUI panel: it never appears
in `render`; read its data via the log, saved files, residue attributes, the `python` tool (§8) or the
MCP `sequence` tool (one-letter sequences of any spec without any panel).

## 2. Make, open, save alignments
```
sequence align #1/A,#2/A,#3/A                  # Clustal Omega web service, blocks until done → new alignment
sequence align #1/A,#2/A program muscle        # MUSCLE5
sequence align fam:1,P0CG48:1,ubb_mouse        # sequence-specs, UniProt accessions/names, pasted sequences
sequence align fam replace true                # realign alignment fam in place (keeps its id)
open ~/fam.fasta ident fam viewer false        # .fasta .aln .msf .pir .sth .hssp; ident names it; viewer false = no panel
open ~/fam.fasta ident raw autoAssociate false viewer false   # this alignment never auto-associates (sequence files only)
open P0CG48 from uniprot associate #1/A        # UniProt sequence + features, forced association; no viewer option
matchmaker #2 to #1 showAlignment true         # pairwise alignment with RMSD header (see structure-alignment)
save ~/fam.aln alignment fam                   # formats: aln, fasta, pir
sequence header fam conservation save ~/cons.txt     # per-column header values (also rmsd, consensus)
```
The chain-spec form and the sequence/UniProt form of `sequence align` cannot be mixed in one list
(`#1/A,P0CG48:1` fails with "Must specify 2 or more protein sequences"): put the structure sequences
into an alignment first (chains-only `sequence align`, or a saved FASTA) and use `ID:index` specs
for everything.

## 3. Sequence–structure association
Open structure chains associate automatically with any sequence they match (≤ 1/10 mismatches).
The "Associated 1ubq chain A to … with 0 mismatches" message is a status-bar line and is NOT in the
`run` output: check associations with §8 or `info residues #1/A:1-3 attribute seq_identity`.
Only associated chains receive residue attributes, selections and `sequence match`. Force or remove:
```
sequence associate #1/A fam:1              # chain → named sequence (forced, any mismatch count)
sequence associate #2/A                    # best match in every open alignment
sequence dissociate #1/A fam
sequence update #1/A alignment fam         # write the full sequence into a coordinate-only model
```
`autoAssociate false` is an option of sequence-file `open` (per alignment, §2), not of structure
files (`open x.pdb autoAssociate false` → "'autoAssociate' has no suffix"); no session-wide switch.

## 4. Superimpose from an alignment, compare sequences
```
sequence match fam #2/A #3/A to #1/A                 # CA/C4' fit on aligned columns, 2 Å iterative pruning
sequence match fam #2-3/A to #1/A                    # same; a comma list "#2/A,#3/A" is rejected
sequence match fam #2/A to #1/A cutoffDistance none  # no pruning
sequence match fam #2/A to #1/A conservation 0.8     # only columns with ≥ 80 % identity; 1.11.1 takes a FRACTION
sequence match fam #2/A to #1/A columns 10,11,12,20  # explicit columns (no ranges)
sequence identity fam                                # all-vs-all % identity → info lines in output
sequence identity fam:1 fam:2 denominator nongap
select #1/A:30-40; sequence expandsel fam            # selection → same columns in every associated chain
```
`conservation 80` (percent, as the docs say) raises "No atoms paired for alignment". The RMSD line
("RMSD between 72 pruned atom pairs is 0.659 angstroms; (across all 74 pairs: 0.808)") is a
status-bar message: read the `run` reply's `value` instead, one 5-tuple per match chain (match
atoms, ref atoms, pruned RMSD, full RMSD, transform), or run the command from `python`.

## 5. Header residue attributes (assigned to associated chains)
| attribute | from | values |
|---|---|---|
| `seq_conservation` | conservation header; computed even while hidden; shown by default for new multi-sequence alignments | AL2CO Z-score (default style; typically −2…+2.5); `identity histogram` style: 0–1 fraction |
| `seq_clustal_conservation` | conservation header in `Clustal characters` style | strings `*` `:` `.` ` ` (not colourable; `seq_conservation` keeps its last numbers) |
| `seq_rmsd` | rmsd header, created when first shown (≥ 2 associated structures; `matchmaker showAlignment` shows it); not updated while hidden | Å per column, None where < 2 structures |
| `seq_identity` | automatic for ≥ 2 sequences | % of the column holding the most common residue (0–100) |
| `seq_consensus` | consensus header while shown | one-letter strings (not colourable) |
```
sequence header fam conservation setting style "identity histogram"   # or AL2CO, "Clustal characters"
sequence header fam conservation setting al2co_cons 0        # 0 entropy, 1 variance, 2 sum-of-pairs
sequence header fam conservation setting al2co_window 3      # sliding window; al2co_gap 0.5 (max gap fraction); al2co_freq 0-2
sequence header fam rmsd show                                # creates seq_rmsd; also hide, save <file>
sequence header conservation hide                            # no id → every open alignment
info residues #1/A attribute seq_conservation                # per-residue values → info lines in output
```

## 6. Conservation colouring
```
color byattribute seq_conservation #1 palette cyanmaroon target c            # AL2CO: auto range over the spec
color byattribute seq_conservation #1,2 palette -1.5,white:2,maroon target cs noValueColor gray
color byattribute seq_conservation #1 palette 0,white:1,red                  # identity-histogram style (0–1)
color byattribute seq_rmsd #1 palette bluered range 0,3                      # structural divergence
color byattribute seq_identity #1 palette 0,red:100,blue
select #1 & ::seq_conservation>1; show sel atoms                             # invariant core
select ::seq_rmsd>2                                                          # divergent loops
key cyanmaroon :low : :high pos 0.05,0.05 size 0.3,0.04                      # 3 colours → 3 labels; match the palette used
```
"134 residues, atom seq_conservation range -0.47 to 2.09" is a status-bar line (not in `run`
output): take the range from §8 (or `info residues … attribute seq_conservation`) and set
`range`/palette stops from it. Residues without a value (unassociated chains, gap-only columns) keep
their colour unless `noValueColor` is given. An attribute whose header was never shown gives "No
known/registered numeric attribute seq_rmsd". For `color byattribute` details see
`representations-and-colouring`.

## 7. BLAST searches and loading hits
```
blastprotein #1/A                                        # chain query, PDB, BLOSUM62, E ≤ 1e-3, 100 seqs, results table
blastprotein #1/A database alphafold maxSeqs 50 cutoff 1e-10 name ubq
blastprotein fam:1 database nr                           # sequence from an open alignment (slow database)
blastprotein P0CG48 database uniref50                    # UniProt accession/name, or a pasted sequence
blastprotein #1/A log true                               # also list hits in the log (name, E-value, score, title)
blastprotein #1/A showResultsTable false loadStructures true onlyBest true   # fetch every hit (one per PDB entry), matchmaker onto #1
blastprotein #1/A showResultsTable false showSequenceAlignment true onlyBest true   # hits + query → alignment "blast-nogui alignments"
```
Databases: `pdb` (default), `nr`, `alphafold`, `esmfold`, `uniref100|90|50`; matrices BLOSUM45–90,
PAM30/70/250, IDENTITY. `loadStructures`/`showSequenceAlignment` act only together with
`showResultsTable false` (with the table shown, fetch hits from the table: double-click or context
menu). `run` returns as soon as the job is submitted; results arrive seconds (pdb) to minutes (nr) later:
1. `wait_for_jobs(timeout_seconds=600)` blocks until `session.tasks` has no running job.
2. The finishing callback (results table, structure loading, log table) runs only after the tool
   returns, so call `scene` or `log` next: new models in `scene`; "BLAST results for:" hit lines,
   "Opened N models, skipped M sequence-only results" and "Webservices job id: …" in `log`.
3. `taskman list` / `taskman kill N` in `run` list and abort jobs ("BlastProtein Job, ID 1").
The results table is a GUI panel (double-click a row: fetch + superimpose one hit); loaded
AlphaFold/ESMFold hits are coloured by confidence. A nogui ChimeraX only logs the hit table.
Alternatives: `alphafold search #1/A` (`alphafold-esmfold-predictions`); `sequence search #1/A`
(MMseqs2 via the RCSB service) answered HTTP 415 when tested.

## 8. Unavoidable Python (`python` tool): alignments, associations, value summary
```python
import numpy as np
out = []
for ident, aln in session.alignments.alignments_map.items():
    assoc = {"#%s/%s" % (c.structure.id_string, c.chain_id): s.name
             for c, s in aln.associations.items() if c.structure}      # closed chains linger briefly
    out.append({"id": ident, "seqs": [s.name for s in aln.seqs], "length": len(aln.seqs[0]),
                "associated": assoc, "headers": [(h.ident, h.shown) for h in aln.headers]})
from chimerax.atomic import AtomicStructure
m = [s for s in session.models.list(type=AtomicStructure) if s.id_string == "1"][0]
v = np.array([getattr(r, "seq_conservation", np.nan) for r in m.residues], float)
result = {"alignments": out, "conservation": {"n": int(np.isfinite(v).sum()), "mean": float(np.nanmean(v)),
          "range": [float(np.nanmin(v)), float(np.nanmax(v))],
          "top10": [int(r.number) for r, x in zip(m.residues, v) if np.isfinite(x) and x >= np.nanpercentile(v, 90)]}}
```

## 9. Verify
- `output` of `sequence align`/`open`: "Alignment identifier is X". Associations are not in the
  output: the §8 `associated` map must list every chain you expect (a missing chain has no
  attributes → `sequence associate`).
- After `color byattribute`: `residue_table` shows the ribbon colours; `render` → `palette` contains
  both palette ends; the value range comes from §8 `range`.
- After BLAST: `wait_for_jobs` result → every job `done`; then `scene` lists the new models and
  `log` the hit table; `layout by="model"` confirms the hits are superimposed on the query.

## Pitfalls
- Alignment ids are positional (`1`, `2`, …) and shared by `sequence align` and matchmaker: read them
  from the log. A wrong id in `sequence header` is parsed as a header name and fails with
  "Should be one of 'consensus', 'conservation', or 'rmsd'".
- `sequence match … conservation` expects 0–1 in 1.11.1 although the docs say percent; its chain list
  is space-separated (`#2/A #3/A`) or a range (`#2-3/A`), never comma-separated.
- `seq_rmsd`/`seq_consensus` need their header shown once; `seq_conservation`/`seq_identity` always
  exist for associated chains. Hidden headers keep stale values (`sequence header ID rmsd show` refreshes).
- Attributes are per alignment: a chain in two alignments keeps the values of the last one
  computed (`sequence refreshAttrs ID`). Closing a structure drops its associations (the sequences
  stay in the alignment); the `sequence chain` alignment of a closed chain closes with it.
- Status-bar messages (association, `sequence match` RMSD, colour range, "BlastProtein finished.")
  never appear in `run` output or `log`; info lines do.
- `blastprotein … loadStructures true` on a multimer hit list opens every chain copy unless
  `onlyBest true`; nr searches can take many minutes. If a job is `done` but neither hit lines nor
  models appear, the result download failed inside ChimeraX ("'bytes' object has no attribute
  'items'" on the console): rerun the command.
- `wait_for_jobs` holds the ChimeraX main thread (GUI frozen meanwhile): submit all jobs first, then wait once.
