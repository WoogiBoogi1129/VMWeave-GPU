// Capture real localhost Grafana and command-output pages. No fabricated frames.
const {chromium}=require('playwright');
const fs=require('fs');const path=require('path');
const crypto=require('crypto');
(async()=>{
 const out=path.resolve(process.argv[2]);fs.mkdirSync(out,{recursive:true});
 const seconds=Number(process.argv[3]||0),label=process.argv[4]||'live';
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1920,height:1200},recordVideo:seconds?{dir:out,size:{width:1920,height:1200}}:undefined});
 const page=await context.newPage();
 const config=process.argv[5]?JSON.parse(fs.readFileSync(process.argv[5],'utf8')):{};
 const url=new URL('http://127.0.0.1:3300/d/flyt-campaign/flyt-campaign');
 url.searchParams.set('orgId','1');url.searchParams.set('from',config.from_ms||'now-15m');url.searchParams.set('to',config.to_ms||'now');
 url.searchParams.set('refresh',config.from_ms?'':'5s');
 for(const run of config.run_ids||[])url.searchParams.append('var-run',run);
 const grafana=url.toString();
 await page.goto(grafana,{waitUntil:'networkidle'});await page.waitForTimeout(4000);
 await page.screenshot({path:path.join(out,label+'-grafana.png'),fullPage:true});
 const dashboard=await(await page.request.get('http://127.0.0.1:3300/api/dashboards/uid/flyt-campaign')).json();
 const info={captured_at:new Date().toISOString(),url:grafana,browser:browser.version(),kind:config.from_ms?'Actual Grafana historical query / 본 측정 사후 조회':'Actual Grafana live view / 실시간 관측',config,
  dashboard_sha256:crypto.createHash('sha256').update(JSON.stringify(dashboard.dashboard)).digest('hex'),errors:[]};
 fs.writeFileSync(path.join(out,label+'-dashboard.json'),JSON.stringify(dashboard.dashboard,null,2));
 if(seconds){await page.waitForTimeout(seconds*1000);await page.screenshot({path:path.join(out,label+'-grafana-end.png'),fullPage:true});}
 if(!config.from_ms){
  const terminal=await context.newPage();await terminal.goto('http://127.0.0.1:9899',{waitUntil:'networkidle'});await terminal.waitForTimeout(1500);
  await terminal.screenshot({path:path.join(out,label+'-output.png'),fullPage:true});
  const response=await terminal.request.get('http://127.0.0.1:9899/snapshot');fs.writeFileSync(path.join(out,label+'-snapshot.json'),await response.text());
 }
 fs.writeFileSync(path.join(out,label+'-capture.json'),JSON.stringify(info,null,2));
 await context.close();await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
