"""Read-only HAMi and NVML collection, also exposed for local Prometheus."""
import json,time,subprocess,threading,urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'.local/sm-pair-20261016';GPU='GPU-c654d43e-43f8-c28e-77c2-1f17a0cbf46a';latest=''
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):
  self.send_response(200);self.send_header('Content-Type','text/plain; version=0.0.4');self.end_headers();self.wfile.write(latest.encode())
def loop():
 global latest
 with (BASE/'monitor.jsonl').open('a',buffering=1) as f:
  while True:
   try:
    h=urllib.request.urlopen('http://10.97.206.19:31992/metrics',timeout=2).read().decode()
    h='\n'.join(l for l in h.splitlines() if GPU in l and 'pod="sm-pair-' in l and l.startswith('hami_container_device_'))
    raw=subprocess.check_output(['nvidia-smi','-i',GPU,'--query-gpu=utilization.gpu,memory.used,clocks.sm,power.draw','--format=csv,noheader,nounits'],text=True,timeout=3).strip()
    g=list(map(float,raw.split(',')))
    try:state=json.loads((BASE/'state.json').read_text())
    except (FileNotFoundError,json.JSONDecodeError):state={}
    utc=time.time();f.write(json.dumps({'utc':utc,'gpu_util':g[0],'memory_mib':g[1],'clock_mhz':g[2],'power_w':g[3],'hami':h,'state':state})+'\n')
    lines=[h,f'sm_pair_gpu_util {g[0]}',f'sm_pair_memory_mib {g[1]}']
    for i,worker in enumerate(state.get('workers',[])):
     lines.append(f'sm_pair_core_limit{{pod="{worker}"}} {state["caps"][i]}')
    latest='\n'.join(lines)+'\n'
   except Exception as e:f.write(json.dumps({'utc':time.time(),'error':repr(e)})+'\n')
   time.sleep(.8)
threading.Thread(target=loop,daemon=True).start();ThreadingHTTPServer(('127.0.0.1',19897),Handler).serve_forever()
