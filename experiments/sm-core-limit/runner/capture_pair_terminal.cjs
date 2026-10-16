// Capture real bash/tmux inspection of saved evidence, not a simulated terminal.
const {chromium}=require('../../../.local/reorganization/browser/node_modules/playwright');
const fs=require('fs'),path=require('path'),cp=require('child_process');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const root=path.resolve(__dirname,'../../..'),base=path.join(root,'.local/sm-pair-20261016'),out=path.join(__dirname,'../evidence/pairs-20261016/screenshots/terminal');fs.mkdirSync(out,{recursive:true});
 const socket='sm-pair-evidence-1016',status=path.join(base,'terminal-status'),rc=path.join(base,'terminal-bashrc');
 fs.writeFileSync(rc,`PS1='evidence$ '\nPROMPT_COMMAND='printf "%s\\n" "$?" > "${status}"'\nHISTFILE=/dev/null\nset -o pipefail\ncd "${root}/experiments/sm-core-limit/evidence/pairs-20261016"\n`);
 const tm=(...args)=>cp.execFileSync('tmux',['-L',socket,...args],{encoding:'utf8'});
 tm('new-session','-d','-s','evidence','-x','180','-y','48','bash','--noprofile','--rcfile',rc,'-i');
 const fd=fs.openSync(path.join(base,'terminal-ttyd.log'),'w');const ttyd=cp.spawn(path.join(root,'.local/stage2-static-20260928/ttyd'),['-i','127.0.0.1','-p','19997','-O','-t','fontSize=17','tmux','-L',socket,'attach','-t','evidence'],{stdio:['ignore',fd,fd]});
 let browser;const records=[];
 async function command(cmd){if(fs.existsSync(status))fs.unlinkSync(status);tm('send-keys','-t','evidence','-l',cmd);tm('send-keys','-t','evidence','Enter');for(let i=0;!fs.existsSync(status);i++){if(i>600)throw Error('command timeout');await sleep(50);}const code=Number(fs.readFileSync(status,'utf8'));records.push({cmd,code,utc:new Date().toISOString()});if(code!==0)throw Error(cmd);}
 try{
 browser=await chromium.launch({headless:true,executablePath:'/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1920,height:1080}});
 for(let i=0;;i++){try{await page.goto('http://127.0.0.1:19997/');break;}catch(e){if(i>30)throw e;await sleep(100);}}
 await page.locator('.xterm-screen').waitFor();await sleep(1000);
 const frames=[['01-results',[
 '# ACTUAL SAVED MEASUREMENTS: 3 fresh pairs, patched HAMi, one GPU',
 `jq -c '.aggregate[] | {cap,runs,hami_util_mean,pmon_util_mean,launches_per_second,throughput_share_pct}' summary.json`,
 '# Per-pair observed usage and throughput',
 `jq -c '.pairs[] | {pair,device_util_mean,workers:[.workers[]|{slot,cap,hami_util_mean,launches_per_second,throughput_share_pct}]}' summary.json`]],
 ['02-identity-cleanup',[
 '# Actual loaded library and enforced Worker environment',
 `jq -c '{sha256,pod_uid}' pair-1/{a,b}/library-mount.json`,
 `jq -c '{pid,env}' pair-1/{a,b}/host-process.json`,
 '# All six channels reached Released',
 `jq -c '{name:.metadata.name,phase:.status.phase}' pair-{1,2,3}/{a,b}/channel-released.json`,
 '# Preserved evidence hashes',
 'sha256sum -c SHA256SUMS | tail -5']]];
 for(const [name,lines] of frames){await command('clear');for(const l of lines)await command(l);await sleep(500);await page.screenshot({path:path.join(out,name+'.png')});fs.writeFileSync(path.join(out,name+'.txt'),tm('capture-pane','-p','-t','evidence'));}
 fs.writeFileSync(path.join(out,'metadata.json'),JSON.stringify({kind:'Real ttyd/tmux/bash post-run inspection of original experiment files',live_experiment_capture:false,captured_utc:new Date().toISOString(),browser:browser.version(),commands:records},null,2));
 }finally{if(browser)await browser.close();ttyd.kill('SIGTERM');tm('kill-server');fs.closeSync(fd);}
})().catch(e=>{console.error(e);process.exit(1)});
