// Actual bash/tmux log inspection, displayed by upstream ttyd. PNG only.
// No asciicast, screencast, video, custom HTML or replacement terminal output.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),cp=require('child_process');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  const root=path.resolve(process.argv[2]),base=path.resolve(process.argv[3]);
  const socket='flyt-s2-static',session='logs',out=path.join(root,'terminal-captures');
  fs.mkdirSync(out,{recursive:true});
  const tm=(...args)=>cp.execFileSync('tmux',['-L',socket,...args],{encoding:'utf8'});
  const rc=path.join(base,'static-bashrc');
  fs.writeFileSync(rc,`PS1='\\u@\\h:\\W\\$ '
PROMPT_COMMAND='printf "%s\\n" "$?" > "$S2_STATUS"'
HISTFILE=/dev/null
set -o pipefail
cd "$RAW"
`);
  const status=[path.join(base,'guest-status'),path.join(base,'worker-status')];
  tm('new-session','-d','-s',session,'-x','180','-y','48','-e','RAW='+path.join(root,'raw'),'-e','S2_STATUS='+status[0],
     'bash','--noprofile','--rcfile',rc,'-i');
  tm('split-window','-h','-t',session,'-e','S2_STATUS='+status[1],'bash','--noprofile','--rcfile',rc,'-i');
  const panes=tm('list-panes','-t',session,'-F','#{pane_id}').trim().split('\n');
  tm('set-option','-t',session,'pane-border-status','top');
  tm('set-option','-t',session,'pane-border-format','#{pane_title}');
  tm('select-pane','-t',panes[0],'-T','Guest stdout / stderr: retrieved SSH logs');
  tm('select-pane','-t',panes[1],'-T','Worker stderr: retrieved kubectl logs');
  const ttydLog=fs.openSync(path.join(base,'ttyd.log'),'w');
  const ttyd=cp.spawn(path.join(base,'ttyd'),['-i','127.0.0.1','-p','9902','-O','-t','fontSize=18',
      'tmux','-L',socket,'attach-session','-t',session],{stdio:['ignore',ttydLog,ttydLog]});
  let browser;const commands=[],captures=[];
  async function command(pane,code){
    if(fs.existsSync(status[pane]))fs.unlinkSync(status[pane]);
    tm('send-keys','-t',panes[pane],'-l',code);tm('send-keys','-t',panes[pane],'Enter');
    const deadline=Date.now()+30000;
    while(!fs.existsSync(status[pane])){if(Date.now()>deadline)throw Error('Terminal command timeout: '+code);await sleep(50);}
    const exit=Number(fs.readFileSync(status[pane],'utf8').trim());
    commands.push({pane:pane===0?'Guest log inspection':'Worker log inspection',command:code,exit_code:exit,utc:new Date().toISOString()});
    if(exit!==0)throw Error('Command failed: '+code);
  }
  try{
    browser=await chromium.launch({headless:true,args:['--no-sandbox']});
    const context=await browser.newContext({viewport:{width:1920,height:1080}}); // No recordVideo option.
    const page=await context.newPage();
    for(let n=0;;n++){try{await page.goto('http://127.0.0.1:9902/');break;}catch(e){if(n>20)throw e;await sleep(250);}}
    await page.locator('.xterm-screen').waitFor();await sleep(1500);
    const frames=[
      ['01-program-binding',
       ['# 1. Executed Guest command and workload','jq -r .guest_command command.json',`jq 'select(.event=="CONDITIONS")' stdout.jsonl`],
       ['# Same allocation, generation and session',`jq '{allocation,generation,session_id,gpu_uuid}' trace-binding.json`,
        'jq -r \'.worker_log_command | join(" ")\' command.json']],
      ['02-malloc-roundtrip',
       ['# 2. cudaMalloc(1 MiB): Guest submit / receive',`jq 'select(.api_id==4112) | {event,request_id,requested_bytes,allocation_handle,transport_status,result_domain,api_result}' guest-trace.jsonl`],
       ['# 2. SAME REQUEST: Worker take / respond',`jq 'select(.api_id==4112) | {event,request_id,requested_bytes,allocation_handle,transport_status,result_domain,api_result}' worker-trace.jsonl`]],
      ['03-h2d',
       ['# 3. H2D: input copy to the allocation',`jq 'select(.api_id==4114 and .copy_direction==1) | {event,request_id,copy_bytes,dst_handle,transport_status,api_result}' guest-trace.jsonl`],
       ['# 3. H2D: Worker result',`jq 'select(.api_id==4114 and .copy_direction==1) | {event,request_id,copy_bytes,dst_handle,transport_status,api_result}' worker-trace.jsonl`]],
      ['04-kernel-sync',
       ['# 4. Kernel launch (8243), then synchronize (4128)',`jq 'select(.api_id==8243 or .api_id==4128) | {event,request_id,api_id,transport_status,api_result}' guest-trace.jsonl`],
       ['# Launch response alone is NOT GPU completion',`jq 'select(.api_id==8243 or .api_id==4128) | {event,request_id,api_id,transport_status,api_result}' worker-trace.jsonl`]],
      ['05-d2h',
       ['# 5. D2H: read back 1 MiB',`jq 'select(.api_id==4114 and .copy_direction==2) | {event,request_id,copy_bytes,src_handle,output_bytes,api_result}' guest-trace.jsonl`],
       ['# 5. D2H: response data length',`jq 'select(.api_id==4114 and .copy_direction==2) | {event,request_id,copy_bytes,src_handle,output_bytes,api_result}' worker-trace.jsonl`]],
      ['06-accuracy-free',
       ['# 6. Actual output verification in the Guest',`jq 'select(.event=="ACCURACY" or .event=="RESULT")' stdout.jsonl`,
        `jq 'select(.api_id==4113 and .event=="receive") | {event,request_id,allocation_handle,api_result}' guest-trace.jsonl`],
       ['# 6. cudaFree: the same allocation handle',`jq 'select(.api_id==4113) | {event,request_id,allocation_handle,transport_status,api_result}' worker-trace.jsonl`,
        '# SHA-256: expected output and actual output',`jq '{reference,output}' array-hashes.json`]],
      ['07-cleanup-verification',
       ['# 7. Recheck original trace records and output bytes','python3 ../../../verify_stage2.py . | jq \'del(.joined)\''],
       ['# 7. Saved post-run cleanup observations',`jq '{phase:.status.phase}' released-channel.json`,
        'cat cleanup.json','cat final-audit.json']]
    ];
    for(const [name,left,right] of frames){
      await command(0,'clear');await command(1,'clear');
      for(const line of left)await command(0,line);
      for(const line of right)await command(1,line);
      await sleep(400);
      await page.screenshot({path:path.join(out,name+'.png')});
      for(let pane=0;pane<2;pane++)fs.writeFileSync(path.join(out,name+(pane===0?'-guest.txt':'-worker.txt')),tm('capture-pane','-p','-t',panes[pane]));
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
