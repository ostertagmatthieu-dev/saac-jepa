from _common import *
import argparse,json,numpy as np
from scipy.stats import t
p=argparse.ArgumentParser(); p.add_argument('--n',type=int,default=6); p.add_argument('--effect',type=float,default=.8); a=p.parse_args();
# simple Monte Carlo paired t-test power proxy, plus exact sign-flip resolution
rng=np.random.default_rng(0); hit=0; N=20000
for _ in range(N):
 d=rng.normal(a.effect,1,a.n); stat=d.mean()/(d.std(ddof=1)/np.sqrt(a.n)+1e-12); pv=2*(1-t.cdf(abs(stat),a.n-1)); hit+=pv<.05
print(json.dumps({'n_runs':a.n,'standardized_effect':a.effect,'paired_t_power_mc':hit/N,'exact_signflip_min_two_sided_resolution':2/(2**a.n),'note':'n=6 has modest power; report run-level effects, exact paired tests and uncertainty, not only p-values'},indent=2))
