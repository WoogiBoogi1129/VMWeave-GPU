"""Audited, host-only diagnostics; never modify the original campaign bundle."""
import csv,gzip,hashlib,json,os,random,statistics,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
BASE=ROOT/'.local/shm-latency-20261001'
RESULTS=HERE/'results'
RESULTS.mkdir(exist_ok=False)
LIB=ROOT/'.local/performance-20260930/artifacts/libflyt_guest.so'
original=ROOT/'experiments/evidence/results/2026-09-30-performance'
protocol=json.loads((original/'protocol.json').read_text())
assert hashlib.sha256(LIB.read_bytes()).hexdigest()==protocol['artifact_sha256'][LIB.name]
def run(args):
    start=time.time();r=subprocess.run(list(map(str,args)),cwd=ROOT,text=True,capture_output=True,timeout=120)
    with (RESULTS/'commands.jsonl').open('a') as f:f.write(json.dumps({'utc':start,'argv':list(map(str,args)),'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'seconds':time.time()-start})+'\n')
    if r.returncode:raise RuntimeError(r.stderr)
    return r.stdout
run(['gcc','-O2','-Wall','-Wextra','-Werror','-pthread','-Iruntime/shm/shm-queue/include','-Iruntime/shm/shm-contract/include',HERE/'queue_probe.c','-L'+str(LIB.parent),'-Wl,-rpath,'+str(LIB.parent),'-lflyt_guest','-o',BASE/'queue-probe'])
run(['gcc','-O2','-Wall','-Wextra','-Werror',HERE/'copy_probe.c','-o',BASE/'copy-probe'])
metadata={'utc':time.time(),'source_commit':run(['git','rev-parse','HEAD']).strip(),'library_sha256':hashlib.sha256(LIB.read_bytes()).hexdigest(),'scope':'Host normal-RAM queue/copy component tests. No VM, CUDA, HAMi, BAR mapping or Guest I/O thread. No original measurements altered.','cpu_affinity':[48,50],'lscpu':run(['lscpu']),'uname':run(['uname','-a']),'compiler':run(['gcc','--version']),'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.c')},'binaries':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [BASE/'queue-probe',BASE/'copy-probe']}}
(RESULTS/'environment.json').write_text(json.dumps(metadata,indent=2)+'\n')
for symbol in ['flyt_shm_worker_take','flyt_shm_try_receive','flyt_shm_receive','flyt_shm_submit']:
    (RESULTS/(symbol+'.asm')).write_text(run(['objdump','-d','--disassemble='+symbol,LIB]))
conditions=[(p,0,16) for p in ['stock','worker_spin','guest_spin','both_spin']]+[('both_spin',a,b) for n in [4096,1048576,16777216] for a,b in [(n,0),(0,n)]]
rows=[]
for rep in range(1,4):
    order=conditions.copy();random.Random(20261001+rep).shuffle(order)
    for policy,a,b in order:
        name=f'q-r{rep}-{policy}-{a}-{b}';path=BASE/(name+'.csv')
        r=json.loads(run([BASE/'queue-probe',policy,a,b,1,path]));r.update(repeat=rep,name=name)
        with path.open() as f:lat=[float(x['seconds']) for x in csv.DictReader(f)]
        assert len(lat)==r['count'] and abs(statistics.mean(lat)*1e6-r['mean_us'])<.001
        assert r['final_payload_check']=='PASS'
        with gzip.open(RESULTS/(name+'.csv.gz'),'wb') as f:f.write(path.read_bytes())
        rows.append(r);print(name,round(r['mean_us'],3),'us',flush=True)
copies=[]
for rep in range(1,4):
    order=[(method,n) for method in ['snapshot','memcpy'] for n in [4096,1048576,16777216]]
    random.Random(20261011+rep).shuffle(order)
    for method,n in order:
        r=json.loads(run(['taskset','-c','48',BASE/'copy-probe',method,n]));r['repeat']=rep;copies.append(r)
summary={'queue':rows,'copies':copies,'queue_summary':{},'copy_summary':{}}
for policy,a,b in conditions:
    group=[r for r in rows if (r['policy'],r['input_bytes'],r['output_bytes'])==(policy,a,b)]
    summary['queue_summary'][f'{policy}/{a}/{b}']={'n':len(group),'mean_us':statistics.mean(r['mean_us'] for r in group),'sd_us':statistics.stdev(r['mean_us'] for r in group),'cpu_cores':statistics.mean(r['cpu_cores'] for r in group)}
for method in ['snapshot','memcpy']:
    for n in [4096,1048576,16777216]:
        group=[r for r in copies if r['method']==method and r['bytes']==n]
        summary['copy_summary'][f'{method}/{n}']={'n':len(group),'mean_us':statistics.mean(r['mean_us'] for r in group),'sd_us':statistics.stdev(r['mean_us'] for r in group)}
(RESULTS/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print('DIAGNOSTICS_COMPLETE',json.dumps(summary['queue_summary']),flush=True)
