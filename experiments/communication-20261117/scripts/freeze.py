from common import *
from artifacts import LC,LS,COMP
import random

def freeze():
 target=O/'protocol/frozen.json'
 assert not target.exists(),'do not overwrite a frozen protocol'
 pilots={'N':'pilot-N-final','V':'pilot-V2','F':'pilot-F-final','L':'pilot-L2'}
 for mode,label in pilots.items():
  e=json.loads((O/'results'/label/'execution.json').read_text())
  assert e['status']=='passed' and len(e['results'])==16
  assert all(x['correctness']=='PASS' for x in e['results'])
 sources={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [O/'src/probe.c',O/'src/sequence.ptx',*[O/'scripts'/f for f in ['common.py','infra.py','backends.py','flyt.py','artifacts.py','run_session.py','observe.py','runtime.py']]]}
 artifacts={str(p.relative_to(B/'artifacts')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (B/'artifacts').rglob('*') if p.is_file() and not p.is_symlink() and (p.parent.name in ['N','V','F','L'] or p.name in ['sequence.cubin','sequence.ptx'])}
 orders=['NVFL','VLNF','LFVN','FNLV','NFLV']
 # First four backend orders: each backend occurs once in every position.
 assert all(len({o[i] for o in orders[:4]})==4 for i in range(4))
 blocks=[]
 for b,order in enumerate(orders,1):
  conditions=list(range(16));random.Random(20261117+b).shuffle(conditions)
  blocks.append({'block':b,'backend_order':list(order),'condition_order':conditions})
 save(target,{'schema':1,'frozen_utc':time.time(),'git_head':call(['git','rev-parse','HEAD'],cwd=R).strip(),'gpu_index':1,'gpu_uuid':GPU,'allocator':'vmweave-hami-dra; hami-core-gpu.project-hami.io','capacity':{'cores':100,'memory':'97887Mi'},'hami_policy':'default same full-capacity DRA injection; no GPU_CORE_UTILIZATION_POLICY override','cpu':{'guest_vcpu':4,'guest_memory':'16Gi','qemu':[8,9,10,11],'native':[8,9,10,11],'server':[12,13,14,15],'dedicated':False,'strict_memory_numa_binding':False},'images':{'vmweave':IM,'lupine_client':LC,'lupine_server':LS,'compiler':COMP,'flyt_cell':'localhost/flyt-gpu-cell@sha256:0b21e0df1222f5861b522994a80416e243870663372d3cd2a886d36a221efbbd'},'sources':sources,'artifacts':artifacts,'pilots':pilots,'blocks':blocks,'duration_s':30,'warmup_min_s':10,'warmup_min_operations':10,'p95_min_samples':1000,'conditions':[{'id':0,'type':'kernel','K':1},*[{'id':1+d*6+i,'type':direction,'bytes':size} for d,direction in enumerate(['H2D','D2H']) for i,size in enumerate([4,4096,65536,1048576,16777216,67108864])],*[{'id':13+i,'type':'kernel','K':K} for i,K in enumerate([10,100,1000])]],'input':'xorshift32 seed 20261117; pre-generated reusable pageable host buffers','correctness':'full transfer buffer pre/post; increment accumulator plus final sequence for kernels; CUDA status checked on every call','elapsed':'CLOCK_MONOTONIC; stop new operations at >=30s, drain last submitted batch; throughput denominator includes loop and sample-storage overhead','raw':'one uint64 little-endian elapsed_ns per completed operation/batch, gzip lossless after timing','statistics':'5 block values; paired V/F and V/L geometric ratios with log-scale t CI df4; arithmetic t CI for block metrics; no pooled-call inference','exclusions':'CUDA failure or incorrect output, foreign target-GPU process, node pressure or newly observed hardware/thermal slowdown. Preserve raw; no replacement based on performance rank/variance. Missing p95/CPU remains N/A.','limits':['single client/default stream/pageable','same-node VM-to-Pod virtual network','Lupine standalone backend, not HAMi integrated scheduler result','N is Pod baseline, not a VM transport-only control','F uses same PTX source assembled offline; N/V/L use driver PTX JIT outside timing','shared CPU, DRAM and PCIe host load remains']})
 (O/'protocol/frozen.sha256').write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  frozen.json\n')
 print('PROTOCOL_FROZEN',hashlib.sha256(target.read_bytes()).hexdigest())
if __name__=='__main__':freeze()
