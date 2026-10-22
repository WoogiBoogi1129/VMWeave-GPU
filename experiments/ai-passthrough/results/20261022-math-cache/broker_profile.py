"""Diagnostic wrapper; SIGUSR1/2 delimit only the measured training window."""
import collections,json,os,signal,time
from pathlib import Path
import guest_broker as broker
original_exchange=broker.Transport.exchange
original_serve=broker.Transport.serve
current=None
active=False

def exchange(self,api,data,capacity):
 enabled=active;start=time.perf_counter_ns() if enabled else 0;cpu=time.thread_time_ns() if enabled else 0
 try:return original_exchange(self,api,data,capacity)
 finally:
  if enabled:
   inner=int.from_bytes(data[16:20],'little') if api==broker.CALL else api
   r=self.profile[hex(inner)];r[0]+=1;r[1]+=time.perf_counter_ns()-start;r[2]+=time.thread_time_ns()-cpu;r[3]+=len(data);r[4]=max(r[4],capacity)

def serve(self,conn):
 global current
 current=self;self.profile=collections.defaultdict(lambda:[0,0,0,0,0])
 return original_serve(self,conn)

def start(signum,frame):
 global active
 assert current is not None
 current.profile.clear();active=True
 Path('/tmp/perf/profile-started').write_text(str(time.time()))

def finish(signum,frame):
 global active
 active=False
 Path('/tmp/perf/broker-api-timing.json').write_text(json.dumps({'scope':'measurement only; signals acknowledged outside timer','columns':['calls','exchange_ns','server_thread_cpu_ns','input_bytes','max_output_capacity'],'apis':dict(current.profile)},indent=2))

broker.Transport.exchange=exchange;broker.Transport.serve=serve
Path('/tmp/perf/broker-profile.pid').write_text(str(os.getpid()))
signal.signal(signal.SIGUSR1,start);signal.signal(signal.SIGUSR2,finish)
broker.main()
