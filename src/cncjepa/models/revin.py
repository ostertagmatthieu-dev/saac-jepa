from __future__ import annotations
import torch
import torch.nn as nn


class MaskedRevIN(nn.Module):
    """Reversible instance normalization (Kim et al., 2022) made presence-aware.

    Per-(window, channel) statistics are computed on the CONTEXT window only, and only over
    entries flagged `present==1`. `data.py` writes 0 for absent / masked / schema-dropped
    entries (mean-imputation in z-space), so a naive mean/var over the time axis would be
    biased toward 0 by every masked point; SimMTM's official pretraining code makes the same
    choice (statistics over visible points only).

    A channel with NO present entry in the window (absent sensor, dropped schema view, whole
    channel masked) falls back to the identity (mean 0, std 1): its inputs and predictions
    stay in the global source z-space exactly as without RevIN, so the legacy behaviour for
    unseen channels is preserved rather than replaced by an undefined statistic.

    Defaults (affine=False, subtract_last=False, eps=1e-5) reproduce the settings the official
    PatchTST / iTransformer baselines run with in scripts/66 (`revin=1, affine=0,
    subtract_last=0`, `use_norm=1`), which is the fairness argument for adding it here.
    Statistics are detached and computed in float32 (robust under AMP), like RevIN.
    """

    def __init__(self, num_features: int, eps: float = 1e-5, affine: bool = False, subtract_last: bool = False):
        super().__init__()
        self.num_features = int(num_features); self.eps = float(eps); self.affine = bool(affine); self.subtract_last = bool(subtract_last)
        if self.affine:
            self.weight = nn.Parameter(torch.ones(self.num_features))
            self.bias = nn.Parameter(torch.zeros(self.num_features))

    @torch.no_grad()
    def stats(self, x, present):
        """x, present: (B,T,C). Returns (center, std) of shape (B,1,C), float32, detached."""
        x = x.float(); p = present.float()
        n = p.sum(1, keepdim=True)                                   # B,1,C  present count
        has = n > 0
        nz = n.clamp(min=1.0)
        mean = (x * p).sum(1, keepdim=True) / nz
        var = (((x - mean) ** 2) * p).sum(1, keepdim=True) / nz
        std = torch.sqrt(var + self.eps)
        if self.subtract_last:
            # last PRESENT value per channel (same trick as PersistenceForecaster)
            T = x.shape[1]
            idx = p * torch.arange(1, T + 1, device=x.device, dtype=x.dtype)[None, :, None]
            last = idx.argmax(1, keepdim=True)
            center = torch.gather(x, 1, last)
        else:
            center = mean
        center, std = self._degenerate_policy(center, std, n, has)
        # identity fallback for channels never observed in this window
        center = torch.where(has, center, torch.zeros_like(center))
        std = torch.where(has, std, torch.ones_like(std))
        return center, std

    def _degenerate_policy(self, center, std, n, has):
        """Policy for windows whose statistics are defined but fragile.

        Current behaviour (a): pure RevIN, `std = sqrt(var + eps)`. A channel that is present
        but nearly constant over the 32 s context (e.g. a motor temperature) gets
        std -> sqrt(eps) ~ 3e-3 in z-units, so its within-window noise is amplified ~300x
        before the encoder (the output is mapped back, so metrics are safe, but the latent
        sees amplified noise). This is exactly the degenerate-IQR lesson of `z_power`
        (see normalization.py). It is kept as-is because it is what the official baselines
        do, which is the fairness argument of the comparison.

        TODO(Matthieu): decide whether the JEPA should deviate from strict RevIN here, e.g.
          (b) relative floor in z-units:   std = std.clamp(min=floor)
          (c) blend toward the identity when few points are present (n < n_min):
              w = (n / n_min).clamp(max=1); center = w*center; std = w*std + (1-w)
        Any change here must be mirrored in the config docs and re-measured against the
        control arm; `eps` is already exposed in `model.revin.eps` for the cheap ablation.
        """
        return center, std

    def normalize(self, v, center, std, present=None):
        """v: (B,L,C) in the global z-space -> instance space. `present` re-zeroes absent entries
        so the 'absent -> 0' invariant of data.py holds in the new space too."""
        z = (v.float() - center) / std
        if self.affine: z = z * self.weight + self.bias
        if present is not None: z = z * present.float()
        return z.to(v.dtype)

    def denormalize(self, mu, logvar, center, std):
        """Map the physical head (instance space) back to the global z-space.
        mu <- mu*std + center ; logvar <- logvar + 2*log(std)  (Gaussian scale change)."""
        mu = mu.float(); logvar = logvar.float()
        if self.affine:
            w = self.weight + self.eps * self.eps
            mu = (mu - self.bias) / w
            logvar = logvar - 2.0 * torch.log(w.abs())
        mu = mu * std + center
        logvar = logvar + 2.0 * torch.log(std)
        return mu, logvar

    def extra_repr(self):
        return f'num_features={self.num_features}, eps={self.eps}, affine={self.affine}, subtract_last={self.subtract_last}'
