import json,shlex,subprocess
from common import B,O,save
ACTIVE='ON'
NEXT='ON'
BASE={'VMWEAVE_BULK_COPY':'1','VMWEAVE_BROKER_REUSE':'1','VMWEAVE_BROKER_GATHER':'1','VMWEAVE_BROKER_OWNER':'1'}
BROKER={name:BASE.copy() for name in ['ON','OFF']}
APP={name:{'VMWEAVE_BULK_COPY':'1','VMWEAVE_BULK_DIRECT':'1','VMWEAVE_KERNEL_BATCH':'1' if name=='ON' else '0','LD_LIBRARY_PATH':'/opt/comm/artifacts/V'} for name in ['ON','OFF']}
def application(): return APP[ACTIVE].copy()
def invoke(s,code):
 return subprocess.check_output(s['ssh']+['sudo python3 -c '+shlex.quote(code)],text=True,timeout=40)
def prepare_next(s):
 data=''.join(k+'='+v+'\n' for k,v in BROKER[NEXT].items())
 invoke(s,'from pathlib import Path\np=Path("/etc/vmweave/guest-broker.env");p.write_text('+repr(data)+');p.chmod(0o644)')
 save(B/'next-profile.json',{'profile':NEXT})
def audit(s):
 code='''import pathlib,json
out=[]
for p in pathlib.Path('/proc').glob('[0-9]*'):
 try:
  cmd=(p/'cmdline').read_bytes().replace(b'\\0',b' ').decode()
  if '/opt/vmweave/control/guest_broker.py' not in cmd or 'python3 -c' in cmd:continue
  env=dict(v.split('=',1) for v in (p/'environ').read_text().split('\\0') if '=' in v)
  out.append({'pid':int(p.name),'cmd':cmd,'env':{k:v for k,v in env.items() if k.startswith('VMWEAVE_')}})
 except (OSError,ValueError):pass
print(json.dumps(out))
'''
 rows=json.loads(invoke(s,code));assert len(rows)==1,rows
 actual=rows[0]['env']
 for k,v in BROKER[ACTIVE].items():assert actual.get(k)==v,(ACTIVE,k,actual.get(k),v)
 if ACTIVE=='A':
  for k in BROKER['B']:
   if k!='VMWEAVE_BULK_COPY':assert actual.get(k,'0')=='0',(k,actual.get(k))
 save(O/'evidence'/(s['label']+'-effective-profile.json'),{'profile':ACTIVE,'application':APP[ACTIVE],'broker':rows})
