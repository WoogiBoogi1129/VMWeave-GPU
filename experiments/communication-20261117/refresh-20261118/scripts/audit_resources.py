from common import *
owned={x['uid'] for x in json.loads((B/'owned.json').read_text())}
for f in (O/'evidence').glob('*-session.json'):
 x=json.loads(f.read_text());owned.update(x.get(k,'') for k in ['vmi_uid','launcher_uid','server_uid'])
owned.discard('')
kinds='pods,jobs,configmaps,serviceaccounts,roles,rolebindings,pv,pvc,resourceclaims,vm,vmi,gpuprofiles,gpurequests,sharedmemorychannels,channelattachments'
def remaining():
 items=json.loads(k('get',kinds,'-A','-o','json'))['items'];ids=set(owned)
 while True:
  more={x['metadata']['uid'] for x in items if any(r['uid'] in ids for r in x['metadata'].get('ownerReferences',[]))}
  if more<=ids:break
  ids|=more
 return [{'kind':x['kind'],'namespace':x['metadata'].get('namespace'),'name':x['metadata']['name'],'uid':x['metadata']['uid']} for x in items if x['metadata']['uid'] in ids or x['metadata'].get('labels',{}).get('experiment.vmweave.io/campaign')==NAME]
deadline=time.monotonic()+120
while True:
 rows=remaining()
 if not rows or time.monotonic()>=deadline:break
 time.sleep(3)
save(O/'evidence/final-resource-audit.json',{'utc':time.time(),'remaining_owned_resources':rows,'passed':not rows})
assert not rows,rows
print('PASS: no owned resources or their surviving descendants remain')
