import argparse
from runtime import *
p=argparse.ArgumentParser();p.add_argument('--path',default='N');p.add_argument('--cap',type=int,default=100);p.add_argument('--reps',type=int,default=524288);p.add_argument('--name',required=True);p.add_argument('--seconds',type=int,default=30);a=p.parse_args()
s=Session(a.name,a.path,a.cap)
try:s.prepare();s.execute(seconds=a.seconds,warmup=10,reps=a.reps)
except Exception as e:save(s.out/'failure.json',{'error':str(e),'utc':time.time()});raise
finally:s.close()
