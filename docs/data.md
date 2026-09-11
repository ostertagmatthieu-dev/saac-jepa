# Data

Two public datasets, one ETL, one canonical table. This page covers how to obtain them, where
to put them, what the ingest audits, and how the channel names map. The synthetic path at the
bottom needs no download at all and is what `make smoke` uses.

---

## 1. Download

| | Source (DS01) | Target (DS03) |
|---|---|---|
| Name | THWS five-axis CNC milling dataset | FH JOANNEUM CNC machining data repository |
| Machine | Spinner U5-620 five-axis machining centre | FH JOANNEUM CNC |
| DOI | [10.5281/zenodo.14094887](https://doi.org/10.5281/zenodo.14094887) | [10.17632/gtvvwmz7r7.2](https://doi.org/10.17632/gtvvwmz7r7.2) |
| Host | Zenodo | Mendeley Data |
| Licence | CC BY 4.0 | CC BY 4.0 |
| Extent | 62 NC-program sessions | 7 independent runs |
| Channels | 17 canonical sensors | 10 of those 17 |
| Native rate | 1 Hz process log | Sinumerik IPO-cycle traces |

Both are redistributed under CC BY 4.0 by their publishers; this repository ships neither. The
`data/` directory is gitignored.

## 2. Expected on-disk layout

The ETL paths are `etl.ds01_csv` and `etl.ds03_dir` in `configs/real.yaml`. With the defaults:

```
data/
  DS01/
    15735480/
      data_v1_0_1.csv                        # the whole DS01 process log
  DS03/
    Enerman_Alu/Enerman_Alu_full.csv
    Enerman_PLA/Enerman_PLA_full.csv
    Enerman_Part2/Enerman_Part2_full.csv
    WG_Vorderseite_Alu_part1.csv
    WG_Vorderseite_Alu_part2.csv
    WG_Vorderseite_PLA_part1.csv
    WG_Vorderseite_PLA_part2.csv
    WG_Rueckseite_Alu_part1.csv
    WG_Rueckseite_Alu_part2.csv
    WG_Rueckseite_PLA_part1.csv
    WG_Rueckseite_PLA_part2.csv
```

Seven runs, four of which arrive as two files each. The run order in
`scripts/60_ingest_real_data.py` (`DS03_RUNS`) fixes the synthetic timestamp base day, one day
per run index, so runs never overlap in time. `*_chunk*.csv` and `*.zip` files in the
distribution are deliberately ignored — they were verified redundant with the full/part CSVs.

The ETL writes one canonical table to `paths.data`, by default `data/cnc.parquet`, with columns
`timestamp, machine_id, session_id, run_id`, the four actions and the 17 sensors, in exactly the
order `configs/real.yaml` declares them.

## 3. Run the ETL

```bash
python scripts/60_ingest_real_data.py --config configs/real.yaml
```

| Flag | Default | Meaning |
|---|---|---|
| `--config` | `configs/real.yaml` | Configuration to read; the whole `etl:` section lives there. |
| `--out-data` | `paths.data` from the config | Where to write the canonical parquet. |
| `--audit-out` | `outputs/etl_audit.json` | Machine-readable audit record. |
| `--keep-idle` | off | Keep non-machining rows (`Program_status != etl.run_status_value`); their sessions get an `idle__` prefix. Off by default — only program-running rows are kept. |

No GPU, no training. The script **hard-fails with a non-zero exit** on any provenance or schema
violation rather than producing a table that is quietly wrong.

### What it audits

- **Column presence** — every native DS01 and DS03 column the mapping needs, in every file.
- **Timestamp integrity** — DS01 sessions must be monotonic; duplicate and unparseable
  timestamps are dropped and counted; no duplicate `(machine, session, timestamp)` survives.
- **Contiguity** — per DS03 run, the cycle gaps between consecutive rows, the implied duration
  against the row count, and, for the multi-part runs, whether the parts actually join. Broken
  contiguity is reported per run and fails `ds03_contiguity_all_ok`.
- **Session segmentation** — DS01 sessions are cut at program changes and at gaps longer than
  `etl.session_gap_seconds` (5 s), which limits rows fabricated by interpolation onto the 1 Hz
  grid. Sessions shorter than `etl.min_session_rows` (64) are dropped; at least 30 must survive.
- **Exactly seven DS03 runs** — `ds03_exactly_7_runs` is a hard check. If you see a *six*
  anywhere in this repository's history, it is the synthetic dataset, not DS03.
- **Unit mismatch, sensors** — DS01 and DS03 per-channel mean/std/min/max/NaN-rate side by side
  with the mean ratio, for each of the 10 transfer channels. A ratio far from 1 on a
  same-physical-quantity channel means a missing `etl.unit_scale.ds03` entry.
- **Unit mismatch, actions** — the same table for the four actions, on std and max |·|. This one
  matters as much as the sensors: under source-fitted z-scoring, a target action on a 50×
  smaller scale arrives at the model as approximately zero, and action conditioning is silently
  lost.
- **Split preview** — the deterministic group split over DS01 sessions, with session and row
  counts per split.
- **Schema validation** — the emitted frame is checked against `configs/real.yaml:schema`.

The human report prints all of this; `outputs/etl_audit.json` stores it.

## 4. Unit corrections

Three cross-machine mismatches were found by the audit and corrected at ETL time, in
`configs/real.yaml` under `etl.unit_scale`. They are multipliers applied to DS03.

**Sensors (`etl.unit_scale.ds03`)**

| Channel | Multiplier | Comment in the config |
|---|---|---|
| `spindle_power` | `0.001` | DS03 reports W, DS01 kW (audit mean ratio ~0.0015) |
| `z_power` | `0.001` | same W → kW correction (audit mean ratio ~0.0018) |

**Actions (`etl.unit_scale.ds03_actions`)** — controller units → DS01 physical units, derived
from position derivatives:

| Action | Multiplier | Comment in the config |
|---|---|---|
| `a_spindle_speed` | `0.1666…` (1/6) | deg/s → RPM (measured ratio commanded/actual-RPM = 6.00) |
| `a_feed_x` | `60.0` | mm/s → mm/min (d(pos)/dt check: 51.5× observed = 60 × 0.86 feed attainment) |
| `a_feed_y` | `60.0` | |
| `a_feed_z` | `60.0` | |

One further value in `etl` is explicitly an **assumption, not a measurement**:
`ds03_ipo_seconds: 0.002`, the Sinumerik IPO cycle taken as 2 ms (500 Hz). Sensitivity to it is
examined in `scripts/03_resample_sensitivity_data.py` and
`scripts/57_sampling_rate_sensitivity_train_eval.py`. Two more filters are declared there:
`run_status_value: 3.0` (the machining state) and `exclude_programs: [MA_JOG_STEP1]`, manual
jog-mode segments that are not CNC program runs and were the worst interpolation offenders.

## 5. Channel names

All names below are from `configs/real.yaml:schema` and the mapping tables at the top of
`scripts/60_ingest_real_data.py`.

### The 17 source sensors, and which 10 transfer

| # | Canonical name | DS01 native column | DS03 native column | Transfers |
|---|---|---|---|---|
| 1 | `spindle_current` | `Spindle_smoothed_current` | `Current_SP1` | yes |
| 2 | `spindle_torque` | `Spindle_smoothed_torque` | `Torque_SP1` | yes |
| 3 | `spindle_power` | `Spindle_smoothed_active_power` | `Power_SP1` | yes |
| 4 | `x_current` | `X_Axis_smoothed_current` | `Current_X1` | yes |
| 5 | `x_torque` | `X_Axis_smoothed_torque` | `Torque_X1` | yes |
| 6 | `y_current` | `Y_Axis_smoothed_current` | `Current_Y1` | yes |
| 7 | `y_torque` | `Y_Axis_smoothed_torque` | `Torque_Y1` | yes |
| 8 | `z_current` | `Z_Axis_smoothed_current` | `Current_Z1` | yes |
| 9 | `z_torque` | `Z_Axis_smoothed_torque` | `Torque_Z1` | yes |
| 10 | `z_power` | `Z_Axis_smoothed_active_power` | `Power_Z1` | yes |
| 11 | `spindle_motor_temp` | `Spindle_motor_temperature` | — | no |
| 12 | `x_motor_temp` | `X_Axis_motor_temperature` | — | no |
| 13 | `y_motor_temp` | `Y_Axis_Motor_temperature` | — | no |
| 14 | `z_motor_temp` | `Z_Axis_Motor_temperature` | — | no |
| 15 | `spindle_dc_voltage` | `Spindle_smoothed_intermediate_circuit_voltage` | — | no |
| 16 | `spindle_mod_depth` | `Spindle_smoothed_modulation_depth` | — | no |
| 17 | `ambient_temp` | `General_temperature` | — | no |

The seven absent channels are set to NaN for DS03 rows and carried as *absent* through the
presence and schema indicators; they are not imputed.

### The four actions

| Canonical name | DS01 native column | DS03 native column |
|---|---|---|
| `a_spindle_speed` | `Spindle_speed` | `CommandedSpeed_SP1` |
| `a_feed_x` | `X-axis_feed` | `CommandedSpeed_X1` |
| `a_feed_y` | `Y-axis_feed` | `CommandedSpeed_Y1` |
| `a_feed_z` | `Z-axis_feed` | `CommandedSpeed_Z1` |

## 6. Mapping rules

These rules predate the ETL and still apply to anyone pointing this code at a different
database.

- The table must carry a timestamp, a machine ID, a session ID, a run ID, the source sensor
  columns, the transfer-overlap subset, and the action columns.
- **Do not silently substitute sensor names.** If a channel is not the same physical quantity,
  it is a different channel, and the schema must say so.
- **`configs/base.yaml` ships placeholder sensor and action names. They are not claims about any
  real dataset.** Use `configs/real.yaml` for DS01/DS03 work; `base.yaml` exists as a template
  and for structural tests.
- `scripts/60` refuses to run if its internal mapping order diverges from
  `configs/real.yaml:schema.sensors` / `.actions`, or if `schema.transfer_sensors` names a
  channel DS03 does not provide. Edit both sides together or it fails loudly.
- Relocate the canonical table by changing `paths.data`, not by moving files around the
  scripts.

## 7. The synthetic path

For CPU testing, CI and first contact with the code, no download is needed:

```bash
python examples/make_synthetic_ds01_ds03.py     # writes data/synthetic_ds01_ds03.csv
make smoke                                      # or: python scripts/54_smoke_test_core.py
```

`configs/smoke.yaml` consumes that CSV with a tiny model (`d_model: 32`, 2 epochs). The
generator simulates **30 synthetic DS01 sessions and 6 synthetic DS03 sessions**, 96 rows each,
with 17 placeholder channels of which 10 transfer and a domain shift applied to the target
machine.

**That synthetic 6 is the origin of every stale `n=6` label in this repository's history.** The
real target machine has **7 runs**. `scripts/55_triple_review.py` asserts the synthetic 6
against `configs/smoke.yaml`; `scripts/60` hard-asserts the real 7 against DS03.
