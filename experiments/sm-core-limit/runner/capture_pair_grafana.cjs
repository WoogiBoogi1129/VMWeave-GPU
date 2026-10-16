const {chromium}=require('../../../.local/reorganization/browser/node_modules/playwright');
const fs=require('fs'),path=require('path');
(async()=>{
 const out=path.resolve(process.argv[2]);fs.mkdirSync(out,{recursive:true});
 const from=Number(process.argv[3]),to=Number(process.argv[4]);
 const url=`http://127.0.0.1:13097/d/vmweave-sm-pair-20261016?from=${from}&to=${to}&timezone=Asia%2FSeoul&refresh=`;
 const browser=await chromium.launch({headless:true,executablePath:'/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',args:['--no-sandbox']});
 try {
 const page=await browser.newPage({viewport:{width:1920,height:1200}});const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.goto(url,{waitUntil:'networkidle',timeout:60000});await page.getByText('Worker SM utilization (HAMi, percent)',{exact:true}).waitFor();await page.waitForTimeout(3500);
 const text=await page.locator('body').innerText();
 if(text.includes('Datasource was not found')||text.includes('An error occurred')||text.includes('No data'))throw Error(text);
 await page.screenshot({path:path.join(out,'grafana.png'),fullPage:true});fs.writeFileSync(path.join(out,'grafana.txt'),text);
 fs.writeFileSync(path.join(out,'capture.json'),JSON.stringify({url,from,to,captured_utc:new Date().toISOString(),kind:'Actual Grafana screenshot of Prometheus-collected concurrent VM experiment metrics',browser_errors:errors},null,2));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
