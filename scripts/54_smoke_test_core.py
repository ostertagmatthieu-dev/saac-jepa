from _common import *
import subprocess,sys,tempfile,os
cmds=[
 [sys.executable,'examples/make_synthetic_ds01_ds03.py'],
 [sys.executable,'scripts/00_validate_dataset.py','--config','configs/smoke.yaml'],
 [sys.executable,'scripts/10_pretrain_jepa_from_scratch.py','--config','configs/smoke.yaml','--out','outputs/smoke_pre','--device','cpu','--epochs','1'],
 [sys.executable,'scripts/11_finetune_jepa_forecaster.py','--config','configs/smoke.yaml','--pretrained','outputs/smoke_pre/best.pt','--out','outputs/smoke_ft','--device','cpu'],
 [sys.executable,'scripts/30_eval_jepa_multihorizon.py','--config','configs/smoke.yaml','--ckpt','outputs/smoke_ft/best.pt','--device','cpu','--out','outputs/smoke_eval.json']]
for c in cmds:
 print('+',' '.join(c)); subprocess.run(c,check=True)
print('SMOKE_CORE_OK')
