"""Recreate only the disposable qualification VMI and verify a new generation."""
import json,subprocess

def qualify(h,s,baseenv,out):
    assert s['name']=='path-w-1027-qual-recovery-candidate'
    out.mkdir(parents=True,exist_ok=False)
    before=h.get('sharedmemorychannel',s['name'])
    old_vmi=h.get('vmi',s['name'])
    old_worker=h.get('pod',s['worker'])
    assert before['metadata']['uid']==s['channelUID']
    h.save(out/'channel-before.json',before)
    h.k('patch','vm',s['name'],'-n',s['namespace'],'--type=merge','-p','{"spec":{"runStrategy":"Halted"}}')
    h.wait(lambda:not h.get('vmi',s['name']))
    h.wait(lambda:h.get('sharedmemorychannel',s['name']).get('status',{}).get('phase')=='Stopped')
    h.ensure_admin();label=s['name']+'-restart';h.arm_affinity(label);h.drop_admin()
    h.k('patch','vm',s['name'],'-n',s['namespace'],'--type=merge','-p','{"spec":{"runStrategy":"Always"}}')
    v=h.wait(lambda:x if (x:=h.get('vmi',s['name'])) and x.get('status',{}).get('phase')=='Running' and x['status'].get('interfaces') and x['status']['interfaces'][0].get('ipAddress') else None)
    assert v['metadata']['uid']!=old_vmi['metadata']['uid']
    s['ip']=v['status']['interfaces'][0]['ipAddress'];s['ssh'],s['scp']=h.ssh_for(s['ip'],v['metadata']['uid'])
    subprocess.run(s['scp']+['-r',str(h.PUB),'ubuntu@'+s['ip']+':/tmp/package'],check=True)
    h.remote(s,'sudo sh /tmp/package/install_guest_broker.sh /tmp/package && sudo systemctl start vmweave-guest-broker.service')
    h.wait(lambda:subprocess.run(s['ssh']+['sudo test -S /run/vmweave/gpu.sock'],capture_output=True).returncode==0)
    c=h.get('sharedmemorychannel',s['name'])
    pods=json.loads(h.k('get','pods','-n',s['namespace'],'-o','json'))['items']
    worker=next(p for p in pods if p['metadata']['name'].endswith('-worker') and p['status']['phase']=='Running' and any(o.get('uid')==s['channelUID'] for o in p['metadata'].get('ownerReferences',[])))
    launcher=next(p for p in pods if p['metadata']['name'].startswith('virt-launcher-'+s['name']+'-') and p['status']['phase']=='Running')
    s['worker']=worker['metadata']['name']
    (out/'cpu-affinity.log').write_text(h.finish_affinity(label,launcher,worker))
    assert c['metadata']['uid']==s['channelUID']
    assert c['status']['generation']!=before['status']['generation']
    assert c['status']['allocation']!=before['status']['allocation']
    assert worker['metadata']['uid']!=old_worker['metadata']['uid']
    h.stage(s)
    (out/'kernel.log').write_text(h.remote(s,'sudo timeout -k 5 180 '+baseenv+' /tmp/short/correctness'))
    h.wait(lambda:h.get('sharedmemorychannel',s['name']).get('status',{}).get('phase')=='Ready')
    h.save(out/'channel-after.json',h.get('sharedmemorychannel',s['name']))
    h.save(out/'result.json',{'status':'PASS','VMI_UID_changed':True,'worker_UID_changed':True,'allocation_changed':True,'generation_changed':True,'kernel_correctness_after_reboot':True,'old_generation':before['status']['generation'],'new_generation':c['status']['generation']})
    h.save(h.B/'active-session.json',s)
