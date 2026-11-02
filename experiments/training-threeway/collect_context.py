#!/usr/bin/env python3
"""Read existing Prometheus history; never execute a GPU workload or change settings."""
import argparse
import concurrent.futures
import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

SERVICE='http://10.103.23.115:9090'
NODE='192.168.24.21:9100'
OTHER_GPUS=['GPU-7d708c42-8d4a-16d5-0746-474567157aa3','GPU-c654d43e-43f8-c28e-77c2-1f17a0cbf46a','GPU-1b4de6a0-88ae-4004-98b9-035906a2473f']


def request(path,params):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(SERVICE+path+'?'+urllib.parse.urlencode(params),timeout=20) as response:
        value=json.load(response)
    assert value['status']=='success'
    return value


def collect(root,output=None,preview=False):
    if not preview:assert (root/'measurements-complete.json').exists()
    output=output or root/'host-context'
    output.mkdir(parents=True,exist_ok=False)
    save=lambda name,x:(output/name).write_text(json.dumps(x,indent=2)+'\n')
    protocol=json.loads((root/'protocol.json').read_text())
    exits=[json.loads(p.read_text()) for p in (root/'formal').glob('*/*/*/exit.json')]
    end=max(x['end_utc'] for x in exits)
    start=math.ceil(protocol['created_utc']/30)*30
    end=math.floor(end/30)*30
    expected=int((end-start)/30)+1
    node=f'instance="{NODE}"'
    gpu='DCGM_FI_DEV_GPU_UTIL{hostname="gpu-4",UUID=~"'+'|'.join(OTHER_GPUS)+'"}'
    queries={
        'other_gpu_util_percent':(gpu+' and (time()-timestamp('+gpu+')<60)','UUID'),
        'host_load1':('node_load1{'+node+'}',None),
        'host_nonidle_cpu_percent':('100*(1-avg(rate(node_cpu_seconds_total{'+node+',mode="idle"}[1m])))',None),
        'assigned_cpu_nonidle_percent':('100*(1-rate(node_cpu_seconds_total{'+node+',mode="idle",cpu=~"0|1|2|3|4|5|6|7|8|9|10|11"}[1m]))','cpu'),
        'host_memory_available_bytes':('node_memory_MemAvailable_bytes{'+node+'}',None),
    }
    meta={'collected_utc':time.time(),'service':SERVICE,'node_instance':NODE,'start_utc':start,'end_utc':end,'step_seconds':30,'gpu_max_sample_age_seconds':60,'expected_evaluations':expected,'preview':preview,
          'scope':'Existing Prometheus history, 30s query evaluations. GPU samples older than60s excluded. Values are resampled, not independent repeats. Exporter restarts cause gaps. Host CPU includes this experiment.'}
    try:
        identity=request('/api/v1/query',{'query':'node_uname_info{'+node+'}'})
        assert any(x['metric'].get('nodename')=='gpu-4' for x in identity['data']['result'])
        save('node-identity.json',identity)
    except Exception as error:
        meta.update(available=False,error=type(error).__name__)
        save('summary.json',meta)
        return meta

    def fetch(item):
        name,(query,label)=item
        try:
            raw=request('/api/v1/query_range',{'query':query,'start':start,'end':end,'step':30})
            save(name+'.json',{'query':query,'response':raw})
            groups={}
            for series in raw['data']['result']:
                key=series['metric'].get(label,'all') if label else 'all'
                group=groups.setdefault(key,{'values':[],'timestamps':{},'invalid_values':0})
                for timestamp,value in series['values']:
                    value=float(value)
                    if not math.isfinite(value) or (name=='other_gpu_util_percent' and not 0<=value<=100):
                        group['invalid_values']+=1
                        continue
                    group['values'].append(value)
                    group['timestamps'][timestamp]=group['timestamps'].get(timestamp,0)+1
            stats={}
            for key,group in groups.items():
                values=group['values'];timestamps=group['timestamps']
                stats[key]={'min':min(values) if values else None,'max':max(values) if values else None,'resampled_values':len(values),'covered_evaluations':len(timestamps),'coverage_fraction':len(timestamps)/expected,'overlap_evaluations':sum(n>1 for n in timestamps.values()),'invalid_values':group['invalid_values']}
            return name,{'query':query,'series':len(raw['data']['result']),'groups':stats,'available':bool(stats)}
        except Exception as error:
            return name,{'query':query,'available':False,'error':type(error).__name__}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        meta['queries']=dict(pool.map(fetch,queries.items()))
    meta['available']=any(x['available'] for x in meta['queries'].values())
    save('summary.json',meta)
    return meta


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path(__file__).parent/'results/20261102')
    parser.add_argument('--preview-output',type=Path)
    args=parser.parse_args()
    if args.preview_output:assert '.local' in args.preview_output.parts
    result=collect(args.root,args.preview_output,bool(args.preview_output))
    print(json.dumps({'available':result['available'],'preview':result['preview']}))
