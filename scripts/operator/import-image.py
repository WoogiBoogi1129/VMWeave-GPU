#!/usr/bin/env python3
"""Explicit node-local OCI import using one bounded privileged administration Pod."""
import argparse,json,pathlib,subprocess,time,uuid
p=argparse.ArgumentParser();p.add_argument('archive',type=pathlib.Path);p.add_argument('--node',required=True);p.add_argument('--namespace',default='default');p.add_argument('--admin-image',required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
archive=a.archive.resolve(strict=True)
node=json.loads(subprocess.check_output(['kubectl','get','node',a.node,'-o','json'],text=True))
if any(c['type']=='DiskPressure' and c['status']=='True' for c in node['status']['conditions']):raise SystemExit('resolve node DiskPressure before importing images')
summary=json.loads(subprocess.check_output(['kubectl','get','--raw','/api/v1/nodes/'+a.node+'/proxy/stats/summary'],text=True))
fs=summary['node']['runtime']['imageFs']
# Kubelet rounds utilization; retain margin above 16% free plus the archive budget.
if fs['availableBytes']-archive.stat().st_size*4 < fs['capacityBytes']*0.16:raise SystemExit('insufficient image filesystem headroom; use a registry or recover disk space first')
a.output.mkdir(parents=True,exist_ok=False)
name='vmweave-import-'+uuid.uuid4().hex[:8]
pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':a.namespace},'spec':{'nodeName':a.node,'restartPolicy':'Never','activeDeadlineSeconds':180,'automountServiceAccountToken':False,'containers':[{'name':'import','image':a.admin_image,'command':['chroot','/host','/usr/bin/podman','load','-i',str(archive)],'securityContext':{'privileged':True,'runAsUser':0},'resources':{'requests':{'cpu':'100m','memory':'128Mi'}},'volumeMounts':[{'name':'host','mountPath':'/host'}]}],'volumes':[{'name':'host','hostPath':{'path':'/','type':'Directory'}}]}}
def k(*xs,input=None):return subprocess.check_output(['kubectl',*xs],input=json.dumps(input) if input is not None else None,text=True)
created=json.loads(k('create','-f','-','-o','json',input=pod));(a.output/'pod-created.json').write_text(json.dumps(created,indent=2))
try:
 deadline=time.monotonic()+180
 while time.monotonic()<deadline:
  x=json.loads(k('get','pod',name,'-n',a.namespace,'-o','json'))
  if x['status']['phase'] in ['Succeeded','Failed']:break
  time.sleep(2)
 (a.output/'pod-result.json').write_text(json.dumps(x,indent=2))
 if x['status']['phase']!='Succeeded':raise SystemExit('import failed: '+str(x['status']))
 log=k('logs',name,'-n',a.namespace);(a.output/'log.txt').write_text(log);print(log)
finally:
 x=json.loads(k('get','pod',name,'-n',a.namespace,'-o','json'))
 if x['metadata']['uid']==created['metadata']['uid']:k('delete','pod',name,'-n',a.namespace,'--wait=false')
