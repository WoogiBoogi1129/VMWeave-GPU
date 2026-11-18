"""Seal the reviewed refresh, including the archived original manifests."""
from pathlib import Path
import hashlib
import json
import re

P = Path(__file__).resolve().parents[1]
Q = P / 'refresh-20261118'
assert json.loads((P / 'analysis/independent-verification.json').read_text())['passed']
assert json.loads((Q / 'evidence/cleanup-complete.json').read_text())['namespace_removed']
assert json.loads((Q / 'evidence/final-resource-audit.json').read_text())['passed']
assert json.loads((Q / 'evidence/campaign-complete.json').read_text())
assert (P / 'REPORT.md').exists()
files = [p for p in sorted(P.rglob('*')) if p.is_file()
         and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.pyo')
         and p not in (P / 'SHA256SUMS', P / 'bundle.json')]
for p in files:
    assert 'private' not in p.relative_to(P).parts, p
    assert p.stat().st_size < 100 * 1024 * 1024, ('GitHub file limit', str(p))
    if p.suffix in ('.gz', '.png', '.bin'):
        continue
    text = p.read_text(errors='replace')
    assert not re.search(r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----', text), p
    assert not re.search(r'\b(?:ghp_|github_pat_|hf_)[A-Za-z0-9_]{24,}', text), p
    assert not re.search(r'\bAKIA[0-9A-Z]{16}\b', text), p
bundle = {
    'files_without_root_manifest': len(files),
    'bytes_without_root_manifest': sum(p.stat().st_size for p in files),
    'selection': 'analysis/selection.json',
    'raw_format': 'gzip uint64 little-endian nanoseconds',
    'integrity': 'SHA256SUMS covers every public file except itself and Python bytecode, including archived manifests',
    'secret_checks': ['private-key headers', 'GitHub/Hugging Face token patterns', 'AWS access key pattern'],
    'private_data': 'Operational snapshots stay outside this directory. Temporary experiment SSH keys and cloud image were removed.',
}
(P / 'bundle.json').write_text(json.dumps(bundle, indent=2) + '\n')
files.append(P / 'bundle.json')
(P / 'SHA256SUMS').write_text(''.join(
    hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + str(p.relative_to(P)) + '\n'
    for p in sorted(files)))
print(json.dumps(bundle, indent=2))
