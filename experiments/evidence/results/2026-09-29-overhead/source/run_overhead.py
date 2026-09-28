"""Sequential N/T/S campaign. Preregistered 7 windows per fresh session."""
import argparse,gzip,hashlib,json,os,shlex,shutil,subprocess,sys,time
from pathlib import Path
import campaign_runtime as c
from overhead_tcp import TCP
P=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--repetitions',default='1,2,3');p.add_argument('--condition-mask',type=int,default=127);a=p.parse_args();b=a.base.resolve();output=a.output.resolve();output.mkdir(parents=True,exist_ok=True)
c.WORKER=json.loads((b/'images.json').read_text())['worker']
orders=['NTS','TSN','SNT'];rotation=[0,2,4]
def cleanpod(p):
 return {'name':p['metadata']['name'],'uid':p['metadata']['uid'],'image_status':p.get('status',{}).get('containerStatuses'),'annotations':p['metadata'].get('annotations',{}),'node':p['spec'].get('nodeName')}
def copyback(r,prefix,dest):
 scp=['scp','-i',str(b/'artifacts/guest-key'),'-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(r.out/'known-hosts')]
 c.call(scp+['ubuntu@'+r.ip+':'+prefix+'-*',str(dest)],timeout=300)
for rep in map(int,a.repetitions.split(',')):
 for label in orders[(rep-1)%3]:
  session=f'r{rep}-{label}';name=f'evidence-perf-{rep}-{label.lower()}';out=output/session;out.mkdir(exist_ok=False)
  r=TCP(b,name) if label=='T' else c.Run(b,name,backend='shm' if label=='S' else 'native-hami-disabled',worker_image=c.WORKER)
  print('SESSION_START',session,time.time(),flush=True)
  try:
   inventory=c.call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader']);(out/'gpu-before.csv').write_text(inventory)
   if c.GPU in inventory:raise RuntimeError('Target GPU has an existing compute process; refusing overlapping measurement')
   r.prepare();identity=json.loads((r.out/'identity.json').read_text());identity.update({'path':label,'session':session,'cpu_sampling':'nonoverlapping whole Pod cgroups','trace':'off','condition_rotation':rotation[(rep-1)%3]})
   if label=='N':uids={'native':r.uid};identity['pod']=cleanpod(c.get('pod',r.name))
   else:uids={'launcher':identity['launcher_uid'],'server':identity.get('worker_uid',identity.get('cell_uid'))}
   c.save(out/'identity.json',identity);c.save(b/'state.json',{'session':session,'path':label,'uids':uids})
   if label!='N':
    clocks=[]
    for _ in range(5):
     t0=time.time();g=float(c.call(r.ssh+['date +%s.%N']).strip());t1=time.time();clocks.append({'host_before':t0,'guest':g,'host_after':t1,'offset':g-(t0+t1)/2,'uncertainty':(t1-t0)/2})
    c.save(out/'clock-map.json',clocks)
   if label=='S':
    c.call(['scp','-i',str(b/'artifacts/guest-key'),'-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(r.out/'known-hosts'),str(b/'artifacts/probe-S'),str(b/'artifacts/work.ptx'),'ubuntu@'+r.ip+':/tmp/campaign/'])
    prefix='/tmp/campaign/'+session;cmd=r.ssh+['sudo env FLYT_TRACE_REQUESTS=0 FLYT_LAYOUT=/tmp/campaign/layout.bin FLYT_IVSHMEM_BDF='+r.bdf+' FLYT_SLOT=0 LD_LIBRARY_PATH=/tmp/campaign /tmp/campaign/probe-S batch 30 60 10 '+prefix+' /tmp/campaign/work.ptx '+str(rotation[(rep-1)%3])+' '+str(a.condition_mask)]
   elif label=='T':
    prefix='/tmp/perf/'+session;cmd=r.ssh+['sudo env SM_CORE='+str(r.sm)+' LD_LIBRARY_PATH=/tmp/perf /tmp/perf/probe-T batch 30 60 10 '+prefix+' /tmp/perf/work.cubin '+str(rotation[(rep-1)%3])+' '+str(a.condition_mask)]
   else:
    prefix='/evidence/'+session;cmd=['kubectl','exec','-n',c.NS,r.name,'--','taskset','-c','0-7','/evidence/probe-N','batch','30','60','10',prefix,'/evidence/work.ptx',str(rotation[(rep-1)%3]),str(a.condition_mask)]
   c.save(out/'command.json',{'command':cmd[-1] if label!='N' else shlex.join(cmd),'durations':{'micro':30,'throughput':60,'warmup_min':10,'warmup_iterations_min':50}})
   library=False;results=[]
   with (out/'stdout.txt').open('w') as f,(out/'stderr.txt').open('w') as err,(out/'host-events.jsonl').open('w') as events:
    proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=err,text=True)
    import threading
    timer=threading.Timer(1500,proc.kill);timer.start()
    try:
     for line in proc.stdout:
      f.write(line);f.flush()
      if not line.startswith('{'):continue
      try:row=json.loads(line)
      except ValueError:continue
      events.write(json.dumps({'host_received_utc':time.time(),'record':row})+'\n');events.flush()
      print(session,line.strip(),flush=True)
      if row['event']=='RESULT':results.append(row)
      if row['event']=='WARMUP_START' and not library:
       uid=r.uid if label=='N' else c.get('pod',r.worker)['metadata']['uid']
       info=c.k(['exec','-i','-n',c.NS,'evidence-c28-affinity','--','python3','-',uid],input=(P/'overhead_runtime_info.py').read_text())
       runtime=json.loads(info);c.save(out/'runtime-libraries.json',runtime)
       if label in ['N','S']:
        assert runtime and all(x['environment'].get('GPU_CORE_UTILIZATION_POLICY')=='DISABLE' for x in runtime)
        assert all(any('libvgpu' in p for p in x['library_hashes']) for x in runtime)
        assert all(x['environment'].get('FLYT_TRACE_REQUESTS') in [None,'0'] and not x['environment'].get('FLYT_TRACE_CALLS') for x in runtime)
       else:
        assert runtime and not any('libvgpu' in p for x in runtime for p in x['library_hashes'])
       (out/'gpu-processes.csv').write_text(c.call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_memory','--format=csv']))
       library=True
       if label=='T':
        (out/'tcp-connections.txt').write_text(c.call(r.ssh+['ss -tnp; ip -brief address; uname -a; cat /etc/os-release']))
        (out/'rpcinfo.txt').write_text(c.k(['exec','-n',c.NS,r.worker,'--','rpcinfo','-p','127.0.0.1']))
     code=proc.wait(timeout=1500)
    finally:
     timer.cancel()
     if proc.poll() is None:proc.terminate()
   c.save(out/'execution.json',{'exit_code':code,'results':results,'expected_windows':a.condition_mask.bit_count()})
   if code or len(results)!=a.condition_mask.bit_count() or any(x['status']!='PASS' for x in results):raise RuntimeError('Invalid session '+session)
   incoming=r.out/'samples';incoming.mkdir()
   if label=='N':
    for f in (b/'artifacts').glob(session+'-*'):shutil.copy2(f,incoming/f.name)
   else:copyback(r,prefix,incoming)
   for f in incoming.iterdir():
    if f.suffix=='.csv':
     with f.open('rb') as src,(out/(f.name+'.gz')).open('wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0,compresslevel=6) as gz:shutil.copyfileobj(src,gz)
    else:shutil.copy2(f,out/f.name)
   if label=='S':(out/'worker.log').write_text(c.k(['logs','-n',c.NS,r.worker]))
   if label=='T':(out/'client-manager.log').write_text(c.call(r.ssh+['sudo cat /tmp/perf/manager.log']))
  except Exception as e:
   c.save(out/'failure.json',{'error':str(e),'utc':time.time()});raise
  finally:
   r.close()
   for file in ['cleanup.json','cpu-pinning.txt','cell.log','resource-seed.txt','guest-dependencies.txt']:
    if (r.out/file).exists():shutil.copy2(r.out/file,out/file)
   c.save(b/'state.json',{'session':'between-sessions','path':'none','uids':{}})
  print('SESSION_COMPLETE',session,time.time(),flush=True)
print('CAMPAIGN_COMPLETE',time.time(),flush=True)
