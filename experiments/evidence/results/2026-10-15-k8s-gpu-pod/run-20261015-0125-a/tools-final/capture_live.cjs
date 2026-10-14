// Capture a real ttyd/tmux terminal executing the supplied live observation command.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),cp=require('child_process');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const [rootArg,step,command]=process.argv.slice(2),root=path.resolve(rootArg);
 const socket='gpu-pod-'+process.pid,session='evidence';
 const tm=(...args)=>cp.execFileSync('tmux',['-L',socket,...args],{encoding:'utf8'});
 const tmp=path.join(root,'terminal',step);fs.mkdirSync(tmp,{recursive:true});
 const status=path.join(tmp,'status'),rc=path.join(tmp,'bashrc');
 fs.writeFileSync(rc,`PS1='evidence$ '\nHISTFILE=/dev/null\nPROMPT_COMMAND='printf "%s" "$?" > ${status}'\nset -o pipefail\n`);
 tm('new-session','-d','-s',session,'-x','160','-y','48','bash','--noprofile','--rcfile',rc,'-i');
 tm('set-option','-t',session,'status','off');
 const fd=fs.openSync(path.join(tmp,'ttyd.txt'),'w');
 const ttyd=cp.spawn(path.resolve('.local/overhead-20260929/ttyd'),['-i','127.0.0.1','-p','9908','-O','-t','fontSize=18','tmux','-L',socket,'attach-session','-t',session],{stdio:['ignore',fd,fd]});
 let browser;
 try{
  browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1920,height:1080}});
  for(let i=0;;i++){try{await page.goto('http://127.0.0.1:9908/');break;}catch(e){if(i>=20)throw e;await sleep(150);}}
  await page.locator('.xterm-screen').waitFor();await sleep(300);
  if(fs.existsSync(status))fs.unlinkSync(status);
  tm('send-keys','-t',session,'-l',command);tm('send-keys','-t',session,'Enter');
  const until=Date.now()+55000;
  while(!fs.existsSync(status)){if(Date.now()>until)throw Error('observation command timeout');await sleep(100);}
  await sleep(400);
  const iso=new Date().toISOString(),stamp=iso.replace(/[:.]/g,'-');
  const name=`${step}_host-and-guest_${stamp}.png`,dest=path.join(root,'screenshots','original',name);
  fs.mkdirSync(path.dirname(dest),{recursive:true});await page.screenshot({path:dest});
  fs.writeFileSync(path.join(tmp,'screen.txt'),tm('capture-pane','-p','-S','-','-t',session));
  const meta={step,file:'screenshots/original/'+name,captured_at:iso,timezone:'UTC',run_id:path.basename(root),kind:'actual live ttyd/tmux terminal screenshot',command,exit_code:Number(fs.readFileSync(status,'utf8')),tool:'Playwright Chromium '+browser.version(),edited:false};
  fs.writeFileSync(path.join(tmp,'capture.json'),JSON.stringify(meta,null,2)+'\n');console.log(JSON.stringify(meta));
  if(meta.exit_code)process.exitCode=1;
 }finally{if(browser)await browser.close();ttyd.kill('SIGTERM');tm('kill-server');fs.closeSync(fd);}
})().catch(e=>{console.error(e);process.exit(1)});
