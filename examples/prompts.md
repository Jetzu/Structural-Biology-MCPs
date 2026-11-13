# Prompts to copy

Ask these in Claude Code, Codex or the Agent Chat panel inside PyMOL or ChimeraX. The right-hand column lists the
tools an agent typically uses; it reads the matching skill first for non-trivial jobs.

## Figures

| prompt | app | tools |
|---|---|---|
| Make a publication figure of ubiquitin (1UBQ): cartoon coloured by secondary structure, Lys48 and Lys63 as labelled sticks, white background. | PyMOL | `skill`, `run`, `render` |
| Render the current view at 2400x1800 with a transparent background for a slide, and check nothing is cut off. | either | `render`, `analyze_image` |
| Make a three-panel figure of 1UBQ: cartoon, surface and B-factor putty, same orientation in every panel. | PyMOL | `skill`, `run`, `get_view`, `set_view`, `render` |
| Colour the AlphaFold model of human p53 by pLDDT and label the domains that are confidently predicted. | ChimeraX | `run`, `residue_table`, `render` |
| Record a 360° rotation movie of the current scene as an MP4. | either | `skill`, `run` |

## Looking without vision

| prompt | app | tools |
|---|---|---|
| Is the ligand visible in the current view, or hidden behind the protein? | either | `layout` (`occlusion=True`) |
| Show haemoglobin (4HHB) with each chain in its own colour, then tell me how much of each chain is visible and which chains hide each other. | PyMOL | `run`, `layout` |
| Did my last command change anything on screen? | either | `compare_renders` |
| Check this figure I saved (`~/Desktop/figure.png`): is anything clipped, and is the contrast good enough for print? | either | `analyze_image` |
| What did I just do in the PyMOL window? | PyMOL | `events`, `scene` |

## Structure analysis

| prompt | app | tools |
|---|---|---|
| Superpose closed (1AKE) and open (4AKE) adenylate kinase, colour them differently and give me the RMSD. | PyMOL | `align`, `alignment_info`, `render` |
| Which residues of barnase contact barstar (1BRS)? Give me the polar contacts only. | either | `contacts`, `residue_table` |
| Show the hydrogen bonds between biotin and streptavidin (1STP) and list the residues involved. | ChimeraX | `skill`, `run`, `contacts`, `render` |
| How large is the buried surface area of the 1BRS interface? | ChimeraX | `skill`, `run` (`measure buriedarea`) |
| Mutate Lys48 of ubiquitin to arginine, pick the best rotamer and tell me whether it clashes. | either | `mutate`, `render` |
| Give me the sequence of every chain in 4HHB with residue numbering. | either | `sequence` |
| Which residues of this AlphaFold model have pLDDT below 50? | either | `residue_table` |

## Maps and density

| prompt | app | tools |
|---|---|---|
| Show the 2mFo-DFc density of ubiquitin at 1.5 sigma around the Ile44 hydrophobic patch as a carved mesh. | PyMOL | `skill`, `run`, `map_info`, `set_isolevel`, `render` |
| Open the GroEL cryo-EM map EMD-1080 as a surface coloured radially from its centre, side view. | ChimeraX | `run`, `render` |
| Fit the 1PRW model into EMD-1080 and report the correlation. | ChimeraX | `skill`, `run`, `wait_for_jobs` |

## Sessions and several windows

| prompt | app | tools |
|---|---|---|
| Save the current session and a PDB of chain A to my Desktop. | either | `save_file` |
| I have two PyMOL windows open; load 1UBQ in the one named "work". | PyMOL | `status`, `connect`, `run` |
| Remember how you made this figure as a skill so you can do it again next time. | either | `save_skill` |
