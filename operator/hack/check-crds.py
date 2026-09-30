#!/usr/bin/env python3
"""Check preserved schema contracts and chart copies; never rewrite legacy evidence."""
import json,pathlib
root=pathlib.Path(__file__).resolve().parents[2]
for f in (root/'operator/config/crd/bases').glob('*.json'):
 d=json.loads(f.read_text());assert d['spec']['group']=='vmweave.io';assert d['spec']['scope']=='Namespaced';assert not d['spec']['names']['kind'].startswith('Flyt')
 assert d==json.loads((root/'charts/vmweave-operator/crds'/f.name).read_text()),f
print('PASS: VMWeave API group, scope and chart schema copies')
