// Actual read-only output viewer. First independent run is recorded continuously.
const {chromium} = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const out = path.resolve(process.argv[2]);
  const url = process.argv[3] || 'http://127.0.0.1:9898/';
  fs.mkdirSync(out, {recursive:true});
  const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
  let context = await browser.newContext({viewport:{width:1920,height:1440},
    recordVideo:{dir:out,size:{width:1920,height:1440}}});
  let page = await context.newPage();
  const deadline = Date.now()+20*60*1000;
  while (true) {
    try {await page.goto(url, {waitUntil:'domcontentloaded',timeout:3000});break;}
    catch(e) {if (Date.now()>deadline) throw e; await new Promise(r=>setTimeout(r,1000));}
  }
  const seen = new Set(); let recording = true;
  while (Date.now()<deadline) {
    const state = await page.evaluate(() => window.evidence || null);
    if (state) {
      const ready = state.stage==='RUNNING' && Object.keys(state.checks||{}).length>0 && Object.values(state.checks).every(Boolean);
      const phase = ready?'MAPPED':state.stage;
      const key = state.run_id+'-'+phase;
      if ((ready || ['PROBE_COMPLETE','RELEASED','COMPLETE'].includes(phase)) && !seen.has(key)) {
        seen.add(key);
        await page.screenshot({path:path.join(out,key+'.png'),fullPage:true});
        fs.writeFileSync(path.join(out,key+'.json'),JSON.stringify({captured_at:new Date().toISOString(),
          browser:browser.version(),url,kind:'Actual live command-output browser viewer',state},null,2));
        console.log('CAPTURED '+key);
      }
      if (recording && phase==='RELEASED' && state.run_id.endsWith('-01')) {
        const video = page.video();
        await context.close();
        await video.saveAs(path.join(out,'stage1-first-run-live.webm'));
        const original = await video.path();
        if (original!==path.join(out,'stage1-first-run-live.webm')) fs.unlinkSync(original);
        recording=false;
        context=await browser.newContext({viewport:{width:1920,height:1440}});
        page=await context.newPage();
        await page.goto(url,{waitUntil:'domcontentloaded'});
      }
      if (state.complete) break;
    }
    await page.waitForTimeout(500);
  }
  await context.close();await browser.close();
  if (![...seen].some(key=>key.endsWith('-03-COMPLETE'))) throw Error('Complete capture missing');
})().catch(e=>{console.error(e);process.exit(1)});
