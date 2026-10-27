"""Correctness only: production code with a test-only file mapping in the Broker.

No PCI attachment, VM, Kubernetes or production library changes. GPU UUID must be
passed explicitly. Refuses occupied GPU / existing worker markers. Every matrix
condition owns a fresh channel, Broker and CUDA session. CUDA_VISIBLE_DEVICES is
visibility restriction, not a hardware reservation; the lock coordinates this test.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess as S
import sys
import tempfile
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source/runtime/shm/control'))
from provision import provision

def wait_for(fn, processes, seconds=15):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if any(p.poll() is not None for p in processes):raise RuntimeError('test service exited')
        if fn():return
        time.sleep(.02)
    raise TimeoutError('test service startup/cleanup')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--gpu',required=True)
    parser.add_argument('--only',nargs='*');parser.add_argument('--output',default='host-gpu')
    parser.add_argument('--probe',choices=['gpu','lifecycle'],default='gpu')
    args=parser.parse_args();dest=ROOT/'validation'/args.output;dest.mkdir()
    lock=open('/tmp/vmweave-validation-'+args.gpu+'.lock','w')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def idle_gpu():
        apps=S.check_output(['nvidia-smi','-i',args.gpu,'--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
        if apps:raise RuntimeError('GPU has existing compute processes: '+apps)
    idle_gpu()
    marker=Path('/tmp/vmweave-slot-0-mapped');guest=Path('/tmp/vmweave-slot-0-guest')
    assert not marker.exists() and not guest.exists(),'existing local slot 0'
    matrix=json.loads((ROOT/'preparation/matrix.json').read_text())
    common={k:v for k,v in os.environ.items() if not k.startswith(('VMWEAVE_','FLYT_')) and k!='LD_PRELOAD'}
    common.update(CUDA_VISIBLE_DEVICES=args.gpu,LD_LIBRARY_PATH=str(ROOT/'validation/cuda-libs'))
    report=[]
    for condition in matrix['conditions']:
        name=condition['name']
        if args.only and name not in args.only:continue
        idle_gpu();row={'name':name,'features':condition['features'],'status':'RUNNING'};report.append(row)
        worker=broker=None;logs=[]
        try:
            with tempfile.TemporaryDirectory(prefix='vmw-val-') as tmp:
                tmp=Path(tmp);aid=uuid.uuid4().hex
                provision(tmp,aid,uuid.uuid4().hex,[uuid.uuid4().hex],os.getuid(),os.getgid())
                channel=tmp/aid
                (dest/(name+'-layout.bin')).write_bytes((channel/'layout.bin').read_bytes())
                envs={role:dict(common) for role in ('application','broker','worker')}
                for role,values in matrix['base'].items():envs[role].update(values)
                for feature in condition['features']:
                    for role,values in matrix['flags'][feature].items():
                        envs['worker' if role=='cuda_child' else role].update(values)
                sock=tmp/'broker.sock'
                envs['application']['VMWEAVE_BROKER_SOCKET']=str(sock)
                envs['worker'].update(VMWEAVE_RESOURCE_BACKEND='hami',VMWEAVE_GPU_UUID=args.gpu,
                    VMWEAVE_MEMORY_BYTES=str(2*1024**3),CUDA_DEVICE_MEMORY_LIMIT='2G',
                    CUDA_DEVICE_SM_LIMIT='100',GPU_CORE_UTILIZATION_POLICY='disable',
                    CUDA_DEVICE_MEMORY_SHARED_CACHE=str(tmp/'hami.cache'),
                    LD_PRELOAD='/usr/local/vgpu/libvgpu.so.v2.10.0')
                envs['broker'].update(VMWEAVE_LAYOUT=str(channel/'layout.bin'),VMWEAVE_IVSHMEM_BDF='0000:00:00.0',VMWEAVE_SLOT='0',VMWEAVE_TEST_CHANNEL=str(channel/'channel'),LD_PRELOAD=str(ROOT/'build-tests/host_mapping.so'))
                row['environments']={role:{k:v for k,v in env.items() if k.startswith(('VMWEAVE_','CUDA_'))} for role,env in envs.items()}
                wlog=open(dest/(name+'-worker.log'),'w');logs.append(wlog)
                worker=S.Popen([str(ROOT/'build/vmweave-shm-session-worker'),str(channel),'0'],env=envs['worker'],stdout=wlog,stderr=S.STDOUT,start_new_session=True)
                wait_for(marker.exists,[worker])
                blog=open(dest/(name+'-broker.log'),'w');logs.append(blog)
                broker=S.Popen([sys.executable,str(ROOT/'source/runtime/shm/control/guest_broker.py'),'--library',str(ROOT/'build/libvmweave_guest.so'),'--socket',str(sock)],env=envs['broker'],stdout=blog,stderr=S.STDOUT,start_new_session=True)
                wait_for(sock.exists,[worker,broker])
                with open(dest/(name+'-probe.log'),'w') as log:
                    envs['application']['VMWEAVE_TEST_OWNER']=envs['broker'].get('VMWEAVE_BROKER_OWNER','0')
                    script='gpu_probe.py' if args.probe=='gpu' else 'broker_lifecycle.py'
                    S.run([sys.executable,str(ROOT/'tests'/script),str(dest/(name+'-probe.json')),str(worker.pid),str(broker.pid)],env=envs['application'],stdout=log,stderr=S.STDOUT,check=True,timeout=180)
                # Explicit CLOSE must reap the CUDA child while the Broker stays alive.
                children=Path(f'/proc/{worker.pid}/task/{worker.pid}/children')
                wait_for(lambda:not children.read_text().strip(),[worker,broker])
                row['session_child_reaped']=True;row['status']='PASS'
        except BaseException as e:
            row['status']='FAIL';row['error']=repr(e);raise
        finally:
            for proc in (broker,worker):
                if proc is not None and proc.poll() is None:
                    proc.terminate()
                    try:proc.wait(8)
                    except S.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            for log in logs:log.close()
            row['worker_exit']=None if worker is None else worker.returncode
            row['broker_exit']=None if broker is None else broker.returncode
            row['markers_removed']=not marker.exists() and not guest.exists()
            (dest/'results.json').write_text(json.dumps(report,indent=2)+'\n')
            print(name,row['status'],flush=True)
        assert row['markers_removed'] and row['worker_exit']==0,row
    idle_gpu()

if __name__=='__main__':main()
