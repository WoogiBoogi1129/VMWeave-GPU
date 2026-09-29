"""Publish an explicit allowlist of evidence, excluding VM cloud-init and keys."""
import argparse
import gzip
import hashlib
import json
import shutil
import struct
from pathlib import Path
from analyze_campaign import json_lines, read_json

RUN_FILES={
    'manifest.json','metrics.json','stdout.jsonl','stderr.txt','host-events.jsonl',
    'command.json','clock-map.json','monotonic-clock-map.json','identity.json',
    'runtime-libraries.json','cleanup.json','failure.json',
    'guest-config/binding.json','guest-config/layout.bin','guest-config/guest.env',
}
BASE_FILES={
    'protocol.json','protocol-amendments.json','run-order.json','MEASUREMENTS_COMPLETE.json',
    'full-run-matrix.json','policy-contract.json',
    'reference-long-hashes.json','reference-short-hashes.json','reference-long-b-hashes.json',
    'control-tests.txt','controller-image.txt','preallocation-failure-cleanup.json',
    'monitor-affinity.json','clock-bridge.jsonl','clock-bridge-errors.txt',
}


def copy_file(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)


def compress(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    # A deterministic header keeps repeated exports reviewable.
    with source.open('rb') as src,target.open('wb') as raw:
        with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as dst:
            shutil.copyfileobj(src,dst)


def export(base,out):
    out.mkdir(parents=True,exist_ok=True)
    (out/'protocol').mkdir(exist_ok=True)
    uids=set()
    for directory in sorted((base/'runs').iterdir()):
        if not directory.is_dir():continue
        dest=out/'runs'/directory.name
        for name in RUN_FILES:
            if (directory/name).exists():copy_file(directory/name,dest/name)
        # Preserve placement/NUMA observations; exclude long QEMU command strings
        # containing internal key-file paths. Actual key material is never read.
        pins=[]
        for pin in json_lines(directory/'cpu-pinning.txt'):
            uids.add(pin['pod_uid'])
            for proc in pin.get('processes',[]):proc.pop('command',None)
            pins.append(pin)
        if pins:
            dest.mkdir(parents=True,exist_ok=True)
            (dest/'cpu-pinning.json').write_text(json.dumps(pins,indent=2)+'\n')
        if (directory/'identity.json').exists():
            identity=read_json(directory/'identity.json')
            uids.update(identity[k] for k in ['uid','worker_uid','launcher_uid'] if k in identity)
        layout=directory/'guest-config/layout.bin'
        if layout.exists():
            raw=layout.read_bytes();region,sessions=struct.unpack_from('<QI',raw,32)
            (dest/'layout-summary.json').write_text(json.dumps({'source':'guest-config/layout.bin','region_bytes':region,
                'session_count':sessions,'sha256':hashlib.sha256(raw).hexdigest()},indent=2)+'\n')
    for name in BASE_FILES:
        if (base/name).exists():copy_file(base/name,out/'protocol'/name)
    for name in ['terminal.txt','terminal.timing','calibration-terminal.txt','references-terminal.txt','clockretry-terminal.txt']:
        if (base/name).exists():compress(base/name,out/'terminal'/(name+'.gz'))
    compress(base/'observations.jsonl',out/'samples/observations.jsonl.gz')
    (out/'samples').mkdir(exist_ok=True)
    with (out/'samples/cpu-observations.jsonl.gz').open('wb') as raw:
        with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as dst:
            for snapshot in json_lines(base/'cpu-observations.jsonl'):
                if 'processes' not in snapshot:continue
                snapshot['processes']=[p for p in snapshot['processes'] if any(u in p['cgroup'] or u.replace('-','_') in p['cgroup'] for u in uids)]
                if snapshot['processes']:dst.write((json.dumps(snapshot)+'\n').encode())
    for name in ['prometheus.yml','dashboards/campaign.json','provisioning/datasources/prometheus.yaml']:
        copy_file(base/'monitoring'/name,out/'monitoring'/name)
    for file in (base/'source-loaded').glob('*.py'):
        copy_file(file,out/'protocol/source-loaded'/file.name)
    if (base/'captures').exists():
        for file in sorted((base/'captures').rglob('*')):
            if file.is_file() and file.suffix in {'.png','.webm','.json'}:
                copy_file(file,out/'captures'/file.relative_to(base/'captures'))
    artifacts=[]
    for file in sorted((base/'artifacts').iterdir()):
        if file.suffix not in {'.bin','.so'} and not file.name.startswith('campaign-probe-'):continue
        artifacts.append({'name':file.name,'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
    (out/'protocol/artifact-hashes.json').write_text(json.dumps(artifacts,indent=2)+'\n')
    # Reference outputs contain public deterministic synthetic inputs only.
    for name in ['reference-long.bin','reference-short.bin','reference-long-b.bin']:
        if (base/'artifacts'/name).exists():compress(base/'artifacts'/name,out/'references'/(name+'.gz'))
    return uids


def checksum(out):
    lines=[]
    for file in sorted(out.rglob('*')):
        if file.is_file() and file.name!='SHA256SUMS':
            lines.append(hashlib.sha256(file.read_bytes()).hexdigest()+'  '+str(file.relative_to(out)))
    (out/'SHA256SUMS').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();export(a.base,a.output);checksum(a.output)
    print(a.output)
