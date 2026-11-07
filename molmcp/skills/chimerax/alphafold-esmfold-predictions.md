---
name: alphafold-esmfold-predictions
title: AlphaFold and ESMFold predictions
app: chimerax
description: Fetch AlphaFold Database / ESM Atlas models (by UniProt or by matching open structures), run predictions, colour by pLDDT confidence (palette alphafold/esmfold) with a colour key, plot and use PAE (domains, contacts), hide low-confidence regions, measure deviation from experiment
tags: alphafold, esmfold, plddt, pae, prediction, confidence, uniprot, colabfold
---
Use for "get the AlphaFold model of …", "colour by confidence", "show the PAE plot", "predict this
sequence". Fetches need internet. Syntax verified against the ChimeraX 1.11 docs.

## 1. Get models
```
alphafold fetch P29474                         # AlphaFold DB (v4) by UniProt accession or name
open P29474 from alphafold                     # same thing
alphafold fetch P29474 alignTo #1/A trim true  # superimpose on an open chain, same chain ID, trimmed
alphafold match #1                             # one model per protein chain of #1, superimposed (matchmaker)
alphafold match #1/A,B trim false pae true     # full length, also fetch the PAE matrix
alphafold search #1/A                          # BLAST the AlphaFold DB → hit list panel (GUI)
esmfold fetch MGYP000542242899                 # ESM Metagenomic Atlas by MGnify id
esmfold match #1                               # k-mer search of the atlas, superimposed
alphafold predict #1/A                         # ColabFold on Google Colab (browser sign-in; minutes–hours)
alphafold predict SEQ1,SEQ2                    # multimer: comma-separated, no spaces, ≥16 residues each
esmfold predict #1/A                           # ESM Atlas server, ≤ 400 residues
```
Fetched files are cached in `~/Downloads/ChimeraX/AlphaFold/` (`ignoreCache true` re-downloads).
`alphafold match` logs per chain: UniProt id, RMSD, length, seen, % identity, and assigns the
residue attributes `c_alpha_distance`, `missing_structure`, `same_sequence` on the prediction.

## 2. Confidence colouring (pLDDT is stored in the B-factor column)
```
color bfactor #2 palette alphafold               # 0 red, 50 orange, 70 yellow, 90 cornflowerblue, 100 blue
color bfactor #2 palette alphafold target c      # cartoon only
color bfactor #3 palette esmfold                 # ESMFold pLDDT is 0–1
color bfactor #2 palette alphafold range 50,100  # spread the colours over a narrower range
key alphafold :0 :50 :70 :90 :100 pos 0.05,0.05 size 0.3,0.04 fontSize 18    # 5 labels for 5 colours
key red:low orange: yellow: cornflowerblue: blue:high
2dlabels text "pLDDT" xpos 0.05 ypos 0.1 size 18
```
Hide or de-emphasise low confidence:
```
hide @@bfactor<50 cartoons                       # probably disordered
color @@bfactor<70 gray target c; transparency @@bfactor<70 70 target c
select @@bfactor<50; info selection level residue
```
```python
from chimerax.atomic import AtomicStructure
s = [m for m in session.models.list(type=AtomicStructure) if m.id_string == "2"][0]
b = s.residues.existing_principal_atoms.bfactors          # one pLDDT per residue (CA)
result = {"n": int(len(b)), "mean_plddt": float(b.mean()), "frac_ge90": float((b >= 90).mean()),
          "frac_ge70": float((b >= 70).mean()), "frac_lt50": float((b < 50).mean())}
```

## 3. Deviation from an experimental structure (after `alphafold match` / `esmfold match`)
```
color byattribute c_alpha_distance #2 palette bluered range 0,5 target c     # Å per residue
color byattribute c_alpha_distance #2 palette 0,blue:2,white:5,red
hide #2 & ::missing_structure cartoons                                        # absent in the experiment
```

## 4. PAE (predicted aligned error)
```
alphafold pae #2 uniprotId P29474                 # fetch + plot the PAE matrix for model #2 (GUI plot)
alphafold pae #2 file ~/Downloads/model_pae.json  # local JSON (AlphaFold/ColabFold/AF3), .npz (Boltz), .npy (Chai)
open ~/model_pae.json structure #2                # same via open (format pae)
alphafold pae #2 colorDomains true                # cluster into rigid domains → residue attribute pae_domain
alphafold pae #2 colorDomains true minSize 10 connectMaxPae 5 cluster 0.5
color #2 & ::pae_domain=1 red target c            # recolour one domain
alphafold contacts #2/A toAtoms #2/B distance 8   # inter-chain pseudobonds coloured by PAE (plot must be open)
alphafold contacts sel palette blue:red range 1,5 maxPae 10
key pae :0 : : :15 : : :30                        # colour key matching the pae palette
```
PAE plots are GUI panels (not in `render`); the pseudobond colouring is.

## 5. Typical figure
```
alphafold fetch P29474; hide atoms; cartoon
color bfactor #1 palette alphafold; set bgColor white; lighting soft; graphics silhouettes true
key alphafold :0 :50 :70 :90 :100 pos 0.65,0.05 size 0.3,0.04
view; save ~/af_plddt.png width 2000 supersample 3
```

## 6. Verify
- `scene` → new model named after the UniProt id; `model_info` → chains and residue ranges.
- `output` of `alphafold match` holds the table (RMSD, % identity) — report those numbers.
- `render` → `palette` dominated by blue/cornflower blue for a confident model; much orange/red
  means low confidence. `layout by="chain"` for multimer predictions.
- `selection_info("@@bfactor<50")` → how many residues are low confidence.

## Pitfalls
- Palette `alphafold` is value-based (0–100); a `range` overrides those values (colours spread
  evenly over the range).
- ESMFold pLDDT is 0–1: use `palette esmfold`, not `alphafold`.
- `alphafold match` superimposes and trims by default (`trim false` keeps full length) and gives
  the model the chain ID of the matched chain.
- Experimental B-factors are not confidences: do not apply `palette alphafold` to them.
- `alphafold predict` needs a Google account and a browser; results land in
  `~/Downloads/ChimeraX/AlphaFold/prediction_N` and open automatically when done.
