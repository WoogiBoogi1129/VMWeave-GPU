// Capture real bash/tmux inspection of saved evidence, not a simulated terminal.
const {chromium}=require('../../.local/reorganization/browser/node_modules/playwright');
const fs=require('fs'),path=require('path'),cp=require('child_process');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const root=path.resolve(__dirname,'../..'),base=path.join(root,'.local/vram-accounting-20261016'),out=path.join(__dirname,'evidence/20261016/terminal');fs.mkdirSync(out,{recursive:true});
 const socket='vram-evidence-1016',status=path.join(base,'terminal-status'),rc=path.join(base,'terminal-bashrc');
 fs.writeFileSync(rc,`PS1='evidence$ '\nPROMPT_COMMAND='printf "%s\\n" "$?" > "${status}"'\nHISTFILE=/dev/null\nset -o pipefail\ncd "${__dirname}"\n`);
 const tm=(...args)=>cp.execFileSync('tmux',['-L',socket,...args],{encoding:'utf8'});
 tm('new-session','-d','-s','evidence','-x','180','-y','48','bash','--noprofile','--rcfile',rc,'-i');
 const fd=fs.openSync(path.join(base,'terminal-ttyd.log'),'w');const ttyd=cp.spawn(path.join(root,'.local/stage2-static-20260928/ttyd'),['-i','127.0.0.1','-p','19996','-O','-t','fontSize=17','tmux','-L',socket,'attach','-t','evidence'],{stdio:['ignore',fd,fd]});
 let browser;const records=[];
 async function command(cmd){if(fs.existsSync(status))fs.unlinkSync(status);tm('send-keys','-t','evidence','-l',cmd);tm('send-keys','-t','evidence','Enter');for(let i=0;!fs.existsSync(status);i++){if(i>600)throw Error('command timeout');await sleep(50);}const code=Number(fs.readFileSync(status,'utf8'));records.push({cmd,code,utc:new Date().toISOString()});if(code!==0)throw Error(cmd);}
 try{
 browser=await chromium.launch({headless:true,executablePath:'/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1920,height:1080}});
 for(let i=0;;i++){try{await page.goto('http://127.0.0.1:19996/');break;}catch(e){if(i>30)throw e;await sleep(100);}}
 await page.locator('.xterm-screen').waitFor();await sleep(1000);
 const frames=[['01-boundary',[
 '# POST-RUN ORIGINAL LOG INSPECTION: exact successful / failed allocations',
 `jq -c 'select(.label=="warm-max" or .label=="warm-min-fail") | {label,rc,bytes,live_requested,free,total,verify_rc}' results/20261016/runs/vram-single-r1-{1024,4096}/events.jsonl`,
 '# Independent repeats, quota bytes, usable bytes, accounting residual',
 `jq -c '.singles[] | {run,quota_mib,baseline_bytes,warm_max,min_failure,ledger_max_abs_residual}' evidence/20261016/summary.json`]],
 ['02-rounding-recovery',[
 '# Byte-level rounding and successful recovery after quota OOM',
 `jq -c 'select(.label=="rounding" or .label=="cumulative-over" or .label=="after-oom-check" or .label=="refill-check" or .label=="recovery") | {label,bytes,rc,live_requested,free,verify_rc}' results/20261016/runs/vram-single-r1-1024/events.jsonl`,
 '# Channel release evidence (both quotas)',
 `jq -c '{name:.metadata.name,phase:.status.phase,reason:.status.reason}' results/20261016/runs/vram-single-r1-{1024,4096}/channel-released.json`]],
 ['03-pair',[
 '# Two VMs: simultaneous near-boundary allocations, OOM and survivor checks',
 `jq -c 'select(.label=="pair-near" or .label=="pair-over" or .label=="pair-survivor") | {label,rc,live_requested,free,total,verify_rc}' results/20261016/runs/vram-pair-v3-r1-ab-{a,b}/events.jsonl`,
 '# Repeated independent pairs',
 `jq -c '.pairs[] | {run,status,direction}' evidence/20261016/summary.json`]],
 ['04-pytorch',[
 '# PyTorch staged allocator observations, original JSON fields',
 `jq -c 'select(.stage!="done") | {stage,allocated,reserved,free,total}' results/20261016/runs/vram-torch-r1-{1024,4096}/torch-events.jsonl`,
 '# Full evidence audit',
 'python3 analyze.py --final']],
 ['05-trained-boundary',[
 '# Supplementary: post-training direct CUDA allocation to the logical quota boundary',
 `jq -c 'select(.stage|startswith("trained-")) | {stage,direct_requested,api_rc,free,total}' results/20261016/runs/vram-mlp-boundary-v2-r1-{1024,4096}/torch-events.jsonl`,
 '# Independently matched Worker NVML and HAMi snapshots (byte units)',
 `jq -c '.supplementary_trained_boundary[] | .run as $r | .stages[] | select(.stage=="trained-max") | {run:$r,hami_bytes,nvml_process_bytes,nvml_minus_hami_bytes}' evidence/20261016/summary.json`]]];
 for(const [name,lines] of frames){await command('clear');for(const l of lines)await command(l);await sleep(500);await page.screenshot({path:path.join(out,name+'.png')});fs.writeFileSync(path.join(out,name+'.txt'),tm('capture-pane','-p','-t','evidence'));}
 fs.writeFileSync(path.join(out,'metadata.json'),JSON.stringify({kind:'Real ttyd/tmux/bash post-run inspection of original experiment files',live_experiment_capture:false,captured_utc:new Date().toISOString(),browser:browser.version(),commands:records},null,2));
 }finally{if(browser)await browser.close();ttyd.kill('SIGTERM');tm('kill-server');fs.closeSync(fd);}
})().catch(e=>{console.error(e);process.exit(1)});
