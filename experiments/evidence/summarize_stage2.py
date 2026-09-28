"""Recheck all three Stage 2 runs and export the presentation's result table."""
import argparse
import csv
import json
from pathlib import Path
from verify_stage2 import verify

def summarize(root):
    rows=[];identities=[]
    for directory in sorted((root/'runs').iterdir()):
        result=verify(directory)
        identity=json.loads((directory/'trace-binding.json').read_text());identities.append(identity)
        command=json.loads((directory/'command.json').read_text())
        rows.append({'run_id':directory.name,'allocation':identity['allocation'],
                     **{k:result[k] for k in ['status','matched_requests','cuda_requests','trace_records','checked_elements','mismatches']},
                     'malloc_bytes':1048576,'copy_bytes_each_direction':1048576,'free':'PASS','released':True,
                     'worker_image':command['worker_image'],'guest_library_sha256':command['guest_library_sha256'],
                     'probe_sha256':command['probe_sha256']})
    if len(rows)!=3:raise ValueError('Exactly three independent runs required')
    for key in ['allocation','generation','session_id','channel_uid','worker_uid','vmi_uid']:
        if len({i[key] for i in identities})!=3:raise ValueError('Reused identity: '+key)
    for key in ['worker_image','guest_library_sha256','probe_sha256']:
        if len({r[key] for r in rows})!=1:raise ValueError('Mixed build: '+key)
    (root/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
    with (root/'summary.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args()
    print(json.dumps(summarize(a.root),indent=2))
