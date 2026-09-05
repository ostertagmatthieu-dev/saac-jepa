from __future__ import annotations
import torch
import torch.nn.functional as F

def off_diagonal(x):
    n,m=x.shape; assert n==m
    return x.flatten()[:-1].view(n-1,n+1)[:,1:].flatten()

def vicreg(z, sim_coeff=25., var_coeff=25., cov_coeff=1., target_std=1.0):
    if z.ndim==3: z=z.reshape(-1,z.shape[-1])
    z=z-z.mean(0)
    std=torch.sqrt(z.var(dim=0,unbiased=False)+1e-4)
    var_loss=torch.mean(F.relu(target_std-std))
    cov=(z.T@z)/(max(1,z.shape[0]-1))
    cov_loss=off_diagonal(cov).pow(2).sum()/z.shape[-1]
    # no paired invariance term here; latent prediction loss supplies invariance
    return var_coeff*var_loss + cov_coeff*cov_loss

def jepa_latent_loss(pred,target,kind='smooth_l1'):
    if kind=='smooth_l1': return F.smooth_l1_loss(pred,target)
    if kind=='mse': return F.mse_loss(pred,target)
    if kind=='cosine': return (1-F.cosine_similarity(pred,target,dim=-1)).mean()
    raise ValueError(kind)

def gaussian_nll(mu, logvar, target, mask=None):
    lv=logvar.clamp(-8,8); loss=.5*(lv+(target-mu).pow(2)*torch.exp(-lv))
    if mask is not None:
        loss=loss*mask; return loss.sum()/(mask.sum()+1e-8)
    return loss.mean()
