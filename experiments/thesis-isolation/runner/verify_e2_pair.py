"""Read-only stage-2 topology check. Does not submit CUDA work."""
import struct
from common import *
def main():
 state=json.loads((BASE/'e2-prepared-pair.json').read_text());rows=state['sessions']
 for r in rows:
  ns,name=r['namespace'],r['name']
  c=get('sharedmemorychannels.vmweave.io',name,ns);v=get('vmi',name,ns);p=get('pod',r['worker'],ns)
  assert c['metadata']['uid']==r['channel_uid'] and p['metadata']['uid']==r['worker_uid']
  assert v['status']['phase']=='Running' and c['status']['gpuUUID']==GPU
  layout=(Path(r['out'])/'guest-config/layout.bin').read_bytes()
  size=struct.unpack_from('<Q',layout,32)[0]
  pv=json.loads(k('get','pv',r['pv'],'-o','json'));directory=pv['spec']['local']['path']
  backing=directory+'/'+c['status']['allocation']+'/channel'
  actual=int(admin(['stat','-c','%s','/host'+backing]).strip());assert actual==size
  r.update(shm_bytes=size,backing_path=backing,current_phase=c['status']['phase'],worker_image_ids=[x.get('imageID') for x in p['status'].get('containerStatuses',[])])
 assert rows[0]['backing_path']!=rows[1]['backing_path']
 state.update(status='PREPARED',gpu_computation_verified=False,measurement_started=False,verified_utc=time.time())
 save(Path(state['preparation'])/'verification.json',state);save(BASE/'e2-prepared-pair.json',state)
 print(json.dumps(state,indent=2))
if __name__=='__main__':main()
