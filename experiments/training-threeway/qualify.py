from measure import *

def comparisons(s):
 copy(s,[R/'experiments/training-threeway/compare.py'],'/tmp/training/')
 checks=[]
 for case in CASES:
  key=slug(case)
  paths={mode:B/'tensors'/mode/(key+'-cuda.pt') for mode in ['passthrough','flyt','vmweave']}
  meta=[json.loads(next((O/'qualification').glob('*/'+mode+'/'+key+'/result.json')).read_text()) for mode in paths]
  assert len({x['fixture_sha256'] for x in meta})==1
  assert len({x['torch'] for x in meta})==1
  targets=['flyt','vmweave']
  if case[0]=='small':paths['cpu']=B/'tensors/passthrough'/(key+'-cpu.pt');targets+=['cpu']
  for mode,p in paths.items():
   target='/tmp/training/'+mode+'-reference.pt'
   S.run(s['scp']+[str(p),'ubuntu@'+s['ip']+':'+target],check=True,capture_output=True)
  for mode in targets:
   target='/tmp/training/compare-'+key+'-'+mode+'.json'
   cmd=['env','LD_LIBRARY_PATH=/opt/flyt-cuda-libs:/opt/flyt-evidence/driver','/opt/torch-venv/bin/python','/tmp/training/compare.py','/tmp/training/passthrough-reference.pt','/tmp/training/'+mode+'-reference.pt','--out',target]
   result=S.run(s['ssh']+[shlex.join(cmd)],capture_output=True,text=True,timeout=120)
   d=O/'correctness'/key;d.mkdir(parents=True,exist_ok=True)
   (d/(mode+'.log')).write_text(result.stdout+result.stderr)
   S.run(s['scp']+['ubuntu@'+s['ip']+':'+target,str(d/(mode+'.json'))],check=True,capture_output=True)
   check=json.loads((d/(mode+'.json')).read_text());checks.append({'case':key,'comparison':mode,'passed':check['passed']})
   save(O/'correctness/summary.json',{'checks':checks,'complete':False})
   assert result.returncode==0 and check['passed'],(key,mode)
 save(O/'correctness/summary.json',{'checks':checks,'complete':True,'all_passed':all(x['passed'] for x in checks)})

if __name__=='__main__':
 for mode in ['vmweave','flyt','passthrough']:
  for group,offset in enumerate(range(0,len(CASES),5),1):
   s=None
   try:
    s=open_mode(mode,'qualification-g'+str(group))
    for case in CASES[offset:offset+5]:measure(s,case,'qualification','initial',correctness=True)
    if mode=='passthrough' and offset+5>=len(CASES):
     for case in CASES:
      if case[0]=='small':measure(s,case,'qualification','initial',correctness=True,device='cpu')
     comparisons(s)
   finally:
    if s:close_mode(s)
    else:recover_start(mode)
 print('ALL_CORRECTNESS_PASSED',flush=True)
