import harness as h
import subprocess,json,time,sys
h.stage=lambda s:None
s=None
kind=sys.argv[1]
try:
 s=h.prepare_vmw('v054-fault2-'+kind)
 subprocess.run(s['scp']+[str(h.B/'fault_client.py'),'ubuntu@'+s['ip']+':/tmp/'],check=True)
 log=(h.B/('fault-'+kind+'-client.log')).open('w')
 p=subprocess.Popen(s['ssh']+['sudo env VMWEAVE_STATE_CACHE=0 VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock VMWEAVE_BULK_COPY=1 python3 /tmp/fault_client.py'],stdout=log,stderr=log)
 h.wait(lambda:subprocess.run(s['ssh']+['test -f /tmp/fault-ready'],capture_output=True).returncode==0,90)
 # Pause the Worker child so COPY cannot complete, then inject failure in flight.
 ps=h.k('exec','-n',h.NS,s['worker'],'--','ps','-eo','pid,args')
 ids=[line.split()[0] for line in ps.splitlines() if 'vmweave-shm-session-worker' in line and '--session ' in line]
 assert len(ids)==1,ps
 h.k('exec','-n',h.NS,s['worker'],'--','kill','-STOP',ids[0])
 h.remote(s,'touch /tmp/fault-go')
 h.wait(lambda:subprocess.run(s['ssh']+['test -f /tmp/fault-submitting'],capture_output=True).returncode==0,10)
 time.sleep(.5)
 if kind=='worker':h.k('exec','-n',h.NS,s['worker'],'--','kill','-KILL',ids[0])
 else:
  h.remote(s,'sudo systemctl kill --signal=SIGKILL vmweave-guest-broker.service')
  h.k('exec','-n',h.NS,s['worker'],'--','kill','-CONT',ids[0])
 assert p.wait(timeout=50)==0
 result=json.loads(h.remote(s,'cat /tmp/fault-result.json'));assert result['seconds']<40
 h.save(h.B/('fault-'+kind+'.json'),result)
 print('FAULT PASS',kind,result,flush=True)
finally:
 if s:h.cleanup_vmw(s)
 h.drop_admin()
