"""Live Prometheus exporter and actual experiment output viewer (localhost only)."""
import argparse
import html
import json
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

GPU='GPU-7d708c42-8d4a-16d5-0746-474567157aa3'
p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--port',type=int,default=9899);a=p.parse_args()
a.base.mkdir(parents=True,exist_ok=True)
state={'metrics':'','snapshot':{}};lock=threading.Lock()
def loop():
 while True:
  started=time.time();data={'timestamp':started,'gpu_uuid':GPU,'errors':[],'runs':[]};lines=[]
  try:
   raw=subprocess.check_output(['nvidia-smi','-i',GPU,'--query-gpu=uuid,utilization.gpu,memory.used,power.draw,clocks.sm','--format=csv,noheader,nounits'],text=True,timeout=3)
   data['gpu']=raw;v=[x.strip() for x in raw.split(',')]
   for key,val in zip(['gpu_utilization_percent','gpu_memory_mib','gpu_power_watts','gpu_clock_mhz'],v[1:]):
    try:lines.append('flyt_'+key+'{gpu_uuid="'+GPU+'"} '+str(float(val)))
    except ValueError:pass
   data['processes']=subprocess.check_output(['nvidia-smi','-i',GPU,'--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory','--format=csv,noheader,nounits'],text=True,timeout=3)
  except Exception as e:data['errors'].append(str(e))
  try:
   with urllib.request.urlopen('http://192.168.24.21:31992/metrics',timeout=2) as r:raw=r.read().decode()
   chosen=[s for s in raw.splitlines() if GPU in s and ('hami_container_device_' in s or 'hami_host_gpu_memory_used_bytes' in s)]
   data['hami']='\n'.join(chosen);lines.extend(chosen)
  except Exception as e:data['errors'].append(str(e))
  for directory in sorted((a.base/'runs').glob('*')):
   try:
    m=json.loads((directory/'manifest.json').read_text());events=[]
    f=directory/'stdout.jsonl'
    if f.exists():
     for s in f.read_text().splitlines():
      try:events.append(json.loads(s))
      except ValueError:pass
    lab='{run_id='+json.dumps(directory.name)+',backend='+json.dumps(m['backend'])+',compute='+json.dumps(str(m['compute']))+'}'
    result=next((r for r in reversed(events) if r.get('event')=='RESULT'),None)
    progress=next((r for r in reversed(events) if r.get('event') in ('PROGRESS','MEASUREMENT_END','RESULT')),None)
    active=bool(events and not result and not (directory/'cleanup.json').exists())
    lines += ['flyt_run_active'+lab+' '+str(int(active)), 'flyt_compute_setting'+lab+' '+str(m['compute'])]
    if progress:lines += ['flyt_completed_work_total'+lab+' '+str(progress['completed'])]
    if result:
     for key in ['elapsed_seconds','throughput','mismatches','checked_elements']:
      lines.append('flyt_run_'+key+lab+' '+str(result[key]))
    if active:
     data['runs'].append({'run_id':directory.name,'backend':m['backend'],'compute':m['compute'],'active':active,'last_event':events[-1] if events else None})
   except (OSError,ValueError,KeyError):pass
  data['completed_at']=time.time();lines.append('flyt_collector_timestamp_seconds '+str(data['completed_at']))
  lines.append('flyt_collector_errors '+str(len(data['errors'])))
  with (a.base/'observations.jsonl').open('a') as f:f.write(json.dumps(data)+'\n')
  with lock:state.update(metrics='\n'.join(lines)+'\n',snapshot=data)
  time.sleep(max(.05,1-(time.time()-started)))

PAGE='''<!doctype html><meta charset="utf-8"><title>FLYT actual experiment output</title>
<style>body{background:#0d1421;color:#cce0f5;font:16px monospace;margin:20px}h1{font-size:24px;color:#6dd5ed}pre{white-space:pre-wrap;border:1px solid #405068;padding:14px}a{color:#6dd5ed}</style>
<h1>FLYT — actual command output / 실제 실험 기록</h1><div id="stamp"></div>
<a href="http://127.0.0.1:3300/d/flyt-campaign/flyt-campaign?orgId=1&refresh=5s" target="_blank">Open actual Grafana dashboard</a>
<h2>Experiment command & output (live file tail)</h2><pre id="terminal"></pre><h2>GPU UUID / process observation</h2><pre id="gpu"></pre>
<script>async function tick(){let d=await(await fetch('/snapshot')).json();document.getElementById('stamp').textContent=new Date(d.timestamp*1000).toISOString()+' | Source: running experiment, live read-only log viewer';document.getElementById('gpu').textContent=d.gpu+'\\n'+d.processes;document.getElementById('terminal').textContent=await(await fetch('/terminal')).text();}tick();setInterval(tick,1000)</script>'''
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  with lock:
   if self.path=='/metrics':body=state['metrics'].encode();kind='text/plain; version=0.0.4'
   elif self.path=='/snapshot':body=json.dumps(state['snapshot']).encode();kind='application/json'
   elif self.path=='/terminal':
    f=a.base/'terminal.txt';body=('\n'.join(f.read_text(errors='replace').splitlines()[-28:]) if f.exists() else 'Waiting for actual runner output').encode();kind='text/plain'
   else:body=PAGE.encode();kind='text/html'
  self.send_response(200);self.send_header('Content-Type',kind);self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass
threading.Thread(target=loop,daemon=True).start()
ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
