"""Real-data ETL: DS01 (Bosch/Sinumerik 1 Hz process log) + DS03 (Sinumerik IPO-cycle traces) -> one canonical parquet.

Hard-fails (non-zero exit) on any provenance/schema violation. Writes a full audit JSON and prints a human report.
No GPU, no training. See configs/real.yaml:etl for every tunable (notably ds03_ipo_seconds, an ASSUMPTION).
"""
from _common import *
import argparse, sys
import numpy as np, pandas as pd
from cncjepa.config import load_config, dump_json
from cncjepa.data import validate_schema

# --- canonical schema (must match configs/real.yaml schema.sensors/actions exactly, in order) ---
DS01_SENSOR={'spindle_current':'Spindle_smoothed_current','spindle_torque':'Spindle_smoothed_torque','spindle_power':'Spindle_smoothed_active_power',
 'x_current':'X_Axis_smoothed_current','x_torque':'X_Axis_smoothed_torque','y_current':'Y_Axis_smoothed_current','y_torque':'Y_Axis_smoothed_torque',
 'z_current':'Z_Axis_smoothed_current','z_torque':'Z_Axis_smoothed_torque','z_power':'Z_Axis_smoothed_active_power',
 'spindle_motor_temp':'Spindle_motor_temperature','x_motor_temp':'X_Axis_motor_temperature','y_motor_temp':'Y_Axis_Motor_temperature','z_motor_temp':'Z_Axis_Motor_temperature',
 'spindle_dc_voltage':'Spindle_smoothed_intermediate_circuit_voltage','spindle_mod_depth':'Spindle_smoothed_modulation_depth','ambient_temp':'General_temperature'}
DS01_ACTION={'a_spindle_speed':'Spindle_speed','a_feed_x':'X-axis_feed','a_feed_y':'Y-axis_feed','a_feed_z':'Z-axis_feed'}
DS01_META=['time','Program_status','Program_path']

DS03_SENSOR={'spindle_current':'Current_SP1','spindle_torque':'Torque_SP1','spindle_power':'Power_SP1','x_current':'Current_X1','x_torque':'Torque_X1',
 'y_current':'Current_Y1','y_torque':'Torque_Y1','z_current':'Current_Z1','z_torque':'Torque_Z1','z_power':'Power_Z1'}
DS03_ACTION={'a_spindle_speed':'CommandedSpeed_SP1','a_feed_x':'CommandedSpeed_X1','a_feed_y':'CommandedSpeed_Y1','a_feed_z':'CommandedSpeed_Z1'}
DS03_META=['part','block','Cycle']
DS03_NEED=DS03_META+list(DS03_SENSOR.values())+list(DS03_ACTION.values())
# run_name -> file(s) relative to etl.ds03_dir. Order fixes the timestamp base day (run_index).
# *_chunk*.csv and *.zip are deliberately ignored: verified redundant with the full/part CSVs.
DS03_RUNS=[('Enerman_Alu',['Enerman_Alu/Enerman_Alu_full.csv']),('Enerman_PLA',['Enerman_PLA/Enerman_PLA_full.csv']),('Enerman_Part2',['Enerman_Part2/Enerman_Part2_full.csv']),
 ('WG_Vorderseite_Alu',['WG_Vorderseite_Alu_part1.csv','WG_Vorderseite_Alu_part2.csv']),('WG_Vorderseite_PLA',['WG_Vorderseite_PLA_part1.csv','WG_Vorderseite_PLA_part2.csv']),
 ('WG_Rueckseite_Alu',['WG_Rueckseite_Alu_part1.csv','WG_Rueckseite_Alu_part2.csv']),('WG_Rueckseite_PLA',['WG_Rueckseite_PLA_part1.csv','WG_Rueckseite_PLA_part2.csv'])]
DS03_BASE_DAY='2024-06-01'

CHECKS=[]
def chk(name,ok,detail=''):
    CHECKS.append({'check':name,'ok':bool(ok),'detail':str(detail)}); return bool(ok)
def die(msg):
    print(f'ETL_FAIL: {msg}',file=sys.stderr); raise SystemExit(1)
def _f(v):
    try: v=float(v)
    except (TypeError,ValueError): return None
    return v if np.isfinite(v) else None


def prog_base(p):
    """'/_N_EXT_DIR/.../_N_CAM_OEFFNER_MPF' -> 'CAM_OEFFNER'. Non-MPF paths degrade gracefully."""
    b=str(p).strip().rstrip('/').split('/')[-1]
    if b.startswith('_N_'): b=b[3:]
    if b.endswith('_MPF'): b=b[:-4]
    return b or 'UNKNOWN'


def intern(values):
    """Object column whose entries are shared (dedup) -- keeps 1.5M-row string columns cheap."""
    return pd.Series(pd.Categorical(values)).astype(object)


def canon_cols(cfg):
    s=cfg['schema']; return ['timestamp','machine_id','session_id','run_id']+list(s['actions'])+list(s['sensors'])


def drop_short(df,minrows,tag,audit):
    n=df.groupby('session_id',sort=False)['timestamp'].transform('size')
    dropped=sorted(df.loc[n<minrows,'session_id'].astype(str).unique().tolist())
    audit[f'{tag}_sessions_dropped_below_min_rows']={'min_session_rows':int(minrows),'n_dropped':len(dropped),'session_ids':dropped}
    return df[n>=minrows].reset_index(drop=True)


# ------------------------------------------------------------------ DS01
def load_ds01(cfg,keep_idle,audit):
    e=cfg['etl']; src=Path(e['ds01_csv'])
    if not src.exists(): die(f'DS01 csv not found: {src}')
    hdr=list(pd.read_csv(src,index_col=0,nrows=0).columns)
    need=list(DS01_SENSOR.values())+list(DS01_ACTION.values())+DS01_META
    miss=[c for c in need if c not in hdr]
    chk('ds01_native_columns_present',not miss,f'missing={miss}')
    if miss: die(f'DS01 {src} missing {len(miss)} native columns: {miss}')
    d=pd.read_csv(src,index_col=0,low_memory=False)
    n_raw=len(d)
    d['timestamp']=pd.to_datetime(d['time'],errors='coerce')
    n_bad_ts=int(d['timestamp'].isna().sum())
    d=d.dropna(subset=['timestamp']).sort_values('timestamp',kind='mergesort')
    dup=d['timestamp'].duplicated(keep='first'); n_dup=int(dup.sum()); d=d[~dup]
    st=pd.to_numeric(d['Program_status'],errors='coerce')
    is_run=(st==float(e['run_status_value']))
    n_run=int(is_run.sum())
    if not keep_idle:
        m=is_run.to_numpy(); d=d[m]; is_run=is_run[m]
    d=d.reset_index(drop=True); is_run=is_run.reset_index(drop=True)
    if not len(d): die('DS01 has zero rows after timestamp/status filtering')
    path=d['Program_path'].astype(str)
    excl=set(e.get('exclude_programs',[]) or []); n_excl=0
    if excl:
        keepm=~path.map(prog_base).isin(excl); n_excl=int((~keepm).sum())
        d=d[keepm.to_numpy()].reset_index(drop=True); is_run=is_run[keepm.to_numpy()].reset_index(drop=True); path=path[keepm.to_numpy()].reset_index(drop=True)
        if not len(d): die('DS01 has zero rows after exclude_programs filtering')
    gap=d['timestamp'].diff().dt.total_seconds()
    new=(path!=path.shift())|gap.isna()|(gap>float(e['session_gap_seconds']))
    if keep_idle: new=new|(is_run!=is_run.shift())        # keep segments status-homogeneous so the 'idle' prefix is well defined
    epi=(new.cumsum()-1).to_numpy()
    base=path.map(prog_base).to_numpy()
    runf=is_run.to_numpy()
    sid=intern([('' if r else 'idle__')+f'S{int(i):03d}__{b}' for r,i,b in zip(runf,epi,base)])
    out=pd.DataFrame({'timestamp':d['timestamp'].to_numpy(),'machine_id':'DS01','session_id':sid.to_numpy(),'run_id':sid.to_numpy()})
    for c,n in DS01_ACTION.items(): out[c]=pd.to_numeric(d[n],errors='coerce').astype('float64').to_numpy()
    for c,n in DS01_SENSOR.items(): out[c]=pd.to_numeric(d[n],errors='coerce').astype('float64').to_numpy()
    prog={s_:b_ for s_,b_ in zip(sid.to_numpy(),base)}
    audit['ds01_ingest']={'file':str(src),'n_raw_rows':int(n_raw),'n_unparseable_timestamps':n_bad_ts,'n_duplicate_timestamps_dropped':n_dup,
        'run_status_value':float(e['run_status_value']),'n_rows_status_is_run':n_run,'keep_idle':bool(keep_idle),
        'exclude_programs':sorted(excl),'n_rows_excluded_by_program':n_excl,
        'session_gap_seconds':float(e['session_gap_seconds']),'n_sessions_pre_min_rows':int(pd.Series(sid).nunique()),
        'program_status_counts':{str(k):int(v) for k,v in st.value_counts(dropna=False).items()}}
    out=drop_short(out,int(e['min_session_rows']),'ds01',audit)
    # episode table + monotonicity check
    tbl=[]; mono=True
    for s_,g in out.groupby('session_id',sort=False):
        mono=mono and bool(g['timestamp'].is_monotonic_increasing)
        tbl.append({'session_id':str(s_),'program':str(prog.get(s_,'?')),'n_rows':int(len(g)),
                    't_start':str(g['timestamp'].iloc[0]),'t_end':str(g['timestamp'].iloc[-1])})
    audit['ds01_episodes']=sorted(tbl,key=lambda r:r['session_id'])
    chk('ds01_sessions_timestamps_monotonic',mono)
    return out


# ------------------------------------------------------------------ DS03
def load_ds03(cfg,audit):
    e=cfg['etl']; root=Path(e['ds03_dir']); ipo=float(e['ds03_ipo_seconds'])
    scale=dict(((e.get('unit_scale') or {}).get('ds03') or {}))
    bad=[k for k in scale if k not in DS03_SENSOR]
    if bad: die(f'etl.unit_scale.ds03 references non-DS03 canonical sensors: {bad}')
    # Actions carry their own controller units (Sinumerik trace: axes mm/s, spindle deg/s) and must be
    # brought to the DS01 physical units (mm/min, RPM) before source-fit z-scoring, or they vanish on target.
    ascale=dict(((e.get('unit_scale') or {}).get('ds03_actions') or {}))
    abad=[k for k in ascale if k not in DS03_ACTION]
    if abad: die(f'etl.unit_scale.ds03_actions references unknown actions: {abad}')
    only01=[c for c in cfg['schema']['sensors'] if c not in DS03_SENSOR]
    frames=[]; runrep=[]
    for ri,(run,files) in enumerate(DS03_RUNS):
        paths=[root/f for f in files]
        for p in paths:
            if not p.exists(): die(f'DS03 file not found: {p}')
            miss=[c for c in DS03_NEED if c not in list(pd.read_csv(p,nrows=0).columns)]
            if miss: die(f'DS03 {p} missing {len(miss)} of {len(DS03_NEED)} native columns: {miss}')
        parts=[pd.read_csv(p,usecols=DS03_NEED) for p in paths]
        contig=None; contig_detail=''
        if len(parts)==2:
            a=int(parts[0]['Cycle'].max()); b=int(parts[1]['Cycle'].min()); contig=bool(b==a+1)
            contig_detail=f'part1_max_cycle={a} part2_min_cycle={b}'
            if not contig: print(f'[WARN] {run}: concatenation not contiguous ({contig_detail}); continuing.')
        g=pd.concat(parts,ignore_index=True) if len(parts)>1 else parts[0]
        raw_inc=bool(g['Cycle'].is_monotonic_increasing and g['Cycle'].is_unique)
        n_pre=len(g)
        g=g.sort_values('Cycle',kind='mergesort').drop_duplicates('Cycle').reset_index(drop=True)
        dc=g['Cycle'].diff()
        n_gaps=int((dc.iloc[1:]!=1).sum())
        gid=(dc!=1).cumsum().astype('int64')                       # first row: NaN!=1 -> True -> groups start at 1
        pv=pd.to_numeric(g['part'],errors='coerce')
        pp=pv.astype('Int64').astype(str) if bool(pv.notna().all()) else g['part'].astype(str)   # '0'/'1', not '0.0'/'1.0'
        segs=pd.DataFrame({'p':pp,'g':gid}).drop_duplicates()
        omap={}; multi=set()
        for p_,sub in segs.groupby('p',sort=False):
            gs=sorted(int(v) for v in sub['g'])
            if len(gs)>1: multi.add(p_)
            for j,gv in enumerate(gs): omap[(p_,gv)]=j
        sid=intern([f'{run}__part{p_}'+(f'_g{omap[(p_,int(gv))]}' if p_ in multi else '') for p_,gv in zip(pp,gid)])
        cyc=g['Cycle'].to_numpy(np.float64)
        ts=pd.Timestamp(DS03_BASE_DAY)+pd.Timedelta(days=ri)+pd.to_timedelta(cyc*ipo,unit='s')
        out=pd.DataFrame({'timestamp':np.asarray(ts),'machine_id':'DS03','session_id':sid.to_numpy(),'run_id':run})
        for c,n in DS03_ACTION.items(): out[c]=pd.to_numeric(g[n],errors='coerce').astype('float64').to_numpy()*float(ascale.get(c,1.0))
        for c,n in DS03_SENSOR.items(): out[c]=pd.to_numeric(g[n],errors='coerce').astype('float64').to_numpy()*float(scale.get(c,1.0))
        for c in only01: out[c]=np.full(len(out),np.nan,dtype='float64')
        frames.append(out)
        runrep.append({'run_id':run,'run_index':int(ri),'files_used':[str(p) for p in paths],'files_ignored':'*_chunk*.csv, *.zip (verified redundant)',
            'n_rows_raw':int(n_pre),'n_rows':int(len(g)),'n_duplicate_cycles_dropped':int(n_pre-len(g)),
            'cycle_min':int(g['Cycle'].iloc[0]),'cycle_max':int(g['Cycle'].iloc[-1]),
            'raw_cycle_strictly_increasing':raw_inc,'cycle_gap_count':n_gaps,'n_sessions':int(pd.Series(sid).nunique()),
            'contiguity_check':contig,'contiguity_detail':contig_detail,
            'implied_duration_s_rows':float(len(g)*ipo),'implied_duration_s_cycle_span':float((int(g['Cycle'].iloc[-1])-int(g['Cycle'].iloc[0]))*ipo),
            't_start':str(out['timestamp'].iloc[0]),'t_end':str(out['timestamp'].iloc[-1])})
    chk('ds03_native_columns_present',True,f'{len(DS03_NEED)} columns verified in each of {sum(len(f) for _,f in DS03_RUNS)} files')
    chk('ds03_contiguity_all_ok',all(r['contiguity_check'] is not False for r in runrep),
        [r['run_id'] for r in runrep if r['contiguity_check'] is False])
    audit['ds03_runs']=runrep
    audit['ds03_ingest']={'dir':str(root),'ipo_seconds':ipo,'base_day':DS03_BASE_DAY,'unit_scale':{k:float(v) for k,v in scale.items()},
        'unit_scale_actions':{k:float(v) for k,v in ascale.items()},
        'ds01_only_sensors_set_nan':only01}
    df=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=canon_cols(cfg))
    return drop_short(df,int(e['min_session_rows']),'ds03',audit)


# ------------------------------------------------------------------ audit helpers
def sess_hist(df):
    n=df.groupby('session_id',sort=False)['timestamp'].size()
    if not len(n): return {'n_sessions':0}
    return {'n_sessions':int(len(n)),'sessions_ge_64':int((n>=64).sum()),'min':int(n.min()),'p25':float(n.quantile(.25)),
            'median':float(n.median()),'p75':float(n.quantile(.75)),'max':int(n.max())}


def chan_stats(df,cols):
    r={}
    for c in cols:
        s=pd.to_numeric(df[c],errors='coerce')
        r[c]={'nan_rate':float(s.isna().mean()) if len(s) else 1.0,'mean':_f(s.mean()),'std':_f(s.std()),'min':_f(s.min()),'max':_f(s.max())}
    return r


def split_preview(d01,cfg):
    """Byte-for-byte replication of cncjepa.data.deterministic_group_split's group assignment (source machine only)."""
    seed=int(cfg.get('seed',0)); rng=np.random.default_rng(seed)
    groups=np.array(sorted(d01['session_id'].dropna().astype(str).unique()))
    rng.shuffle(groups)
    n=len(groups)
    ntr=max(1,int(round(n*cfg['protocol']['source_train_fraction']))); nv=max(1,int(round(n*cfg['protocol']['source_val_fraction'])))
    if ntr+nv>=n: ntr=max(1,n-2); nv=1
    tr,va,te=set(groups[:ntr]),set(groups[ntr:ntr+nv]),set(groups[ntr+nv:])
    sz=d01.groupby('session_id',sort=False)['timestamp'].size()
    rows=lambda s:int(sz.reindex(sorted(s)).fillna(0).sum())
    return {'seed':seed,'n_source_sessions':int(n),'train':{'n_sessions':len(tr),'n_rows':rows(tr),'session_ids':sorted(tr)},
            'val':{'n_sessions':len(va),'n_rows':rows(va),'session_ids':sorted(va)},
            'test':{'n_sessions':len(te),'n_rows':rows(te),'session_ids':sorted(te)},
            'note':'computed on pre-resample rows; script 02 splits the resampled frame, so session ids match but row counts differ'}


def report(audit,cfg):
    s=cfg['schema']; L=[]; A=L.append
    A('='*100); A('REAL-DATA ETL AUDIT'); A('='*100)
    A('\n-- PROVENANCE ---------------------------------------------------------------')
    A(f"DS01 file        : {audit['ds01_ingest']['file']}")
    A(f"DS03 dir         : {audit['ds03_ingest']['dir']}  (ignored: *_chunk*.csv, *.zip -- verified redundant)")
    A(f"DS03 ipo_seconds : {audit['ds03_ingest']['ipo_seconds']}  ASSUMPTION (Sinumerik IPO 2 ms / 500 Hz); sweep via scripts 03 and 57")
    A(f"DS03 base day    : {audit['ds03_ingest']['base_day']} + 1 day per run index (runs never overlap in time)")
    A(f"DS03 unit_scale  : {audit['ds03_ingest']['unit_scale'] or '{} (all 1.0)'}")
    A(f"DS03 NaN sensors : {audit['ds03_ingest']['ds01_only_sensors_set_nan']}")
    A(f"DS01 dedup       : {audit['ds01_ingest']['n_duplicate_timestamps_dropped']} duplicate timestamps dropped (keep=first); "
      f"{audit['ds01_ingest']['n_unparseable_timestamps']} unparseable dropped; keep_idle={audit['ds01_ingest']['keep_idle']}")
    A(f"\n  {'canonical':<20}    {'DS01 native':<48} | {'DS03 native'}")
    for c in s['sensors']:
        A(f"  {c:<20} <- {DS01_SENSOR.get(c,'(none)'):<48} | {DS03_SENSOR.get(c,'(NaN)')}")
    for c in s['actions']:
        A(f"  {c:<20} <- {DS01_ACTION.get(c,'(none)'):<48} | {DS03_ACTION.get(c,'(NaN)')}")
    A('\n-- PER MACHINE --------------------------------------------------------------')
    for m,d in audit['per_machine'].items():
        A(f"  {m}: rows={d['n_rows']} sessions={d['n_sessions']} runs={d['n_runs']} | session len "
          f"min={d['session_len']['min']} p25={d['session_len']['p25']:.0f} med={d['session_len']['median']:.0f} "
          f"p75={d['session_len']['p75']:.0f} max={d['session_len']['max']} | >=64 rows: {d['session_len']['sessions_ge_64']}")
    A('\n-- DS01 EPISODES ------------------------------------------------------------')
    A(f"  {'session_id':<34}{'program':<26}{'rows':>7}  {'t_start':<21}{'t_end':<21}")
    for r in audit['ds01_episodes']:
        A(f"  {r['session_id']:<34}{r['program'][:25]:<26}{r['n_rows']:>7}  {r['t_start']:<21}{r['t_end']:<21}")
    A('\n-- DS03 RUNS ----------------------------------------------------------------')
    A(f"  {'run':<22}{'rows':>9}{'dur_s':>11}{'gaps':>7}{'sess':>6}  contiguity")
    for r in audit['ds03_runs']:
        c='n/a (single file)' if r['contiguity_check'] is None else ('OK  '+r['contiguity_detail'] if r['contiguity_check'] else 'BROKEN  '+r['contiguity_detail'])
        A(f"  {r['run_id']:<22}{r['n_rows']:>9}{r['implied_duration_s_rows']:>11.1f}{r['cycle_gap_count']:>7}{r['n_sessions']:>6}  {c}")
    A('\n-- UNIT-MISMATCH DETECTOR (transfer channels, DS01 vs DS03) ------------------')
    st1=audit['channel_stats'].get('DS01',{}); st3=audit['channel_stats'].get('DS03',{})
    A(f"  {'channel':<20}{'DS01 mean':>12}{'DS01 std':>12}{'DS01 min':>12}{'DS01 max':>12}{'nan':>7} |"
      f"{'DS03 mean':>12}{'DS03 std':>12}{'DS03 min':>12}{'DS03 max':>12}{'nan':>7}{'mean ratio':>13}")
    fm=lambda v:f'{"NaN":>12}' if v is None else f'{v:12.4g}'
    for c in s['transfer_sensors']:
        x=st1.get(c,{}); y=st3.get(c,{})
        rt=x['mean']/y['mean'] if (x.get('mean') is not None and y.get('mean')) else None
        A(f"  {c:<20}{fm(x.get('mean'))}{fm(x.get('std'))}{fm(x.get('min'))}{fm(x.get('max'))}{x.get('nan_rate',1):>7.2f} |"
          f"{fm(y.get('mean'))}{fm(y.get('std'))}{fm(y.get('min'))}{fm(y.get('max'))}{y.get('nan_rate',1):>7.2f}"
          f"{('%13.4g'%rt) if rt is not None else '          n/a'}")
    A('  (large |mean ratio| away from 1 on a same-physical-quantity channel => set etl.unit_scale.ds03 for it)')
    # Actions matter as much as sensors: source-fit z-scoring makes a target action with a 50x smaller
    # scale arrive at the model as ~0, and the model then ignores it (silent loss of action conditioning).
    A('\n-- UNIT-MISMATCH DETECTOR (ACTIONS, DS01 vs DS03) ----------------------------')
    A(f"  {'action':<20}{'DS01 std':>12}{'DS01 max|.|':>13} |{'DS03 std':>12}{'DS03 max|.|':>13}{'std ratio':>12}")
    for c in s['actions']:
        x=st1.get(c,{}); y=st3.get(c,{})
        rt=x['std']/y['std'] if (x.get('std') is not None and y.get('std')) else None
        mx=lambda d:max(abs(d.get('min') or 0),abs(d.get('max') or 0))
        A(f"  {c:<20}{fm(x.get('std'))}{mx(x):13.4g} |{fm(y.get('std'))}{mx(y):13.4g}"
          f"{('%12.4g'%rt) if rt is not None else '         n/a'}")
    A('  (|std ratio| far from 1 => target actions vanish under source z-scoring => set etl.unit_scale.ds03_actions)')
    sp=audit['split_preview']
    A('\n-- SPLIT PREVIEW (deterministic_group_split, DS01 only) ---------------------')
    A(f"  seed={sp['seed']} source_sessions={sp['n_source_sessions']}")
    for k in ('train','val','test'): A(f"  {k:<6} sessions={sp[k]['n_sessions']:>4}  rows={sp[k]['n_rows']:>9}")
    A(f"  note: {sp['note']}")
    A('\n-- HARD CHECKS --------------------------------------------------------------')
    for c in audit['checks']: A(f"  [{'PASS' if c['ok'] else 'FAIL'}] {c['check']}{('  '+c['detail']) if c['detail'] else ''}")
    return '\n'.join(L)


# ------------------------------------------------------------------ main
p=argparse.ArgumentParser(description='Ingest DS01 + DS03 real CNC data into the canonical parquet table.')
p.add_argument('--config',default='configs/real.yaml')
p.add_argument('--out-data',default=None,help='default: paths.data from config')
p.add_argument('--audit-out',default='outputs/etl_audit.json')
p.add_argument('--keep-idle',action='store_true',help='keep non-machining rows (Program_status != etl.run_status_value); their sessions get an idle__ prefix')
a=p.parse_args(); cfg=load_config(a.config); s=cfg['schema']
out_data=Path(a.out_data or cfg['paths']['data'])

if list(DS01_SENSOR)!=list(s['sensors']): die(f"script sensor mapping order != config schema.sensors\n  script={list(DS01_SENSOR)}\n  config={list(s['sensors'])}")
if list(DS01_ACTION)!=list(s['actions']): die(f"script action mapping order != config schema.actions\n  script={list(DS01_ACTION)}\n  config={list(s['actions'])}")
if [c for c in s['transfer_sensors'] if c not in DS03_SENSOR]: die('config schema.transfer_sensors contains channels DS03 does not provide')

audit={'config':str(a.config),'out_data':str(out_data),'keep_idle':bool(a.keep_idle),
       'mapping':{'DS01':{'sensors':dict(DS01_SENSOR),'actions':dict(DS01_ACTION)},'DS03':{'sensors':dict(DS03_SENSOR),'actions':dict(DS03_ACTION)}}}
d01=load_ds01(cfg,a.keep_idle,audit)
d03=load_ds03(cfg,audit)
cols=canon_cols(cfg)
df=pd.concat([d01[cols],d03[cols]],ignore_index=True)

audit['per_machine']={}
for m,g in df.groupby('machine_id',sort=False):
    audit['per_machine'][str(m)]={'n_rows':int(len(g)),'n_sessions':int(g['session_id'].nunique()),'n_runs':int(g['run_id'].nunique()),'session_len':sess_hist(g)}
audit['channel_stats']={str(m):chan_stats(g,list(s['sensors'])+list(s['actions'])) for m,g in df.groupby('machine_id',sort=False)}
audit['split_preview']=split_preview(d01,cfg)

vs=validate_schema(df,cfg); audit['validate_schema']=vs
chk('validate_schema_ok',vs['ok'],f"missing={vs['missing']} extra={vs['extra']}")
ndup=int(df.duplicated(subset=['machine_id','session_id','timestamp']).sum())
chk('no_duplicate_machine_session_timestamp',ndup==0,f'n_duplicates={ndup}')
n01=audit['per_machine'].get('DS01',{}).get('session_len',{}).get('sessions_ge_64',0)
chk('ds01_sessions_ge_64_at_least_30',n01>=30,f'n={n01} (expected ~43)')
n03=audit['per_machine'].get('DS03',{}).get('n_runs',0)
chk('ds03_exactly_7_runs',n03==7,f'n={n03}')
chk('final_frame_nonempty',len(df)>0,f'n_rows={len(df)}')
audit['checks']=CHECKS; audit['n_rows_total']=int(len(df)); audit['columns']=cols

dump_json(audit,a.audit_out)
txt=report(audit,cfg); print(txt)
Path(a.audit_out).with_suffix('.txt').write_text(txt+'\n',encoding='utf-8')
print(f'\nwrote: {a.audit_out}')
bad=[c['check'] for c in CHECKS if not c['ok']]
# Parquet is written only when every hard check passes, so downstream scripts can never pick up a bad table.
if bad: die(f'{len(bad)} hard check(s) failed: {bad} -- {out_data} NOT written; see {a.audit_out}')
out_data.parent.mkdir(parents=True,exist_ok=True)
df.to_parquet(out_data,engine='pyarrow',index=False)
print(f'wrote: {out_data}  ({len(df)} rows, {len(cols)} cols)')
print('ETL_OK')
