// Capture the unmodified official asciinema player rendering a real PTY recording.
// PNGs and WebM are replay exports; the original .cast remains authoritative.
const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
(async()=>{
  const root=path.resolve(process.argv[2]);
  const url=process.argv[3] || 'http://127.0.0.1:9901/';
  const out=path.join(root,'terminal-captures');fs.mkdirSync(out,{recursive:true});
  const excerpts=path.join(root,'slide-excerpts');fs.mkdirSync(excerpts,{recursive:true});
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const context=await browser.newContext({viewport:{width:1920,height:1080}});
  const page=await context.newPage();await page.goto(url);
  await page.waitForFunction(()=>window.player && window.player.getDuration()>0);
  await page.evaluate(async()=>{await window.player.play();window.player.pause();});
  const chapters=JSON.parse(fs.readFileSync(path.join(root,'chapters.json')));
  const captures=[];
  for(const chapter of chapters){
    await page.evaluate(async seconds=>{window.player.pause();await window.player.seek(seconds);},chapter.seconds);
    await page.waitForTimeout(250);
    await page.locator('.ap-player').screenshot({path:path.join(out,chapter.name+'.png')});
    const height={'03-settings':490,'05-gpu-pid':460,'06-result':435}[chapter.name];
    if(height){
      const box=await page.locator('.ap-player').boundingBox();
      await page.screenshot({path:path.join(excerpts,chapter.name+'.png'),clip:{...box,height}});
    }
    captures.push({...chapter,kind:'Official asciinema player replay of actual PTY output'});
  }
  const duration=await page.evaluate(()=>window.player.getDuration());
  await context.close();
  const recording=await browser.newContext({viewport:{width:1920,height:1080},recordVideo:{dir:out,size:{width:1920,height:1080}}});
  const movie=await recording.newPage();await movie.goto(url);
  await movie.waitForFunction(()=>window.player && window.player.getDuration()>0);
  await movie.evaluate(()=>{window.playbackEnded=false;window.player.addEventListener('ended',()=>window.playbackEnded=true);return window.player.play();});
  await movie.waitForFunction(()=>window.playbackEnded,{},{timeout:Math.ceil(duration*1000)+30000});
  const video=movie.video();await recording.close();
  const target=path.join(out,'stage1-terminal-replay.webm');await video.saveAs(target);
  const original=await video.path();if(original!==target)fs.unlinkSync(original);
  fs.writeFileSync(path.join(out,'metadata.json'),JSON.stringify({browser:browser.version(),
    player:'asciinema-player 3.6.3; upstream distribution unchanged',
    source:'../stage1.cast',recordingDurationSeconds:duration,playbackSpeed:1,idleTimeLimit:null,captures},null,2)+'\n');
  await browser.close();console.log('Captured '+captures.length+' terminal frames and full 1x playback.');
})().catch(e=>{console.error(e);process.exit(1)});
