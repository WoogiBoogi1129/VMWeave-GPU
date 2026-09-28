// Actual bash/tmux log inspection, displayed by upstream ttyd. PNG only.
// No asciicast, screencast, video, custom HTML or replacement terminal output.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),cp=require('child_process');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  const root=path.resolve(process.argv[2]),base=path.resolve(process.argv[3]);
  const socket='flyt-s3-static',session='logs',out=path.join(root,'terminal-captures');
  fs.mkdirSync(out,{recursive:true});
  const tm=(...args)=>cp.execFileSync('tmux',['-L',socket,...args],{encoding:'utf8'});
  const rc=path.join(base,'static-bashrc');
  fs.writeFileSync(rc,`PS1='\\u@\\h:\\W\\$ '
PROMPT_COMMAND='printf "%s\\n" "$?" > "$S3_STATUS"'
HISTFILE=/dev/null
set -o pipefail
cd "$RAW"
`);
  const status=[path.join(base,'guest-status'),path.join(base,'worker-status')];
  tm('new-session','-d','-s',session,'-x','180','-y','48','-e','RAW='+path.join(root,'pair-1'),'-e','S3_STATUS='+status[0],
     'bash','--noprofile','--rcfile',rc,'-i');
  tm('split-window','-h','-t',session,'-e','S3_STATUS='+status[1],'bash','--noprofile','--rcfile',rc,'-i');
  const panes=tm('list-panes','-t',session,'-F','#{pane_id}').trim().split('\n');
  tm('set-option','-t',session,'pane-border-status','top');
  tm('set-option','-t',session,'pane-border-format','#{pane_title}');
  tm('select-pane','-t',panes[0],'-T','VM A: 1 GiB limit / retrieved logs');
  tm('select-pane','-t',panes[1],'-T','VM B: 4 GiB limit / retrieved logs');
  const ttydLog=fs.openSync(path.join(base,'ttyd.log'),'w');
  const ttyd=cp.spawn(path.join(base,'ttyd'),['-i','127.0.0.1','-p','9903','-O','-t','fontSize=18',
      'tmux','-L',socket,'attach-session','-t',session],{stdio:['ignore',ttydLog,ttydLog]});
  let browser;const commands=[],captures=[];
  async function command(pane,code){
    if(fs.existsSync(status[pane]))fs.unlinkSync(status[pane]);
    tm('send-keys','-t',panes[pane],'-l',code);tm('send-keys','-t',panes[pane],'Enter');
    const deadline=Date.now()+30000;
    while(!fs.existsSync(status[pane])){if(Date.now()>deadline)throw Error('Terminal command timeout: '+code);await sleep(50);}
    const exit=Number(fs.readFileSync(status[pane],'utf8').trim());
    commands.push({pane:pane===0?'VM A log inspection':'VM B log inspection',command:code,exit_code:exit,utc:new Date().toISOString()});
    if(exit!==0)throw Error('Command failed: '+code);
  }
  try{
    browser=await chromium.launch({headless:true,args:['--no-sandbox']});
    const context=await browser.newContext({viewport:{width:1920,height:1080}}); // No recordVideo option.
    const page=await context.newPage();
    for(let n=0;;n++){try{await page.goto('http://127.0.0.1:9903/');break;}catch(e){if(n>20)throw e;await sleep(250);}}
    await page.locator('.xterm-screen').waitFor();await sleep(1500);
    const both=(fn)=>['A','B'].map(fn);
    const frames=[
      ['01-binding', ...both(vm=>['# 1. Actual VM / Worker / same physical GPU',`jq '{worker,gpu_uuid,vmi_uid,worker_uid}' ${vm}/identity.json`,
       `jq '{requested:.request.spec.memory,applied:.channel.status.memoryMiB}' ${vm}/applied.json`])],
      ['02-baseline-and-B-allocation',
       ['# 2. VM A: precheck complete; waiting for command',`jq 'select(.event=="MEMINFO" and .phase=="ready")' A/stdout.jsonl`],
       ['# 2. VM B: allocate 1536 MiB and retain it',`jq 'select(.event=="ALLOC" and .phase=="large")' B/stdout.jsonl`]],
      ['03-same-request-different-results',...both(vm=>['# 3. SAME 1536 MiB request; compare api_result',`jq 'select(.event=="ALLOC" and .phase=="large")' ${vm}/stdout.jsonl`,
       '# Worker response for that allocation request',`sed -n 's/^FLYT_TRACE //p' ${vm}/worker-stderr.txt | jq 'select(.event=="respond" and .api_id==4112 and .requested_bytes==1610612736) | {request_id,requested_bytes,api_result,transport_status}'`])],
      ['04-A-recovery-B-continuation',
       ['# 4. VM A: same process succeeds with 128 MiB',`jq 'select(.event=="ALLOC" and .phase=="small")' A/stdout.jsonl`,
        `jq -s '[.[]|select(.event=="PROGRESS" and .live_allocated_bytes==134217728)][0]' A/stdout.jsonl`],
       ['# 4. VM B: actual records bracketing A events',`cat B/continuation-excerpt.jsonl | jq '{A_event,host_received_utc,completed:.record.completed,live_bytes:.record.live_allocated_bytes,mismatches:.record.mismatches}'`]],
      ['05-correctness-and-free',...both(vm=>['# 5. Final sample verification and release',`jq 'select(.event=="FREE" and .phase=="final" or .event=="RESULT")' ${vm}/stdout.jsonl`])],
      ['06-offline-verification-and-cleanup',
       ['# 6. Independent check of logs and saved output bytes',`python3 ../../../verify_stage3.py . | jq '{status,pair,B_checks_by_host_receipt_interval,B_same_live_allocation}'`],
       ['# 6. Both channels released',`jq '{name:.metadata.name,phase:.status.phase}' A/released-channel.json B/released-channel.json`,
        'cat ../final-audit.json']]
    ];
    for(const [name,left,right] of frames){
      await command(0,'clear');await command(1,'clear');
      for(const line of left)await command(0,line);
      for(const line of right)await command(1,line);
      await sleep(400);
      await page.screenshot({path:path.join(out,name+'.png')});
      for(let pane=0;pane<2;pane++)fs.writeFileSync(path.join(out,name+(pane===0?'-A.txt':'-B.txt')),tm('capture-pane','-p','-t',panes[pane]));
      captures.push({name,utc:new Date().toISOString(),kind:'Live ttyd/tmux screenshot of post-run original log inspection'});
    }
    fs.writeFileSync(path.join(out,'metadata.json'),JSON.stringify({recording:false,video:false,
      ttyd:cp.execFileSync(path.join(base,'ttyd'),['--version'],{encoding:'utf8'}).trim(),
      tmux:cp.execFileSync('tmux',['-V'],{encoding:'utf8'}).trim(),browser:browser.version(),captures},null,2)+'\n');
    await context.close();
  } finally{
    fs.writeFileSync(path.join(out,'commands.json'),JSON.stringify(commands,null,2)+'\n');
    if(browser)await browser.close();ttyd.kill('SIGTERM');tm('kill-server');fs.closeSync(ttydLog);
  }
})().catch(e=>{console.error(e);process.exit(1)});
