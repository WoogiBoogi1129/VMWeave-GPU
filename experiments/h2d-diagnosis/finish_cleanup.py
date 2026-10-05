"""Finish UID-scoped cleanup of completed helper Pods and the campaign admin."""
from common import *
import urllib.request,urllib.error
plan=json.loads((OUT/'cleanup-plan.json').read_text());uids={x['uid'] for x in plan}
proxylog=(BASE/'cleanup-proxy.txt').open('a');proxy=subprocess.Popen(['kubectl','proxy','--address=127.0.0.1','--port=18081'],stdout=proxylog,stderr=subprocess.STDOUT)
try:
 def ready():
  assert proxy.poll() is None, 'Campaign proxy failed to start'
  try:return urllib.request.urlopen('http://127.0.0.1:18081/version',timeout=2).status==200
  except OSError:return False
 wait(ready,30)
 def gone():
  for item in plan:
   try:
    with urllib.request.urlopen('http://127.0.0.1:18081'+item['api_path'],timeout=10) as r:
     obj=json.load(r);assert obj['metadata']['uid']==item['uid'],'Name reused: do not delete replacement'
     return False
   except urllib.error.HTTPError as e:
    if e.code!=404:raise
  return True
 wait(gone,120)
 pods=json.loads(k('get','pods','-n',NS,'-o','json'))['items'];chosen=[]
 for p in pods:
  md=p['metadata'];admin_pod=md['name']==HELPER
  if admin_pod:assert md.get('labels',{}).get('vmweave.io/campaign')=='h2d-diagnosis-20261005'
  elif not any(r['uid'] in uids for r in md.get('ownerReferences',[])):continue
  else:assert p['status']['phase'] in ['Succeeded','Failed']
  chosen.append(p)
 save(OUT/'cleanup-final-pods.json',chosen)
 for p in chosen:
  md=p['metadata'];path='/api/v1/namespaces/'+NS+'/pods/'+md['name']
  body={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':md['uid']},'propagationPolicy':'Background'}
  req=urllib.request.Request('http://127.0.0.1:18081'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='DELETE')
  try:
   with urllib.request.urlopen(req,timeout=30) as r:r.read()
  except urllib.error.HTTPError as e:
   if e.code!=404:raise
finally:proxy.terminate();proxy.wait();proxylog.close()
wait(lambda:not get('pod',HELPER),90)
