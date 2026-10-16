"""Dedicated local Prometheus exporter; preserve raw target-GPU observations."""
import json,time,subprocess,threading,urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'.local/vram-accounting-20261016';BASE.mkdir(exist_ok=True)
GPU='GPU-7d708c42-8d4a-16d5-0746-474567157aa3';latest='';state={}
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):
  data=latest.encode();self.send_response(200);self.send_header('Content-Type','text/plain; version=0.0.4');self.end_headers();self.wfile.write(data)
def loop():
 global latest
 with (BASE/'monitor.jsonl').open('a',buffering=1) as f:
  while True:
   try:
    h=urllib.request.urlopen('http://10.97.206.19:31992/metrics',timeout=2).read().decode();h='\n'.join(l for l in h.splitlines() if GPU in l and l.startswith('hami_container_device_memory_bytes'))
    g=subprocess.check_output(['nvidia-smi','-i',GPU,'--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=3).strip().split(',')
    ps=subprocess.check_output(['nvidia-smi','-i',GPU,'--query-compute-apps=pid,used_gpu_memory,process_name','--format=csv,noheader,nounits'],text=True,timeout=3).strip()
    try:s=json.loads((BASE/'state.json').read_text())
    except (FileNotFoundError,json.JSONDecodeError):s={}
    row={'utc':time.time(),'gpu_mib':float(g[0]),'util_pct':float(g[1]),'processes':ps,'hami':h,'state':s};f.write(json.dumps(row)+'\n')
    lines=[h,f'vram_device_used_bytes {float(g[0])*1048576}',f'vram_device_util_pct {float(g[1])}']
    for name,v in s.items():
     for key in ['live_requested','free','total']:
      if key in v:lines.append(f'vram_{key}_bytes{{run="{name}"}} {v[key]}')
    latest='\n'.join(lines)+'\n'
   except Exception as e:f.write(json.dumps({'utc':time.time(),'error':str(e)})+'\n')
   time.sleep(.5)
threading.Thread(target=loop,daemon=True).start();ThreadingHTTPServer(('127.0.0.1',19896),Handler).serve_forever()
