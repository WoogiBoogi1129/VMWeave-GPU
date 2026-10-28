// Photograph an actual interactive SSH terminal; no reconstructed command output.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),cp=require('child_process'),net=require('net');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const root=__dirname,repo=path.resolve(root,'../../../..');
const connection=JSON.parse(fs.readFileSync(path.join(root,'connection.json')));
const socket='nested-nodes-'+process.pid,session='capture';
const tm=(...args)=>cp.execFileSync('tmux',['-L',socket,...args],{encoding:'utf8'});
const screen=()=>tm('capture-pane','-p','-S','-','-t',session);
async function until(predicate,label){
 const limit=Date.now()+45000;
 while(!predicate()){if(Date.now()>limit)throw Error('Timeout: '+label);await pause(150);}
}
async function command(line,expect){
 tm('send-keys','-t',session,'-l',line);tm('send-keys','-t',session,'Enter');
 await until(()=>{const s=screen();return expect(s)&&/ubuntu@vw-k8s-cp-01:.*\$\s*$/.test(s.trimEnd());},line);
}
(async()=>{
 const ssh=['ssh','-tt','-i',path.join(repo,'.local/nested-k8s-20261028/id_ed25519'),'-o','StrictHostKeyChecking=yes','-o',`UserKnownHostsFile=${repo}/.local/nested-k8s-20261028/known_hosts`,'-o','ConnectTimeout=10','ubuntu@'+connection.ssh_service_ip];
 let ttyd,browser,fd;
 try{
  tm('new-session','-d','-s',session,'-x','220','-y','40',...ssh);
  tm('set-option','-t',session,'status','off');
  await until(()=>/ubuntu@vw-k8s-cp-01:.*\$\s*$/.test(screen().trimEnd()),'SSH login');
  const port=await new Promise(resolve=>{const s=net.createServer();s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>resolve(p));});});
  fd=fs.openSync(path.join(root,'ttyd.log'),'w');
  ttyd=cp.spawn(path.join(repo,'.local/overhead-20260929/ttyd'),['-i','127.0.0.1','-p',String(port),'-O','-t','fontSize=20','tmux','-L',socket,'attach-session','-t',session],{stdio:['ignore',fd,fd]});
  browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:2400,height:900},deviceScaleFactor:1});
  for(let n=0;;n++){try{await page.goto('http://127.0.0.1:'+port);break;}catch(e){if(n===30)throw e;await pause(100);}}
  await page.locator('.xterm-screen').waitFor();await pause(300);
  await command('clear',()=>true);
  await command('date --iso-8601=seconds',s=>/\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d/.test(s));
  await command('hostname',s=>/\nvw-k8s-cp-01\r?\n/.test(s));
  await command('kubectl config current-context',s=>s.includes('kubernetes-admin@vmweave-nested'));
  await command('kubectl get nodes -o wide',s=>/vw-k8s-cp-01\s+Ready\s+control-plane/.test(s)&&/vw-k8s-worker-01\s+Ready/.test(s));
  const transcript=screen();fs.writeFileSync(path.join(root,'terminal.txt'),transcript);
  // Capture after the real command returns its prompt and the terminal has rendered.
  await pause(500);
  const file='control-plane-kubectl-get-nodes-wide.png';
  await page.screenshot({path:path.join(root,file)});
  fs.writeFileSync(path.join(root,'capture.json'),JSON.stringify({captured_at:new Date().toISOString(),kind:'actual interactive SSH ttyd/tmux terminal screenshot',edited:false,file,command:'kubectl get nodes -o wide',guest_hostname:'vw-k8s-cp-01',context:'kubernetes-admin@vmweave-nested',connection,tool:'Playwright Chromium '+browser.version(),viewport:{width:2400,height:900},both_nodes_ready:true},null,2)+'\n');
  console.log(file);console.log(transcript.trim());
 }finally{
  if(browser)await browser.close();if(ttyd)ttyd.kill('SIGTERM');
  try{tm('kill-server');}catch(_){}if(fd!==undefined)fs.closeSync(fd);
 }
})().catch(e=>{try{fs.writeFileSync(path.join(root,'capture-error.txt'),String(e));}catch(_){}console.error(e);process.exit(1)});
