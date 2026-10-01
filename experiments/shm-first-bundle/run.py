"""Four-way VM ablation. Every session is a fresh VM/channel/Worker."""
import random
from runtime import *
import runtime

variants=json.loads((BASE/'variants.json').read_text())
stage=sys.argv[1] if len(sys.argv)>1 else 'pilot'
ensure_admin()
save(OUT/('environment-'+stage+'.json'),{'source_commit':call(['git','rev-parse','HEAD']).strip(),
 'source_diff':call(['git','diff','--','runtime','scripts/test-shm-training.sh']),
 'gpu':call(['nvidia-smi','-q']), 'monitor':json.loads((BASE/'monitor.json').read_text())})
def run_one(name,variant,seconds,warmup,mask=31,resume=False):
 runtime.IMAGES['worker']=variants[variant]['worker']
 if resume:s=Session.resume_premeasurement(name)
 else:s=Session(name);s.prepare()
 s.variant=variant
 save(s.out/'variant.json',variants[variant])
 save(s.out/'mapping.json',{'guest':call(s.ssh+["cat /proc/cpuinfo | head -25; cat /sys/bus/pci/devices/"+s.bdf+"/resource; ls /sys/bus/pci/devices/"+s.bdf+"/resource*; cat /sys/devices/system/clocksource/clocksource0/current_clocksource"]),
 'cpu_before':cpu_snapshot(s)})
 prefix='/tmp/perf/'+name
 cmd=s.command('probe-S',['batch',seconds,seconds,warmup,prefix,'/tmp/perf/work.ptx',random.Random(name).randrange(5),mask])
 cmd[-1]=cmd[-1].replace('sudo env ','sudo env FLYT_WAIT_MODE='+variants[variant]['wait']+' FLYT_COPY_MODE='+variants[variant]['copy']+' FLYT_SPIN_US='+str(variants[variant].get('spin_us',20))+' FLYT_METRICS=1 ')
 try:
  execute_stream(s,cmd,prefix)
 finally:
  save(s.out/'cpu-after.json',cpu_snapshot(s))
  s.close()
 print('SESSION_COMPLETE',name,flush=True)
def cpu_snapshot(s):
 identity=json.loads((s.out/'identity.json').read_text());result={'utc':time.time(),'pods':{}}
 for role in ['worker','launcher']:
  uid=identity[role+'_uid']
  for p in Path('/sys/fs/cgroup/kubepods.slice').glob('*/*pod*.slice'):
   if uid in p.name or uid.replace('-','_') in p.name:
    result['pods'][role]={'cpu':(p/'cpu.stat').read_text(),'memory':(p/'memory.current').read_text()}
 return result
if stage=='pilot':
 for v in ['base','both']:run_one('sf-pilot-'+v,v,2,1)
elif stage=='pilot-zero':
 run_one('sf-pilot-zero-both','both',5,2)
elif stage=='resume-prepared':
 name=sys.argv[2];run_one(name,name.split('-')[-1],10,3,resume=True)
elif stage=='formal':
 protocol={'repeats':5,'conditions':['query','kernel','copy-4096','copy-1048576','copy-16777216'],
  'duration_s':10,'warmup_min_s':3,'warmup_min_operations':50,'variants':variants,
  'metrics':True,'cap':100,'seed':20261001,'scope':'SHM first-bundle ablation, no TCP-only causal claim',
  'acceptance':'No correctness failures. Target query/kernel mean -50%, 16MiB copies -25%; report p95 and total Worker/launcher CPU; do not enable permanent two-core spinning.'}
 if not (OUT/'protocol.json').exists():save(OUT/'protocol.json',protocol)
 else:assert json.loads((OUT/'protocol.json').read_text())==protocol
 for rep in range(1,6):
  order=list(variants);random.Random(20261001+rep).shuffle(order)
  for v in order:
   name=f'sf-r{rep}-{v}'
   if (OUT/'runs'/name/'cleanup.json').exists():
    assert json.loads((OUT/'runs'/name/'execution.json').read_text())['exit_code']==0
    continue
   if (OUT/'runs'/name).exists():raise RuntimeError('Preserve and review incomplete run '+name)
   run_one(name,v,10,3)
else:raise ValueError(stage)
