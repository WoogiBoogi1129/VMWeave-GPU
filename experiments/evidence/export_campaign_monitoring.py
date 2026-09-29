"""Export real Prometheus responses; optionally post recorded Grafana events.

Grafana credentials, when needed, are read from a private JSON file supplied by
--auth. Its contents are never included in exports. No generated time series.
"""
import argparse
import base64
import csv
import json
import urllib.parse
import urllib.request
from pathlib import Path
from analyze_campaign import json_lines, read_json

p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--auth',type=Path)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
registry_path=a.base/'annotation-registry.json'
registry=read_json(registry_path) if registry_path.exists() else {}
headers={'Content-Type':'application/json'}
if a.auth:
    auth=read_json(a.auth)
    headers['Authorization']='Basic '+base64.b64encode((auth['username']+':'+auth['password']).encode()).decode()
annotations=[];intervals=[]
for directory in sorted((a.base/'runs').iterdir()):
    if not (directory/'cleanup.json').exists() or not (directory/'manifest.json').exists():continue
    m=read_json(directory/'manifest.json')
    if not m['conditions'].get('phase','').startswith(('C5-','C6-')):continue
    events=list(json_lines(directory/'stdout.jsonl'))
    offset=uncertainty=0;anchor=None
    if (directory/'clock-map.json').exists():
        best=min(read_json(directory/'clock-map.json'),key=lambda r:r['uncertainty']);offset=best['offset'];uncertainty=best['uncertainty']
    if (directory/'monotonic-clock-map.json').exists():
        best=min(read_json(directory/'monotonic-clock-map.json'),key=lambda r:r['uncertainty']);anchor=best['host_minus_guest_monotonic'];uncertainty=best['uncertainty']
    times=[]
    for e in events:
        if e['event'] not in ['WARMUP_START','WARMUP_END','MEASUREMENT_START','MEASUREMENT_END']:continue
        t=e['monotonic_seconds']+anchor if anchor is not None else e['utc_seconds']-offset
        times.append(t)
        key=directory.name+':'+e['event']
        ann={'time':round(t*1000),'tags':['flyt-campaign',directory.name,e['event']],
             'text':f"{directory.name}: {e['event']}; source stdout.jsonl; clock uncertainty ±{uncertainty:.3f}s; "+('monotonic bridge' if anchor is not None else 'wall-clock mapping (may step)')}
        annotations.append(ann)
        if a.auth and key not in registry:
            req=urllib.request.Request('http://127.0.0.1:3300/api/annotations',data=json.dumps(ann).encode(),headers=headers,method='POST')
            with urllib.request.urlopen(req,timeout=10) as response:registry[key]=json.load(response)
            registry_path.write_text(json.dumps(registry,indent=2)+'\n')
    if times:
        start=min(times)-5;end=read_json(directory/'cleanup.json')['utc_seconds']+5
        intervals.append({'run_id':directory.name,'from':start,'to':end,'from_ms':round(start*1000),'to_ms':round(end*1000)})
        dest=a.output/'queries'/directory.name;dest.mkdir(parents=True,exist_ok=True)
        queries={
          'gpu':'{__name__=~"flyt_gpu_.*"}',
          'run':'{__name__=~"flyt_(run_.*|completed_work_total|compute_setting)",run_id="'+directory.name+'"}',
          'health':'{__name__=~"up|flyt_collector_timestamp_seconds|flyt_collector_errors",job="flyt-campaign"}',
          'hami':'{__name__=~"hami_container_device_.*",pod=~"'+directory.name+'(-channel-worker)?"}'}
        for name,query in queries.items():
            file=dest/(name+'.json')
            if file.exists():continue
            params={'query':query,'start':start,'end':end,'step':1}
            with urllib.request.urlopen('http://127.0.0.1:9099/api/v1/query_range?'+urllib.parse.urlencode(params),timeout=30) as response:data=json.load(response)
            if data.get('status')!='success':raise RuntimeError(data)
            file.write_text(json.dumps({'request':params,'response':data},separators=(',',':'))+'\n')
(a.output/'annotations.json').write_text(json.dumps(annotations,indent=2)+'\n')
(a.output/'intervals.json').write_text(json.dumps(intervals,indent=2)+'\n')
print(json.dumps({'exported_intervals':len(intervals),'annotations':len(annotations)}))
