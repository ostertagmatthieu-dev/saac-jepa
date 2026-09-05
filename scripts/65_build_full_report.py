"""Consolidate every pipeline output into ONE file: outputs/FULL_REPORT.md.
Stdlib only. Safe to run at any time; re-run to refresh the snapshot.
"""
from pathlib import Path
import argparse, json, time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs'

# Known artifacts first, in reading order; everything else discovered after.
PRIORITY = [
    'etl_audit.txt', 'etl_audit.json',
    'audit_sessions_channels.json', 'split_manifest.json', 'resample_sensitivity.json',
    'normalizers.json', 'corruption_manifest.json',
    'p3fix_diagnostics.json', 'p3fix_abc/abc_summary.csv',
    'jepa_pretrain/history.csv', 'jepa_pretrain/latent_health.csv',
    'jepa_finetune/history.csv', 'jepa_finetune/load_audit.json',
    'saac_jepa/history.csv', 'saac_jepa/latent_health.csv',
    'random_search/ranked_methods.csv', 'random_search/confirmed_top5.csv', 'random_search/LOCKED_BEST.json',
    'transfer_ds01_ds03.json', 'per_channel_run.csv', 'eval_multihorizon.json',
    'normalization_sensitivity.json', 'schema_robustness.json', 'calibration.json',
    'orchestrator/status.json',
]
SKIP_DIRS = {'_archive_pre_p3fix', 'smoke_pre', 'smoke_ft'}
MAX_BYTES = 40_000          # per-file embed cap
MAX_CSV_ROWS = 40


def fmt_json(p):
    try:
        obj = json.loads(p.read_text())
    except Exception as e:
        return f'(unreadable json: {e})'
    s = json.dumps(obj, indent=2)
    return s if len(s) <= MAX_BYTES else s[:MAX_BYTES] + f'\n... (truncated, {len(s)} bytes total)'


def fmt_csv(p):
    lines = p.read_text().splitlines()
    body = lines[:MAX_CSV_ROWS]
    if len(lines) > MAX_CSV_ROWS:
        body.append(f'... ({len(lines)-MAX_CSV_ROWS} more rows)')
    return '\n'.join(body)


def fmt_log(p):
    txt = p.read_text(errors='replace')
    if len(txt) > MAX_BYTES:
        txt = '... (head truncated)\n' + txt[-MAX_BYTES:]
    return txt


def emit(fh, rel, p):
    fh.write(f'\n## {rel}\n\n')
    fh.write(f'`{p}` — {p.stat().st_size} bytes, modified {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime))}\n\n')
    kind = p.suffix.lower()
    fh.write('```' + ({'.json': 'json', '.csv': 'csv'}.get(kind, '')) + '\n')
    if kind == '.json':
        fh.write(fmt_json(p))
    elif kind == '.csv':
        fh.write(fmt_csv(p))
    else:
        fh.write(fmt_log(p))
    fh.write('\n```\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(OUT / 'FULL_REPORT.md'))
    a = ap.parse_args()
    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    with open(out_path, 'w') as fh:
        fh.write('# CNC SAAC-JEPA / RoboPAD V1 — rapport consolidé\n')
        fh.write(f'\nGénéré: {time.strftime("%Y-%m-%d %H:%M:%S")} — toutes les sorties du pipeline dans un seul fichier.\n')
        fh.write('Régénérer: `python scripts/65_build_full_report.py`\n')
        for rel in PRIORITY:
            p = OUT / rel
            if p.is_file():
                emit(fh, rel, p)
                seen.add(p)
        fh.write('\n# Autres sorties découvertes\n')
        for p in sorted(OUT.rglob('*')):
            if not p.is_file() or p in seen or p == out_path:
                continue
            if any(part in SKIP_DIRS for part in p.relative_to(OUT).parts):
                continue
            if p.suffix.lower() not in ('.json', '.csv', '.txt', '.log', '.md'):
                continue
            if p.name == 'FULL_REPORT.md':
                continue
            emit(fh, str(p.relative_to(OUT)), p)
            seen.add(p)
    print(out_path)


if __name__ == '__main__':
    main()
