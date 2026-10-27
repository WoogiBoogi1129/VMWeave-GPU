import subprocess as S,json,time,sys,fcntl
from pathlib import Path
B=Path(__file__).resolve().parent
O=Path('experiments/ai-passthrough/results/20261027-path-optimization-vm')
protocol=json.loads((O/'protocol.json').read_text());gpu=protocol['gpu']
lock=open('/tmp/vmweave-validation-'+gpu+'.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
def status(stage,**kw):
    (O/'status.json').write_text(json.dumps({'stage':stage,'updated_unix':time.time(),**kw},indent=2)+'\n')
def idle():
    end=time.monotonic()+30
    while time.monotonic()<end:
        if not S.check_output(['nvidia-smi','-i',gpu,'--query-compute-apps=pid','--format=csv,noheader'],text=True).strip():return
        time.sleep(1)
    raise RuntimeError('GPU still has a compute client')
def run(mode,label):
    idle();status('RUNNING',mode=mode,label=label)
    print('START',label,mode,flush=True)
    with open(B/(label+'-'+mode+'.log'),'w') as out:
        S.run([sys.executable,'-u',str(B/'run_session.py'),mode,label],stdout=out,stderr=S.STDOUT,check=True,timeout=1000)
    idle();print('DONE',label,mode,flush=True)
try:
    for i,order in enumerate(protocol['orders'],1):
        for mode in order:run(mode,'r'+str(i))
    status('MEASUREMENTS_COMPLETE_ANALYSIS_PENDING')
except BaseException as e:
    status('STOPPED',error=repr(e));raise
