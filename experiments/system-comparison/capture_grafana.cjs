// Capture actual Grafana responses after measurement. No generated screenshots.
const {chromium}=require('playwright');const fs=require('fs'),path=require('path');
(async()=>{
 const root=path.resolve(process.argv[2]),base=path.resolve(process.argv[3]),stage=process.argv[4]||'all';
 const mon=JSON.parse(fs.readFileSync(path.join(base,'monitor.json'))),out=path.join(root,'captures');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});const context=await browser.newContext({viewport:{width:1920,height:1900}});const page=await context.newPage();const meta=[];
 try{for(const name of fs.readdirSync(path.join(root,'runs')).sort()){
  if(!/^sc-r[15]-/.test(name))continue;

  const dir=path.join(root,'runs',name);if(!fs.existsSync(path.join(dir,'cleanup.json')))continue;
  const events=fs.readFileSync(path.join(dir,'stdout.jsonl'),'utf8').split('\n').filter(x=>x.startsWith('{')).map(x=>JSON.parse(x)).filter(x=>x.utc);
  const id=JSON.parse(fs.readFileSync(path.join(dir,'identity.json'))),offset=id.clock_offset||0;
  const from=Math.floor((Math.min(...events.map(x=>x.utc))-offset-5)*1000),to=Math.ceil((Math.max(...events.map(x=>x.utc))-offset+5)*1000);
  const url=mon.grafana+`/d/vmweave-system-comparison/vmweave-system-comparison?from=${from}&to=${to}&timezone=utc&refresh=`;
  await page.goto(url,{waitUntil:'networkidle',timeout:60000});await page.getByText('GPU utilization — whole device',{exact:true}).waitFor();await page.waitForTimeout(1500);
  const text=await page.locator('body').innerText();if(text.includes('An error occurred')||text.includes('Datasource was not found'))throw Error(text);
  await page.screenshot({path:path.join(out,name+'-grafana.png'),fullPage:true});fs.writeFileSync(path.join(out,name+'-grafana.txt'),text);
  meta.push({run:name,url,from,to,captured_utc:new Date().toISOString(),kind:'Actual Grafana with retained Prometheus data; post-run inspection'});
 }}finally{fs.writeFileSync(path.join(out,'grafana-'+stage+'-metadata.json'),JSON.stringify({browser:browser.version(),viewport:{width:1920,height:1900},captures:meta},null,2)+'\n');await context.close();await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
