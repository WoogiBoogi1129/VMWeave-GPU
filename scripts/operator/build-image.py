#!/usr/bin/env python3
"""Build deterministic OCI operator/helper images without Docker or registry writes."""
import argparse,gzip,hashlib,io,json,pathlib,tarfile
p=argparse.ArgumentParser();p.add_argument('--kind',choices=['operator','helper','worker','hook'],required=True);p.add_argument('--base',type=pathlib.Path);p.add_argument('--binary',type=pathlib.Path,default=pathlib.Path('.local/vmweave-operator/manager'));p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--name',required=True);a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2]
def digest(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def pack(v):return json.dumps(v,separators=(',',':'),sort_keys=True).encode()
def info(path,data):
 t=tarfile.TarInfo(path);t.size=len(data);t.mode=0o644;return t
base=tarfile.open(a.base) if a.base else None
if a.kind!='operator' and not base:p.error('helper/worker/hook requires --base OCI archive')
if base:
 idx=json.load(base.extractfile('index.json'));d=idx['manifests'][0]['digest'];manifest=json.load(base.extractfile('blobs/sha256/'+d.split(':')[1]));cfg=json.load(base.extractfile('blobs/sha256/'+manifest['config']['digest'].split(':')[1]))
else:manifest={'schemaVersion':2,'mediaType':'application/vnd.oci.image.manifest.v1+json','layers':[]};cfg={'architecture':'amd64','os':'linux','config':{},'rootfs':{'type':'layers','diff_ids':[]}}
buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode='w') as t:
 files=[]
 if a.kind=='operator':files=[('manager',a.binary,0o755),('etc/ssl/certs/ca-certificates.crt',pathlib.Path('/etc/ssl/certs/ca-certificates.crt'),0o644)]
 else:
  files=[('opt/flyt/control/'+f.name,f,0o644) for f in (root/'runtime/shm/control').glob('*.py')]
  if a.kind=='hook':files.append(('usr/bin/onDefineDomain',root/'runtime/shm/control/domain_hook.py',0o755))
 for name,f,mode in files:
  data=f.read_bytes();x=info(name,data);x.mode=mode;t.addfile(x,io.BytesIO(data))
layer=buf.getvalue();gz=gzip.compress(layer,mtime=0);ld=digest(gz);cfg['rootfs']['diff_ids'].append(digest(layer));manifest['layers'].append({'mediaType':'application/vnd.oci.image.layer.v1.tar+gzip','size':len(gz),'digest':ld})
cfg['config'].setdefault('Labels',{}).update({'org.opencontainers.image.title':'VMWeave '+a.kind,'vmweave.io/api-group':'vmweave.io','vmweave.io/helper-contract':'1'})
if a.kind=='operator':cfg['config'].update(Entrypoint=['/manager'],Cmd=[],User='65532:65532')
cb=pack(cfg);cd=digest(cb);manifest['config']={'mediaType':'application/vnd.oci.image.config.v1+json','size':len(cb),'digest':cd};mb=pack(manifest);md=digest(mb)
idx={'schemaVersion':2,'manifests':[{'mediaType':'application/vnd.oci.image.manifest.v1+json','size':len(mb),'digest':md,'annotations':{'org.opencontainers.image.ref.name':a.name}}]}
a.output.parent.mkdir(parents=True,exist_ok=True)
with tarfile.open(a.output,'w') as out:
 if base:
  for x in base:
   if x.name.startswith('blobs/') and x.isfile():out.addfile(x,base.extractfile(x))
 for name,data in [('blobs/sha256/'+ld[7:],gz),('blobs/sha256/'+cd[7:],cb),('blobs/sha256/'+md[7:],mb),('index.json',pack(idx)),('oci-layout',pack({'imageLayoutVersion':'1.0.0'}))]:out.addfile(info(name,data),io.BytesIO(data))
print(a.name.split(':')[0]+'@'+md)
