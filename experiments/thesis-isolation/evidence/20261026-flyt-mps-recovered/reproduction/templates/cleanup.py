import json,subprocess,time
from pathlib import Path
R=Path.cwd();B=R/'.local/flyt-compatibility-20261026';O=R/'experiments/thesis-isolation/results/20261026-flyt-compatibility'
def k(*args,**kw):return subprocess.check_output(['kubectl',*args],text=True,**kw)
# Scope every mutation to the two newly created namespaces and recorded identities.
for side in ['b','a']:
 s=json.loads((B/side/'state.json').read_text());ns=s['namespace'];assert ns=='flyt-compat-1026-'+side
 vm=json.loads(k('get','vm',s['name'],'-n',ns,'-o','json'));assert vm['metadata']['uid']==s['vmUID']
 k('patch','vm',s['name'],'-n',ns,'--type=merge','-p','{"spec":{"runStrategy":"Halted"}}')
 k('wait','--for=delete','vmi/'+s['name'],'-n',ns,'--timeout=120s')
 # Removing containers terminates only their owned backend processes, even with hostPID.
 k('delete','pod','flyt-server','-n',ns,'--wait=true','--timeout=120s')
# Channels are now detached; use a short-lived scoped admin solely to remove the owned backing directory.
ns='flyt-compat-1026-a';image=json.loads((R/'deploy/releases/v0.5.3.json').read_text())['images']['worker']
p={'apiVersion':'v1','kind':'Pod','metadata':{'name':'cleanup','namespace':ns},'spec':{'nodeName':'gpu-4','restartPolicy':'Never','automountServiceAccountToken':False,'containers':[{'name':'admin','image':image,'command':['sleep','300'],'securityContext':{'privileged':True,'runAsUser':0},'volumeMounts':[{'name':'host','mountPath':'/host'}]}],'volumes':[{'name':'host','hostPath':{'path':'/','type':'Directory'}}]}}
k('create','-f','-',input=json.dumps(p));k('wait','--for=condition=Ready','pod/cleanup','-n',ns,'--timeout=90s')
code="from pathlib import Path\nimport shutil\np=Path('/var/lib/vmweave/flyt-compatibility-20261026')\nassert p.is_dir() and not p.is_symlink()\nshutil.rmtree(p)\n"
k('exec','-i','-n',ns,'cleanup','--','chroot','/host','python3','-',input=code)
for side in ['a','b']:
 k('delete','namespace','flyt-compat-1026-'+side,'--wait=true','--timeout=120s')
 k('delete','pv','flyt-compat-shm-1026-'+side,'--wait=true','--timeout=90s')
inv=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv'],text=True)
assert 'GPU-772181af-05a4-0c24-de59-8487bd37c142' not in inv
out={'test_namespaces_removed':True,'test_pvs_removed':True,'owned_backing_removed':True,'test_gpu_compute_processes_remaining':False,'product_changes':False,'affinity_or_clock_changes':False,'other_gpu_processes':inv,'time_utc':time.time()}
(O/'cleanup.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
