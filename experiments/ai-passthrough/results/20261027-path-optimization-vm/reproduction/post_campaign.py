"""Run supplementary qualifications only after the fixed formal campaign ends."""
import json,time,subprocess as S,sys,fcntl
import rodinia_campaign as h
B=h.B;O=h.O
while True:
    state=json.loads((O/'status.json').read_text())
    if state['stage']=='MEASUREMENTS_COMPLETE_ANALYSIS_PENDING':break
    if state['stage']=='STOPPED':raise RuntimeError(state)
    time.sleep(5)
lock=open('/tmp/vmweave-validation-'+h.GPU+'.lock','w');fcntl.flock(lock,fcntl.LOCK_EX)
def status(stage,**kw):h.save(O/'post-status.json',{'stage':stage,'updated_unix':time.time(),**kw})
def idle():
    assert not S.check_output(['nvidia-smi','-i',h.GPU,'--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
def run(label):
    idle();status('QUALIFYING',label=label);print('START',label,flush=True)
    with open(B/(label+'-candidate.log'),'w') as f:
        S.run([sys.executable,'-u',str(B/'run_session.py'),'candidate',label],stdout=f,stderr=S.STDOUT,check=True,timeout=1200)
    idle();print('DONE',label,flush=True)
try:
    with open(B/'analysis.log','w') as f:S.run([sys.executable,str(B/'analyze.py')],stdout=f,stderr=S.STDOUT,check=True)
    S.run([str(h.R/'.local/evidence-venv/bin/python'),str(B/'plot.py')],check=True)
    run('qual-recovery')
    idle();h.ensure_admin()
    try:
        images=json.loads((B/'images.json').read_text())
        for spin in [0,10,50]:
            key='spin'+str(spin);tag='localhost/vmweave-worker:path-'+key+'-20261027'
            h.admin(['podman','build','--network=none','--pull=never','-t',tag,'-f',str(B/(key+'.Containerfile')),str(B/'image')])
            info=json.loads(h.admin(['podman','image','inspect',tag]))[0]
            digest=info['Digest'];assert digest.startswith('sha256:')
            images[key]='localhost/vmweave-worker@'+digest
        h.save(B/'images.json',images);h.save(O/'diagnostic-worker-images.json',images)
    finally:h.drop_admin()
    for spin in [0,50,10]:run('qual-spin'+str(spin))
    status('COMPLETE');print('POST QUALIFICATION COMPLETE',flush=True)
except BaseException as e:
    status('STOPPED',error=repr(e));raise
