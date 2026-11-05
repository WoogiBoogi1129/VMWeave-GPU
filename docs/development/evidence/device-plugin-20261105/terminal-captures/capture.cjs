// Capture live SSH -> tmux -> ttyd terminal screens with Playwright.
// Usage: NODE_PATH=/path/to/node_modules node capture.cjs /private/config.json
// config: ssh (interactive argv), sshExec (noninteractive argv), output, scratch, ttyd.
// No terminal output is reconstructed, replayed, or painted into the image.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),cp=require('child_process'),net=require('net');
const config=JSON.parse(fs.readFileSync(process.argv[2]));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const socket='vmweave-dp-capture-'+process.pid,session='guest';
const tm=(...args)=>cp.execFileSync('tmux',['-L',socket,...args],{encoding:'utf8'});
const remote=cmd=>cp.spawnSync(config.sshExec[0],[...config.sshExec.slice(1),cmd],{encoding:'utf8',timeout:15000});
const prompt=/ubuntu@dp-dev-20261105:device-plugin-capture\$\s*$/;
const screen=()=>tm('capture-pane','-p','-t',session);
const previous=config.append ? JSON.parse(fs.readFileSync(path.join(config.output,'capture.json'))) : {captures:[]};
const commands=config.append ? JSON.parse(fs.readFileSync(path.join(config.output,'commands.json'))) : [];
const captures=previous.captures;
async function until(fn,timeout,label){const end=Date.now()+timeout;while(!fn()){if(Date.now()>end)throw Error('Timeout: '+label);await sleep(200);}}
async function command(code){
 const r=remote('rm -f /tmp/vmweave-capture-status');if(r.status!==0)throw Error(r.stderr);
 const start=new Date().toISOString();
 tm('send-keys','-t',session,'-l',code);tm('send-keys','-t',session,'Enter');
 let status;
 await until(()=>{const r=remote('cat /tmp/vmweave-capture-status 2>/dev/null');if(r.status===0){status=Number(r.stdout.trim());return true;}return false;},180000,code);
 await until(()=>prompt.test(screen().trimEnd()),15000,'prompt after '+code);
 commands.push({command:code,startedAt:start,finishedAt:new Date().toISOString(),exitCode:status});
 if(status!==0)throw Error('Exit '+status+': '+code+'\n'+screen());
}
const frames=[
 {name:'01-guest-and-prerequisites',height:1050,commands:[
 'date --iso-8601=seconds; hostname; kubectl config current-context',
 'kubectl get nodes -o wide',
 'systemctl is-active vmweave-guest-broker; getent group vmweave',
 'cat /opt/vmweave/source-revision.txt',
 'sha256sum /opt/vmweave/lib/libvmweave_guest.so'
 ]},
 {name:'02-device-plugin-install',height:1250,commands:[
 'date --iso-8601=seconds',
 'cat device-plugin-values.yaml',
 'kubectl label node dp-dev-20261105 vmweave.io/device-plugin=enabled --overwrite',
 'helm upgrade --install vmweave-device-plugin \\\n  oci://ghcr.io/woogiboogi1129/charts/vmweave-device-plugin --version 0.1.0 \\\n  --namespace vmweave-device-plugin --create-namespace -f device-plugin-values.yaml',
 'kubectl -n vmweave-device-plugin rollout status ds/vmweave-device-plugin --timeout=120s'
 ]},
 {name:'03-plugin-and-gpu-registration',height:1100,commands:[
 'date --iso-8601=seconds',
 'kubectl -n vmweave-device-plugin get daemonset,pods -o wide',
 "kubectl get node dp-dev-20261105 -o 'custom-columns=NAME:.metadata.name,GPU-CAPACITY:.status.capacity.vmweave\\.io/gpu,GPU-ALLOCATABLE:.status.allocatable.vmweave\\.io/gpu'",
 'kubectl -n vmweave-device-plugin logs ds/vmweave-device-plugin --tail=10',
 'helm list -n vmweave-device-plugin'
 ]},
 {name:'04-gpu-pod-spec',height:1350,commands:[
 'date --iso-8601=seconds',
 'cat gpu-pod.yaml'
 ]},
 {name:'05-pod-running-and-injected-socket',height:1150,commands:[
 'date --iso-8601=seconds',
 'kubectl create namespace dp-capture-20261105',
 'kubectl apply -f gpu-pod.yaml',
 'kubectl -n dp-capture-20261105 wait --for=condition=Ready pod/vmweave-sgemm --timeout=120s',
 'kubectl -n dp-capture-20261105 get pod vmweave-sgemm -o wide',
 "kubectl -n dp-capture-20261105 exec vmweave-sgemm -- sh -c 'id; printenv VMWEAVE_BROKER_SOCKET; ls -l /run/vmweave/gpu.sock; test ! -e /dev/nvidia0 && echo /dev/nvidia0=absent'"
 ]},
 {name:'06-pod-completed-and-sgemm-result',height:1000,commands:[
 'date --iso-8601=seconds',
 "kubectl -n dp-capture-20261105 wait --for=jsonpath='{.status.phase}'=Succeeded pod/vmweave-sgemm --timeout=180s",
 'kubectl -n dp-capture-20261105 get pod vmweave-sgemm -o wide',
 'kubectl -n dp-capture-20261105 logs vmweave-sgemm'
 ]},
 {name:'07-kubectl-describe-completed-pod',height:1900,commands:[
 'date --iso-8601=seconds',
 'kubectl -n dp-capture-20261105 describe pod vmweave-sgemm'
 ]}
 ,{name:'08-final-gpu-availability',height:850,commands:[
 'date --iso-8601=seconds',
 "kubectl wait --for=jsonpath='{.status.allocatable.vmweave\\.io/gpu}'=1 node/dp-dev-20261105 --timeout=90s",
 'kubectl -n vmweave-device-plugin get daemonset,pods',
 "kubectl get node dp-dev-20261105 -o 'custom-columns=NAME:.metadata.name,GPU-CAPACITY:.status.capacity.vmweave\\.io/gpu,GPU-ALLOCATABLE:.status.allocatable.vmweave\\.io/gpu'",
 'kubectl -n dp-capture-20261105 get pod vmweave-sgemm',
 'kubectl -n dp-capture-20261105 logs vmweave-sgemm'
 ]}
];
(async()=>{
 let browser,ttyd,fd;
 try{
  tm('new-session','-d','-s',session,'-x','210','-y','80',...config.ssh);tm('set-option','-t',session,'status','off');
  await until(()=>prompt.test(screen().trimEnd()),30000,'SSH prompt');
  const port=await new Promise(resolve=>{const s=net.createServer();s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>resolve(p));});});
  fd=fs.openSync(path.join(config.scratch,'ttyd.log'),'w');
  ttyd=cp.spawn(config.ttyd,['-i','127.0.0.1','-p',String(port),'-O','-t','fontSize=20','tmux','-L',socket,'attach-session','-t',session],{stdio:['ignore',fd,fd]});
  browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:2300,height:1200},deviceScaleFactor:1});
  for(let i=0;;i++){try{await page.goto('http://127.0.0.1:'+port);break;}catch(e){if(i===30)throw e;await sleep(200);}}
  await page.locator('.xterm-screen').waitFor();await sleep(500);
  for(const frame of frames.filter(f=>!config.frames || config.frames.includes(f.name))){
   await page.setViewportSize({width:2300,height:frame.height});await sleep(300);
   await command('clear');tm('clear-history','-t',session);
   const start=commands.length;
   for(const code of frame.commands)await command(code);
   await sleep(500);
   const transcript=screen().trimEnd()+'\n';
   if(!transcript.includes(frame.commands[0]))throw Error('Frame overflow: '+frame.name);
   fs.writeFileSync(path.join(config.output,frame.name+'.txt'),transcript);
   await page.screenshot({path:path.join(config.output,frame.name+'.png')});
   captures.push({name:frame.name,capturedAt:new Date().toISOString(),width:2300,height:frame.height,commands:commands.slice(start)});
   console.log(frame.name);
  }
  fs.writeFileSync(path.join(config.output,'capture.json'),JSON.stringify({kind:'actual interactive SSH terminal screenshot',edited:false,replayed:false,guest:'dp-dev-20261105',context:'kubernetes-admin@vmweave-device-plugin-test',release:'device-plugin-v0.1.0',browser:'Chromium '+browser.version(),ttyd:cp.execFileSync(config.ttyd,['--version'],{encoding:'utf8'}).trim(),captures},null,2)+'\n');
 }finally{
  fs.writeFileSync(path.join(config.output,'commands.json'),JSON.stringify(commands,null,2)+'\n');
  if(browser)await browser.close();if(ttyd)ttyd.kill('SIGTERM');try{tm('kill-server');}catch(_){}if(fd!==undefined)fs.closeSync(fd);
 }
})().catch(e=>{console.error(e);process.exit(1)});
