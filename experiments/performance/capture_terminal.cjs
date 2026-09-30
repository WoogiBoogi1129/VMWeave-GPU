// Screenshots of real upstream ttyd/tmux running ordinary log-inspection commands.
// No video, replay recording, custom HTML, or simulated terminal output.
const {chromium}=require('playwright');const fs=require('fs'),path=require('path'),cp=require('child_process');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const root=path.resolve(process.argv[2]),base=path.resolve(process.argv[3]),out=path.join(root,'terminal-captures');fs.mkdirSync(out,{recursive:true});
 const socket='vmweave-performance-static',session='logs';const tm=(...v)=>cp.execFileSync('tmux',['-L',socket,...v],{encoding:'utf8'});
 const rc=path.join(base,'terminal-bashrc');fs.writeFileSync(rc,`PS1='\\u@\\h:\\W\\$ '\nPROMPT_COMMAND='printf "%s\\n" "$?" > "$PERF_STATUS"'\nHISTFILE=/dev/null\nset -o pipefail\ncd "$RAW"\n`);
 const status=[0,1].map(i=>path.join(base,'terminal-status-'+i));tm('new-session','-d','-s',session,'-x','180','-y','48','-e','RAW='+root,'-e','PERF_STATUS='+status[0],'bash','--noprofile','--rcfile',rc,'-i');tm('split-window','-h','-t',session,'-e','PERF_STATUS='+status[1],'bash','--noprofile','--rcfile',rc,'-i');
 const panes=tm('list-panes','-t',session,'-F','#{pane_id}').trim().split('\n');tm('set-option','-t',session,'pane-border-status','top');tm('set-option','-t',session,'pane-border-format','#{pane_title}');
 for(let i=0;i<2;i++)tm('select-pane','-t',panes[i],'-T',i?'Original results / verification':'Actual experiment logs — post-run inspection');
 const fd=fs.openSync(path.join(base,'ttyd.log'),'w'),ttyd=cp.spawn(path.resolve('.local/overhead-20260929/ttyd'),['-i','127.0.0.1','-p','9903','-O','-t','fontSize=17','tmux','-L',socket,'attach-session','-t',session],{stdio:['ignore',fd,fd]});let browser;const commands=[],captures=[];
 async function command(pane,code){if(fs.existsSync(status[pane]))fs.unlinkSync(status[pane]);tm('send-keys','-t',panes[pane],'-l',code);tm('send-keys','-t',panes[pane],'Enter');const until=Date.now()+60000;while(!fs.existsSync(status[pane])){if(Date.now()>until)throw Error('command timeout');await sleep(50);}const exit=Number(fs.readFileSync(status[pane],'utf8').trim());commands.push({pane,command:code,exit_code:exit,utc:new Date().toISOString()});if(exit)throw Error('command failed: '+code);}
 try{
 browser=await chromium.launch({headless:true,args:['--no-sandbox']});const context=await browser.newContext({viewport:{width:1920,height:1080}});const page=await context.newPage();for(let n=0;;n++){try{await page.goto('http://127.0.0.1:9903/');break;}catch(e){if(n>20)throw e;await sleep(250);}}await page.locator('.xterm-screen').waitFor();await sleep(1000);
 const frames=[
 ['01-actual-policy-and-procedure',[
 '# Actual Worker environment captured during warmup',
 `jq '.[] | select(.command|contains("flyt-shm-worker")) | {pid,policy:.environment.GPU_CORE_UTILIZATION_POLICY,cap:.environment.CUDA_DEVICE_SM_LIMIT,memory:.environment.CUDA_DEVICE_MEMORY_LIMIT_0}' runs/perf-c-r1-25/runtime-libraries.json`,
 `jq '{cap,gpu_uuid,worker,worker_uid}' runs/perf-c-r1-25/identity.json`],[
 '# Original measured events; automated run, post-run inspection',
 `jq -Rr 'fromjson? | select(.event=="MEASUREMENT_START" or .event=="MEASUREMENT_END" or .event=="RESULT") | [.event,.phase,.completed,.elapsed_s,.status] | @tsv' runs/perf-c-r1-25/stdout.jsonl | column -t`,
 `jq '{released,uid,utc}' runs/perf-c-r1-25/cleanup.json`]],
 ['02-nts-path-comparison',[
 '# Recomputed from all five independent sessions per path',
 'python3 ../../../performance/terminal_table.py . paths'],[
 '# Protocol and raw first-run output',
 `jq '.overhead' protocol-overhead.json`,
 `jq -Rr 'fromjson? | select(.event=="RESULT") | [.mode,.bytes,.completed,.operations_per_s,.mismatches] | @tsv' runs/perf-o-r1-t/stdout.jsonl | column -t`]],
 ['03-single-and-shared-results',[
 '# Output correctness and utilization enforcement are separate',
 'python3 ../../../performance/terminal_table.py . single'],[
 '# Integrated start/stop sharing experiment',
 'python3 ../../../performance/terminal_table.py . shared',
 `jq '.shared | {conditions,solo_window_s,shared_window_s,recovery_window_s}' protocol.json`]],
 ['04-verification-and-resource-audit',[
 '# Independently checked sample counts, clocks, output and release',
 `jq 'del(.runs,.details,.pair_checks)' validation.json`,
 'cat campaign-execution-complete.json'],[
 '# Actual resource cleanup and monitoring audit',
 'cat final-audit.json']]
 ];
 for(const [name,left,right] of frames){await command(0,'clear');await command(1,'clear');for(const c of left)await command(0,c);for(const c of right)await command(1,c);await sleep(350);await page.screenshot({path:path.join(out,name+'.png')});for(let i=0;i<2;i++)fs.writeFileSync(path.join(out,name+'-'+i+'.txt'),tm('capture-pane','-p','-t',panes[i]));captures.push({name,utc:new Date().toISOString(),kind:'Post-run inspection of original logs in real ttyd/tmux'});}
 fs.writeFileSync(path.join(out,'metadata.json'),JSON.stringify({recording:false,video:false,ttyd:cp.execFileSync(path.resolve('.local/overhead-20260929/ttyd'),['--version'],{encoding:'utf8'}).trim(),browser:browser.version(),captures},null,2)+'\n');await context.close();
 }finally{fs.writeFileSync(path.join(out,'commands.json'),JSON.stringify(commands,null,2)+'\n');if(browser)await browser.close();ttyd.kill('SIGTERM');tm('kill-server');fs.closeSync(fd);}
})().catch(e=>{console.error(e);process.exit(1)});
