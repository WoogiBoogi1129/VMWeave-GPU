"""Repair missing OCI history entries without changing filesystem layer bytes."""
import argparse, hashlib, io, json, tarfile
ap=argparse.ArgumentParser();ap.add_argument('source');ap.add_argument('destination')
ap.add_argument('--tag',default='localhost/vmweave-worker:sm-core-base-20261015');a=ap.parse_args()
with tarfile.open(a.source) as src:
    index=json.load(src.extractfile('index.json'));descriptor=index['manifests'][0]
    manifest=json.load(src.extractfile('blobs/sha256/'+descriptor['digest'].split(':')[1]))
    config_descriptor=manifest['config']
    config=json.load(src.extractfile('blobs/sha256/'+config_descriptor['digest'].split(':')[1]))
    layers=len(config['rootfs']['diff_ids']);history=config.get('history',[])
    actual=sum(not row.get('empty_layer',False) for row in history)
    if actual>layers:raise ValueError('History has more layers than rootfs; cannot infer a repair')
    config['history']=history+[{'created_by':'OCI history repair: existing filesystem layer'} for _ in range(layers-actual)]
    additions={}
    def blob(obj):
        data=json.dumps(obj,separators=(',',':')).encode();digest=hashlib.sha256(data).hexdigest()
        additions['blobs/sha256/'+digest]=data
        return 'sha256:'+digest,len(data)
    config_descriptor['digest'],config_descriptor['size']=blob(config)
    descriptor['digest'],descriptor['size']=blob(manifest)
    descriptor['annotations']={'org.opencontainers.image.ref.name':a.tag}
    additions['index.json']=json.dumps(index).encode()
    with tarfile.open(a.destination,'w') as dst:
        for member in src:
            if member.name=='index.json':continue
            dst.addfile(member,src.extractfile(member) if member.isfile() else None)
        for name,data in additions.items():
            member=tarfile.TarInfo(name);member.size=len(data);dst.addfile(member,io.BytesIO(data))
    print(json.dumps({'original_history_layers':actual,'filesystem_layers':layers,'normalized_manifest':descriptor['digest']}))
