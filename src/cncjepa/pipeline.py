from __future__ import annotations
import torch
from torch.utils.data import DataLoader
from .data import load_table, validate_schema, resample_dataframe, deterministic_group_split, WindowDataset, collate
from .normalization import Normalizer
from .utils import seed_worker, make_generator


def prepare(cfg, hz=None, sensor_subset=None, training_mask=True, val_mask=False, resampled_df=None):
    """Build split + datasets.

    `resampled_df` reuses an ALREADY loaded+resampled frame (the first return value of a previous
    prepare call with the same cfg/hz) instead of re-reading and re-resampling the table. Callers
    that need several dataset views of one split -- clean, masked, schema-dropped -- get identical
    splits and normalizers by construction rather than by coincidence, at a third of the I/O.

    `cfg.seed` seeds training (model init, shuffling, stochastic train masks).
    `cfg.eval_seed` (optional, defaults to cfg.seed) seeds everything that defines the
    EVALUATION PROTOCOL: the deterministic group split and the per-index validation mask
    stream. Pinning eval_seed while varying seed keeps every candidate and every seed of an
    architecture search on byte-identical validation folds and validation masks, which the
    taskbook requires before score components may be standardised across candidates.
    Omitting eval_seed reproduces the previous behaviour exactly.
    """
    if resampled_df is None:
        df=load_table(cfg['paths']['data']); val=validate_schema(df,cfg)
        if not val['ok']: raise ValueError(f"Missing columns: {val['missing']}")
        df=resample_dataframe(df,cfg,hz=hz)
    else: df=resampled_df
    seed=int(cfg.get('seed',0)); eseed=int(cfg.get('eval_seed',seed))
    split=deterministic_group_split(df,cfg,seed=eseed)
    s=cfg['schema']; tr=split['source_train']
    ncfg=cfg.get('normalization',{}); nmode=ncfg.get('mode','source_zscore'); nmode={'source_zscore':'zscore','source_robust':'robust'}.get(nmode,nmode)
    # rel_floor guards robust scales against degenerate (near-zero) IQRs; set it to 0.0 in the
    # config ONLY to reproduce the transform of legacy checkpoints trained before the floor.
    sn=Normalizer(nmode,rel_floor=float(ncfg.get('rel_floor',0.05))).fit(tr[s['sensors']].to_numpy(float)); an=Normalizer('zscore').fit(tr[s['actions']].to_numpy(float))
    mask_cfg=cfg.get('masking') if training_mask else {'ratio':0}
    ds={}
    for name,part in split.items():
        if hasattr(part,'columns'):
            is_train=(name=='source_train' and training_mask)
            # Non-train splits get a fixed per-index mask seed so any masked validation
            # is byte-identical across epochs/runs; train stays stochastic (worker-seeded).
            ds[name]=WindowDataset(part,cfg,sn,an,training=is_train,mask_cfg=mask_cfg,sensor_subset=sensor_subset,
                                   mask_rng_seed=(None if is_train else eseed),force_mask=(val_mask and not is_train))
    return df,split,ds,sn,an


def loaders_from_ds(ds,cfg,shuffle_train=True):
    b=int(cfg['train']['batch_size']); nw=int(cfg['train'].get('num_workers',0)); seed=int(cfg.get('seed',0))
    out={}
    for k,v in ds.items():
        out[k]=DataLoader(v,batch_size=b,shuffle=(k=='source_train' and shuffle_train),num_workers=nw,pin_memory=torch.cuda.is_available(),collate_fn=collate,
                          drop_last=(k=='source_train' and len(v)>=b),generator=make_generator(seed),worker_init_fn=(seed_worker if nw>0 else None))
    return out


def batch_to(batch,device):
    return {k:(v.to(device,non_blocking=True) if torch.is_tensor(v) else v) for k,v in batch.items()}
