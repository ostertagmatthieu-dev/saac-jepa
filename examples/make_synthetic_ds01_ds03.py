from pathlib import Path
import numpy as np, pandas as pd
rng=np.random.default_rng(7)
rows=[]
base=Path(__file__).resolve().parents[1]
cols=[f's{i:02d}_'+n for i,n in enumerate([
'power','temperature','vibration_x','vibration_y','vibration_z','wear','spindle_load','torque','current','voltage','acoustic','pressure','flow','axis_x','axis_y','axis_z','production_rate'],1)]
transfer=set(cols[:9]+[cols[-1]])

def sim(machine,session,run,n=96,target=False):
    temp=0.; wear=0.; prod=0.
    t0=pd.Timestamp('2026-01-01')+pd.Timedelta(days=int(session.replace('S','').replace('R','') or 0))
    for t in range(n):
        speed=rng.uniform(-1,1); feed=rng.uniform(-1,1); cool=rng.uniform(0,1); maint=float(rng.random()<.02)
        domain=0.35 if target else 0.
        power=.8*speed+.5*feed+.15*rng.normal()+domain
        temp=.92*temp+.25*power-.35*cool+.08*rng.normal()+.12*domain
        wear=max(0,.985*wear+.025*abs(speed*feed)+.01*max(temp,0)-.15*maint+.01*rng.normal())
        prod=.7*speed+.55*feed-.2*wear+.05*rng.normal()
        sig=np.array([power,temp,
                      .4*speed+.15*rng.normal(),.3*feed+.15*rng.normal(),.2*(speed+feed)+.15*rng.normal(),wear,
                      .6*power+.1*rng.normal(),.4*feed+.2*rng.normal(),.65*power+.1*rng.normal(),.5+.08*rng.normal(),
                      .25*abs(speed)+.2*rng.normal(),.5*cool+.1*rng.normal(),.6*cool+.1*rng.normal(),
                      np.sin(t/12)+.05*rng.normal(),np.cos(t/15)+.05*rng.normal(),np.sin(t/20)+.05*rng.normal(),prod])
        if target:
            for j,c in enumerate(cols):
                if c not in transfer: sig[j]=np.nan
        row={'timestamp':t0+pd.Timedelta(seconds=t),'machine_id':machine,'session_id':session,'run_id':run,
             'a_speed':speed,'a_feed':feed,'a_coolant':cool,'a_maintenance':maint}
        row.update(dict(zip(cols,sig))); rows.append(row)
for i in range(30): sim('DS01',f'S{i:02d}',f'S{i:02d}',96,False)
for i in range(6): sim('DS03',f'R{i:02d}',f'R{i:02d}',96,True)
out=base/'data'/'synthetic_ds01_ds03.csv'; out.parent.mkdir(parents=True,exist_ok=True); pd.DataFrame(rows).to_csv(out,index=False); print(out)
