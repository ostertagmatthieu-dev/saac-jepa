from _common import *
import torch
import torch.nn.functional as F
from pathlib import Path
from cncjepa.pipeline import prepare,loaders_from_ds,batch_to
from cncjepa.ssl_baselines import SSLTransformer,ssl_loss
from cncjepa.metrics import rmse
from cncjepa.utils import atomic_torch_save,device_from_arg

def run_ssl(cfg,method,out,device='auto',pre_epochs=None,ft_epochs=None):
    dev=device_from_arg(device); _,_,ds,_,_=prepare(cfg,training_mask=False); ld=loaders_from_ds(ds,cfg); C=len(cfg['schema']['sensors']); A=len(cfg['schema']['actions']); H=len(cfg['protocol']['horizons']); m=SSLTransformer(C,A,H,cfg['model']['d_model'],cfg['model']['nhead'],cfg['model']['encoder_layers']).to(dev)
    opt=torch.optim.AdamW(m.parameters(),lr=cfg['train']['lr'],weight_decay=cfg['train']['weight_decay']); pe=pre_epochs or max(1,cfg['train']['epochs']//2)
    for ep in range(pe):
        m.train()
        for bi,b in enumerate(ld['source_train']):
            if cfg['train'].get('max_batches_per_epoch') is not None and bi>=int(cfg['train']['max_batches_per_epoch']): break
            b=batch_to(b,dev); opt.zero_grad(); loss=ssl_loss(m,b['x'],method,ratio=cfg['masking']['ratio']); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(),1); opt.step()
    # fine-tune forecasting using same pretrained encoder
    best=1e18; fe=ft_epochs or max(1,cfg['train']['epochs']//2)
    for ep in range(fe):
        m.train()
        for bi,b in enumerate(ld['source_train']):
            if cfg['train'].get('max_batches_per_epoch') is not None and bi>=int(cfg['train']['max_batches_per_epoch']): break
            b=batch_to(b,dev); opt.zero_grad(); p=m.predict(b['x'],b['future_actions']); mask=b['target_present']; loss=((p-b['y']).pow(2)*mask).sum()/(mask.sum()+1e-8); loss.backward(); opt.step()
        m.eval(); ys=[]; ps=[]; ms=[]
        with torch.no_grad():
            for b in ld['source_val']:
                b=batch_to(b,dev); p=m.predict(b['x'],b['future_actions']); ys.append(b['y'].cpu()); ps.append(p.cpu()); ms.append(b['target_present'].cpu())
        y=torch.cat(ys).numpy(); p=torch.cat(ps).numpy(); mask=torch.cat(ms).numpy().astype(bool); score=rmse(__import__('numpy').where(mask,y,__import__('numpy').nan),__import__('numpy').where(mask,p,__import__('numpy').nan))
        if score<best: best=score; atomic_torch_save({'model':m.state_dict(),'cfg':cfg,'method':method,'best':best},Path(out)/'best.pt')
    return best
