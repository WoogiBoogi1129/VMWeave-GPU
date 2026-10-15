"""Sequential, fresh-process A/B measurements on an otherwise idle GPU."""
import argparse, hashlib, json, os, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / '.local/sm-core-limit-20261015/artifacts'
GPU = 'GPU-772181af-05a4-0c24-de59-8487bd37c142'

def run(variant, limit, seconds, warmup, reps, out):
    out.mkdir(parents=True, exist_ok=False)
    apps = subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader'],text=True)
    if GPU in apps: raise RuntimeError('Test GPU is occupied')
    lib = ART / ('libvgpu-'+variant+'.so')
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=GPU, LD_PRELOAD=str(lib),
               CUDA_DEVICE_MEMORY_LIMIT='2048m', CUDA_DEVICE_SM_LIMIT=str(limit),
               CUDA_DEVICE_MEMORY_SHARED_CACHE=str(out/'cache'),
               GPU_CORE_UTILIZATION_POLICY='FORCE', LIBCUDA_LOG_LEVEL='3')
    config = dict(variant=variant,limit=limit,duration_seconds=seconds,warmup=warmup,reps=reps,gpu=GPU,
                  sha256=hashlib.sha256(lib.read_bytes()).hexdigest())
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    with (out/'stdout.jsonl').open('w') as stdout, (out/'watcher.log').open('w') as stderr, (out/'gpu.csv').open('w') as samples:
        p = subprocess.Popen([str(ART/'sm-probe'),str(seconds),str(warmup),str(reps)],env=env,stdout=stdout,stderr=stderr)
        start=time.monotonic(); mapped=False
        try:
            while p.poll() is None:
                if time.monotonic()-start>seconds+90: raise TimeoutError('Probe exceeded time budget')
                if not mapped:
                    maps=Path(f'/proc/{p.pid}/maps').read_text()
                    if str(lib) in maps:
                        (out/'maps.txt').write_text(maps);mapped=True
                row=subprocess.check_output(['nvidia-smi','-i',GPU,'--query-gpu=utilization.gpu,memory.used,clocks.sm,power.draw','--format=csv,noheader,nounits'],text=True)
                samples.write(f'{time.monotonic()-start:.3f},'+row);samples.flush();time.sleep(1)
            if p.returncode: raise RuntimeError(f'Probe returned {p.returncode}')
            if not mapped: raise RuntimeError('Expected library not observed')
        finally:
            if p.poll() is None:p.terminate();p.wait(timeout=15)
    rows=[json.loads(x) for x in (out/'stdout.jsonl').read_text().splitlines() if x.startswith('{')]
    result=next(x for x in rows if x['event']=='result')
    util=[float(x.split(',')[1]) for x in (out/'gpu.csv').read_text().splitlines() if float(x.split(',')[0])>=warmup+2]
    result.update(config,device_util_mean=sum(util)/len(util),samples=len(util),returncode=p.returncode)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=int,default=270);ap.add_argument('--warmup',type=int,default=30)
    ap.add_argument('--limits',default='10,25,50,75,100');ap.add_argument('--variants',default='original,patched')
    ap.add_argument('--repeat',type=int,default=3);ap.add_argument('--reps',type=int,default=8192);ap.add_argument('--name',required=True)
    a=ap.parse_args();base=ROOT/'experiments/sm-core-limit/evidence'/a.name;results=[]
    for repeat in range(a.repeat):
        limits=list(map(int,a.limits.split(',')));variants=a.variants.split(',')
        if repeat%2:limits.reverse();variants.reverse()
        for limit in limits:
            for variant in variants:
                results.append(run(variant,limit,a.seconds,a.warmup,a.reps,base/f'r{repeat+1}-{variant}-{limit}'))
                (base/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
