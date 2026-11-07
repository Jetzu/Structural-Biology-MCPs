---
name: alphafold-plddt
title: AlphaFold / predicted models: load and colour by confidence (pLDDT)
app: pymol
description: Fetch AlphaFold DB models, colour by pLDDT with the standard palette, hide low-confidence regions, compare with experimental structures
tags: alphafold, plddt, confidence, prediction, colouring
---
When to use: the user mentions AlphaFold, ESMFold, a predicted model, pLDDT, confidence or a UniProt accession.

1. Load a model. AlphaFold DB files store pLDDT in the B-factor column.
   ```
   fetch AF-P69905-F1, type=cif, async=0
   ```
   (`AF-<UniProt>-F1`; use `load /path/model.pdb` for local predictions; ColabFold/ESMFold PDBs also put pLDDT in `b`.)
   If the download fails, run: `python` tool → `cmd.load("https://alphafold.ebi.ac.uk/files/AF-P69905-F1-model_v4.cif", "AF-P69905-F1")`.
2. Standard AlphaFold colouring (very high ≥ 90 dark blue, confident 70–90 light blue, low 50–70 yellow, very low < 50 orange):
   ```
   set_color af_vhigh, [0.0, 0.325, 0.839]
   set_color af_high,  [0.396, 0.741, 0.949]
   set_color af_low,   [1.0, 0.859, 0.075]
   set_color af_vlow,  [1.0, 0.490, 0.271]
   color af_vhigh, b > 90
   color af_high,  b > 70 and b < 90.01
   color af_low,   b > 50 and b < 70.01
   color af_vlow,  b < 50.01
   show cartoon
   ```
   Alternative continuous ramp: `spectrum b, red_yellow_green_blue, AF-P69905-F1, minimum=50, maximum=90`.
3. Hide or de-emphasise disordered regions (common for figures):
   ```
   hide cartoon, b < 50
   set cartoon_transparency, 0.6, b < 70
   ```
   Report what you hid: `measure(kind="count", selection1="AF-P69905-F1 and name CA and b < 50")` gives the residue count.
4. Find low-confidence residues as a list: `residue_table(selection="AF-P69905-F1 and name CA and b < 50")` (b_mean = pLDDT).
5. Compare with an experimental structure: `fetch 1a3n, async=0` then `align(mobile="AF-P69905-F1", target="1a3n and chain A")`
   (sequence-based alignment is right for the same protein; use method="super" for homologues). Colour the experimental
   structure grey (`color grey70, 1a3n`) so the pLDDT palette stays readable.
6. PAE (predicted aligned error) is not in the structure file; say so if asked, and offer to colour by domain instead.
7. Verify with `render`: dominant colours should be the four palette names (density/skyblue/yellow/orange families);
   the `palette` list in the analysis confirms the mapping before you report.
