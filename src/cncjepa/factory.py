from __future__ import annotations
from .models.jepa import ActionConditionedJEPA,SchemaAdaptiveJEPA
from .models.baselines import *

def build_jepa(cfg,schema_adaptive=True):
    C=len(cfg['schema']['sensors']); A=len(cfg['schema']['actions'])
    return (SchemaAdaptiveJEPA if schema_adaptive else ActionConditionedJEPA)(C,A,cfg)

def build_forecaster(name,cfg):
    C=len(cfg['schema']['sensors']); A=len(cfg['schema']['actions']); T=int(cfg['protocol']['context_len']); H=len(cfg['protocol']['horizons']); d=int(cfg['model']['d_model'])
    name=name.lower()
    if name=='persistence': return PersistenceForecaster(C,H)
    if name=='drift': return LinearDriftForecaster(C,H,cfg['protocol']['horizons'])
    if name=='mlp': return MLPForecaster(C,A,T,H,d)
    if name=='gru': return RNNForecaster(C,A,H,d,'gru')
    if name=='lstm': return RNNForecaster(C,A,H,d,'lstm')
    if name=='tcn': return TCNForecaster(C,A,H,d)
    if name=='transformer': return TransformerForecaster(C,A,H,d,cfg['model']['nhead'],cfg['model']['encoder_layers'])
    if name=='dlinear': return DLinearForecaster(C,A,T,H)
    if name=='tsmixer': return TSMixerForecaster(C,A,T,H,d)
    if name=='patchtst': return PatchTSTLike(C,A,T,H,d,cfg['model']['nhead'],cfg['model']['encoder_layers'],cfg['model'].get('patch_len',4))
    if name=='itransformer': return ITransformerLike(C,A,T,H,d,cfg['model']['nhead'],cfg['model']['encoder_layers'])
    if name=='rssm': return RSSMForecaster(C,A,H,d)
    raise ValueError(name)
