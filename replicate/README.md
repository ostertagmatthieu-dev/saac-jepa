# Replicate packaging

This directory packages the sealed M03 world model for
[Replicate](https://replicate.com/ostertagmatthieu-dev/saac-jepa-world-model) with
[Cog](https://github.com/replicate/cog). It serves the same ONNX export as the
[demo Space](https://huggingface.co/spaces/mostertag/saac-jepa-world-model), on CPU. The Cog build
context is this directory, so none of the repository's data, outputs or third-party code goes into
the image.

| File | Role |
|---|---|
| `cog.yaml` | CPU image, Python 3.12, pinned `requirements.txt` |
| `predict.py` | Checks the artefact hashes at startup, encodes a JSON window, returns the forecast |
| `fetch_weights.py` | Downloads the artefacts from the Space at a pinned revision and checks their SHA-256 |
| `weights/` | Downloaded artefacts, git-ignored but baked into the image |

## Push a new version

Cog needs Docker running. The predictor uses `BaseRunner.run()` and `cog.yaml` uses the `run` key,
so use Cog 0.23 or later. To try the image locally first, pass a file holding
`{"window": "<the window JSON, as a string>"}` to `cog run --json @inputs.json`.

```bash
cd replicate
python fetch_weights.py
cog login
cog push r8.im/ostertagmatthieu-dev/saac-jepa-world-model
```

`fetch_weights.py` refuses any file whose hash differs from the one pinned in the script. The
checkpoint, config and normalizer hashes are those in `LOCKED_BEST.json`, and `predict.py` checks
them again when the container starts.

## Input

The `window` input is a JSON string. All series are at 1 Hz, in the physical units of the DS01
source machine after the ETL (power in kW, feeds in mm/min; see [docs/data.md](../docs/data.md) §4).

```json
{
  "sensors":         {"spindle_current": [32 numbers or null], "x_torque": [...], ...},
  "past_commands":   {"a_spindle_speed": [32 numbers or null], ...},
  "future_commands": {"a_spindle_speed": [16 numbers], "a_feed_x": [...], "a_feed_y": [...], "a_feed_z": [...]},
  "hidden":          ["z_power"]
}
```

- `sensors`: the last 32 s of any subset of the 17 sensors in `config.yaml`. A `null`, or a sensor
  left out, counts as missing. The sensor stays in the schema, which is how the sealed evaluation
  treats the 7 channels that the target machine does not record.
- `past_commands` (optional): the four commands over the same 32 s. Missing values are set to the
  source mean.
- `future_commands`: the four commands for the next 16 s, with no missing values. For horizon h the
  model receives their mean over the first h seconds.
- `hidden` (optional): sensors to remove from the schema entirely, like the demo's hide toggle.

`coverage` (default 0.9) sets the central interval of the Gaussian head.

## Output

```json
{
  "horizons_s": [1, 2, 4, 8, 16],
  "coverage": 0.9,
  "forecast": {"spindle_current": {"mean": [5], "std": [5], "lower": [5], "upper": [5]}, ...},
  "transfer_sensors": ["spindle_current", ...],
  "model": {"method": "M03", "checkpoint_sha256": "...", "onnx_sha256": "..."}
}
```

A forecast is returned for all 17 sensors, but only the 10 `transfer_sensors` were evaluated on the
target machine. Forecasts for the others are unvalidated there.

## Check

On the 2,457 target windows of the demo Space's DS03 copy, the predictor gives RMSE 0.545579 and
MAE 0.352358 (normalized units, 10 transfer sensors × 5 horizons), the sealed values. On the Space's
five PyTorch reference windows, which include hidden sensors and scaled commands, `mu` and `logvar`
differ from PyTorch by at most 6·10⁻⁶.
