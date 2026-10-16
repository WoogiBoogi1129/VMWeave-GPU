"""Expose collected samples without replacing their original timestamps/files."""
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
import json,time
ROOT=Path(__file__).resolve().parents[1]/'results/20261016'
def run_label(p):
 return ('equal-budget-' if 'equal-budget' in p.relative_to(ROOT).parts else '')+p.parent.parent.name
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  lines=[]
  files=list(ROOT.glob('**/gpu.csv'))
  if files:
   p=max(files,key=lambda p:p.stat().st_mtime)
   if time.time()-p.stat().st_mtime<5:
    rows=p.read_text().strip().splitlines();parts=rows[-1].split(',')
    if len(parts)==6:
     for k,v in zip(['utilization','memory_MiB','clock_MHz','power_W','temperature_C'],parts[1:]):
      try:lines.append(f'ai_gpu_{k}{{run="{run_label(p)}",condition="{p.parent.name}"}} {float(v)}')
      except ValueError:pass
  for p in ROOT.glob('**/result.json'):
   try:
    r=json.loads(p.read_text())
    if 'samples_per_second' in r:lines.append(f'ai_throughput{{run="{run_label(p)}",condition="{p.parent.name}"}} {r["samples_per_second"]}')
   except (ValueError,OSError):pass
  body=('\n'.join(lines)+'\n').encode();self.send_response(200);self.send_header("Content-Type","text/plain; version=0.0.4");self.end_headers();self.wfile.write(body)
 def log_message(self,*a):pass
HTTPServer(('127.0.0.1',19898),Handler).serve_forever()
