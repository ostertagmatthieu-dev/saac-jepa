# SAAC-JEPA V2 — public data survey

State of the search: **2026-09-16**. Machine-readable companions: [candidates.csv](candidates.csv) (one row per machine × dataset) and [search_log.csv](search_log.csv) (every query with its hit count). The rows, levels and roles below are generated from one data file, so the CSV and this page agree by construction.

This is a planning document for V2. It reads metadata, data papers and file headers only. No dataset was downloaded in full and no statistic was computed on any candidate, so every candidate can still serve as a sealed target.

---

## 1. Summary

- **The V1 transfer stays inside one machine family.** The THWS source (Martinez et al., 2025) was recorded on a Spinner U5-620 and the FH JOANNEUM target (Brillinger et al., 2025) on a Spinner U5-630. Both machines run Siemens 840D sl, and the JOANNEUM export uses the same SINUMERIK Edge signal addresses as the other Sinumerik candidates [S03, S04, S21]. V1 transfers across machines of one builder and one controller family. Other builders and controllers are untested.
- **The JOANNEUM target (Brillinger et al., 2025) is no longer sealed.** It was read twice (the locked pass and the RevIN ablation) [S01]. V2 needs a new target that nobody on the team has opened.
- **The search found 53 candidate rows covering 47 machine identities.** Of these, 35 are unseen machine tools in Tier 1–2, and Tier 1 alone spans seven controller families: Siemens, Heidenhain, Fagor, Hurco, Haas, ISG and a Rockwell collector. 16 further sources are excluded with a reason. The search stopped at saturation: the last two query rounds brought no new source or target candidate.
- **Recommended sealed target: KIT DMG Mori CMX 600 V (Ströbel et al., 2025b).**
  - 54 runs under CC BY 4.0.
  - The same SINUMERIK Edge export as Ströbel et al. (2025a), whose signal list is verified. All 10 transfer channels and the commanded speeds are therefore expected; the list is inferred and must be confirmed before sealing.
  - Paired-test power is 0.95 for d = 0.5 with 54 runs. V1 had 0.20 with 7 runs (§2).
  - KIT DMC 60 H (Ströbel et al., 2025a, 32 runs) is the replication target.
- **Recommended new sources.**
  - The JOANNEUM Spinner U5-630, extended with 23 never-read runs (Abdul Hadi, 2021).
  - A large SINUMERIK machine that also logs the motor temperatures of the THWS source (Sáinz de la Maza et al., 2025).
  - Three MTConnect machines (Kim et al., 2026).
  - The Michigan mill (Sun, n.d.).
  - The three LUH machines (Denkena et al., 2023, M1–M3), which include a Heidenhain controller.
- **Action tests.** The Michigan mill (Sun, n.d.) varies the feed on purpose. The JOANNEUM machine has 12 spindle-power levels (Abdul Hadi, 2021). MU-TCM (Peralta Abadia et al., 2025) varies speed and feed but needs a ≥ 10 Hz grid. The ISW feed-drive datasets (ISW Stuttgart, 2025) test actions at axis level.
- **The strongest planning / causal candidates.**
  - MU-TCM (Peralta Abadia et al., 2025): measured flank wear.
  - LUH (Denkena et al., 2023, M1–M3): flank wear on three machines.
  - The LUH lathe (Denkena et al., 2026): roughness and diameter as outcomes.
  - causRCA (Mehling et al., 2025): the only public machine-tool data with a reference causal graph.
- **The main risks.**
  - Channel semantics across vendors (load %, target torque, clamp-on currents).
  - The 1 Hz grid, which removes short-run datasets.
  - NC-ND licences on four KIT datasets.
  - KIT download terms that a person must accept.

## 2. What V2 needs

Research questions, derived from paper §7–§8:

| # | Question | Role |
|---|---|---|
| RQ1 | Which public machines let training span several machines, so invariance is measured rather than assumed (§7 i)? | **S** source |
| RQ2 | Which unseen machine can be a new sealed target with enough statistical power? | **T** target |
| RQ3 | Which data vary the commands on purpose, to re-test action use? V1 found that shuffling actions moved target RMSE by < 0.005 (§8). | **A** action bench |
| RQ4 | Which data link actions to a measured outcome, for planning and off-line policy evaluation (§7 iii–iv, App. F)? | **P** planning |
| — | Sensor-only series without actions, for representation pretraining. | **X** |

Minimum requirements (gates) per role:

| Role | Requirement |
|---|---|
| S | Public access; ≥ 1 canonical channel, or a shared new channel (load %, positions); actions direct or derivable; ≥ 1 h usable at 1 Hz (the THWS source has 8.3 h) |
| T | Machine not used in V1; ≥ 5 canonical channels; actions present; **≥ 15 independent units**; windows at 1 Hz |
| A | Designed variation (≥ 3 levels) of at least one action, with drive signals or setpoints |
| P | Actions plus a measured outcome (wear, quality, deformation, root cause) |
| X | Continuous series without actions |

Why 15 units: a Node port of `scripts/09_transfer_power_analysis.py` [S60] uses the same method: 20,000 Monte-Carlo draws, paired t-test, two-sided α = 0.05.

| Independent units | Power at d = 0.8 | Power at d = 0.5 | Smallest exact sign-flip p |
|---|---|---|---|
| 7 (JOANNEUM target, V1) | 0.43 | 0.20 | 1.6e-2 |
| 10 | 0.62 | 0.30 | 2.0e-3 |
| **15** | **0.83** | 0.45 | 6.1e-5 |
| 20 | 0.93 | 0.57 | 1.9e-6 |
| 32 (Ströbel et al., 2025a) | 0.99 | 0.79 | 4.7e-10 |
| 54 (Ströbel et al., 2025b) | 1.00 | **0.95** | 1.1e-16 |

## 3. Method

The search ran in five layers. Every query and its hit count is in [search_log.csv](search_log.csv).

| Layer | What was searched | Volume |
|---|---|---|
| L1 API | DataCite, 10 queries in EN/DE/FR plus 3 publisher snowballs (KIT, LUIS, DaRUS); OpenAIRE, 10 queries; MDPI *Data* through Crossref, 3 queries | 562 DataCite hits → 269 unique titles → 145 keyword-relevant → ≈ 55 metadata records read |
| L2 data papers | *Data in Brief* and *Scientific Data* 2015–2026 through Europe PMC | 127 unique papers |
| L3 snowball | OpenAlex, forward and backward citations of 8 seed data papers (Martinez et al., 2025; Brillinger et al., 2025; Ströbel et al., 2025a; Denkena et al., 2023; Abdul Hadi, 2021; Schmitt & Engelmann, 2024; Kim et al., 2026; Peralta Abadia et al., 2025) | 43 citing works, 51 references |
| L4 portals and lists | KAMP, NIST SMS Test Bed, NASA PCoE, PHM Society / IEEE DataPort, three curated lists | 7 checks |
| L5 web | ≈ 20 searches (EN/KO), including Kaggle; Kaggle API licence checks | — |
| Round 2 | 5 DataCite queries on controller vocabulary (Edge, NCU, Heidenhain/Fanuc/Haas…, OPC UA, drive currents, digital twin) | no new S/T candidate |

**Stopping rule.** The search stops after two consecutive rounds without a new source or target candidate. Round 2 and the final L5 round met that rule.

**Evidence levels.** Each row states one of the following:
- **Repository:** the DataCite, Zenodo, Mendeley, KIT or Kaggle API record.
- **Paper:** a peer-reviewed data paper, read through PMC.
- **Sample header:** a file header read under the user's approval. Only two partial reads were approved: the first 2 MB of one Abdul Hadi (2021) JSON file and the 1.8 MB features file of Piecuch & Żabiński (2025).
- **Secondary:** a curated list or blog.

Anything absent from those sources is written **n.d.**, never guessed.

**Limitations of this survey.**
- The Zenodo search and record API answered HTTP 504 all day. Zenodo DOIs are covered through DataCite metadata, but full-text search was not possible.
- MDPI and Nature pages refused scripted access, so PMC mirrors were used instead.
- KIT RADAR downloads require accepting terms of use. They were not accepted, so the Ströbel et al. (2025a, 2025b) signal list comes from the data paper.
- Some page summaries were produced by a small model. Every claim that carries weight was checked against the DataCite record or a PMC text, and one such summary proved wrong (a paper licence reported as the data licence).

## 4. Scoring

**Gates.**
- G1: public access with usable terms.
- G2: real time series, not per-part aggregates.
- G3: the role requirements of §2.

**Levels (0–3), one per criterion.**

| Criterion | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| overlap `ov` | no canonical channel | 1–2 or unverified | 3–6 | ≥ 7 of the 17 canonical channels |
| actions `ac` | absent | run-level setpoints only | derivable (actual speed, positions) | commanded signals recorded |
| regime `rg` | constant | observational production | varied, levels n.d. | designed, ≥ 3 levels |
| windows `wn` (48 s at 1 Hz) | none | not documented | 1–5 h | ≥ 5 h |
| units `un` | ≤ 2 | 3–6 or n.d. | 7–14 | ≥ 15 |
| outcomes `oc` | none | model-generated labels | energy, anomaly labels | measured wear / quality / deformation / root cause |
| licence `li` | none or restricted | NC / ND / conflict | SA or partly missing | CC BY, CC0, PD, BSD, Apache |
| provenance `pv` | none | repository text only | detailed documentation | data paper + NC code / units |
| integration `ic` | inaccessible | > 20 GB or gated | moderate formats (JSON, HDF5, MAT) | small CSV/XLSX |

**Role scores.** Each score is a weighted mean of levels, on a 0–3 scale. It only orders candidates *after* the gates.

| Role | Weights |
|---|---|
| S | ov .30, ac .20, wn .20, li .10, ic .10, pv .10 |
| T | ov .25, ac .20, un .25, wn .10, li .10, pv .10 |
| A | rg .35, ac .25, ov .15, wn .10, li .15 |
| P | oc .35, ac .25, rg .15, un .15, li .10 |

**Sensitivity analysis.** Every weight is multiplied by an independent U(0.5, 1.5) draw, 2,000 times. The table in §6 reports how often each top-5 member stays in the top 5.

## 5. Comparison table

`?` after a role means the role holds once the missing duration is documented. Levels are listed in the order ov/ac/rg/wn/un/oc/li/pv/ic. The full field set, with notes, is in [candidates.csv](candidates.csv).

### V1 references

| Reference | Machine (controller) | Dataset · DOI | Licence | Canon. ch. | Actions | Regime | Rate · usable at 1 Hz | Units | Outcomes | Levels | Roles | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Martinez et al. 2025** | Spinner U5-620 (5-axis, lab) (Siemens 840D sl) | THWS five-axis production data set (V1 source) · [10.5281/zenodo.14094887](https://doi.org/10.5281/zenodo.14094887) | CC BY 4.0 | 17 | direct (spindle speed, X/Y/Z feed) | production-like changeover matrix | 1 Hz · 26,879 windows | 62 sessions | phase labels | 3/3/1/3/3/1/3/3/3 | V1 source | S01, S02, S03 |
| **Brillinger et al. 2025** | Spinner U5-630 (5-axis) (Siemens 840D sl v4.8 + Simatic IPC227E edge) | FH JOANNEUM CNC machining data repository (V1 target) · [10.17632/gtvvwmz7r7.2](https://doi.org/10.17632/gtvvwmz7r7.2) | CC BY 4.0 | 10 | direct (CMD_SPEED) | mixed parts/materials | 500 (2 ms, per publisher) Hz · 2,457 windows | 7 runs | energy | 3/3/2/2/2/2/3/3/3 | V1 target | S01, S02, S04 |

### Tier 1 — controller or drive signals

| Reference | Machine (controller) | Dataset · DOI | Licence | Canon. ch. | Actions | Regime | Rate · usable at 1 Hz | Units | Outcomes | Levels | Roles | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Ströbel et al. 2025a** | Deckel Maho DMC 60 H (3-axis horizontal, retrofitted) (Siemens SINUMERIK 840D + SINUMERIK Edge) | KIT Multimodal Dataset 1 (process monitoring / anomalies) · [10.35097/hvvwn1kfwf7qt48z](https://doi.org/10.35097/hvvwn1kfwf7qt48z) | CC BY 4.0 | 10 | direct (CMD_SPEED per axis and spindle) | varied parts, tools, strategies, depths and widths of cut; 3 materials | 500 Hz · many (runs 99-1,191 s) | 32 experiments (paper) / 33 (repository) | 8 anomaly types incl. tool wear, chatter | 3/3/2/3/3/2/3/3/1 | S T A? | S05, S06 |
| **Ströbel et al. 2025b** | DMG Mori CMX 600 V (3-axis vertical) (Siemens SINUMERIK 840D + SINUMERIK Edge) | KIT Multimodal Dataset 2 · [10.35097/vnnu3n9z7ndsnhfd](https://doi.org/10.35097/vnnu3n9z7ndsnhfd) | CC BY 4.0 | 10 | direct (CMD_SPEED, same app as Ströbel et al. (2025a)) | industrial components, tools and strategies; 3 materials | 500 Hz · n.d. (likely many) | 54 experiments | labelled pictures | 3/3/2/1/3/2/3/2/1 | S? T? A? | S07, S06 |
| **Ströbel et al. 2023a** | DMG Mori CMX 600 V (Siemens Industrial Edge (SINUMERIK)) | KIT training and validation dataset 1 (time-series prediction) · [10.35097/1462](https://doi.org/10.35097/1462) | CC BY-NC-ND 4.0 🟠 | 0 | n.d. (NC-driven) | train part + validation part, steel and aluminium, with/without workpiece (aircut) | 500 Hz · n.d. | several recordings (n.d.) | none | 1/1/2/1/1/0/1/2/2 | — | S08 |
| **Ströbel et al. 2023b** | Deckel Maho DMC 60 H (Siemens Industrial Edge (retrofit)) | KIT training and validation dataset 2 (same series as dataset 1) · [10.35097/1738](https://doi.org/10.35097/1738) | CC BY-NC 4.0 🟠 | 0 | n.d. (NC-driven) | same experimental series as Ströbel et al. (2023a), built for cross-machine transfer | 500 Hz · n.d. | several recordings (n.d.) | none | 1/1/2/1/1/0/1/2/2 | — | S09 |
| **Ströbel et al. 2024** | CMX 600 V and DMC 60 H (Siemens Industrial Edge) | KIT training and validation dataset 3 (standardised CSV + simulated inputs) · [10.35097/fefwiljideoropmh](https://doi.org/10.35097/fefwiljideoropmh) | CC BY-NC-ND 4.0 🟠 | 0 | n.d. | training part and validation part, steel and aluminium, aircut | 500 Hz · n.d. | n.d. | none | 1/1/2/1/1/0/1/2/3 | — | S10 |
| **Ströbel et al. 2025c** | Deckel Maho DMC 60 H (retrofitted, Kistler 9255C) (Siemens Industrial Edge) | KIT part series dataset (time-series prediction) · [10.35097/ctvuj6dgzepzmk0g](https://doi.org/10.35097/ctvuj6dgzepzmk0g) | CC BY-NC-ND 4.0 🟠 | 0 | NC codes document the varied setpoints | designed variations of depth of cut, feed rate and spindle speed on 3 geometries x 2 materials | 500 Hz · n.d. | n.d. (3 geometries x 2 materials x variations) | none | 1/2/2/1/1/0/1/2/2 | — | S11 |
| **Schlagenhauf et al. 2023** | n.d. (KIT wbk milling machine) (n.d. (JSON export at 500 Hz)) | Multivariate time series of milling 16MnCr5 (anomaly detection) · [10.35097/1398](https://doi.org/10.35097/1398) | CC BY 4.0 | 0 | feed 191 vs 1,150 mm/min by tool type (metadata) | 7 runs, 2 tool diameters, HSS vs solid carbide, fixed 3 mm depth | 500 Hz · n.d. | 7 runs (11 zip files) | workpiece anomalies, tool breakage | 1/1/1/1/1/2/3/2/2 | — | S12 |
| **Denkena et al. 2023 · M1** | DMG Mori Milltap 700 (ball screws) (Siemens Sinumerik 840D sl) | LUH IFW milling with varying tool wear and machine tools (M1) · [10.17632/zpxs87bjt8.3](https://doi.org/10.17632/zpxs87bjt8.3) | CC BY 4.0 | 4 | feed derivable from tool_position; commanded speed/feed not included | identical parameters on all machines (ap = 2 mm); tool wear varies | 500 Hz · n.d. (one operation per file) | 9 tools over M1-M3 (split n.d.); ≈2,147 files on M1 (paper summary) | flank wear VB (interpolated between measurements) | 2/2/0/1/1/3/3/3/2 | S? P | S13, S14 |
| **Denkena et al. 2023 · M2** | DMG Mori HSC 30 linear (direct drives) (Siemens Sinumerik 840D sl) | LUH IFW milling dataset (M2) · [10.17632/zpxs87bjt8.3](https://doi.org/10.17632/zpxs87bjt8.3) | CC BY 4.0 | 1 | feed derivable from tool_position | identical parameters; tool wear varies | 500 Hz · n.d. | 9 tools over M1-M3 (split n.d.); ≈2,136 files on M2 | flank wear VB | 1/2/0/1/1/3/3/3/2 | S? P | S13, S14 |
| **Denkena et al. 2023 · M3** | DMG Mori HSC 55 linear (direct drives) (Heidenhain iTNC 530) | LUH IFW milling dataset (M3) · [10.17632/zpxs87bjt8.3](https://doi.org/10.17632/zpxs87bjt8.3) | CC BY 4.0 | 1 | feed derivable from tool_position | identical parameters; tool wear varies | 500 Hz · n.d. | 9 tools over M1-M3 (split n.d.); ≈2,135 files on M3 | flank wear VB | 1/2/0/1/1/3/3/3/2 | S? P | S13, S14 |
| **Kim et al. 2026 · Hurco VM20i** | Hurco VM20i (3-axis) (Hurco WinMax + MTConnect) | Purdue MSM multi-sensor + MTConnect (imi_vm20i) · [10.34740/kaggle/ds/8392825](https://doi.org/10.34740/kaggle/ds/8392825) | CC BY 4.0 | 0 | spindle speed + override; feed derivable from positions | lab plan: several feeds, depths, widths, up/down milling, 3 materials | ≈1 (MTConnect) Hz · yes (≈3 h) | n.d. (experiment units in label.csv) | normal / abnormal / tool defect labels | 1/2/2/2/1/2/3/3/2 | S | S15 |
| **Kim et al. 2026 · Hurco VMX30Ui** | Hurco VMX30Ui (5-axis) (Hurco WinMax + MTConnect) | Purdue MSM (imi_vmx30ui) · [10.34740/kaggle/ds/8392825](https://doi.org/10.34740/kaggle/ds/8392825) | CC BY 4.0 | 0 | spindle speed + override; feed derivable | lab plan as Kim et al. (2026, Hurco VM20i) | ≈1 Hz · yes (≈1.6 h) | n.d. | labels | 1/2/2/2/1/2/3/3/2 | S | S15 |
| **Kim et al. 2026 · Haas VF-10** | Haas VF-10 (3-axis, production) (Haas NGC + MTConnect adapter) | Purdue MSM (tmf_vf10) · [10.34740/kaggle/ds/8392825](https://doi.org/10.34740/kaggle/ds/8392825) | CC BY 4.0 | 0 | spindle speed; feed derivable | production (observational) | ≈1 Hz · yes (≈3.3 h) | n.d. | labels (97.5 % normal) | 1/2/1/2/1/2/3/3/2 | S | S15 |
| **Sun n.d.** | CNC mill, SMART testbed (model n.d.) (n.d. (Rockwell Cloud Collector Agent)) | CNC Mill Tool Wear (University of Michigan) · [Kaggle](https://www.kaggle.com/datasets/shasun/tool-wear-detection-in-cnc-mill) | CC0 (Public Domain) | 7 | direct (CommandVelocity per axis and spindle) | designed: feed rate × clamp pressure (2.5/3.0/4.0 bar) × tool condition | 10 Hz · few | 18 experiments | tool worn/unworn, passed visual inspection, completed | 3/3/3/1/3/2/3/1/3 | S? T? A | S16, S17 |
| **Schmitt & Engelmann 2024** | HERMLE C600 U (5-axis, contract manufacturer) (Heidenhain iTNC 530) | THWS series production data set for 5-axis CNC milling · [10.5281/zenodo.10853254](https://doi.org/10.5281/zenodo.10853254) | CC BY 4.0 | 0 | FeedRate (path) + SpindleSpeed | series production (observational), 13 series with changeovers | n.d. Hz · n.d. | 13 production series | up to 23 phase labels | 0/2/1/1/2/1/3/3/3 | — | S18, S19 |
| **Abdul Hadi 2021** | Spinner U5-630 (FH JOANNEUM, V1 target machine) (Siemens 840D sl v4.8 + Simatic IPC227E) | HF-dataset from Edge Device (2021) · [10.17632/w35nf2fw5m.1](https://doi.org/10.17632/w35nf2fw5m.1) | CC BY 4.0 | 10 | direct (CMD_SPEED) | 12 spindle-power input levels (2.5-20 kW) at fixed 10,000 rpm; 2 parts | 500 Hz · yes (≈150 per file, estimate) | 23 experiments | energy | 3/3/2/2/3/2/3/3/2 | S A? | S20, S21, S04 |
| **Wuwer & Brillinger 2021** | Spinner U5-630 (FH JOANNEUM, V1 target machine) (NCU (Sinumerik 840D sl)) | Energy consumption for a CNC machining process (2021) · [10.17632/7cghj7fffp.1](https://doi.org/10.17632/7cghj7fffp.1) | CC BY 4.0 | 10 | direct (NCU, as Abdul Hadi (2021)) | 2 parts | n.d. (NCU raw) Hz · n.d. | 2 parts | energy per NC line | 2/2/1/1/0/2/3/2/2 | S? | S22, S21, S04 |
| **Peralta Abadia et al. 2025** | LAGUN L1000 (vertical machining centre) (Fagor CNC 8065) | MU-TCM face-milling dataset · [10.48764/3hdp-gf23](https://doi.org/10.48764/3hdp-gf23) | CC BY 4.0 | 9 | actual speed/feed + designed setpoints | designed: vc 50/100/200 m/min × f 0.05-0.2 mm/rev × VB 0-0.3 mm × 2 materials | 250 Hz · 0 (4-36 s cutting per test) | 32 experiments | flank wear VB (measured) | 3/2/3/0/3/3/3/3/2 | A P | S23 |
| **Duo et al. 2019** | Lagun vertical machining centre (model n.d.) (n.d.) | Drilling test data from new and worn bits · [10.48764/myma-ys63](https://doi.org/10.48764/myma-ys63) | CC BY 4.0 | 0 | fixed per geometry | fixed cutting conditions; wear varies | 250 Hz · 0 (one hole per file) | 90 holes | tool wear level | 1/1/0/0/3/3/3/2/3 | P | S24 |
| **Vicomtech n.d.** | CNC lathe (model n.d., Mondragon facilities) (n.d.) | Vicomtech machine tool wear dataset · [GitHub](https://github.com/Vicomtech/dataset-machine-tool-wear) | CC BY-SA 4.0 🟠 | 3 | programmed feed + spindle speed | 13 tools | n.d. Hz · 0 (1 s segments) | 13 tools | remaining useful life | 2/2/1/0/2/3/2/2/3 | P | S25 |
| **Dreyer et al. 2026** | Micro5 (5-axis micro machine, <10 kg moving mass) (ISG kernel (kinematics type 57)) | Machining quality prediction (AE, accelerometers, axis currents) · [10.5281/zenodo.6505073](https://doi.org/10.5281/zenodo.6505073) | CC BY-NC-ND 4.0 🟠 | 4 | n.d. (spindle 33,000 rpm) | milling direction, stair count, lubrication | 1000 Hz · n.d. | 6 experiments | machining quality | 2/1/1/1/1/3/1/2/2 | P | S26 |
| **Sáinz de la Maza et al. 2025** | Large 5-axis machining centre, RLLLR (84 kW head, C table), model n.d. (Siemens SINUMERIK 840D sl) | Large scale machine tool axes heating data · [10.5281/zenodo.16579804](https://doi.org/10.5281/zenodo.16579804) | CC BY 4.0 | 10 | derivable (actual speeds, positions) | programmed heating cycles (details n.d.) | 1 Hz · likely many (1 Hz native) | 3 days | thermal deformation (IDS), temperatures | 3/2/1/2/1/3/3/2/3 | S P | S27 |
| **Dominguez Caballero et al. 2023** | DMG Mori DMU 40 eVo linear (5-axis) (n.d.) | Sensor signals for machine tool and process health assessment · [10.15131/shef.data.24125715.v1](https://doi.org/10.15131/shef.data.24125715.v1) | CC BY 4.0 | 0 | feed and spindle override reductions (6-10 %) in the fingerprint routine | interventions: heavy/unbalanced tool, override, misalignment, cracks, wear; spindle 5,000 / 12,000 rpm | n.d. Hz · n.d. | 24 workpieces + routine repeats | fault class labels | 0/1/2/1/3/2/3/2/1 | — | S28, S62 |
| **Piecuch & Żabiński 2025** | Haas VF-1 (3-axis) (Haas + Beckhoff C6920 acquisition) | Open milling dataset for tool life (Rzeszów) · [10.6084/m9.figshare.28589216](https://doi.org/10.6084/m9.figshare.28589216) | CC BY 4.0 | 4 | cycle metadata only (ADOC, RDOC) | ADOC 5/10 mm × RDOC 4.5/8 mm, optimal and non-optimal | 500 (currents) Hz · n.d. | 14 tools, 968 cycles | tool life to failure | 2/1/2/1/2/3/3/3/1 | P | S29 |

### Tier 2 — mostly external sensors

| Reference | Machine (controller) | Dataset · DOI | Licence | Canon. ch. | Actions | Regime | Rate · usable at 1 Hz | Units | Outcomes | Levels | Roles | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Li et al. 2024** | DX-650 high-speed CNC mill (n.d.) | JUST_CAS multi-sensor milling dataset · [10.17632/8jk3kyxmbn.1](https://doi.org/10.17632/8jk3kyxmbn.1) | CC BY 4.0 | 1 | setpoints as metadata | designed: 5,000-10,000 rpm × 800-1,600 mm/min × depth × width; 2 materials | 50000 Hz · 0 (1 s samples) | 115 samples | n.d. | 1/1/3/0/3/0/3/3/3 | A | S30 |
| **Li Y. 2021** | milling machine (n.d.; "DMU" appears only in a user comment) (n.d.) | Tool wear dataset of NUAA_Ideahouse · [10.21227/3aa1-5e83](https://doi.org/10.21227/3aa1-5e83) | CONFLICT: CC BY 4.0 (DataCite) vs "copyright reserved" (page) 🟠 | 2 | controller data (n.d.) | sidewall (fixed) and closed pockets (continuously varying engagement) | n.d. Hz · n.d. | n.d. | tool wear | 1/1/2/1/1/3/1/2/2 | P | S31 |
| **Pratap et al. 2024** | CNC machining centre (model n.d.) (n.d.) | Digital Twin for CNC Power Dataset · [10.17632/4m9n7zzvwk.1](https://doi.org/10.17632/4m9n7zzvwk.1) | CC BY 4.0 | 0 | designed setpoints | designed: 5 spindle speeds (S1920-S2450) × feeds × 5 depths (ap1-ap5) | n.d. Hz · n.d. | dozens of cut/aircut runs | power consumption | 1/1/3/1/2/2/3/2/3 | A? | S32 |
| **Anas uddin et al. 2024** | CNC milling machine (model n.d.) (n.d.) | Print+Mill Dataset · [10.5281/zenodo.12793026](https://doi.org/10.5281/zenodo.12793026) | CC BY 4.0 | 1 | feed, spindle speed | multi-material | n.d. Hz · n.d. | n.d. | workpiece images | 1/2/1/1/1/2/3/1/2 | S? | S33 |
| **Tapia Fernandez et al. 2024** | Ibarmia THR-16 and GMTK VR 2.4 (n.d.) | Milling tests in 2 machining centres: energy consumption · [10.5281/zenodo.14445879](https://doi.org/10.5281/zenodo.14445879) | CC BY 4.0 | 0 | n.d. | milling tests Jul-Nov 2023 | n.d. Hz · n.d. | n.d. | energy | 0/0/1/1/1/2/3/1/2 | X | S34 |
| **Tnani et al. 2022** | 3 production machining centres (M01, M02, M03) (n.d.) | Bosch CNC Machining dataset · [GitHub](https://github.com/boschresearch/CNC_Machining) | BSD-3-Clause (repository) | 0 | absent | production, 2018-2021 | 2000 Hz · n.d. | 3 machines × 15 operations | good / bad labels | 0/0/1/1/2/2/3/3/3 | X | S40 |
| **Agogino & Goebel 2007** | Matsuura MC-510V (n.d.) | NASA PCoE Milling data set · nasa-pcoe:milling | no explicit licence (use at own risk, cite) 🟠 | 1 | setpoints as metadata | designed: DOC 1.5/0.75 mm × feed 413/206.5 mm/min × 2 materials | n.d. in sources read Hz · n.d. | 16 cases | flank wear VB | 1/1/2/1/3/3/1/2/3 | P | S41 |
| **PHM Society 2010** | Röders Tech RFM760 (n.d.) | PHM 2010 data challenge · ieee-dataport:2010-phm-society-conference-data-challenge | restricted / unclear 🔴 | 0 | constant (10,400 rpm, 1,555 mm/min) | constant parameters | 50000 Hz · n.d. | 6 cutters × 315 cuts | flank wear | 0/0/0/1/1/3/0/2/1 | — | S42 |
| **Rizwan 2026** | SANJI VMC 650 (3-axis) (n.d. (external Arduino DAQ)) | Spindle vibration and current, low-cost DAQ · [10.5281/zenodo.21608173](https://doi.org/10.5281/zenodo.21608173) | CC BY 4.0 | 1 | constant (1,800 rpm, 1,500 mm/min) | constant, production | n.d. Hz · n.d. | 24 tool-wear cycles | tool wear cycle | 1/0/0/1/3/3/3/1/2 | X | S43 |
| **Denkena et al. 2026** | IFW lathe (model n.d.) (n.d.) | Multivariate time series for surface roughness and dimensional error in turning · [10.25835/9xffqwnc](https://doi.org/10.25835/9xffqwnc) | CC BY 3.0 | 0 | designed setpoints | designed: feed × cutting speed × depth × material | n.d. Hz · n.d. | n.d. (per cut) | surface roughness + diameter deviation per cut | 1/1/3/1/1/3/3/2/2 | A? P | S45 |
| **Harigovind et al. 2025** | Kirloskar Turnmaster 40 lathe (n.d.) | Sensor-based turning dataset for surface roughness · [10.17632/ybyhxv4czd.3](https://doi.org/10.17632/ybyhxv4czd.3) | CC BY 4.0 | 0 | setpoints as metadata | designed 3 × 3 × 3: 400/630/1,000 rpm × 0.05/0.1/0.16 mm/rev × 0.2/0.4/0.6 mm | n.d. Hz · n.d. | 27 runs | surface roughness | 0/1/3/1/3/3/3/3/3 | A? P | S48 |
| **Schibsdat 2026** | TUHH IPMT CNC lathe (model n.d.) (n.d.) | ExtraDrey tool wear experiment dataset · [10.15480/882.17237](https://doi.org/10.15480/882.17237) | Public Domain Mark | 0 | fractional factorial setpoints | fractional factorial design, 2 materials | n.d. Hz · 0 (30 s experiments) | n.d. (cutting edges to failure) | max flank wear | 0/1/3/0/1/3/3/2/2 | A? P | S44 |
| **Artabe Zamalloa et al. 2026** | n.d. (n.d.) | Tool wear in drilling of Inconel 718 plates · [10.82518/ttacdo](https://doi.org/10.82518/ttacdo) | CC BY 4.0 | 0 | different cutting conditions per drill | 7 drill bits, varied conditions | n.d. Hz · n.d. | 7 drills | flank wear | 0/1/2/1/1/3/3/1/3 | P | S47 |
| **QIT milling dataset 2024** | n.d. (n.d.) | Milling dataset from QIT (full tool life) · [10.6084/m9.figshare.27323346.v2](https://doi.org/10.6084/m9.figshare.27323346.v2) | CC BY 4.0 | 0 | n.d. | complex circumferential paths | n.d. Hz · n.d. | 68 samples (≈5 M rows each) | wear images and values | 0/0/1/1/3/3/3/1/1 | X | S59 |
| **Inconel 718 BBD dataset 2024** | n.d. (n.d.) | Multi-sensor power prediction, Box-Behnken design · [10.7910/dvn/1g3ssb](https://doi.org/10.7910/dvn/1g3ssb) | CC BY-NC 4.0 🟠 | 0 | designed setpoints | Box-Behnken design, several geometric profiles | n.d. Hz · n.d. | n.d. | power, power per unit material | 1/1/3/1/1/2/1/2/2 | A? | S58 |
| **Haber Guerra et al. 2022** | GAMHE 5.0 pilot line machines (n.d.) (n.d.) | AI for quality control: micro/macro milling · [10.5281/zenodo.6303449](https://doi.org/10.5281/zenodo.6303449) | CC BY 4.0 | 0 | cutting parameters | n.d. | n.d. Hz · n.d. | n.d. | surface roughness | 0/1/1/1/1/3/3/1/2 | P | S50 |
| **CNC Solutions et al. 2025** | CNC machines at 2 sites (CNC Solutions, LMS Patras) (n.d.) | i-CNC chatter vibration dataset · [10.5281/zenodo.15308467](https://doi.org/10.5281/zenodo.15308467) | CC BY 4.0 | 0 | absent | trial events | n.d. Hz · n.d. | 2 files | chatter indicator (model-generated) | 0/0/0/1/0/1/3/1/3 | X | S51 |
| **Denkena et al. 2024** | IFW lathe (model n.d.) (n.d.) | Anomaly detection for hybrid workpieces using DTW · [10.25835/ph65zrpv](https://doi.org/10.25835/ph65zrpv) | CC BY-NC 3.0 🟠 | 0 | n.d. | error-free runs vs artificial grooves | n.d. Hz · n.d. | n.d. | groove location labels | 0/0/1/1/1/2/1/1/2 | X | S46 |

### Tier 3 — adjacent domains

| Reference | Machine (controller) | Dataset · DOI | Licence | Canon. ch. | Actions | Regime | Rate · usable at 1 Hz | Units | Outcomes | Levels | Roles | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **ISW Stuttgart 2025** | ISW five-axis milling machine (feed drives) (frequency inverter, PI velocity + P position) | ISW feedforward / sliding-mode datasets (DaRUS 4513, 3900, 6114, 4746) · [10.18419/darus-4513](https://doi.org/10.18419/darus-4513) | CC BY 4.0 | 0 | direct (designed setpoints, sweeps) | system identification: constant velocities, sweeps, PRBS | n.d. Hz · n.d. | many measurements | tracking error | 1/3/3/1/2/2/3/3/2 | A | S36 |
| **Hinze et al. 2022–2023** | ISW ball screw + linear direct drive test bench (cascaded P-PI / sliding mode) | ISW ball screw datasets (DaRUS 3252, 3292, 3152, 3003, 3109, 2563) · [10.18419/darus-3003](https://doi.org/10.18419/darus-3003) | CC BY 4.0 (2563, 3109); not stated in DataCite for 3252, 3292, 3152, 3003 🟠 | 0 | direct (PRBS, sweeps, disturbance steps) | system identification | n.d. Hz · n.d. | many measurements | tracking error | 0/3/3/1/2/2/2/3/2 | A | S37 |
| **Villoria et al. 2026** | precision ball-screw feed axis bench (servo motion control) | State-dependent ball-screw positioning error dataset · [10.5281/zenodo.22768582](https://doi.org/10.5281/zenodo.22768582) | CC BY 4.0 | 0 | direct (systematically varied kinematics) | designed kinematic conditions | n.d. Hz · n.d. | n.d. | positioning error | 0/3/3/1/1/3/3/2/2 | A P | S38 |
| **Yao 2025** | ball screw test bench (self-sensing motor drive) | Current and vibration signals for ball screw feed drive · [10.21227/5vj0-3132](https://doi.org/10.21227/5vj0-3132) | CC BY 4.0 | 0 | n.d. | healthy vs bent screw | 800 Hz · n.d. | n.d. | health class | 0/0/1/1/1/2/3/1/2 | X | S39 |
| **Mehling et al. 2025** | industrial vertical lathe (KAMAX production; Schuster) (CNC via OPC UA; ISG hardware-in-the-loop twin) | causRCA · [10.5281/zenodo.15876410](https://doi.org/10.5281/zenodo.15876410) | Apache-2.0 | 0 | fault injections in the HIL twin | 170 normal real-operation sets + 100 fault sets (19 scenarios) | event-based Hz · n.d. | 270 datasets | root-cause labels + expert causal graph (92 nodes, 104 edges) | 0/2/3/1/3/3/3/2/2 | A P | S35 |
| **SPARK dataset 2026** | 22 industrial machines incl. DMG Mori DMU 125 monoBLOCK, mills, lathes (n/a (grid meters)) | SPARK high-resolution energy data · [10.35097/bjdg3m3rg5jv3skk](https://doi.org/10.35097/bjdg3m3rg5jv3skk) | CC BY 4.0 | 0 | absent | observational, 1-7 years | 0.2 Hz · no (5 s grid) | 22 machines | none | 0/0/1/0/3/0/3/3/2 | X | S49 |
| **Randomized-load motor dataset n.d.** | industrial AC motors 1-7.5 HP + HVAC motor (variable frequency drive) | Vibration, current, torque, RPM under randomized speed and load · [10.17632/9r82jppsn7.1](https://doi.org/10.17632/9r82jppsn7.1) | CC BY 4.0 | 0 | direct (VFD speed fluctuation 0-16 %, brake load 0/30/60/90 %) | randomized speed and load + faults | 25600-100000 Hz · n.d. | many recordings (>60 GB) | fault class | 0/3/3/1/2/2/3/3/1 | A | S53 |
| **Downs & Vogel 1993** | Tennessee Eastman process (simulation) (simulated plant control) | Tennessee Eastman Process Dataset · [10.21227/n7q3-4b49](https://doi.org/10.21227/n7q3-4b49) | CC BY 4.0 | 0 | direct (manipulated variables) | faults + normal operation | n.d. Hz · n.d. | n.d. | fault labels | 0/3/2/1/2/2/3/2/2 | A? | S54 |
| **Pamplin 2026** | Fanuc M800-iA robot + drilling end-effector (Fanuc 0i-F CNC) | Robotic drilling cycles with anomalies · [10.17639/nott.7629](https://doi.org/10.17639/nott.7629) | CC BY-NC 4.0 🟠 | 0 | fixed (2,000 rpm, 150 mm/min) + anomalies incl. incorrect parameters | 109 normal + 18 anomalous cycles | n.d. Hz · n.d. | 127 cycles | anomaly labels | 0/1/1/1/3/2/1/1/2 | — | S52 |
| **Hedberg et al. 2016** | NIST Manufacturing Lab (Mazak, Hurco) (MTConnect) | SMS Test Bed volatile data stream + query-able repository · [10.18434/t4fk54](https://doi.org/10.18434/t4fk54) | NIST open licence | 0 | MTConnect | observational | event-based Hz · n.d. | n.d. | n.d. | 0/1/1/1/1/0/3/2/0 | — | S55 |
| **KAMP n.d.** | Korean SME CNC equipment (n.d.) (n.d.) | KAMP manufacturing AI datasets (CNC) · portal:kamp-ai.kr | registration; redistribution of original data restricted 🔴 | 0 | setpoints | n.d. | n.d. Hz · n.d. | n.d. | quality | 0/1/1/1/1/2/0/0/0 | — | S56 |

## 6. Role rankings and weight sensitivity

| Role | Pool | Top 5 (score, share of 2,000 weight draws in which the row stays top 5) |
|---|---|---|
| S | 13 | **Ströbel et al. 2025a** 2.80 (100 %) · **Abdul Hadi 2021** 2.70 (100 %) · **Sáinz de la Maza et al. 2025** 2.50 (100 %) · **Sun n.d.** 2.40 (100 %) · **Ströbel et al. 2025b** 2.30 (99 %) |
| T | 3 | **Ströbel et al. 2025a** 3.00 (100 %) · **Ströbel et al. 2025b** 2.70 (100 %) · **Sun n.d.** 2.60 (100 %) |
| A | 17 | **Sun n.d.** 2.80 (100 %) · **Ströbel et al. 2025a** 2.65 (98 %) · **Abdul Hadi 2021** 2.55 (88 %) · **ISW Stuttgart 2025** 2.50 (82 %) · **Ströbel et al. 2025b** 2.45 (48 %) |
| P | 18 | **Peralta Abadia et al. 2025** 2.75 (100 %) · **Mehling et al. 2025** 2.75 (100 %) · **Villoria et al. 2026** 2.70 (100 %) · **Harigovind et al. 2025** 2.50 (100 %) · **Piecuch & Żabiński 2025** 2.20 (12 %) |


**Ströbel et al. (2025a, 2025b) also top the S and A rankings.** V2-A still keeps them as targets, because they are the only unseen machines with the full transfer set and ≥ 15 runs. Without them, the S ranking starts with Abdul Hadi (2021), Sáinz de la Maza et al. (2025), Sun (n.d.) and Kim et al. (2026), and the A ranking with Sun (n.d.), Abdul Hadi (2021) and ISW Stuttgart (2025).

The T pool holds three rows. Ströbel et al. (2025a) is the only one with a documented duration today. Ströbel et al. (2025b) moves from `T?` to `T` once its run durations are read from the RADAR documentation. Sun (n.d.) is a weak target: wax workpieces, runs of 46–233 s, and faulty readings flagged by its authors.

## 7. Channel overlap across machines

`1` means documented in the sources; `?` means inferred from the same export application. The extra columns are candidate *new* vocabulary entries, and none of them may replace a canonical channel (`docs/data.md` §6).

| Machine | sp_I | sp_T | sp_P | x_I | x_T | y_I | y_T | z_I | z_T | z_P | sp_θ | x_θ | y_θ | z_θ | sp_Udc | sp_mod | amb_θ | load% | cmd_pos | act_pos | foll_err | F_axis | I_CT | P_mach | vib | canon. |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| THWS source · Spinner U5-620 (Martinez et al., 2025) | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |  |  |  |  |  |  |  |  | 17 |
| JOANNEUM target · Spinner U5-630 (Brillinger et al., 2025; Abdul Hadi, 2021) | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |  |  |  |  |  |  |  | 1 | 1 | 1 | 1 |  |  |  |  | 10 |
| Ströbel et al. (2025a) KIT DMC 60 H | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |  |  |  |  |  |  |  | 1 | 1 | 1 |  | 1 |  |  | 1 | 10 |
| Ströbel et al. (2025b) KIT CMX 600 V | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? |  |  |  |  |  |  |  | ? | ? | ? |  | 1 |  |  | 1 | 10 |
| Denkena et al. (2023, M1) LUH Milltap 700 |  | 1 |  |  | 1 |  | 1 |  | 1 |  |  |  |  |  |  |  |  |  |  | 1 | 1 | 1 |  |  |  | 4 |
| Denkena et al. (2023, M2) LUH HSC 30 linear |  | 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 1 | 1 | 1 |  |  |  | 1 |
| Denkena et al. (2023, M3) LUH HSC 55 linear (Heidenhain) |  | 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 1 | 1 | 1 |  |  |  | 1 |
| Kim et al. (2026) Purdue Hurco ×2 / Haas |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 1 |  | 1 |  |  |  | 1 | 1 | 0 |
| Sun (n.d.) Michigan SMART | 1 |  | 1 | 1 |  | 1 |  | 1 |  | 1 |  |  |  |  | 1 |  |  |  | 1 | 1 |  |  |  |  |  | 7 |
| Peralta Abadia et al. (2025) MU Lagun L1000 (Fagor) | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |  |  |  |  |  |  |  |  |  |  | 1 |  | 1 |  |  | 1 | 9 |
| Dreyer et al. (2026) HES-SO Micro5 | 1 |  |  | 1 |  | 1 |  | 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 1 | 4 |
| Sáinz de la Maza et al. (2025) CFAA large 840D sl | 1 |  | 1 | 1 |  | 1 |  | 1 |  | 1 | 1 | 1 | 1 | 1 |  |  |  | 1 |  | 1 |  |  |  |  |  | 10 |
| Piecuch & Żabiński (2025) Rzeszów Haas VF-1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 1 |  | 1 | 0 |

Legend: I current, T torque, P power, θ motor temperature, Udc DC-link voltage; the first 10 columns are the V1 transfer set.

Two readings of the matrix:
1. **Outside V1, the full 10-channel transfer set exists only on Ströbel et al. (2025a, 2025b) (inferred).**
   - Peralta Abadia et al. (2025) has 9 of the 10.
   - Sun (n.d.) and Sáinz de la Maza et al. (2025) have 6 each (currents and powers, no torques). Sáinz de la Maza et al. (2025) adds the four motor temperatures that the THWS source has and the JOANNEUM target lacks.
   - The Sinumerik Edge machines share the same addresses (`CURRENT`, `TORQUE`, `POWER`, `CMD_SPEED`, `LOAD`).
2. **`load_pct` connects the MTConnect machines to the Sinumerik cluster.** It appears on the JOANNEUM machine (Brillinger et al., 2025), Ströbel et al. (2025a), Ströbel et al. (2025b), Kim et al. (2026) and Sáinz de la Maza et al. (2025). Its cross-vendor equivalence (drive utilisation versus percent of rated load) must be audited before it enters the schema.

## 8. Findings that change the V2 plan

1. **V1 is intra-builder and intra-controller** (§1). A V2 claim about cross-machine transfer needs at least one non-Siemens controller in the evaluation.
2. **The THWS series-production set (Schmitt & Engelmann, 2024) is not the THWS source machine.** It comes from a HERMLE C600 U with a Heidenhain iTNC 530, in production at a contract manufacturer [S19]. The plan had assumed the opposite. Its verified features are status, feed and spindle speed only.
3. **Two 2021 Mendeley datasets come from the JOANNEUM machine** (Abdul Hadi, 2021; Wuwer & Brillinger, 2021) [S04, S21]. The first adds 23 never-read runs with the same 78-field Edge export, verified from the header. They give the JOANNEUM machine 30+ units for adaptation and action tests, but they are not an unseen machine.
4. **The IPO assumption has written support.** The 2025 and 2021 JOANNEUM data papers (Brillinger et al., 2025; Abdul Hadi, 2021) both state 2 ms (500 Hz) sampling on the IPC227E edge device [S04, S21]. `etl.ds03_ipo_seconds: 0.002` is therefore documented by the publisher, though still not measured: the header field `CycleTimeMs` reads 0. A `HFProbeCounter` exists and can support a measured check during ETL.
5. **KIT runs cross-machine designs on purpose.** Ströbel et al. (2023a, 2023b) are the same experimental series on two machines, published "to enable a study of the transferability of models between machines" [S09]. They make a clean machine-shift control, but under NC / NC-ND licences.
6. **The 1 Hz grid is a filter in its own right.** MU-TCM (9 of the 10 transfer channels, Fagor, clean speed × feed plan) has 4–36 s cuts, and JUST has 1 s samples, so neither yields a 48 s window at 1 Hz. A 10 Hz arm without the THWS source is the only way to use them.
7. **KIT RADAR, KAMP and IEEE DataPort each gate access** (terms, account, subscription). These steps need a human decision and cannot be scripted.

## 9. Recommended V2 data configuration

### Main configuration: V2-A, multi-source with a sealed KIT target

| Part | Rows | Why |
|---|---|---|
| Sources (training and source-only selection) | Martinez et al. (2025); Brillinger et al. (2025) with Abdul Hadi (2021) and Wuwer & Brillinger (2021); Sáinz de la Maza et al. (2025); Kim et al. (2026); Sun (n.d.); Denkena et al. (2023, M1–M3) (conditional on durations) | Up to 10 machines and ≥ 4 controller families (Siemens, Heidenhain, Hurco WinMax, Haas NGC); canonical and load-% channels overlap |
| Sealed target T1 | **Ströbel et al. (2025b)** KIT CMX 600 V | 54 runs, CC BY, full transfer set, commanded speeds; never opened |
| Replication target T2 | **Ströbel et al. (2025a)** KIT DMC 60 H | 32 runs, CC BY; opened only after the T1 pass |
| Kept out of training | Ströbel et al. (2023a, 2023b, 2024, 2025c) and Schlagenhauf et al. (2023) | Same KIT lab and machines as T1/T2 |
| Action bench | Abdul Hadi (2021), Sun (n.d.); Peralta Abadia et al. (2025) (10 Hz arm); ISW Stuttgart (2025) (axis level) | Designed or stepped commands |
| Planning / causal | Peralta Abadia et al. (2025), Denkena et al. (2023, M1–M3), Denkena et al. (2026), Mehling et al. (2025) | Measured outcomes; causal ground truth |

**Sealing procedure for T1 and T2.**
1. Download the files.
2. Record SHA-256 hashes in the lock file.
3. Run a schema-only check that prints column names, row counts and timestamp monotonicity, and no values.
4. Leave every other file closed until the V2 lock, as the V1 protocol did.

The same-lab link between T1 and T2 means that T2 replicates the machine effect, not the lab effect.

**ETL effort.**

| Effort | Rows | Why |
|---|---|---|
| Low | Ströbel et al. (2025a), Ströbel et al. (2025b), Abdul Hadi (2021), Wuwer & Brillinger (2021) | Same Edge schema as the JOANNEUM target, so its ingestion path in `scripts/60_ingest_real_data.py` can be reused; unit corrections still to be audited |
| Medium | Sáinz de la Maza et al. (2025) (XLSX at 1 Hz), Sun (n.d.) (CSV at 10 Hz), Kim et al. (2026) (MTConnect CSV at ≈ 1 s) | Common formats, one table per machine |
| High | Denkena et al. (2023, M1–M3) (HDF5; feeds derived from positions), Peralta Abadia et al. (2025) (MAT), Piecuch & Żabiński (2025) | Piecuch & Żabiński (2025) needs an RMS transform of clamp-on phase currents |

**Download volume.** About 100 GB for Ströbel et al. (2025a, 2025b). Add 26 GB for Sheffield and 25 GB for Rzeszów if those are used.

### Alternative: V2-B, leave-one-machine-out inside the Sinumerik Edge family

**Pool.** Martinez et al. (2025), Brillinger et al. (2025) with Abdul Hadi (2021), Ströbel et al. (2025a), Ströbel et al. (2025b) and Sáinz de la Maza et al. (2025): five machines with the same signal semantics.

**Protocol.** Each fold holds one machine out.

**Trade-off.** It has the simplest ETL and the best channel coverage. Its claim is also weaker, because it covers a single controller family. It is useful as a stepping stone before V2-A.

### Risks to track

| Risk | Mitigation |
|---|---|
| Unit and semantic drift across vendors (W vs kW, mm/s vs mm/min, target vs measured torque, load %) | Extend the unit-mismatch audit of `scripts/60` to every new machine; keep uncertain channels as new vocabulary entries |
| Short runs vanish at 1 Hz | Report usable windows per machine before training; optional 10 Hz arm |
| NC / ND licences (Ströbel et al., 2023a, 2023b, 2024, 2025c, Dreyer et al. (2026), Li Y. (2021) conflict) | Use only if needed; never redistribute transformed data; keep them out of released artefacts |
| Gated downloads (RADAR terms, KAMP account, IEEE subscription) | A human accepts or declines; log the decision |
| Same-lab target pair | Declare T2 as a machine replication, not a lab replication |

## 10. Open unknowns (to close before the V2 lock)

- [ ] Ströbel et al. (2025b): per-run durations and the confirmed signal list (RADAR documentation).
- [ ] Ströbel et al. (2025a, 2025b): units of `POWER` and `CMD_SPEED`, checked against the unit corrections applied to the JOANNEUM target.
- [ ] Schlagenhauf et al. (2023): machine identity (MDPI *Data* 7(12):175).
- [ ] Denkena et al. (2023, M1–M3): file durations and the tool split per machine (`filelist.csv`).
- [ ] Kim et al. (2026): count of independent experiments (`label.csv`).
- [ ] Sun (n.d.): feed levels (`train.csv`).
- [ ] Schmitt & Engelmann (2024): the remaining 12 NC features (Zenodo / MDPI once reachable).
- [ ] Sáinz de la Maza et al. (2025): recorded hours and heating cycle design (XLSX).
- [ ] Dominguez Caballero et al. (2023): signal list (`Readme.txt`, not downloaded).
- [ ] Li Y. (2021): licence conflict (contact the authors only with approval).
- [ ] Pratap et al. (2024) and Denkena et al. (2026): signal content of the power logs and of the HDF5 file.
- [ ] Tapia Fernandez et al. (2024), Rizwan (2026) and Mehling et al. (2025): details hidden by the Zenodo outage.
- [ ] Hedberg et al. (2016): NIST SMS Test Bed availability.
- [ ] MTConnect load % versus Sinumerik `LOAD`: equivalence audit.

## 11. Excluded sources

| Source | Reason | Where checked |
|---|---|---|
| AI4I 2020 predictive maintenance | synthetic data (fails G2) | jonathanwvd/awesome-industrial-datasets |
| CWRU / PRONOSTIA bearings | bearing benches without machine-tool actions | plan §4 |
| KIT ball screw / machine-tool surface defect images (10.35097/1511, 1340, 1278) | images, not time series (fails G2) | DataCite |
| Kaggle ziya07 multi-sensor CNC tool wear | 0.6 MB table without provenance (fails G2) | S61 |
| Kaggle adorigueto CNC turning roughness | aggregated tables (fails G2) | S61 |
| Rzeszów FeatureAndMetadata_Milling.csv | per-cycle aggregates; use raw_data.zip instead | S29 |
| CRISP program backup (10.17632/9ymhr8ncwz) | PLC source code, not data | DataCite |
| TU Wien pilot factory AutomationML (10.48436/njhwb-pm507) | ontology, not time series | DataCite |
| PMSM drive fault dataset (Zenodo 22744389) | Simulink simulation of a motor, no machine tool | DataCite |
| CNC control programs (Zenodo 17888812) | NC code only | DataCite |
| FEM cutting-force and surface-roughness tables (Zenodo 21128247, 21518386, 21297034) | simulation or per-cut tables | DataCite |
| Real-time monitoring of machining accuracy (Zenodo 20308265) | paper, not data | DataCite |
| Science Data Bank tool-wear result tables (sciencedb.05992 etc.) | result tables, NC-SA | DataCite |
| "CNC machining quality prediction ... 2 TB dataset" (PHM 2022) | no public download found | IEEE Xplore 9808708 |
| Yan et al. actionable world models (arXiv 2503.01411) | injection moulding; no public data stated | S57 |
| HAAS Studio reproducibility package (Zenodo 20771475) | unrelated (work-organisation study) | DataCite |

## 12. Audit of this table

A seeded draw of 20 % of the 52 candidate rows present at audit time (11 rows; Denkena et al. (2024) was added afterwards from its DataCite record) was re-checked on five fields each: licence, machine, controller, sampling rate and independent units (55 cells), against the DataCite records and the data papers.

- **One error.** Denkena et al. (2023, M1) stated "3 tools" per LUH machine. That was an inference from 9 tools over 3 machines; the split is not documented. The value was corrected in Denkena et al. (2023, M1–M3).
- **One cell with weak support.** The Li Y. (2021) machine name "DMU" appears only in a user comment on the IEEE DataPort page. It is now marked as such.
- **Error rate:** 1 / 55 = 1.8 %.
- **Separate correction from the plan stage:** a model-written page summary had given the licence of an arXiv paper as the licence of a dataset.

**Link check (2026-09-16).** 73 URLs and DOIs were checked. 55 answered 200 or 206. The other 18 are DOIs that resolve at doi.org, but whose landing pages either block scripted clients (figshare, Dataverse and ORDA answered 202; IEEE DataPort answered 403) or were unavailable (Zenodo was in its 504 outage; NIST and TUHH ended on a redirect). All 18 DOIs were confirmed as registered through the DataCite API during the search.

## 13. Sources

### Dataset references

- Martinez, M., Schmitt, A.-M., Schiffler, A., Engelmann, B. (2025). *Production data set for five-axis CNC milling with multiple changeovers*. Scientific Data 12:1067; data on Zenodo. https://doi.org/10.5281/zenodo.14094887
- Brillinger, M., Abdul Hadi, M., Trabesinger, S., Schmid, J., Lackner, F. (2025). *CNC machining data repository: geometry, NC code & high-frequency energy consumption data for aluminum and plastic machining*. Data in Brief 61:111814; data on Mendeley Data. https://doi.org/10.17632/gtvvwmz7r7.2
- Ströbel, R., Kuck, M., Oexle, F., Kader, H., Puchta, A., Noack, B., Fleischer, J. (2025a). *A multimodal dataset for process monitoring and anomaly detection in industrial CNC milling*. Data in Brief (2025), 10.1016/j.dib.2025.112207; data on KIT RADAR. https://doi.org/10.35097/hvvwn1kfwf7qt48z
- Ströbel, R., Kuck, M., Oexle, F. (2025b). *A multimodal dataset 2 for process monitoring and anomaly detection in industrial CNC milling*. KIT RADAR. https://doi.org/10.35097/vnnu3n9z7ndsnhfd
- Ströbel, R., Probst, Y., Fleischer, J. (2023a). *Training and validation dataset of milling processes for time series prediction*. KIT RADAR. https://doi.org/10.35097/1462
- Ströbel, R., Mau, M., Deucker, S., Fleischer, J. (2023b). *Training and validation dataset 2 of milling processes for time series prediction*. KIT RADAR. https://doi.org/10.35097/1738
- Ströbel, R., Mau, M., Kader, H., Erd, D., Bless, D., Deucker, S., et al. (2024). *Training and validation dataset 3 of milling processes for time series prediction*. KIT RADAR. https://doi.org/10.35097/fefwiljideoropmh
- Ströbel, R., Kader, H., Mau, M., Deucker, S., Bless, D., Oexle, F. (2025c). *Part series dataset of milling processes for time series prediction*. KIT RADAR. https://doi.org/10.35097/ctvuj6dgzepzmk0g
- Schlagenhauf, T., Wolf, J., Puchta, A. (2023). *Multivariate time series dataset of milling 16MnCr5 for anomaly detection*. KIT RADAR; paper in MDPI Data 7(12):175. https://doi.org/10.35097/1398
- Denkena, B., Klemme, H., Stiehl, T. H. (2023). *Multivariate time series data of milling processes with varying tool wear and machine tools*. Data in Brief 50:109574; data by Stiehl on Mendeley Data. https://doi.org/10.17632/zpxs87bjt8.3
- Kim, E., Sim, Y., Li, A. S., Mostafiz, M. I., Van Meter, Z., Jun, M. B.-G., Bertino, E., Shakouri, A. (2026). *Multi-sensor and MTConnect dataset of metal cutting anomaly in milling from laboratory and industry settings*. Scientific Data (2026), 10.1038/s41597-026-07255-7; data on Kaggle. https://doi.org/10.34740/kaggle/ds/8392825
- Sun, S. (University of Michigan SMART testbed) (n.d.). *CNC Mill Tool Wear*. Kaggle. https://www.kaggle.com/datasets/shasun/tool-wear-detection-in-cnc-mill
- Schmitt, A.-M., Engelmann, B. (2024). *A series production data set for five-axis CNC milling*. MDPI Data 9(5):66; data on Zenodo. https://doi.org/10.5281/zenodo.10853254
- Abdul Hadi, M. (2021). *HF-dataset from Edge Device*. Mendeley Data; data paper in Data in Brief (2021), 10.1016/j.dib.2021.107670. https://doi.org/10.17632/w35nf2fw5m.1
- Wuwer, M., Brillinger, M. (2021). *Energy consumption for a CNC machining process*. Mendeley Data. https://doi.org/10.17632/7cghj7fffp.1
- Peralta Abadia, J. J., Cuesta Zabaljauregui, M., Larrinaga Barrenechea, F. (2025). *Mondragon Unibertsitatea face-milling dataset for smart tool condition monitoring*. Scientific Data (2025), 10.1038/s41597-025-05168-5; data on Mondragon eBiltegia. https://doi.org/10.48764/3hdp-gf23
- Duo, A., Basagoiti, R., Arrazola, P. J., Aperribay Zubia, J., Cuesta Zabalajauregui, M. (2019). *Drilling test data from new and worn bits*. Mondragon University. https://doi.org/10.48764/myma-ys63
- Vicomtech (raw data from Mondragon Unibertsitatea) (n.d.). *Machine tool wear dataset*. GitHub. https://github.com/Vicomtech/dataset-machine-tool-wear
- Dreyer, J., Carrino, S., Ghorbel, H., Cotofrei, P. (2026). *Machine learning solution for machining quality prediction using acoustic emissions, accelerometers and current data*. Discover Applied Sciences 8:776; data on Zenodo. https://doi.org/10.5281/zenodo.6505073
- Sáinz de la Maza García, Á., Sastoque Pinilla, L., López de Lacalle, L. N. (2025). *Large scale machine tool axes heating data: 49 thermocouples, 14 integral deformation sensors*. Zenodo. https://doi.org/10.5281/zenodo.16579804
- Dominguez Caballero, J. A., Moore, J., Stammers, J. (2023). *Sensor signals for machine tool and process health assessment*. University of Sheffield ORDA. https://doi.org/10.15131/shef.data.24125715.v1
- Piecuch, G., Żabiński, T. (2025). *A new open dataset from a milling process – data for classification and estimation of tool life*. Scientific Data (2025), 10.1038/s41597-025-04923-y; data on figshare. https://doi.org/10.6084/m9.figshare.28589216
- Li, G., Zheng, H., Xu, S., Zhu, K., Liu, Y., Jiang, R., Sun, L., Ning, Y. (2024). *Multi-sensor monitoring dataset for milling process with varied parameters and materials*. Data in Brief (2024); data on Mendeley Data. https://doi.org/10.17632/8jk3kyxmbn.1
- Li, Y. (NUAA Ideahouse) (2021). *Tool wear dataset*. IEEE DataPort. https://doi.org/10.21227/3aa1-5e83
- Pratap, A., Chou Kao, Y., Hsiung, P.-A., Sardana, N. (2024). *Digital twin for CNC power dataset*. Mendeley Data. https://doi.org/10.17632/4m9n7zzvwk.1
- Anas uddin, M., Gaiardelli, S., Lora, M., Cheng, D. S., Fummi, F. (2024). *Print+Mill dataset*. Zenodo. https://doi.org/10.5281/zenodo.12793026
- Tapia Fernandez, E., Sastoque Pinilla, L., Lopez-Novoa, U. (2024). *Milling tests in 2 machining centres: energy consumption data*. Zenodo. https://doi.org/10.5281/zenodo.14445879
- Tnani et al. (Bosch Research) (2022). *Smart data collection system for brownfield CNC milling machines: a new benchmark dataset for data-driven machine monitoring*. Procedia CIRP (2022); data on GitHub. https://github.com/boschresearch/CNC_Machining
- Agogino, A., Goebel, K. (BEST Lab, UC Berkeley) (2007). *Milling data set*. NASA Prognostics Data Repository. https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/
- PHM Society (2010). *2010 PHM Society Conference Data Challenge*. PHM Society / IEEE DataPort. https://ieee-dataport.org/documents/2010-phm-society-conference-data-challenge
- Rizwan, M. (2026). *Spindle vibration and current signals collected from CNC VMC using low cost DAQ*. Zenodo. https://doi.org/10.5281/zenodo.21608173
- Denkena, B., Bergmann, B., Buhl, H., Handrup, M. (2026). *Multivariate time series dataset for predicting surface roughness and dimensional error in longitudinal turning*. LUIS (Leibniz Universität Hannover). https://doi.org/10.25835/9xffqwnc
- Harigovind, H., Nair, B., Sakthivel, N. R. (2025). *A sensor based turning dataset for data-driven surface roughness estimation*. Mendeley Data; paper in Scientific Data (2026). https://doi.org/10.17632/ybyhxv4czd.3
- Schibsdat, S. (2026). *Tool wear experiment dataset for the evaluation of sensor informativeness in longitudinal turning (ExtraDrey)*. TUHH. https://doi.org/10.15480/882.17237
- Artabe Zamalloa, A., Polvorosa, R., Fernández Valdivieso, A., Ponce Vanegas, F. (2026). *Tool wear in drilling of Inconel 718 plates*. DIPC Dataverse. https://doi.org/10.82518/ttacdo
- Authors n.d. (QIT) (2024). *Milling dataset*. figshare. https://doi.org/10.6084/m9.figshare.27323346.v2
- Authors n.d. (2024). *Multi-sensor based power prediction models for different geometrical profiles using Box Behnken design on Inconel 718*. Harvard Dataverse. https://doi.org/10.7910/dvn/1g3ssb
- Haber Guerra, R., Castaño Romero, F., Villalonga Jaén, A. (2022). *Artificial intelligence for quality control in manufacturing operations: micro-mechanical milling in the Pilot Line GAMHE 5.0*. Zenodo. https://doi.org/10.5281/zenodo.6303449
- CNC Solutions; LMS Lab, University of Patras; Fogus Innovations & Services (2025). *i-CNC use case: vibration data and associated chatter indication during milling process with CNC machines*. Zenodo. https://doi.org/10.5281/zenodo.15308467
- Institute for Control Engineering of Machine Tools and Manufacturing Units (ISW), University of Stuttgart (2025). *Replication data for feedforward and sliding-mode control on a five-axis milling machine*. DaRUS. https://doi.org/10.18419/darus-4513
- Hinze, C., Zeh, L., Xu, H., et al. (ISW) (2022–2023). *Ball screw drive identification and control datasets*. DaRUS. https://doi.org/10.18419/darus-3003
- Villoria et al. (Universidad de León) (2026). *State-dependent ball-screw positioning error dataset*. Zenodo. https://doi.org/10.5281/zenodo.22768582
- Yao, Y. (2025). *Current and vibration signals for ball screw feed drive under health and bend condition*. IEEE DataPort. https://doi.org/10.21227/5vj0-3132
- Mehling, C. W., Pieper, S., Lüke, T. (2025). *causRCA: real-world dataset for causal discovery and root cause analysis in machinery*. Zenodo. https://doi.org/10.5281/zenodo.15876410
- Karlsruhe Institute of Technology (2026). *SPARK: high-resolution energy data from a sustainable industrial production area in Karlsruhe*. KIT RADAR; paper in Scientific Data (2026). https://doi.org/10.35097/bjdg3m3rg5jv3skk
- Authors n.d. (n.d.). *Vibration, current, torque, RPM dataset for multiple fault conditions in industrial-scale electric motors under randomized speed and load variations*. Mendeley Data (PMC12361783). https://doi.org/10.17632/9r82jppsn7.1
- Downs, J. J., Vogel, E. F. (process); dataset release on IEEE DataPort (1993). *Tennessee Eastman process dataset*. IEEE DataPort. https://doi.org/10.21227/n7q3-4b49
- Pamplin, B. (2026). *Robotic drilling cycles – single Al plate with sample anomalies*. University of Nottingham. https://doi.org/10.17639/nott.7629
- Hedberg, T., Luce, M., Barnard Feeney, A., Helu, M. (2016). *Volatile data stream (VDS) for the Smart Manufacturing Systems (SMS) Test Bed using MTConnect*. NIST. https://doi.org/10.18434/t4fk54
- Korea AI Manufacturing Platform (n.d.). *Manufacturing AI datasets (CNC)*. kamp-ai.kr (registration). https://www.kamp-ai.kr/
- Denkena, B., Bergmann, B., Klemme, H., Handrup, M. (2024). *Anomaly detection method for hybrid workpieces using dynamic time warping*. LUIS (Leibniz Universität Hannover). https://doi.org/10.25835/ph65zrpv

### Evidence records cited in the tables

| Id | Source | Link |
|---|---|---|
| S01 | SAAC-JEPA paper, arXiv:2609.16071v1 (§5.1, §7, §8, App. F) | <https://arxiv.org/abs/2609.16071> |
| S02 | Repository docs/data.md (V1 schema and unit corrections) | [docs/data.md](../../docs/data.md) |
| S03 | DataCite record, THWS production data set (Spinner U5-620, Siemens 840D-SL) | <https://doi.org/10.5281/zenodo.14094887> |
| S04 | FH JOANNEUM data paper, Data in Brief 61:111814 (Spinner U5-630, Sinumerik 840D sl, IPC227E at 2 ms) | <https://pmc.ncbi.nlm.nih.gov/articles/PMC12269468/> |
| S05 | DataCite record, KIT Multimodal Dataset 1 (DMC 60 H) | <https://doi.org/10.35097/hvvwn1kfwf7qt48z> |
| S06 | Data paper, Data in Brief 2025, 10.1016/j.dib.2025.112207 (SINUMERIK Edge signal list, durations) | <https://pmc.ncbi.nlm.nih.gov/articles/PMC12621317/> |
| S07 | DataCite record + RADAR landing page, KIT Multimodal Dataset 2 (CMX 600V) | <https://doi.org/10.35097/vnnu3n9z7ndsnhfd> |
| S08 | DataCite record, KIT training/validation dataset 1 (CMX 600 V) | <https://doi.org/10.35097/1462> |
| S09 | DataCite record, KIT training/validation dataset 2 (DMC 60H, cross-machine design) | <https://doi.org/10.35097/1738> |
| S10 | DataCite record, KIT training/validation dataset 3 (CMX 600 V + DMC 60H, CSV) | <https://doi.org/10.35097/fefwiljideoropmh> |
| S11 | DataCite record, KIT part series dataset (DMC 60H, varied depth/feed/speed) | <https://doi.org/10.35097/ctvuj6dgzepzmk0g> |
| S12 | DataCite record + RADAR file listing, KIT 16MnCr5 anomaly dataset | <https://doi.org/10.35097/1398> |
| S13 | DataCite record + Mendeley public API file listing, LUH milling dataset | <https://doi.org/10.17632/zpxs87bjt8.3> |
| S14 | Data paper, Data in Brief 50:109574 (three DMG Mori machines, controllers, signal names) | <https://pmc.ncbi.nlm.nih.gov/articles/PMC10558710/> |
| S15 | Data paper, Scientific Data 2026, 10.1038/s41597-026-07255-7 (Purdue MSM) | <https://pmc.ncbi.nlm.nih.gov/articles/PMC13314991/> |
| S16 | Kaggle API metadata, CNC Mill Tool Wear (licence CC0, description) | <https://www.kaggle.com/datasets/shasun/tool-wear-detection-in-cnc-mill> |
| S17 | Column description of the Michigan dataset (makinarocks curated list) | <https://github.com/makinarocks/awesome-industrial-machine-datasets/blob/master/data-explanation/CNC%20Mill%20Tool%20Wear/README.md> |
| S18 | DataCite record, THWS series production data set 2024 | <https://doi.org/10.5281/zenodo.10853254> |
| S19 | Sensors 24(2):330 using the same data (HERMLE C600 U, Heidenhain iTNC 530, feature names) | <https://pmc.ncbi.nlm.nih.gov/articles/PMC10819623/> |
| S20 | DataCite record + Mendeley listing + JSON header read (first 2 MB, 2026-09-16), HF-dataset from Edge Device | <https://doi.org/10.17632/w35nf2fw5m.1> |
| S21 | Data paper, Data in Brief 2021, 10.1016/j.dib.2021.107670 (Spinner U5-630, 23 experiments, 2.5-20 kW) | <https://pmc.ncbi.nlm.nih.gov/articles/PMC8661459/> |
| S22 | DataCite record + Mendeley listing, Energy consumption for a CNC machining process | <https://doi.org/10.17632/7cghj7fffp.1> |
| S23 | Data paper, Scientific Data 2025, MU-TCM face-milling (Lagun L1000, Fagor 8065, 16 internal signals) | <https://pmc.ncbi.nlm.nih.gov/articles/PMC12102343/> |
| S24 | DataCite record, Mondragon drilling test data | <https://doi.org/10.48764/myma-ys63> |
| S25 | GitHub README + LICENSE.txt, Vicomtech machine tool wear dataset | <https://github.com/Vicomtech/dataset-machine-tool-wear> |
| S26 | Article, Discover Applied Sciences 8:776 (2026) + Zenodo record 6505073 (Micro5, ISG kernel) | <https://pmc.ncbi.nlm.nih.gov/articles/PMC13341891/> |
| S27 | DataCite record (full description), large machining centre axes heating data (SINUMERIK 840D sl, 1 Hz) | <https://doi.org/10.5281/zenodo.16579804> |
| S28 | DataCite record + figshare API file list, Sheffield machine tool health dataset (DMU 40 eVo linear) | <https://doi.org/10.15131/shef.data.24125715.v1> |
| S29 | Data paper, Scientific Data 2025 (Haas VF-1, current transformers) + figshare API + features header read | <https://pmc.ncbi.nlm.nih.gov/articles/PMC12006439/> |
| S30 | Data paper, Data in Brief 2024 (DX-650, 50 kHz, 50,000 points per sample) + Mendeley listing | <https://pmc.ncbi.nlm.nih.gov/articles/PMC11298887/> |
| S31 | IEEE DataPort page + DataCite record, NUAA_Ideahouse tool wear dataset | <https://doi.org/10.21227/3aa1-5e83> |
| S32 | DataCite record + Mendeley listing, Digital Twin for CNC Power Dataset | <https://doi.org/10.17632/4m9n7zzvwk.1> |
| S33 | DataCite record, Print+Mill Dataset | <https://doi.org/10.5281/zenodo.12793026> |
| S34 | DataCite record, milling tests in 2 machining centres (energy) | <https://doi.org/10.5281/zenodo.14445879> |
| S35 | DataCite record (full description), causRCA vertical lathe dataset | <https://doi.org/10.5281/zenodo.15876410> |
| S36 | DataCite records, ISW Stuttgart five-axis milling machine feed-drive datasets (DaRUS 6114, 4513, 3900) | <https://doi.org/10.18419/darus-4513> |
| S37 | DataCite records, ISW ball screw test bench datasets (DaRUS 3252, 3292, 3152, 3003, 3109, 2563) | <https://doi.org/10.18419/darus-3003> |
| S38 | DataCite record, state-dependent ball-screw positioning error dataset (Universidad de León) | <https://doi.org/10.5281/zenodo.22768582> |
| S39 | DataCite record, ball screw feed drive current and vibration (IEEE DataPort) | <https://doi.org/10.21227/5vj0-3132> |
| S40 | GitHub repository + LICENSE (BSD-3-Clause), Bosch CNC Machining; Kaggle CSV mirror | <https://github.com/boschresearch/CNC_Machining> |
| S41 | NASA PCoE repository page (terms, citation) + PMC9824545 (signals, design) | <https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/> |
| S42 | IEEE DataPort PHM 2010 page (subscription) + PMC11360168 (machine, constant parameters) | <https://ieee-dataport.org/documents/2010-phm-society-conference-data-challenge> |
| S43 | DataCite record, SANJI VMC 650 low-cost DAQ dataset | <https://doi.org/10.5281/zenodo.21608173> |
| S44 | DataCite record, TUHH ExtraDrey turning dataset | <https://doi.org/10.15480/882.17237> |
| S45 | DataCite record + LUH data portal page, longitudinal turning multivariate time series | <https://doi.org/10.25835/9xffqwnc> |
| S46 | DataCite record, LUH hybrid workpiece anomaly detection (turning) | <https://doi.org/10.25835/ph65zrpv> |
| S47 | DataCite record, tool wear in drilling of Inconel 718 (DIPC Dataverse) | <https://doi.org/10.82518/ttacdo> |
| S48 | DataCite record, Inconel-625 turning dataset (Kirloskar Turnmaster 40) | <https://doi.org/10.17632/ybyhxv4czd.3> |
| S49 | DataCite record, SPARK energy data (KIT Campus North, 22 machines) | <https://doi.org/10.35097/bjdg3m3rg5jv3skk> |
| S50 | DataCite records, GAMHE 5.0 micro/macro milling quality datasets | <https://doi.org/10.5281/zenodo.6303449> |
| S51 | DataCite record, i-CNC chatter vibration dataset | <https://doi.org/10.5281/zenodo.15308467> |
| S52 | DataCite record, robotic drilling cycles (Fanuc 0i-F end-effector) | <https://doi.org/10.17639/nott.7629> |
| S53 | Data paper, industrial motors under randomized speed and load (VFD), Mendeley DOIs | <https://pmc.ncbi.nlm.nih.gov/articles/PMC12361783/> |
| S54 | DataCite record, Tennessee Eastman Process Dataset (IEEE DataPort) | <https://doi.org/10.21227/n7q3-4b49> |
| S55 | DataCite record, NIST SMS Test Bed volatile data stream; smstestbed.nist.gov unreachable on 2026-09-16 | <https://doi.org/10.18434/t4fk54> |
| S56 | KAMP access terms (registration, no redistribution), secondary source | <https://goodstream.co.kr/docs/blog/posts/2025-10-20-using-kamp/> |
| S57 | Yan et al., arXiv:2503.01411 (injection moulding; no public data stated on the abstract page) | <https://arxiv.org/abs/2503.01411> |
| S58 | DataCite record, Inconel 718 power prediction, Box-Behnken design (Harvard Dataverse) | <https://doi.org/10.7910/dvn/1g3ssb> |
| S59 | figshare API, Milling dataset from QIT (Ti6Al4V, rotary dynamometer) | <https://doi.org/10.6084/m9.figshare.27323346.v2> |
| S60 | Repository scripts/09_transfer_power_analysis.py (paired-test power proxy) | [scripts/09_transfer_power_analysis.py](../../scripts/09_transfer_power_analysis.py) |
| S61 | Kaggle API metadata for excluded Kaggle tables (ziya07, adorigueto) | <https://www.kaggle.com/datasets/ziya07/multi-sensor-cnc-tool-wear-dataset> |
| S62 | Sheffield companion paper abstract, 10.1177/0954405420960892 | <https://doi.org/10.1177/0954405420960892> |

All web sources were accessed on 2026-09-16.

## Appendix — data dictionary of `candidates.csv`

| Column | Meaning |
|---|---|
| `id`, `reference`, `tier` | Stable row key for scripts; author-year reference used in the text; tier 1 (controller or drive signals), 2 (external sensors), 3 (adjacent), `ref` (V1) |
| `machine_uid` | Machine identity used for de-duplication; rows with the same uid are the same physical machine |
| `canonical_channels` | Count of the 17 canonical channels of the THWS source documented for the machine |
| `new_channels` | Channels that must enter the vocabulary as new entries |
| `actions`, `regime` | How commands are recorded; how they vary |
| `usable_hours`, `windows_1hz`, `windows_10hz` | Duration and window availability for K = 32, max H = 16 |
| `independent_units` | Runs, experiments, tools or days that can serve as statistical units |
| `leakage_vs_v1_datasets` | Relation to the V1 machines (Martinez et al., 2025; Brillinger et al., 2025) |
| `lv_*` | Levels 0–3 (§4) |
| `role_fit` | Roles passing the gates (§2); `?` = pending documentation |
| `score_*` | Weighted role scores (§4), blank for references |
| `evidence` | Source ids of §13 |
| `confidence` | Strongest evidence level used |
| `verified_on` | Date of the check |
