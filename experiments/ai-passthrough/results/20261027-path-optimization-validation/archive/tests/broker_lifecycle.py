"""Actual Broker/Worker failure and cleanup checks on dedicated test processes."""
import array
import json
import mmap
import os
from pathlib import Path
import signal
import socket
import struct
import sys
import time

MAGIC=0x32574D56
sockpath=os.environ['VMWEAVE_BROKER_SOCKET'];worker=int(sys.argv[2]);broker=int(sys.argv[3])
def receive(s,n):
    data=b''
    while len(data)<n:
        p=s.recv(n-len(data))
        if not p:raise EOFError()
        data+=p
    return data
def connect():
    s=socket.socket(socket.AF_UNIX);s.settimeout(35);s.connect(sockpath);return s
def call(s,api,cap=0):
    s.sendall(struct.pack('<IIQQ',MAGIC,api,0,cap));magic,rc,n=struct.unpack('<IIQ',receive(s,16))
    assert magic==MAGIC;return rc,receive(s,n)
def children():return Path(f'/proc/{worker}/task/{worker}/children').read_text().split()
def wait_empty():
    end=time.monotonic()+5
    while children() and time.monotonic()<end:time.sleep(.01)
    assert not children()
def count(s):assert call(s,0x1001,4)==(0,struct.pack('<i',1))
def clean(s):assert call(s,2)==(0,b'');s.close();wait_empty();time.sleep(.05)
def bulk(s):
    s.sendall(struct.pack('<IIQQ',MAGIC,0x7ff2,0,0))
    data,control,flags,_=s.recvmsg(16,socket.CMSG_SPACE(array.array('i').itemsize))
    data+=receive(s,16-len(data));assert struct.unpack('<IIQ',data)==(MAGIC,0,0)
    fds=array.array('i');fds.frombytes(control[0][2]);assert len(fds)==1 and not flags
    fd=fds[0];region=mmap.mmap(fd,32*1024*1024);identity=os.fstat(fd).st_ino;os.close(fd)
    return region,identity

rows=[]
def passed(name):rows.append(name);print('PASS',name,flush=True)
s=connect();count(s)
busy=connect();assert struct.unpack('<IIQ',receive(busy,16))==(MAGIC,46,0);busy.close()
time.sleep(2.2);count(s);clean(s);passed('busy rejection and idle heartbeat')
fd_before={pid:len(list(Path(f'/proc/{pid}/fd').iterdir())) for pid in (worker,broker)}
old=None
try:
    for i in range(10):
        s=connect();count(s);region,identity=bulk(s)
        if old is not None:
            old[:16]=b'X'*16;assert identity!=old_id and region[:16]==b'\0'*16
            old.close()
        old,old_id=region,identity
        # Alternate explicit CLOSE and EOF, both must retire the CUDA session.
        if i%2:clean(s)
        else:s.close();wait_empty();time.sleep(.05)
    passed('ten fresh sessions, retained old arena isolation, CLOSE and EOF')
finally:
    if old is not None:old.close()
fd_after={pid:len(list(Path(f'/proc/{pid}/fd').iterdir())) for pid in (worker,broker)}
assert fd_before==fd_after,(fd_before,fd_after);passed('no Broker/Worker FD growth after repeated sessions')
s=connect();count(s);rc,lease=call(s,0x7ff0,24);assert rc==0 and len(lease)==24
pids=children();assert len(pids)==1;os.kill(int(pids[0]),signal.SIGKILL)
assert s.recv(1)==b'';s.close();wait_empty();time.sleep(.05)
s=connect();count(s);clean(s);passed('cached session child death fences client, next session recovers')
if os.environ.get('VMWEAVE_TEST_OWNER')=='1':
    s=connect();count(s);s.sendall(b'\x56')
    begin=time.monotonic();assert s.recv(1)==b'';elapsed=time.monotonic()-begin
    assert 28<elapsed<35,elapsed;s.close();wait_empty();time.sleep(.05)
    s=connect();count(s);clean(s);passed('partial packet deadline with heartbeat and subsequent recovery')
Path(sys.argv[1]).write_text(json.dumps({'status':'PASS','checks':rows,'fd_before':fd_before,'fd_after':fd_after},indent=2)+'\n')
