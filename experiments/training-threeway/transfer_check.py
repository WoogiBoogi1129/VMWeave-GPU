#!/usr/bin/env python3
"""Untimed changing-payload validation; never mixed into performance samples."""
import argparse
import hashlib
import json
from pathlib import Path
import torch


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    assert not args.out.exists()
    torch.set_num_threads(1)
    assert torch.cuda.is_available() and torch.cuda.device_count()==1
    checks=[]
    for model,batch,widths in [('small',32,(32,8)),('large',1024,(2048,1024))]:
        host=[torch.arange(batch*w,dtype=torch.float32).reshape(batch,w) for w in widths]
        device=[torch.empty_like(x,device='cuda') for x in host]
        returned=[torch.empty_like(x) for x in host]
        previous=None
        for iteration in range(4):
            # Distinct exactly representable integer payloads on every visit.
            expected=[x+iteration*8 for x in host]
            for src,dst in zip(expected,device):
                dst.copy_(src,non_blocking=False)
                dst.mul_(2)
            for src,dst in zip(device,returned):
                dst.copy_(src,non_blocking=False)
            torch.cuda.synchronize()
            assert all(torch.equal(actual,source*2) for actual,source in zip(returned,expected))
            digest=hashlib.sha256(b''.join(x.numpy().tobytes() for x in returned)).hexdigest()
            assert digest!=previous
            previous=digest
            checks.append({'model':model,'batch':batch,'iteration':iteration,'h2d_bytes':sum(x.numel()*4 for x in expected),'d2h_bytes':sum(x.numel()*4 for x in returned),'output_sha256':digest,'passed':True})
    result={'passed':True,'checks':checks,'torch':str(torch.__version__),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'scope':'Changing payload H2D, in-place CUDA multiplication, D2H; no performance metric.'}
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
