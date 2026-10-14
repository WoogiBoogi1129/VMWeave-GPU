"""Four pilot conditions, isolated pairs; stop on unexpected result or cleanup failure."""
from common import *
import sys
name='native-peer-pilot-'+time.strftime('%Y%m%d%H%M%S',time.gmtime());out=OUT/name;out.mkdir();results=[]
print('OUTPUT',out,flush=True)
save(out/'status.json',{'state':'RUNNING','utc':time.time(),'completed':0,'total':4})
for direction,operation in [('ab','read'),('ab','write'),('ba','read'),('ba','write')]:
 log=out/(direction+'-'+operation+'.log')
 with log.open('w') as f:
  r=subprocess.run([sys.executable,'-u',str(ROOT/'experiments/thesis-isolation/runner/native_peer_pilot.py'),direction,operation],stdout=f,stderr=subprocess.STDOUT)
 text=log.read_text();paths=[line[7:] for line in text.splitlines() if line.startswith('OUTPUT ')]
 results.append({'direction':direction,'operation':operation,'returncode':r.returncode,'path':paths[0] if paths else None})
 save(out/'conditions.json',results)
 if r.returncode:
  save(out/'status.json',{'state':'STOPPED_UNEXPECTED','utc':time.time(),'completed':len(results)-1,'conditions':results});print('STOPPED',direction,operation,flush=True);sys.exit(1)
 print('COMPLETE',direction,operation,flush=True)
 save(out/'status.json',{'state':'RUNNING','utc':time.time(),'completed':len(results),'total':4})
save(out/'status.json',{'state':'COMPLETE','utc':time.time(),'completed':4,'total':4})
print('CAMPAIGN_COMPLETE',flush=True)
