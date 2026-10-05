"""After monitors stop, losslessly compress large text logs and record both hashes."""
from common import *
import hashlib,lzma
assert (BASE/'stop-monitor').exists()
assert (OUT/'followup-complete.json').exists()
records=[]
for p in sorted(OUT.rglob('*')):
    if not p.is_file() or p.suffix not in ('.txt','.jsonl','.csv') or p.stat().st_size<65536:continue
    raw=p.read_bytes();z=Path(str(p)+'.xz')
    assert not z.exists(),z
    z.write_bytes(lzma.compress(raw,preset=6))
    assert lzma.decompress(z.read_bytes())==raw
    records.append({'original':str(p.relative_to(OUT)),'archive':str(z.relative_to(OUT)),
        'bytes':len(raw),'archive_bytes':z.stat().st_size,'sha256':hashlib.sha256(raw).hexdigest(),
        'archive_sha256':hashlib.sha256(z.read_bytes()).hexdigest()})
    p.unlink()
save(OUT/'archive-manifest.json',records)
