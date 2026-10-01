// Screenshots of real upstream ttyd/tmux running ordinary log-inspection commands.
// No video, replay recording, custom HTML, or simulated terminal output.
const {chromium}=require('playwright');const fs=require('fs'),path=require('path'),cp=require('child_process');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const root=path.resolve(process.argv[2]),base=path.resolve(process.argv[3]),out=path.join(root,'terminal-captures');fs.mkdirSync(out,{recursive:true});
 const socket='vmweave-shmfirst-static',session='logs';const tm=(...v)=>cp.execFileSync('tmux',['-L',socket,...v],{encoding:'utf8'});
 const rc=path.join(base,'terminal-bashrc');fs.writeFileSync(rc,`PS1='\\u@\\h:\\W\\$ '\nPROMPT_COMMAND='printf "%s\\n" "$?" > "$PERF_STATUS"'\nHISTFILE=/dev/null\nset -o pipefail\ncd "$RAW"\n`);
 const status=[0,1].map(i=>path.join(base,'terminal-status-'+i));tm('new-session','-d','-s',session,'-x','180','-y','48','-e','RAW='+root,'-e','PERF_STATUS='+status[0],'bash','--noprofile','--rcfile',rc,'-i');tm('split-window','-h','-t',session,'-e','PERF_STATUS='+status[1],'bash','--noprofile','--rcfile',rc,'-i');
 const panes=tm('list-panes','-t',session,'-F','#{pane_id}').trim().split('\n');tm('set-option','-t',session,'pane-border-status','top');tm('set-option','-t',session,'pane-border-format','#{pane_title}');
 for(let i=0;i<2;i++)tm('select-pane','-t',panes[i],'-T',i?'Original results / verification':'Actual experiment logs — post-run inspection');
 const fd=fs.openSync(path.join(base,'ttyd.log'),'w'),ttyd=cp.spawn(path.resolve('.local/overhead-20260929/ttyd'),['-i','127.0.0.1','-p','9905','-O','-t','fontSize=17','tmux','-L',socket,'attach-session','-t',session],{stdio:['ignore',fd,fd]});let browser;const commands=[],captures=[];
 async function command(pane,code){if(fs.existsSync(status[pane]))fs.unlinkSync(status[pane]);tm('send-keys','-t',panes[pane],'-l',code);tm('send-keys','-t',panes[pane],'Enter');const until=Date.now()+60000;while(!fs.existsSync(status[pane])){if(Date.now()>until)throw Error('command timeout');await sleep(50);}const exit=Number(fs.readFileSync(status[pane],'utf8').trim());commands.push({pane,command:code,exit_code:exit,utc:new Date().toISOString()});if(exit)throw Error('command failed: '+code);}
 try{
 browser=await chromium.launch({headless:true,args:['--no-sandbox']});const context=await browser.newContext({viewport:{width:1920,height:1080}});const page=await context.newPage();for(let n=0;;n++){try{await page.goto('http://127.0.0.1:9905/');break;}catch(e){if(n>20)throw e;await sleep(250);}}await page.locator('.xterm-screen').waitFor();await sleep(1000);
 const frames=[
  [
    "01-policy-and-output",
    [
      "# Actual measured Worker environment",
      "jq '.[] | {pid,environment,executable_sha256}' runs/sf-r1-both/runtime-libraries.json",
      "cat runs/sf-r1-both/guest-artifact-hashes.txt"
    ],
    [
      "# Actual formal measurements and full-output validation",
      "jq -Rr 'fromjson? | select(.event==\"RESULT\") | [.mode,.bytes,.completed,.operations_per_s,.mismatches] | @tsv' runs/sf-r1-both/stdout.jsonl | column -t",
      "jq '{released,uid,utc}' runs/sf-r1-both/cleanup.json"
    ]
  ],
  [
    "02-latency-and-cpu",
    [
      "# Mean latency in microseconds: query, kernel, H2D16MiB, D2H16MiB",
      "jq -r '.summary|to_entries[]|[.key,.value.query.mean_us,.value.kernel.mean_us,.value[\"h2d-16777216\"].mean_us,.value[\"d2h-16777216\"].mean_us]|@tsv' summary.json | column -t",
      "jq '{complete,latency_targets_pass,p95_regression_guard_pass,candidate_eligible,improvements}' validation.json"
    ],
    [
      "# Saturated CPU cores and CPU microseconds per kernel iteration",
      "jq -r '.summary|to_entries[]|[.key,.value[\"kernel-1048576\"].cores,.value[\"kernel-1048576\"].cpu_us_iteration]|@tsv' cpu-summary.json | column -t",
      "# Explicit preparation recovery; no measurement replay",
      "cat runs/sf-r1-base/preparation-resume.json"
    ]
  ]
];
 for(const [name,left,right] of frames){await command(0,'clear');await command(1,'clear');for(const c of left)await command(0,c);for(const c of right)await command(1,c);await sleep(350);await page.screenshot({path:path.join(out,name+'.png')});for(let i=0;i<2;i++)fs.writeFileSync(path.join(out,name+'-'+i+'.txt'),tm('capture-pane','-p','-t',panes[i]));captures.push({name,utc:new Date().toISOString(),kind:'Post-run inspection of original logs in real ttyd/tmux'});}
 fs.writeFileSync(path.join(out,'metadata.json'),JSON.stringify({recording:false,video:false,ttyd:cp.execFileSync(path.resolve('.local/overhead-20260929/ttyd'),['--version'],{encoding:'utf8'}).trim(),browser:browser.version(),captures},null,2)+'\n');await context.close();
 }finally{fs.writeFileSync(path.join(out,'commands.json'),JSON.stringify(commands,null,2)+'\n');if(browser)await browser.close();ttyd.kill('SIGTERM');tm('kill-server');fs.closeSync(fd);}
})().catch(e=>{console.error(e);process.exit(1)});

