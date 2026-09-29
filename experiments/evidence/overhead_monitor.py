"""Read-only 1-second GPU/CPU collector and standard Prometheus exporter."""
import argparse,json,os,subprocess,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
p=argparse.ArgumentParser();p.add_argument('base',type=Path);a=p.parse_args();os.sched_setaffinity(0,{48,49,50,51});cache='';lock=threading.Lock()
def loop():
 global cache
 while True:
  t=time.time();o={'utc':t,'errors':[]};m=[]
  try:
   state=json.loads((a.base/'state.json').read_text());labels='{session='+json.dumps(state['session'])+',path='+json.dumps(state['path'])+'}';o['state']=state
   raw=subprocess.check_output(['nvidia-smi','-i','GPU-7d708c42-8d4a-16d5-0746-474567157aa3','--query-gpu=uuid,utilization.gpu,memory.used,temperature.gpu,clocks.sm,clocks.mem,power.draw','--format=csv,noheader,nounits'],text=True,timeout=.8).strip();o['gpu_raw']=raw;v=raw.split(',')
   for i,key in enumerate(['gpu_util_percent','gpu_memory_mib','gpu_temperature_c','gpu_sm_clock_mhz','gpu_mem_clock_mhz','gpu_power_w'],1):m.append('perf_'+key+labels+' '+str(float(v[i])))
   f=a.base/'cpu.jsonl'
   if f.exists():
    with f.open('rb') as h:h.seek(max(0,f.stat().st_size-16000));rows=h.read().decode().splitlines()
    cpu=json.loads(rows[-1]);o['cpu']=cpu
    if cpu.get('session')==state['session']:
     for pod in cpu['pods']:m.append('perf_pod_cpu_seconds_total'+labels[:-1]+',role='+json.dumps(pod['role'])+'} '+str(pod['usage_usec']/1e6))
  except Exception as e:o['errors'].append(str(e))
  m+=['perf_collector_errors '+str(len(o['errors'])),'perf_collector_timestamp_seconds '+str(t)];o['duration']=time.time()-t
  with (a.base/'observations.jsonl').open('a') as f:f.write(json.dumps(o)+'\n')
  with lock:cache='\n'.join(m)+'\n'
  time.sleep(max(.05,1-(time.time()-t)))
class H(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path!='/metrics':self.send_error(404);return
  with lock:b=cache.encode()
  self.send_response(200);self.send_header('Content-Type','text/plain; version=0.0.4');self.end_headers();self.wfile.write(b)
 def log_message(self,*args):pass
threading.Thread(target=loop,daemon=True).start();ThreadingHTTPServer(('127.0.0.1',9898),H).serve_forever()
