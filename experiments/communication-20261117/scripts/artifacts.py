from common import *
LC='ghcr.io/lupinemachines/lupine-client:v2.1.0-cuda-12.9.1-ubuntu24.04@sha256:b8b57e2f612f224d5ac158bb05b15df48323ed6a66a809f4749f5368104601b3'
LS='ghcr.io/lupinemachines/lupine-server:v2.1.0-cuda-12.9.1-ubuntu24.04@sha256:dbb0febb22f8fb054fe5ac2150df316df366aba5d0ed8649e43ed35e7890e494'
COMP='docker.io/nvidia/cuda:12.8.1-cudnn-devel-ubuntu22.04@sha256:ad6d59a3bbf3e82c1c849c9ac09cfc2a3e0bbb8655042fd899be6681b3fe2a85'
if __name__=='__main__':
 for name,image in [('compiler',COMP),('lupine-client-compatible',LC),('lupine-server-compatible',LS)]:
  if not get('pod',name):
   create({'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':NS,'labels':{'hami.io/webhook':'ignore'}},'spec':{'nodeName':NODE,'restartPolicy':'Never','automountServiceAccountToken':False,'containers':[{'name':'main','image':image,'command':['sleep','86400'],'resources':{'limits':{'cpu':'2','memory':'8Gi'}},'env':[{'name':'NVIDIA_VISIBLE_DEVICES','value':'void'}],'volumeMounts':[{'name':'workspace','mountPath':'/work'}]}],'volumes':[{'name':'workspace','hostPath':{'path':str(R),'type':'Directory'}}]}})
 print('artifact pods created')
