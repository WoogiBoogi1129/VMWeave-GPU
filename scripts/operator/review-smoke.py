#!/usr/bin/env python3
"""Verify two pre-enrolled namespaces against a running review-mode Operator."""
import argparse,json,pathlib,subprocess,time,uuid
p=argparse.ArgumentParser();p.add_argument('--namespaces',nargs=2,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();name='review-'+uuid.uuid4().hex[:8];created=[]
def k(*xs,input=None):return subprocess.check_output(['kubectl',*xs],input=json.dumps(input) if input is not None else None,text=True)
report={'namespaces':a.namespaces,'name':name,'checks':[]}
try:
 for ns in a.namespaces:
  missing={'name':'missing','uid':str(uuid.uuid4())};image='example.invalid/unused@sha256:'+'a'*64
  o={'apiVersion':'vmweave.io/v1alpha1','kind':'SharedMemoryChannel','metadata':{'name':name,'namespace':ns},'spec':{'vmRef':missing,'requestRef':missing,'pvcRef':missing,'sessions':1,'uid':107,'gid':107,'image':image,'workerImage':image,'hookImage':image}}
  c=json.loads(k('create','-f','-','-o','json',input=o));created.append((ns,c['metadata']['uid']))
 for ns,uid in created:
  deadline=time.monotonic()+60
  while True:
   c=json.loads(k('get','sharedmemorychannels.vmweave.io',name,'-n',ns,'-o','json'))
   if c.get('status',{}).get('phase')=='ReviewOnly':break
   if time.monotonic()>deadline:raise RuntimeError('review timeout '+ns)
   time.sleep(1)
  assert c['metadata']['uid']==uid and not c['metadata'].get('finalizers') and not c['status'].get('allocation')
  assert c['status']['observedGeneration']==c['metadata']['generation']
  rv=c['metadata']['resourceVersion'];time.sleep(6);after=json.loads(k('get','sharedmemorychannels.vmweave.io',name,'-n',ns,'-o','json'));assert rv==after['metadata']['resourceVersion']
  report['checks'].append({'namespace':ns,'uid':uid,'reviewOnly':True,'noFinalizer':True,'noAllocation':True,'stableStatus':True})
 report['status']='PASS'
finally:
 for ns,uid in created:
  c=json.loads(k('get','sharedmemorychannels.vmweave.io',name,'-n',ns,'-o','json'))
  if c['metadata']['uid']==uid:k('delete','sharedmemorychannels.vmweave.io',name,'-n',ns,'--wait=true','--timeout=20s')
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
