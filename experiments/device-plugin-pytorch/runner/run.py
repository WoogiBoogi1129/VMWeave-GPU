#!/usr/bin/env python3
"""Explicit, isolated inner-cluster functional runner. SSH credentials stay local."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parents[1]
TORCH='docker.io/pytorch/pytorch@sha256:eee11b3b3872a8c838e35ef48f08b2d5def2080902c7f666831310ca1a0ef2be'
GUEST='ghcr.io/woogiboogi1129/vmweave-device-plugin-guest@sha256:79d6c83dc938caf9e6d17b5ee06f4214170b63589b8f6bd635b9f6827559ece4'
LIBSHA='32bf53906f6cd4fd681c7af9068aad6274ea8c972c31e57d5efaf009e74e1bc5'
p=argparse.ArgumentParser();p.add_argument('--connection',type=Path,required=True);p.add_argument('--results',type=Path,required=True)
p.add_argument('action',choices=['prepare','render','run','collect']);p.add_argument('--name');p.add_argument('--mode',choices=['cpu','gpu','hold'],default='gpu');p.add_argument('--profile',choices=['default','compat'],default='default');p.add_argument('--hold-seconds',type=int,default=0);p.add_argument('--no-wait',action='store_true');p.add_argument('--killable',action='store_true')
a=p.parse_args();c=json.loads(a.connection.read_text());ns=c['namespace'];runid=c['runID'];a.results.mkdir(parents=True,exist_ok=True)

def ssh(command,data=None,check=True):
 r=subprocess.run(c['sshArgv']+[command],input=data,text=True,capture_output=True,timeout=120)
 if check and r.returncode:raise RuntimeError(r.stderr)
 return r

def kubectl(*args,data=None,check=True):
 return ssh(shlex.join(['kubectl','--context',c['context'],*args]),data,check)

def create(obj):return kubectl('create','-f','-',data=json.dumps(obj))
def owned():
 obj=json.loads(kubectl('get','ns',ns,'-o','json').stdout)
 assert obj['metadata']['labels'].get('vmweave-experiment')==runid,'namespace belongs to a different run'

def manifest(name):
 gpu=a.mode!='cpu'
 sec={'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}}
 argv=['python','-u','/work/verify.py','--mode',a.mode,'--profile',a.profile,'--hold-seconds',str(a.hold_seconds)]
 entry=shlex.join(argv)
 if a.killable:entry=entry+' & child=$!; echo "$child" > /results/child.pid; wait "$child"'
 else:entry='exec '+entry
 if gpu:entry='export LD_LIBRARY_PATH="/opt/vmweave/adapter${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"; '+entry
 app={'name':'pytorch','image':TORCH,'imagePullPolicy':'IfNotPresent','command':['/bin/sh','-ec'],'args':[entry],
      'securityContext':sec,'env':[{'name':'HOME','value':'/tmp'},{'name':'PYTHONDONTWRITEBYTECODE','value':'1'}],
      'resources':{'requests':{'cpu':'500m','memory':'1Gi'},'limits':{'cpu':'2','memory':'3Gi'}},
      'volumeMounts':[{'name':'code','mountPath':'/work','readOnly':True},{'name':'results','mountPath':'/results'},{'name':'tmp','mountPath':'/tmp'}]}
 spec={'restartPolicy':'Never','automountServiceAccountToken':False,'activeDeadlineSeconds':600,'terminationGracePeriodSeconds':10,
       'nodeSelector':{'kubernetes.io/hostname':c['node']},
       'securityContext':{'runAsNonRoot':True,'runAsUser':1000,'runAsGroup':1000,'fsGroup':1000,'supplementalGroups':[c['brokerGID']],'seccompProfile':{'type':'RuntimeDefault'}},
       'containers':[app],'volumes':[{'name':'code','configMap':{'name':'verify-code'}},{'name':'results','emptyDir':{}},{'name':'tmp','emptyDir':{}}]}
 if gpu:
  app['resources']['limits']['vmweave.io/gpu']=1
  app['env'] += [{'name':'LD_PRELOAD','value':'/opt/vmweave/adapter/libvmweave_guest.so'},{'name':'VMWEAVE_MIRROR_DEVICE_VA','value':'1'}]
  app['volumeMounts'].append({'name':'adapter','mountPath':'/opt/vmweave/adapter','readOnly':True})
  spec['volumes'].append({'name':'adapter','emptyDir':{}})
  spec['initContainers']=[{'name':'guest-adapter','image':GUEST,'imagePullPolicy':'IfNotPresent','securityContext':sec,
    'command':['sh','-ec'],'args':[f'cp /opt/vmweave/guest/libvmweave_guest.so /adapter/; cd /adapter; echo "{LIBSHA}  libvmweave_guest.so" | sha256sum -c -; ln -s libvmweave_guest.so libcuda.so.1; chmod 0555 libvmweave_guest.so'],
    'volumeMounts':[{'name':'adapter','mountPath':'/adapter'}],'resources':{'requests':{'cpu':'10m','memory':'32Mi'},'limits':{'cpu':'200m','memory':'64Mi'}}}]
 return {'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':ns,'labels':{'vmweave-experiment':runid}},'spec':spec}

def collect(name):
 d=a.results/name;d.mkdir(exist_ok=True)
 pod=json.loads(kubectl('-n',ns,'get','pod',name,'-o','json').stdout)
 assert pod['metadata']['labels']['vmweave-experiment']==runid
 (d/'pod.json').write_text(json.dumps(pod,indent=2)+'\n')
 for container in ['pytorch','guest-adapter']:
  r=kubectl('-n',ns,'logs',name,'-c',container,check=False)
  if r.returncode==0:(d/(container+'.txt')).write_text(r.stdout)
 (d/'describe.txt').write_text(kubectl('-n',ns,'describe','pod',name).stdout)
 print(json.dumps({'pod':name,'phase':pod['status']['phase'],'uid':pod['metadata']['uid']}),flush=True)
 return pod

if a.action=='prepare':
 code=(HERE/'workloads/verify.py').read_text();sha=hashlib.sha256(code.encode()).hexdigest()
 create({'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns,'labels':{'vmweave-experiment':runid}}})
 create({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'verify-code','namespace':ns},'immutable':True,'data':{'verify.py':code}})
 (a.results/'protocol.json').write_text(json.dumps({'runID':runid,'namespace':ns,'context':c['context'],'node':c['node'],'officialImage':TORCH,'guestImage':GUEST,'guestLibrarySHA256':LIBSHA,'verificationSourceSHA256':sha,'rtol':1e-4,'atol':1e-6,'benchmark':False},indent=2)+'\n')
 print('prepared',ns)
elif a.action=='render':
 assert a.name
 print(json.dumps(manifest(a.name),indent=2))
else:
 assert a.name;owned()
 if a.action=='run':
  obj=manifest(a.name);d=a.results/a.name;d.mkdir(exist_ok=False);(d/'submitted.json').write_text(json.dumps(obj,indent=2)+'\n');print(create(obj).stdout,flush=True)
  if a.no_wait:raise SystemExit(0)
  for _ in range(330):
   pod=json.loads(kubectl('-n',ns,'get','pod',a.name,'-o','json').stdout)
   if pod['status']['phase'] in ['Succeeded','Failed']:break
   time.sleep(2)
  else:collect(a.name);raise TimeoutError('Pod deadline; inspect retained evidence')
 result=collect(a.name)
 if a.action=='run' and result['status']['phase']!='Succeeded':sys.exit(1)
