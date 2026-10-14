"""Repair OCI history length only; preserve every filesystem layer byte-for-byte."""
import hashlib,io,json,sys,tarfile
src,dst=sys.argv[1:]
with tarfile.open(src) as t:
 index=json.load(t.extractfile('index.json'));md=index['manifests'][0];mp='blobs/sha256/'+md['digest'].split(':')[1];manifest=json.load(t.extractfile(mp));cd=manifest['config'];cp='blobs/sha256/'+cd['digest'].split(':')[1];config=json.load(t.extractfile(cp))
 n=len(config['rootfs']['diff_ids']);history=config.get('history',[]);actual=sum(not x.get('empty_layer',False) for x in history)
 assert actual<=n,(actual,n)
 config['history']=history+[{'created_by':'OCI history repair: existing filesystem layer'} for _ in range(n-actual)]
 additions={}
 def blob(obj):
  data=json.dumps(obj,separators=(',',':')).encode();digest=hashlib.sha256(data).hexdigest();additions['blobs/sha256/'+digest]=data;return 'sha256:'+digest,len(data)
 cd['digest'],cd['size']=blob(config);md['digest'],md['size']=blob(manifest);md['annotations']={'org.opencontainers.image.ref.name':'localhost/vmweave-worker:boundary-base-20261014'}
 additions['index.json']=json.dumps(index).encode()
 with tarfile.open(dst,'w') as out:
  for member in t:
   if member.name=='index.json':continue
   out.addfile(member,t.extractfile(member) if member.isfile() else None)
  for path,data in additions.items():
   member=tarfile.TarInfo(path);member.size=len(data);out.addfile(member,io.BytesIO(data))
 print(json.dumps({'original_history_layers':actual,'filesystem_layers':n,'normalized_manifest':md['digest']}))
