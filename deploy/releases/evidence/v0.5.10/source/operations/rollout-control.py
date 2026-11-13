import json,subprocess,sys,time,shlex,hashlib
from pathlib import Path
D=Path(__file__).resolve().parent;ROOT=D.parents[1];source=(D/'source-revision.txt').read_text().strip()
sys.path.insert(0,str(D.parent/'device-plugin-20261105'));import lab
ns=lab.NS;vm=lab.VM;images=json.load(open(D/'images.json'))
def run(args,**kwargs):return subprocess.check_output(args,text=True,timeout=600,**kwargs)
def k(*args):return run(['kubectl','-n',ns,*args])
def save(name,obj):(D/(name+'.json')).write_text(json.dumps(obj,indent=2)+'\n')
def get(kind,name=vm):
 s=k('get',kind,name,'--ignore-not-found','-o','json');return json.loads(s) if s.strip() else None
def patch(kind,name,changes):
 obj=get(kind,name);ops=[{'op':'test','path':'/metadata/uid','value':obj['metadata']['uid']},{'op':'test','path':'/metadata/resourceVersion','value':obj['metadata']['resourceVersion']}]+[{'op':'replace','path':path,'value':value} for path,value in changes.items()]
 return json.loads(k('patch',kind,name,'--type=json','-p',json.dumps(ops),'-o','json'))
def wait(predicate,seconds=300):
 until=time.monotonic()+seconds
 while time.monotonic()<until:
  value=predicate()
  if value:return value
  time.sleep(3)
 raise TimeoutError(str(predicate))
def host(*args):return k('exec','v0510-release-admin','--','chroot','/host',*args)
# Retain management scope, TLS, mode, CRDs and workload settings.
records=[]
for name,system in [('nested','vmweave-nested-system'),('vmweave','vmweave-system')]:
 values=json.load(open(D/(name+'-values-before.json')));values['image']['digest']=images['operator'].split('@')[1];save(name+'-values-after',values)
 chart=D/'vmweave-operator-0.5.10.tgz'
 rendered=run(['helm','template',name,str(chart),'-n',system,'-f',str(D/(name+'-values-after.json'))]);(D/(name+'-rendered.yaml')).write_text(rendered)
 (D/(name+'-upgrade.txt')).write_text(run(['helm','upgrade',name,str(chart),'-n',system,'-f',str(D/(name+'-values-after.json')),'--wait','--timeout=180s']))
 for component in ['controller','webhook']:
  deployment=name+'-'+component;run(['kubectl','-n',system,'rollout','status','deployment/'+deployment,'--timeout=120s'])
  obj=json.loads(run(['kubectl','-n',system,'get','deployment',deployment,'-o','json']));assert obj['spec']['template']['spec']['containers'][0]['image']==images['operator']
  save(deployment+'-after',obj)
  pods=json.loads(run(['kubectl','-n',system,'get','pods','-l','app='+deployment,'-o','json']))['items'];live=[p for p in pods if not p['metadata'].get('deletionTimestamp')];assert len(live)==1 and all(c['ready'] for c in live[0]['status']['containerStatuses'])
  records.append(dict(namespace=system,deployment=deployment,image=images['operator'],podUID=live[0]['metadata']['uid'],imageID=live[0]['status']['containerStatuses'][0]['imageID'],ready=True))
 assert json.loads(run(['helm','get','values',name,'-n',system,'-o','json']))==values
 save(name+'-helm-after',json.loads(run(['helm','status',name,'-n',system,'-o','json'])))
 print('Helm upgraded',name,flush=True)
save('deployments-after',records)
