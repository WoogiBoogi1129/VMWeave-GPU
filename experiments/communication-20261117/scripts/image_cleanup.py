"""Remove only campaign-introduced, unreferenced node image cache entries. No prune."""
from common import *
def cleanup_images():
 refs=[x['image'] for x in json.loads((O/'evidence/artifact-image-identities.json').read_text())]
 refs += ['localhost/flyt-gpu-cell@sha256:0b21e0df1222f5861b522994a80416e243870663372d3cd2a886d36a221efbbd','localhost/flyt-cluster-manager@sha256:7789348f62da6f2d9fa1ee031d323be1cf7f6e1b44c563d104745e0deca9a0b8']
 pods=json.loads(k('get','pods','-A','-o','json'))['items']
 used=sorted(set(c['image'] for p in pods for c in p['spec'].get('containers',[])+p['spec'].get('initContainers',[])))
 code='''import subprocess,json
rows=[];used_ids=set()
def inspect(ref):
 r=subprocess.run(['crictl','inspecti',ref],text=True,capture_output=True)
 return json.loads(r.stdout)['status'] if r.returncode==0 else None
for ref in USED:
 x=inspect(ref)
 if x:used_ids.add(x['id'])
for ref in REFS:
 x=inspect(ref)
 if x is None:rows.append({'image':ref,'status':'already_absent'});continue
 containers=json.loads(subprocess.check_output(['crictl','ps','-a','-o','json']))['containers']
 active_refs={c.get('imageRef','') for c in containers}
 if x['id'] in used_ids or any(x['id'] in r or r in x.get('repoDigests',[]) for r in active_refs):
  rows.append({'image':ref,'status':'retained_referenced','id':x['id']});continue
 remove_ref=x['id']
 r=subprocess.run(['crictl','rmi',remove_ref],text=True,capture_output=True)
 absent=inspect(ref) is None
 rows.append({'image':ref,'remove_reference':remove_ref,'id':x['id'],'status':'removed' if absent else 'remove_failed','absent_after_removal':absent,'remove_returncode':r.returncode,'detail':r.stdout+r.stderr})
print(json.dumps(rows,indent=2))
'''.replace('REFS',repr(refs)).replace('USED',repr(used))
 result=json.loads(admin(code,300));save(O/'evidence/image-cleanup.json',result);return result
if __name__=='__main__':print(json.dumps(cleanup_images(),indent=2))
