const {chromium}=require('../../.local/reorganization/browser/node_modules/playwright');
const fs=require('fs'),path=require('path');
(async()=>{
 const out=path.resolve(process.argv[2]);fs.mkdirSync(out,{recursive:true});
 const from=Number(process.argv[3]),to=Number(process.argv[4]);
 const filter=(process.argv[5]||'').split(',').filter(Boolean).map(x=>'&var-run='+encodeURIComponent(x)).join('');
 const url=`http://127.0.0.1:13096/d/vmweave-vram-20261016?from=${from}&to=${to}&timezone=Asia%2FSeoul&refresh=${filter}`;
 const browser=await chromium.launch({headless:true,executablePath:'/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1920,height:1250}});const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.goto(url,{waitUntil:'networkidle',timeout:60000});await page.getByText('GPU physical memory (NVML, MiB resolution)',{exact:true}).waitFor();await page.waitForTimeout(3000);
 const text=await page.locator('body').innerText();
 if(text.includes('Datasource was not found')||text.includes('An error occurred'))throw Error(text);
 await page.screenshot({path:path.join(out,'grafana.png'),fullPage:true});fs.writeFileSync(path.join(out,'grafana.txt'),text);
 fs.writeFileSync(path.join(out,'capture.json'),JSON.stringify({url,from,to,captured_utc:new Date().toISOString(),kind:'Actual Grafana screenshot of Prometheus-collected experiment metrics; post-run absolute time window',browser_errors:errors},null,2));await browser.close();
})();
