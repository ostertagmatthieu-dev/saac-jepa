from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset
from .masking import mixed_mask, random_point_mask, block_mask, channel_mask, event_mask, apply_mask


def load_table(path):
    path=Path(path)
    if path.suffix.lower() in ('.parquet','.pq'): return pd.read_parquet(path)
    if path.suffix.lower() in ('.csv','.txt'): return pd.read_csv(path)
    raise ValueError(f'Unsupported table: {path}')


def validate_schema(df,cfg):
    s=cfg['schema']; req=[s['timestamp'],s['machine'],s['session'],s['run']]+s['actions']+s['sensors']
    missing=[c for c in req if c not in df.columns]
    return {'ok':not missing,'missing':missing,'extra':[c for c in df.columns if c not in req], 'n_rows':len(df)}


def resample_group(g,timestamp,sensor_cols,action_cols,hz=1.0):
    g=g.copy(); g[timestamp]=pd.to_datetime(g[timestamp],errors='coerce')
    if g[timestamp].isna().all(): return g
    g=g.dropna(subset=[timestamp]).sort_values(timestamp).set_index(timestamp)
    rule=pd.to_timedelta(1.0/hz,unit='s')
    agg={c:'mean' for c in sensor_cols}; agg.update({c:'last' for c in action_cols})
    meta=[c for c in g.columns if c not in sensor_cols+action_cols]
    for c in meta: agg[c]='last'
    out=g.resample(rule).agg(agg)
    out[sensor_cols]=out[sensor_cols].interpolate(limit_direction='both')
    out[action_cols]=out[action_cols].ffill().bfill()
    for c in meta: out[c]=out[c].ffill().bfill()
    return out.reset_index()


def resample_dataframe(df,cfg,hz=None):
    s=cfg['schema']; hz=hz or cfg['protocol']['eval_hz']; keys=[s['machine'],s['session'],s['run']]
    parts=[]
    for _,g in df.groupby(keys,dropna=False,sort=False):
        parts.append(resample_group(g,s['timestamp'],s['sensors'],s['actions'],hz))
    return pd.concat(parts,ignore_index=True) if parts else df.iloc[:0].copy()


def deterministic_group_split(df,cfg,seed=None):
    s=cfg['schema']; seed=cfg.get('seed',0) if seed is None else seed
    rng=np.random.default_rng(seed)
    src=df[df[s['machine']].astype(str)==str(s['source_machine'])]
    tgt=df[df[s['machine']].astype(str)==str(s['target_machine'])]
    key=s['session']; groups=np.array(sorted(src[key].dropna().astype(str).unique()))
    rng.shuffle(groups)
    n=len(groups); ntr=max(1,int(round(n*cfg['protocol']['source_train_fraction']))); nv=max(1,int(round(n*cfg['protocol']['source_val_fraction'])))
    if ntr+nv>=n: ntr=max(1,n-2); nv=1
    tr=set(groups[:ntr]); va=set(groups[ntr:ntr+nv]); te=set(groups[ntr+nv:])
    return {
        'source_train':src[src[key].astype(str).isin(tr)].copy(),
        'source_val':src[src[key].astype(str).isin(va)].copy(),
        'source_test':src[src[key].astype(str).isin(te)].copy(),
        'target_all':tgt.copy(),
        'group_ids':{'train':sorted(tr),'val':sorted(va),'test':sorted(te)}
    }


def target_support_query_split(df,cfg,fraction=0.1):
    s=cfg['schema']; run=s['run']; ts=s['timestamp']; support=[]; query=[]
    for rid,g in df.groupby(run,sort=False):
        g=g.sort_values(ts); n=len(g); k=int(np.floor(n*fraction));
        if fraction>0: k=max(1,k)
        support.append(g.iloc[:k]); query.append(g.iloc[k:])
    return pd.concat(support,ignore_index=True) if support else df.iloc[:0], pd.concat(query,ignore_index=True) if query else df.iloc[:0]

@dataclass
class WindowSpec:
    context_len:int
    horizons:list[int]

class WindowDataset(Dataset):
    """Windowed CNC dataset.

    Masking determinism (P3-FIX): `mask_rng_seed=None` keeps stochastic masks drawn
    from a per-call Generator seeded off the (worker-seeded) global numpy RNG, so
    training masks vary across epochs yet are reproducible run-to-run. When
    `mask_rng_seed` is an int, item i always draws from `default_rng(mask_rng_seed+i)`,
    giving masks that are identical across epochs, runs and worker counts -- required
    for any masked validation used in model selection.
    `force_mask=True` applies masking even when `training=False` (deterministic masked
    validation protocol); default False keeps clean validation unchanged.
    """
    def __init__(self,df,cfg,sensor_normalizer=None,action_normalizer=None,training=False,mask_cfg=None,sensor_subset=None,mask_rng_seed=None,force_mask=False):
        self.df=df.copy(); self.cfg=cfg; self.s=cfg['schema']; self.training=training
        self.mask_rng_seed=None if mask_rng_seed is None else int(mask_rng_seed); self.force_mask=bool(force_mask)
        self.sensors=list(sensor_subset or self.s['sensors']); self.all_sensors=list(self.s['sensors']); self.actions=list(self.s['actions'])
        self.context_len=int(cfg['protocol']['context_len']); self.horizons=list(cfg['protocol']['horizons']); self.max_h=max(self.horizons)
        self.sn=sensor_normalizer; self.an=action_normalizer; self.mask_cfg=mask_cfg or cfg.get('masking',{})
        self.groups=[]
        for key,g in self.df.groupby([self.s['machine'],self.s['session'],self.s['run']],sort=False,dropna=False):
            g=g.sort_values(self.s['timestamp']).reset_index(drop=True)
            if len(g)>=self.context_len+self.max_h: self.groups.append((key,g))
        self.index=[]
        for gi,(_,g) in enumerate(self.groups):
            for end in range(self.context_len, len(g)-self.max_h+1): self.index.append((gi,end))
    def __len__(self): return len(self.index)
    def __getitem__(self,i):
        gi,end=self.index[i]; key,g=self.groups[gi]
        past=g.iloc[end-self.context_len:end]
        fut_idx=[end+h-1 for h in self.horizons]
        future=g.iloc[fut_idx]
        x=past[self.all_sensors].to_numpy(np.float32); a_p=past[self.actions].to_numpy(np.float32); y=future[self.all_sensors].to_numpy(np.float32)
        target_present=np.isfinite(y).astype(np.float32)
        a_f=np.stack([g.iloc[end:end+h][self.actions].to_numpy(np.float32).mean(axis=0) for h in self.horizons],axis=0)
        present=np.isfinite(x).astype(np.float32)
        # Transform BEFORE imputation so absent channels become 0 in z-space (mean-imputation), not
        # (0-center)/scale raw zeros (up to ~264 sigma). Model outputs are provably identical either way
        # (absent tokens are excluded from attention and pooling) but the invariant should not depend on that.
        if self.sn is not None: x=self.sn.transform(x).astype(np.float32); y=self.sn.transform(y).astype(np.float32)
        if self.an is not None: a_p=self.an.transform(a_p).astype(np.float32); a_f=self.an.transform(a_f).astype(np.float32)
        x=np.nan_to_num(x,nan=0.0); y=np.nan_to_num(y,nan=0.0); a_p=np.nan_to_num(a_p,nan=0.0); a_f=np.nan_to_num(a_f,nan=0.0)
        schema=np.ones(len(self.all_sensors),np.float32)
        if set(self.sensors)!=set(self.all_sensors):
            keep=np.array([c in set(self.sensors) for c in self.all_sensors],bool); schema=(keep.astype(np.float32)); x[:,~keep]=0.; present[:,~keep]=0.
        aug=np.zeros_like(present,dtype=bool)
        if (self.training or self.force_mask) and self.mask_cfg and self.mask_cfg.get('ratio',0)>0:
            rng=np.random.default_rng(self.mask_rng_seed+i) if self.mask_rng_seed is not None else np.random.default_rng(int(np.random.randint(0,2**31-1)))
            mode=self.mask_cfg.get('mode','mixed'); xx=x[None]; ratio=float(self.mask_cfg.get('ratio',.35))
            if mode=='random': aug=random_point_mask(xx,ratio,rng)[0]
            elif mode=='block': aug=block_mask(xx,ratio,int(self.mask_cfg.get('block_min',2)),int(self.mask_cfg.get('block_max',12)),rng)[0]
            elif mode=='channel': aug=channel_mask(xx,float(self.mask_cfg.get('channel_drop_prob',.15)),rng)[0]
            elif mode=='event': aug=event_mask(xx,ratio,float(self.mask_cfg.get('event_quantile',.8)),rng)[0]
            elif mode=='mixed': aug=mixed_mask(xx, ratio=ratio, block_min=int(self.mask_cfg.get('block_min',2)), block_max=int(self.mask_cfg.get('block_max',12)), channel_drop_prob=float(self.mask_cfg.get('channel_drop_prob',.15)), event_quantile=float(self.mask_cfg.get('event_quantile',.8)), rng=rng)[0]
            else: raise ValueError(f'Unknown mask mode: {mode}')
            x=apply_mask(x,aug,0.).astype(np.float32); present[aug]=0.
        return {
            'x':torch.from_numpy(x), 'past_actions':torch.from_numpy(a_p), 'future_actions':torch.from_numpy(a_f), 'y':torch.from_numpy(y), 'target_present':torch.from_numpy(target_present),
            'present':torch.from_numpy(present), 'schema':torch.from_numpy(schema), 'aug_mask':torch.from_numpy(aug.astype(np.float32)),
            'machine':str(key[0]),'session':str(key[1]),'run':str(key[2]), 'index':int(end)
        }


def collate(batch):
    out={}
    for k in batch[0]:
        if torch.is_tensor(batch[0][k]): out[k]=torch.stack([b[k] for b in batch])
        elif k in ('machine','session','run'): out[k]=[b[k] for b in batch]
        else: out[k]=torch.tensor([b[k] for b in batch])
    return out


def save_split_manifest(split,cfg,path):
    s=cfg['schema']; d={}
    for name,df in split.items():
        if isinstance(df,pd.DataFrame):
            d[name]={'rows':len(df),'sessions':sorted(df[s['session']].astype(str).unique().tolist()),'runs':sorted(df[s['run']].astype(str).unique().tolist())}
    if 'group_ids' in split: d['group_ids']=split['group_ids']
    Path(path).parent.mkdir(parents=True,exist_ok=True); Path(path).write_text(json.dumps(d,indent=2),encoding='utf-8')
