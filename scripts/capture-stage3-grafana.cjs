// Screenshots of upstream Grafana querying the actual Prometheus database. No video.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
(async()=>{
 const root=path.resolve(process.argv[2]),out=path.join(root,'grafana-captures');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});const metadata=[];
 try {
  const context=await browser.newContext({viewport:{width:1920,height:1300}});const page=await context.newPage();
  for(let n=1;n<=3;n++)for(const kind of ['memory','progress']){
   const window=JSON.parse(fs.readFileSync(path.join(root,'pair-'+n,'plot-window.json')));
   const url='http://127.0.0.1:3301/d/stage3-'+kind+'/stage3-'+kind+'?orgId=1&var-pair=pair-'+n+'&from='+Math.floor(window.start*1000)+'&to='+Math.ceil(window.end*1000)+'&timezone=utc&kiosk';
   await page.goto(url,{waitUntil:'networkidle'});await page.waitForTimeout(3500);
   const text=await page.locator('body').innerText();
   if(text.includes('No data')||text.includes('Data source not found'))throw Error('Grafana has missing data: '+url);
   const name='pair-'+n+'-'+kind;await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});
   fs.writeFileSync(path.join(out,name+'-page.txt'),text+'\n');metadata.push({name,url,window,screenshot_utc:new Date().toISOString(),kind:'Actual Grafana, post-run absolute-time query of measured data'});
  }
  fs.writeFileSync(path.join(out,'metadata.json'),JSON.stringify({recording:false,video:false,browser:browser.version(),captures:metadata},null,2)+'\n');await context.close();
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
