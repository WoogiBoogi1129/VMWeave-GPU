from gpu import *
create_namespace()
for iteration in (1,2):
    assert ready_nodes(),'both nodes must be Ready'
    save(f'cluster/K1-nodes-{iteration}.json',iobj('get','nodes'))
    if iteration==1:time.sleep(30)
systems=iobj('get','pods','-n','kube-system')
assert all(any(c['type']=='Ready' and c['status']=='True' for c in p['status'].get('conditions',[])) for p in systems['items'])
save('cluster/K1-system-pods.json',systems)
# Resolve a versioned utility image once, then submit its immutable manifest digest.
raw=ssh('worker','sudo podman pull docker.io/library/busybox:1.36.1 && sudo podman image inspect docker.io/library/busybox:1.36.1 --format "{{index .RepoDigests 0}}"',stderr=subprocess.STDOUT)
save('raw/busybox-pull.log',raw);image=raw.strip().splitlines()[-1]
assert '@sha256:' in image
template={'metadata':{'labels':{'app':'cpu-web'}},'spec':{'nodeSelector':{'kubernetes.io/hostname':VM},'automountServiceAccountToken':False,'containers':[{'name':'web','image':image,'securityContext':{'capabilities':{'add':['NET_RAW']}},'command':['sh','-ec','mkdir -p /tmp/www; echo nested-k8s-ok > /tmp/www/index.html; exec httpd -f -p 8080 -h /tmp/www'],'resources':{'requests':{'cpu':'10m','memory':'16Mi'},'limits':{'cpu':'100m','memory':'64Mi'}}}]}}
deployment={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'cpu-web','namespace':INNER},'spec':{'replicas':1,'selector':{'matchLabels':{'app':'cpu-web'}},'template':template}}
service={'apiVersion':'v1','kind':'Service','metadata':{'name':'cpu-web','namespace':INNER},'spec':{'selector':{'app':'cpu-web'},'ports':[{'port':80,'targetPort':8080}]}}
client={'apiVersion':'v1','kind':'Pod','metadata':{'name':'cpu-client','namespace':INNER},'spec':{'nodeSelector':{'kubernetes.io/hostname':'vw-k8s-cp-01'},'tolerations':[{'key':'node-role.kubernetes.io/control-plane','operator':'Exists','effect':'NoSchedule'}],'automountServiceAccountToken':False,'containers':[{'name':'client','image':image,'securityContext':{'capabilities':{'add':['NET_RAW']}},'command':['sleep','3600'],'resources':{'requests':{'cpu':'10m','memory':'16Mi'},'limits':{'cpu':'100m','memory':'64Mi'}}}]}}
for x in (deployment,service,client):iapply(x)
save('cluster/K1-manifests.json',{'apiVersion':'v1','kind':'List','items':[deployment,service,client]})
inner('rollout','status','deployment/cpu-web','-n',INNER,'--timeout=180s')
inner('wait','pod/cpu-client','-n',INNER,'--for=condition=Ready','--timeout=180s')
server=iobj('get','pods','-n',INNER,'-l','app=cpu-web')['items'][0]
ip=server['status']['podIP']
for label,cmd in [('pod-ip',['wget','-qO-',f'http://{ip}:8080']),('dns',['nslookup','cpu-web.'+INNER+'.svc.cluster.local']),('service',['wget','-qO-','http://cpu-web']),('mtu',['ping','-c','1','-s','1142',ip])]:
    output=inner('exec','cpu-client','-n',INNER,'--',*cmd);save('cluster/K1-'+label+'.txt',output)
    if label in ('pod-ip','service'):assert output.strip()=='nested-k8s-ok'
client_ip=iobj('get','pod','cpu-client','-n',INNER)['status']['podIP']
save('cluster/K1-reverse-ping.txt',inner('exec',server['metadata']['name'],'-n',INNER,'--','ping','-c','1',client_ip))
inner('logs',server['metadata']['name'],'-n',INNER)
inner('delete','pod',server['metadata']['name'],'-n',INNER,'--wait=true','--timeout=60s')
inner('rollout','status','deployment/cpu-web','-n',INNER,'--timeout=120s')
new=iobj('get','pods','-n',INNER,'-l','app=cpu-web')['items'][0]
assert new['metadata']['uid']!=server['metadata']['uid']
save('cluster/K1-recreated-pod.json',new)
save('cluster/K1-result.json',{'result':'PASS','at':now(),'original_uid':server['metadata']['uid'],'replacement_uid':new['metadata']['uid'],'image':image})
print('K1 PASS',flush=True)
