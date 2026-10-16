"""Render saved experiment evidence and capture it with local Chromium; no GPU rerun."""
import hashlib, html, json, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
P=Path(__file__).resolve().parent
R=P/'results/20261016T053951Z'
S=R/'runs/torch-smoke-1016053953'
F=P/'results/20261016T053702Z/runs/torch-smoke-1016053705'
O=P/'evidence/20261016';O.mkdir(parents=True,exist_ok=True)
read=[]
def text(p):
    read.append(p);return p.read_text()
def obj(p):return json.loads(text(p))
r=obj(S/'result.json');live=obj(S/'channel-live.json');released=obj(S/'channel-released.json');clean=obj(S/'cleanup.json')
rows=[json.loads(l) for l in text(S/'train.jsonl').splitlines()]
gpu=text(S/'gpu-live.txt');after=text(R/'gpu-after.txt');failure=text(F/'stderr.txt')
assert r['status']=='PASS' and live['status']['phase']=='Ready' and released['status']['phase']=='Released' and clean['released']
stamp=datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')
css='''*{box-sizing:border-box}body{margin:0;background:#edf2f7;color:#172b45;font-family:"Noto Sans KR",sans-serif}main{width:1280px;margin:auto;padding:40px}h1{font-size:34px;margin:10px 0}h2{font-size:23px;margin:0 0 16px}p{line-height:1.7}small,.muted{color:#53677f}.top{color:#2266ac;font-size:15px;letter-spacing:2px}.cards{display:flex;gap:16px;margin:24px 0}.card,section{background:white;border:1px solid #d8e2ec;border-radius:14px;padding:24px}.card{flex:1}.value{font-size:28px;font-weight:700;margin-top:8px}.pass{color:#087c60}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}section{margin-bottom:20px}td,th{text-align:left;padding:10px;border-bottom:1px solid #e6ebf0;font-size:15px}table{width:100%;border-collapse:collapse}pre{background:#13243b;color:#e6f1ff;padding:20px;border-radius:9px;white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.65 monospace}.note{background:#fff6e7;border-left:5px solid #d99026;padding:16px 20px}footer{font-size:13px;color:#53677f}'''
def page(title,body):return f'<!doctype html><html lang="ko"><meta charset="utf-8"><title>{title}</title><style>{css}</style><main><div class="top">VMWEAVE · GPU VALIDATION RECORD</div><h1>{title}</h1><p class="muted">실험일 2026-10-16 KST · 저장된 원본 로그의 사후 렌더링 · 실시간 콘솔 캡처 아님</p>{body}<footer>캡처 생성: {stamp}<br>출처: experiments/pytorch-smoke/results/20261016T053951Z · 원본 해시: raw-sha256.json</footer></main></html>'
loss_rows=''.join(f'<tr><td>{x["step"]}</td><td>{x["loss"]:.8f}</td></tr>' for x in rows if x.get('device')=='cuda')
body=f'''<div class="cards"><div class="card">최종 판정<div class="value pass">PASS</div></div><div class="card">CUDA 학습<div class="value">100 steps</div></div><div class="card">Loss 감소<div class="value">{(1-r['final_loss']/r['initial_loss'])*100:.2f}%</div></div><div class="card">가중치 최대 절대오차<div class="value">{r['max_parameter_abs_error']:.2e}</div></div></div>
<div class="grid"><section><h2>학습 조건과 결과</h2><table><tr><td>모델</td><td>Linear 32 → 64 · ReLU → Linear 8</td></tr><tr><td>학습</td><td>FP32 eager · MSE · SGD lr=0.1</td></tr><tr><td>데이터</td><td>합성 회귀 · batch 128 · seed 20261016</td></tr><tr><td>Loss</td><td>{r['initial_loss']:.8f} → {r['final_loss']:.8f}</td></tr><tr><td>CPU 비교</td><td>매 step loss · 최종 gradient / parameter 통과</td></tr><tr><td>허용오차</td><td>rtol=1e-4 · atol=1e-6</td></tr><tr><td>학습 시간</td><td>{r['training_seconds']:.2f}초 (성능 비교 목적 아님)</td></tr></table></section>
<section><h2>VM부터 GPU 회수까지</h2><table><tr><td>VM 생성</td><td>torch-smoke-1016053953</td></tr><tr><td>SSH 접속</td><td>10.85.0.233 · 실행 및 결과 수집 성공</td></tr><tr><td>GPU</td><td>RTX PRO 6000 Blackwell Server Edition</td></tr><tr><td>실행 경로</td><td>Guest → SHM → Worker → GPU</td></tr><tr><td>실행 중</td><td>Channel Ready · Worker PID 3270766</td></tr><tr><td>GPU 메모리</td><td>실행 시 724 MiB → 회수 후 0 MiB</td></tr><tr><td>회수 상태</td><td>Released · 검증 VMI / Worker 삭제</td></tr></table></section></div>
<section><h2>CUDA 학습 loss — 저장된 진행 로그</h2><table><tr><th>Step</th><th>MSE loss</th></tr>{loss_rows}</table><p class="muted">진행 로그는 10 step 간격 및 마지막 step을 기록. 정확성 검사는 100개 전체 loss를 비교.</p></section>
<div class="note"><b>호환성 제한 및 실패 기록</b><p>첫 실행은 CUDA loss.item()에서 SHM CUDA 오류로 실패했다. 명시적 동기화 후 loss.detach().cpu().item()으로 읽는 재실행은 통과했다. PyTorch {html.escape(r['torch'])} 호환 빌드, CUDA {r['cuda']}, cuBLASLt 비활성화 조건이다. 공식 PyTorch 무수정 실행이나 전체 모델 호환성을 의미하지 않는다.</p></div><p></p>'''
(O/'results-screen.html').write_text(page('PyTorch 학습 검증 결과',body))
gpu_target='\n'.join(l for l in gpu.splitlines() if 'gpu_uuid' in l or 'GPU-7d708c42' in l)
raw=f'''<section><h2>1. 최종 실행 결과 — result.json 원문</h2><pre>{html.escape(json.dumps(r,ensure_ascii=False,indent=2))}</pre></section><section><h2>2. 지정 GPU 프로세스 및 회수 후 상태 — 로그 발췌</h2><pre>{html.escape(gpu_target+'\n\n'+after)}</pre><p>다른 GPU의 프로세스 행은 화면에서 제외했다. 원본 파일은 그대로 보존.</p></section><section><h2>3. Channel 수명주기 — JSON 필드 발췌</h2><pre>{html.escape(json.dumps({'name':live['metadata']['name'],'uid':live['metadata']['uid'],'live_phase':live['status']['phase'],'final_phase':released['status']['phase'],'release_reason':released['status']['reason'],'cleanup':clean},indent=2))}</pre></section><section><h2>4. 첫 실행 실패 — stderr.txt 원문</h2><pre>{html.escape(failure)}</pre></section>'''
(O/'raw-evidence-screen.html').write_text(page('실행 원본 증거와 첫 실패',raw))
chrome=Path('/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome')
for name,height in [('results-screen',1710),('raw-evidence-screen',2250)]:
    subprocess.run([str(chrome),'--headless','--no-sandbox','--disable-gpu','--hide-scrollbars','--no-pdf-header-footer','--run-all-compositor-stages-before-draw','--virtual-time-budget=3000',f'--window-size=1280,{height}',f'--screenshot={O/name}.png',(O/f'{name}.html').as_uri()],check=True,capture_output=True)
(O/'raw-sha256.json').write_text(json.dumps({str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(read))},indent=2)+'\n')
(O/'capture.json').write_text(json.dumps({'captured_at_kst':stamp,'method':'Chromium headless screenshot of HTML rendered from saved experiment logs','live_console_capture':False,'browser':subprocess.check_output([str(chrome),'--version'],text=True).strip(),'screenshots':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.glob('*.png')}},indent=2)+'\n')
print(O)
