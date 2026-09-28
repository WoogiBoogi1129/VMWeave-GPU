"""Local Prometheus exporter for Stage3: actual JSONL, HAMi and nvidia-smi only."""
import argparse,json,re,subprocess,threading,time,urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--observations',type=Path,required=True);a=p.parse_args()
state={'text':''};lock=threading.Lock()
def sample():
 while True:
  start=time.time();lines=[];obs={'host_utc':start,'errors':[]}
  for po in sorted(a.output.glob('pair-*')):
   for role,limit in [('A',1024),('B',4096)]:
    f=po/role/'stdout.jsonl'
    if not f.exists():continue
    rows=[]
    for s in f.read_text().splitlines():
     try:rows.append(json.loads(s))
     except ValueError:pass
    if not rows:continue
    labels='{pair='+json.dumps(po.name)+',vm='+json.dumps(role)+'}'
    progress=[x for x in rows if x['event']=='PROGRESS']
    values={'live_bytes':rows[-1]['live_allocated_bytes'],'limit_bytes':limit*1048576,'completed_checks_total':len(progress),'mismatches_total':sum(x['mismatches'] for x in progress),'oom_total':sum(x['event']=='ALLOC' and x['api_result']==2 for x in rows),'last_guest_event_utc':rows[-1]['utc_seconds']}
    for key,value in values.items():lines.append('s3_'+key+labels+' '+str(value))
  try:
   with urllib.request.urlopen('http://192.168.24.21:31992/metrics',timeout=.7) as r:hami=r.read().decode()
   selected=[x for x in hami.splitlines() if 'evidence-s3-0929-' in x and x.startswith('hami_container_device_memory_bytes{')];obs['hami_raw']=selected
   for row in selected:
    match=re.search(r'pod="evidence-s3-0929-(\d+)-([ab])-channel-worker"',row)
    if match:lines.append('s3_hami_memory_bytes{pair="pair-'+match[1]+'",vm="'+match[2].upper()+'"} '+row.rsplit(' ',1)[1])
  except Exception as e:obs['errors'].append('HAMi: '+str(e))
  try:
   raw=subprocess.check_output(['nvidia-smi','-i','GPU-7d708c42-8d4a-16d5-0746-474567157aa3','--query-gpu=uuid,memory.used','--format=csv,noheader,nounits'],text=True,timeout=.7).strip();obs['gpu_raw']=raw;lines.append('s3_gpu_total_memory_bytes '+str(float(raw.split(',')[1])*1048576))
  except Exception as e:obs['errors'].append('GPU: '+str(e))
  obs['duration_seconds']=time.time()-start;obs['prometheus_text']='\n'.join(lines)
  lines+=['s3_collector_errors '+str(len(obs['errors'])),'s3_collector_timestamp_seconds '+str(start)]
  with a.observations.open('a') as f:f.write(json.dumps(obs)+'\n')
  with lock:state['text']='\n'.join(lines)+'\n'
  time.sleep(max(.05,1-(time.time()-start)))
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path!='/metrics':self.send_error(404);return
  with lock:body=state['text'].encode()
  self.send_response(200);self.send_header('Content-Type','text/plain; version=0.0.4');self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass
threading.Thread(target=sample,daemon=True).start();ThreadingHTTPServer(('127.0.0.1',9898),Handler).serve_forever()
