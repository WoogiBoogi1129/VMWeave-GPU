"""Strict offline correlation of actual endpoint records; never compares clocks across hosts."""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import struct

NAMES = {1:'HELLO',2:'GOODBYE',3:'HEARTBEAT',0x1001:'cudaGetDeviceCount',
         0x1010:'cudaMalloc',0x1011:'cudaFree',0x1012:'cudaMemcpy',0x1020:'cudaDeviceSynchronize',
         0x2030:'cuModuleLoadData',0x2031:'cuModuleUnload',0x2032:'cuModuleGetFunction',0x2033:'cuLaunchKernel'}
EVENTS = [('guest','submit'),('worker','take'),('worker','respond'),('guest','receive')]

def parse(text):
    records=[]
    for line in text.splitlines():
        if line.startswith('FLYT_TRACE '):
            records.append(json.loads(line[len('FLYT_TRACE '):]))
    return records

def correlate(guest, worker, binding):
    groups=collections.defaultdict(list)
    for row in guest+worker:
        key=tuple(row[k] for k in ['allocation','generation','session_id','request_id'])
        groups[key].append(row)
    if not groups:raise ValueError('No trace records')
    expected=tuple(binding[k] for k in ['allocation','generation','session_id'])
    joined=[]
    for key, rows in sorted(groups.items()):
        if key[:3]!=expected:raise ValueError('Wrong allocation/generation/session')
        counts=collections.Counter((r['role'],r['event']) for r in rows)
        if counts!=collections.Counter(EVENTS):raise ValueError('Missing or duplicate endpoint event')
        e={ (r['role'],r['event']):r for r in rows }
        s,t,p,r=[e[x] for x in EVENTS]
        if len({(x['api_id'],x['input_bytes']) for x in rows})!=1:raise ValueError('Request differs across endpoints')
        for f in ['transport_status','result_domain','api_result','output_bytes']:
            if p[f]!=r[f]:raise ValueError('Response differs across endpoints')
        if p['transport_status']!=0 or p['api_result']!=0:raise ValueError('Remote transport or CUDA failure')
        domain=0 if s['api_id']<=3 else 1 if s['api_id']<0x2000 else 2
        if p['result_domain']!=domain:raise ValueError('Wrong result domain')
        if not(s['monotonic_ns']<=r['monotonic_ns'] and t['monotonic_ns']<=p['monotonic_ns']):
            raise ValueError('Endpoint-local event order invalid')
        for f in ['requested_bytes','copy_bytes','copy_direction','src_handle','dst_handle']:
            if len({x.get(f) for x in rows})!=1:raise ValueError('Semantic request mismatch: '+f)
        if p.get('allocation_handle')!=r.get('allocation_handle'):raise ValueError('Handle response mismatch')
        joined.append({'request_id':key[3],'api_id':s['api_id'],'api':NAMES.get(s['api_id'],hex(s['api_id'])),
                       'events':4,'input_bytes':s['input_bytes'],'output_bytes':r['output_bytes'],
                       'transport_status':r['transport_status'],'result_domain':r['result_domain'],'api_result':r['api_result'],
                       **{f:r[f] for f in ['requested_bytes','allocation_handle','copy_direction','copy_bytes','src_handle','dst_handle'] if f in r}})
    ids=[r['request_id'] for r in joined]
    if ids!=list(range(1,len(ids)+1)):raise ValueError('Request IDs are not contiguous from 1')
    for endpoint in [guest,worker]:
        if any(a['monotonic_ns']>b['monotonic_ns'] for a,b in zip(endpoint,endpoint[1:])):
            raise ValueError('Endpoint log order invalid')
    return joined

def verify(directory):
    directory=Path(directory)
    read=lambda n:json.loads((directory/n).read_text())
    binding=read('trace-binding.json')
    guest=parse((directory/'guest-stderr.txt').read_text());worker=parse((directory/'worker-stderr.txt').read_text())
    joined=correlate(guest,worker,binding)
    apis=[r['api_id'] for r in joined if r['api_id']!=3]
    if apis!=[1,0x1001,0x1010,0x1012,0x2030,0x2032,0x2033,0x1020,0x1012,0x2031,0x1011,2]:
        raise ValueError('Unexpected CUDA/control lifecycle')
    malloc=next(r for r in joined if r['api_id']==0x1010);free=next(r for r in joined if r['api_id']==0x1011)
    copies=[r for r in joined if r['api_id']==0x1012]
    if malloc['requested_bytes']!=1048576 or not malloc['allocation_handle'] or malloc['allocation_handle']!=free['allocation_handle']:
        raise ValueError('1 MiB allocation/free handle mismatch')
    if [r['copy_direction'] for r in copies]!=[1,2] or any(r['copy_bytes']!=1048576 for r in copies):
        raise ValueError('Copy direction or length mismatch')
    if copies[0]['dst_handle']!=malloc['allocation_handle'] or copies[1]['src_handle']!=malloc['allocation_handle']:
        raise ValueError('Copy used another allocation')
    if copies[0]['input_bytes']!=1048576+48 or copies[1]['output_bytes']!=1048576:raise ValueError('Copy transport lengths mismatch')
    rows=[json.loads(l) for l in (directory/'stdout.jsonl').read_text().splitlines()]
    conditions=next(r for r in rows if r['event']=='CONDITIONS');result=next(r for r in rows if r['event']=='RESULT')
    if result['status']!='PASS' or result['mismatches'] or result['checked_elements']!=262144 or result['checked_bytes']!=1048576:
        raise ValueError('Incorrect output')
    if read('process.json')['exit_code']!=0:raise ValueError('Guest process failed')
    seed=conditions['seed'];source=struct.pack('<262144I',*(seed+i for i in range(262144)))
    reference=struct.pack('<262144I',*(seed+i+19 for i in range(262144)))
    output=gzip.decompress((directory/'output.bin.gz').read_bytes())
    hashes=read('array-hashes.json')
    for name,data in [('input',source),('reference',reference),('output',output)]:
        if hashlib.sha256(data).hexdigest()!=hashes[name]:raise ValueError('Array hash mismatch: '+name)
    if output!=reference:raise ValueError('Offline full-array comparison failed')
    if not read('cleanup.json')['released']:raise ValueError('Not released')
    return {'status':'PASS','matched_requests':len(joined),'cuda_requests':sum(r['api_id']>3 for r in joined),
            'trace_records':len(guest)+len(worker),'checked_elements':262144,'mismatches':0,
            'exact_output_reference_hash_match':True,'cleanup_released':True,'joined':joined}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
    print(json.dumps(verify(a.directory),indent=2))
