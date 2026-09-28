"""Three new allocations: real SHM request/response trace and 1 MiB correctness.

Requires Stage 1 preparation helpers and a separately built trace-enabled Worker
image. Only this experiment's UID-bound channels are drained. No benchmark matrix.
"""
import argparse
import csv
import datetime
import gzip
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import threading
import time

from campaign_runtime import Run, ROOT, NS, GPU, call, k, get, save, wait
from run_stage1 import clean_object
from verify_stage2 import parse, NAMES, verify

HTML='''<!doctype html><meta charset="utf-8"><title>Stage 2 | Actual SHM traces</title>
<style>body{background:#101923;color:#e8f1f7;font:17px monospace;margin:24px}h1{font-size:28px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.box{background:#192838;padding:16px;border-radius:8px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:16px;line-height:1.3}h2{color:#8ed7ff;font-size:20px}
small{color:#a9bbce}table{border-collapse:collapse;width:100%;font-size:16px}th,td{padding:6px;border-bottom:1px solid #375063;text-align:left}
#result{color:#9aefc0}</style><h1>Stage 2 — Guest → shared memory → Worker → Guest</h1>
<small>Actual live command-output viewer / not a desktop terminal or Grafana recording. Trace ON: functionality only.</small>
<pre id="heading"></pre><pre id="binding"></pre><div class="grid">
<div class="box"><h2>Guest stderr — cudaMalloc(1 MiB)</h2><pre id="guest"></pre></div>
<div class="box"><h2>Worker pod logs — same request</h2><pre id="worker"></pre></div></div>
<h2>Observed API requests (heartbeat rows omitted)</h2><table><thead><tr><th>ID</th><th>API</th><th>Guest submit</th><th>Worker take</th><th>Worker respond</th><th>Guest receive</th><th>Transport / API</th></tr></thead><tbody id="rows"></tbody></table>
<h2>Actual Guest stdout / verification / cleanup</h2><pre id="stdout"></pre><pre id="result"></pre>
<small>Clock values are local to each endpoint. No cross-machine timestamp subtraction. Allocation handles are opaque IDs, not CPU/GPU pointers.</small>
<script>function show(id,x){document.getElementById(id).textContent=typeof x==='string'?x:JSON.stringify(x,null,2)}
async function poll(){try{const d=await(await fetch('/state.json',{cache:'no-store'})).json();window.evidence=d;
show('heading',d.run_id+' | '+d.stage+' | observed UTC '+d.utc);show('binding',d.binding||{});
for(const role of ['guest','worker'])show(role,(d[role]||[]).filter(x=>x.api_id===4112).map(x=>
  x.event+'  request_id='+x.request_id+'  monotonic_ns='+x.monotonic_ns+'\\nrequested_bytes='+x.requested_bytes+'  allocation_handle='+x.allocation_handle+
  '\\ninput_bytes='+x.input_bytes+'  output_bytes='+x.output_bytes+'\\ntransport_status='+x.transport_status+'  result_domain='+x.result_domain+'  api_result='+x.api_result).join('\\n\\n'));
const tb=document.getElementById('rows');tb.replaceChildren();for(const r of d.rows||[]){const tr=document.createElement('tr');for(const x of r){const td=document.createElement('td');td.textContent=x;tr.appendChild(td)}tb.appendChild(tr)}
show('stdout',(d.stdout||'').split('\\n').filter(Boolean).slice(-5).join('\\n'));show('result',d.validation||d.cleanup||{});
}catch(e){}setTimeout(poll,400)}poll()</script>'''

def view_rows(guest,worker):
    groups={}
    for r in guest+worker:
        if r['api_id']==3:continue
        groups.setdefault(r['request_id'],{})[(r['role'],r['event'])]=r
    rows=[]
    for i,events in sorted(groups.items()):
        one=next(iter(events.values()));ret=events.get(('guest','receive'))
        name=NAMES.get(one['api_id'],hex(one['api_id']))
        if one.get('copy_direction'):name+=' H2D' if one['copy_direction']==1 else ' D2H'
        rows.append([i,name,*['observed' if x in events else 'pending' for x in [('guest','submit'),('worker','take'),('worker','respond'),('guest','receive')]],
                     f"{ret['transport_status']} / {ret['api_result']}" if ret else 'pending'])
    return rows

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--worker-image',required=True);p.add_argument('--prefix',default='evidence-s2-0928')
    p.add_argument('--port',type=int,default=9899);a=p.parse_args()
    if not re.fullmatch(r'evidence-[a-z0-9-]{1,22}',a.prefix):p.error('Invalid experiment prefix')
    if not re.fullmatch(r'localhost/flyt-worker@sha256:[0-9a-f]{64}',a.worker_image):p.error('Pinned Worker digest required')
    base=a.base.resolve();public=a.output.resolve();art=base/'artifacts'
    for n in ['stage2-probe','campaign-probe-guest','campaign-probe-native']:
        if not os.access(art/n,os.X_OK):raise ValueError('Missing executable '+n)
    public.mkdir(parents=True,exist_ok=False)
    state={'run_id':'pending','stage':'PREPARING','utc':''};lock=threading.Lock()
    def update(**kw):
        with lock:
            state.update(kw,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
            save(public/'live-state.json',state)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):
            if self.path not in ['/','/state.json']:self.send_error(404);return
            with lock:body=json.dumps(state).encode() if self.path=='/state.json' else HTML.encode()
            self.send_response(200);self.send_header('Content-Type','application/json' if self.path=='/state.json' else 'text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
    server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    before=json.loads(k(['get','vmi','-A','-o','json']))['items']
    save(public/'baseline-vmis.json',[{'namespace':v['metadata']['namespace'],'name':v['metadata']['name'],'uid':v['metadata']['uid'],'phase':v['status']['phase']} for v in before])
    try:
        for index in range(1,4):
            run=Run(base,f'{a.prefix}-{index:02d}',compute=50,worker_image=a.worker_image,scope='stage2 request trace; not timing')
            out=public/'runs'/run.name;out.mkdir(parents=True)
            update(run_id=run.name,stage='PREPARING',guest=[],worker=[],rows=[],stdout='',validation={},cleanup={},binding={})
            proc=None
            try:
                run.prepare()
                ch=get('flytsharedmemorychannel',run.name+'-channel');s=ch['status']
                binding={'allocation':s['allocation'],'generation':s['generation'],'session_id':s['sessions'][0],
                         'gpu_uuid':s['gpuUUID'],'channel_uid':run.uid,'worker_uid':s['workerPodUID'],'vmi_uid':run.vmi_uid}
                save(out/'trace-binding.json',binding);update(binding=binding)
                scp=['scp','-i',str(art/'guest-key'),'-o','BatchMode=yes','-o','UserKnownHostsFile='+str(run.out/'known-hosts')]
                call(scp+[str(art/'stage2-probe'),'ubuntu@'+run.ip+':/tmp/campaign/'])
                seed=2026+index
                command='cd /tmp/campaign && sudo env FLYT_TRACE_REQUESTS=1 FLYT_LAYOUT=/tmp/campaign/layout.bin FLYT_IVSHMEM_BDF='+run.bdf+' FLYT_SLOT=0 LD_LIBRARY_PATH=/tmp/campaign ./stage2-probe '+str(seed)
                save(out/'command.json',{'command':command,'worker_logs_command':f'kubectl logs -n {NS} {run.worker}',
                                       'probe_sha256':hashlib.sha256((art/'stage2-probe').read_bytes()).hexdigest(),
                                       'guest_library_sha256':hashlib.sha256((art/'libflyt_guest.so').read_bytes()).hexdigest(),
                                       'worker_image':a.worker_image,'trace_on':True,'timing_experiment':False})
                runtime_saved=False
                with (out/'stdout.jsonl').open('w') as stdout,(out/'guest-stderr.txt').open('w') as stderr:
                    proc=subprocess.Popen(run.ssh+[command],stdout=stdout,stderr=stderr,text=True)
                    deadline=time.monotonic()+180
                    while True:
                        if time.monotonic()>deadline:raise TimeoutError('Stage 2 probe timeout')
                        log=k(['logs','-n',NS,run.worker]);(out/'worker-stderr.txt').write_text(log)
                        guest=parse((out/'guest-stderr.txt').read_text());worker=parse(log)
                        text=(out/'stdout.jsonl').read_text();events=[json.loads(l) for l in text.splitlines() if l.startswith('{') and l.endswith('}')]
                        last=events[-1] if events else {}
                        stage=last.get('operation',last.get('event','RUNNING'))
                        update(stage=stage,guest=guest,worker=worker,rows=view_rows(guest,worker),stdout=text)
                        if any(r['api_id']==0x1010 for r in worker) and not runtime_saved:
                            runtime=json.loads(k(['exec','-i','-n',NS,'evidence-c28-affinity','--','python3','-',s['workerPodUID']],
                                                 input=(ROOT/'experiments/evidence/campaign_runtime_info.py').read_text()))
                            save(out/'runtime-libraries.json',runtime)
                            applied={key:clean_object(get(kind,name),pod=(key=='worker')) for key,kind,name in
                                     [('request','flytgpurequest',run.name+'-request'),('profile','flytgpuprofile',run.name+'-profile'),
                                      ('channel','flytsharedmemorychannel',run.name+'-channel'),('worker','pod',run.worker)]}
                            save(out/'applied.json',applied)
                            (out/'gpu-processes.csv').write_text(call(['nvidia-smi','-i',GPU,'--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory','--format=csv']))
                            runtime_saved=True
                        if proc.poll() is not None:break
                        time.sleep(.5)
                save(out/'process.json',{'exit_code':proc.returncode})
                if proc.returncode:raise RuntimeError('Guest probe failed')
                # Re-read after process exit to include the destructor's GOODBYE.
                (out/'worker-stderr.txt').write_text(k(['logs','-n',NS,run.worker]))
                hashes={}
                for name in ['input','reference','output']:
                    line=call(run.ssh+['sha256sum /tmp/campaign/stage2-'+name+'.bin']).strip()
                    hashes[name]=line.split()[0]
                save(out/'array-hashes.json',hashes)
                call(scp+['ubuntu@'+run.ip+':/tmp/campaign/stage2-output.bin',str(run.out/'output.bin')])
                (out/'output.bin.gz').write_bytes(gzip.compress((run.out/'output.bin').read_bytes(),mtime=0))
                guest=parse((out/'guest-stderr.txt').read_text());worker=parse((out/'worker-stderr.txt').read_text())
                update(stage='PROBE_COMPLETE',guest=guest,worker=worker,rows=view_rows(guest,worker),stdout=(out/'stdout.jsonl').read_text())
                time.sleep(5)
            finally:
                if proc is not None and proc.poll() is None:
                    proc.terminate();proc.wait(timeout=10)
                run.close()
                wait(lambda:not get('vmi',run.name) and not get('pod',run.name+'-channel-worker'),seconds=180)
                for filename in ['manifest.json','identity.json','cpu-pinning.txt','cleanup.json','host-events.jsonl']:
                    if (run.out/filename).exists():shutil.copy2(run.out/filename,out/filename)
                save(out/'released-channel.json',clean_object(get('flytsharedmemorychannel',run.name+'-channel')))
            result=verify(out);save(out/'validation.json',result)
            with (out/'requests.csv').open('w') as f:
                fields=list(dict.fromkeys(k for row in result['joined'] for k in row))
                writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(result['joined'])
            update(stage='RELEASED',validation={k:v for k,v in result.items() if k!='joined'},cleanup={'released':True,'vmi_and_worker_absent':True})
            time.sleep(5)
        after=json.loads(k(['get','vmi','-A','-o','json']))['items']
        baseline={(v['metadata']['namespace'],v['metadata']['name'],v['metadata']['uid']) for v in before}
        remaining={(v['metadata']['namespace'],v['metadata']['name'],v['metadata']['uid']) for v in after}
        if remaining!=baseline:raise RuntimeError('Baseline VMI set changed')
        save(public/'final-audit.json',{'baseline_vmi_set_preserved':True,'vmi_and_worker_absent':True,
                                      'gpu_processes_after':call(['nvidia-smi','-i',GPU,'--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader']).strip()})
        update(stage='COMPLETE',complete=True);time.sleep(8)
    except Exception as e:
        update(stage='FAILED',error=f'{type(e).__name__}: {e}');raise
    finally:server.shutdown()

if __name__=='__main__':main()
