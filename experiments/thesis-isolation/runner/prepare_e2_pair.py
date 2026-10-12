"""Stage 2 only: prepare two VM allocations; never launch a benchmark."""
from session import *

def main():
 name='iso-e2-setup-'+time.strftime('%Y%m%d%H%M%S',time.gmtime())
 out=OUT/'preparation'/name
 out.mkdir(parents=True,exist_ok=False)
 inventory=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
 if GPU in inventory:raise RuntimeError('Selected test GPU is already in use')
 (out/'gpu-before.txt').write_text(inventory)
 sessions=[];rows=[]
 try:
  for slot in ['a','b']:
   s=Session(name+'-'+slot,slot=slot,memory=2048,cap=50);sessions.append(s)
   s.prepare()
   channel=s.get(CHAN,s.name);pod=s.get('pod',s.worker);vmi=s.get('vmi',s.name)
   pvc=s.get('pvc',s.name);profile=s.get('gpuprofiles.vmweave.io','isolation-50-2048')
   assert profile['spec']['gpuUUID']==GPU and profile['spec']['maxClients']==1
   assert profile['spec']['memoryMiB']==2048 and profile['spec']['cores']==50
   assert vmi['status']['phase']=='Running'
   assert GPU in pod['metadata'].get('annotations',{}).get('hami.io/vgpu-devices-allocated','')
   save(s.out/'stage2-channel.json',channel)
   save(s.out/'stage2-worker.json',pod)
   save(s.out/'stage2-profile.json',profile)
   row={'slot':slot,'namespace':s.ns,'name':s.name,'channel_uid':s.uid,'phase':channel['status']['phase'],'worker':s.worker,'worker_uid':pod['metadata']['uid'],'pvc_uid':pvc['metadata']['uid'],'pv':pvc['spec']['volumeName'],'ip':s.ip,'bdf':s.bdf,'gpu_uuid':GPU,'memory_mib':2048,'compute_percent':50,'clients':1,'vcpus':vmi['spec']['domain']['cpu']['cores'],'ram':vmi['spec']['domain']['resources']['requests']['memory'],'vm_cpus':'32-39' if slot=='a' else '40-47','worker_cpus':'48-51' if slot=='a' else '52-55','ssh':s.ssh,'scp':s.scp,'out':str(s.out),'clock_offset':s.offset}
   rows.append(row);save(out/'sessions.json',rows)
   print('VM_PREPARED',slot,s.name,flush=True)
  for field in ['namespace','channel_uid','worker_uid','pvc_uid','pv']:
   assert rows[0][field]!=rows[1][field],field
  save(out/'status.json',{'status':'PREPARED','gpu_computation_verified':False,'measurement_started':False,'sessions':rows,'next_step':'Install verified bundle and validate workload; recheck channel state before use'})
  save(BASE/'e2-prepared-pair.json',{'preparation':str(out),'sessions':rows})
  print('PAIR_PREPARED',out,flush=True)
 except Exception as e:
  save(out/'failure.json',{'error':str(e)})
  for s in sessions:
   try:s.close()
   except Exception as cleanup:save(s.out/'cleanup-error.json',{'error':str(cleanup)})
  raise
if __name__=='__main__':main()
