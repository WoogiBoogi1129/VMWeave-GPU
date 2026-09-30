#!/usr/bin/env python3
"""Generate a development CA and server cert for the central webhook. Never applies."""
import argparse,pathlib,subprocess,re,os
p=argparse.ArgumentParser();p.add_argument('--namespace',default='vmweave-system');p.add_argument('--release',default='vmweave');p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
for s in [a.namespace,a.release]:
 if not re.fullmatch('[a-z0-9]([-a-z0-9]*[a-z0-9])?',s) or len(s)>63:p.error('invalid namespace/release')
a.output.mkdir(parents=True,exist_ok=False);a.output.chmod(0o700)
def run(*args):subprocess.run(['openssl',*args],cwd=a.output,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
run('req','-x509','-newkey','rsa:2048','-nodes','-keyout','ca.key','-out','ca.crt','-days','365','-subj','/CN=VMWeave development CA')
run('req','-newkey','rsa:2048','-nodes','-keyout','tls.key','-out','tls.csr','-subj','/CN='+a.release+'-webhook.'+a.namespace+'.svc')
(a.output/'extensions.cnf').write_text('subjectAltName=DNS:'+a.release+'-webhook.'+a.namespace+'.svc\nextendedKeyUsage=serverAuth\n')
run('x509','-req','-in','tls.csr','-CA','ca.crt','-CAkey','ca.key','-CAcreateserial','-out','tls.crt','-days','90','-extfile','extensions.cnf')
for f in a.output.glob('*.key'):f.chmod(0o600)
print(a.output)
