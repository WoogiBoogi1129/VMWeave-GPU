#!/usr/bin/env python3
"""Install/upgrade the central VMWeave chart; preserve old APIs and workload data."""
import argparse,pathlib,subprocess,json,tempfile,base64
ROOT=pathlib.Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--namespace',default='vmweave-system');p.add_argument('--release',default='vmweave');p.add_argument('--values',type=pathlib.Path,required=True);p.add_argument('--ca',type=pathlib.Path,required=True);a=p.parse_args()
def run(*xs,**kw):return subprocess.check_output(list(xs),text=True,**kw)
# Helm performs schema validation. Values are JSON to keep installation dependencies explicit.
v=json.loads(a.values.read_text());names=v.get('management',{}).get('namespaces',[])
if not names:raise SystemExit('nonempty management.namespaces required')
for n in names:
 run('kubectl','get','namespace',n)
 # A legacy controller may still own the same VM/PVC; do not silently take over.
 d=json.loads(run('kubectl','get','deployments','-n',n,'-o','json'))
 for x in d['items']:
  for c in x['spec']['template']['spec']['containers']:
   env={z['name']:z.get('value') for z in c.get('env',[])}
   if env.get('FLYT_MODE')=='active' and x['spec'].get('replicas',1)>0:raise SystemExit('legacy active deployment must be stopped first: '+n+'/'+x['metadata']['name'])
try:old=json.loads(run('helm','get','values',a.release,'-n',a.namespace,'-o','json')) or {}
except subprocess.CalledProcessError:old={}
removed=set(old.get('management',{}).get('namespaces',[]))-set(names)
for n in removed:
 cs=json.loads(run('kubectl','get','sharedmemorychannels.vmweave.io','-n',n,'-o','json'))['items']
 if cs:raise SystemExit('remove channels after proven reclamation before unregistering '+n)
# Config changes that alter admission scope/mode require an explicit maintenance procedure.
if old and (set(names)!=set(old.get('management',{}).get('namespaces',[])) or v.get('mode','review')!=old.get('mode','review')):
 raise SystemExit('scope/mode change requires staged maintenance; see docs/guides/upgrade-uninstall.md')
v.setdefault('tls',{})['caBundle']=base64.b64encode(a.ca.read_bytes()).decode()
with tempfile.TemporaryDirectory() as td:
 f=pathlib.Path(td)/'values.json';f.write_text(json.dumps(v))
 run('helm','template',a.release,str(ROOT/'charts/vmweave-operator'),'-n',a.namespace,'-f',str(f))
 run('kubectl','get','secret',v['tls'].get('existingSecret','vmweave-webhook-tls'),'-n',a.namespace)
 for crd in sorted((ROOT/'operator/config/crd/bases').glob('*.json')):run('kubectl','apply','--dry-run=server','-f',str(crd))
 for crd in sorted((ROOT/'operator/config/crd/bases').glob('*.json')):print(run('kubectl','apply','-f',str(crd)))
 cmd=['helm','upgrade','--install',a.release,str(ROOT/'charts/vmweave-operator'),'-n',a.namespace,'--skip-crds','--wait','--timeout','180s','-f',str(f)]
 if not old or not old.get('webhook',{}).get('registrationEnabled',True):print(run(*cmd,'--set','webhook.registrationEnabled=false'))
 print(run(*cmd,'--set','webhook.registrationEnabled=true'))
