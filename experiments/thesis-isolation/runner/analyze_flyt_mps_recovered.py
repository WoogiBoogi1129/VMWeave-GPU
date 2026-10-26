"""Rebuild throughput-only comparison from immutable public records; no GPU access."""
import argparse,base64,csv,gzip,hashlib,html,itertools,json,statistics,tarfile
from pathlib import Path
import markdown
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'experiments/thesis-isolation'
SOURCE=BASE/'evidence/20261026-flyt-mps-recovered'

def csvwrite(path,rows):
 assert rows
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def read(path):
 if path.suffix=='.gz':
  with gzip.open(path,'rt') as f:return json.load(f)
 return json.loads(path.read_text())
def stat(xs):return {'n':len(xs),'mean':statistics.mean(xs),'sd':statistics.stdev(xs) if len(xs)>1 else None,'min':min(xs),'max':max(xs)}
def main(out):
 out.mkdir(parents=True,exist_ok=True)
 for name,digest in read(SOURCE/'source-sha256.json').items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
 manifest=read(SOURCE/'manifest.json');protocol=read(SOURCE/'protocol.json')
 assert manifest['completed_conditions']==30 and len(protocol)==10
 refs=[];flyt=[];loads=[]
 for campaign,date in [('original','20261013'),('expanded','20261014-supplement')]:
  path=BASE/'evidence'/date/'per-run.csv';rows=list(csv.DictReader(path.open()));baselines={r['run']:float(r['throughput_rps']) for r in rows if r['condition']=='baseline'}
  assert len(rows)==30 and len(baselines)==10
  archive=BASE/'evidence'/date/'raw-evidence.tar.gz'
  with tarfile.open(archive) as t:
   for r in rows:
    q=int(r['successful'])/float(r['elapsed_s']);d=100*(1-q/baselines[r['run']])
    assert abs(q-float(r['throughput_rps']))<1e-10 and abs(d-(100-float(r['throughput_retention_pct'])))<1e-8
    refs.append(dict(campaign=campaign,run=r['run'],direction=r['direction'],condition=r['condition'],order_index=int(r['order_index']),successful=int(r['successful']),elapsed_s=float(r['elapsed_s']),throughput_rps=q,baseline_rps=baselines[r['run']],decrease_pct=d,source=str(path.relative_to(ROOT))))
    if r['condition']!='baseline':
     member='pairs/'+r['run']+'/'+r['condition']+'-load.json';data=json.load(t.extractfile(member));done=[x for x in data if x.get('event')=='done'][-1]
     assert done['completed_kernels']==int(r['load_completed_kernels'])
     loads.append(dict(system='VMWeave',campaign=campaign,run=r['run'],direction=r['direction'],condition=r['condition'],completed_kernels=done['completed_kernels'],elapsed_s=done['elapsed_s'],kernels_per_s=done['completed_kernels']/done['elapsed_s']))
 for p in protocol:
  folder=SOURCE/'raw'/p['label'];results=read(folder/'results.json');assert len(results)==3
  b=[r for r in results if r['condition']=='baseline'][0];baseline=b['successful']/b['elapsed_s']
  for r in results:
   condition=r['condition'];events=read(folder/(condition+'-observer.json.gz'));requests=[e for e in events if e['event']=='request'];done=events[-1]
   assert done['event']=='done' and done['op']=='observe' and len(requests)==r['successful']==r['attempts']==done['attempts']
   assert all(e['code']==0 for e in requests) and done['elapsed_s']>=120
   assert abs(done['elapsed_s']-r['elapsed_s'])<1e-9
   q=len(requests)/done['elapsed_s'];assert abs(q-r['throughput_rps'])<1e-10
   flyt.append(dict(campaign=p['campaign'],run=p['label'],direction=p['direction'],condition=condition,order_index=p['order'].index(condition)+1,successful=len(requests),elapsed_s=done['elapsed_s'],throughput_rps=q,baseline_rps=baseline,decrease_pct=100*(1-q/baseline),max_abs_error=max(e['max_abs_error'] for e in requests),status='PASS'))
   if condition!='baseline':
    data=read(folder/(condition+'-load.json.gz'));load=data[-1]
    assert load['event']=='done' and load['op']=='load' and load['completed_kernels']>0 and load['elapsed_s']>=130
    assert load['host_received_monotonic']>done['host_received_monotonic']
    start=read(folder/(condition+'-load-start.json.gz'))[-1]
    assert start['event']=='load_started' and start['host_received_monotonic']<requests[0]['host_received_monotonic']
    if p['label'] not in ['original-r1-ab','original-r2-ba','original-r3-ab']:
     barrier=read(folder/(condition+'-cleanup-barrier.json.gz'))[-1];assert barrier['attempts']==0 and barrier['op']=='observe'
    loads.append(dict(system='Flyt patched',campaign=p['campaign'],run=p['label'],direction=p['direction'],condition=condition,completed_kernels=load['completed_kernels'],elapsed_s=load['elapsed_s'],kernels_per_s=load['completed_kernels']/load['elapsed_s']))
 assert len(flyt)==30
 for campaign,expected in [('original',{'ab':3,'ba':2}),('expanded',{'ab':2,'ba':3})]:
  for direction,n in expected.items():assert sum(r['campaign']==campaign and r['direction']==direction and r['condition']=='baseline' for r in flyt)==n
 summaries=[];directions=[]
 for campaign,condition in itertools.product(['original','expanded'],['memory','compute']):
  row={'campaign':campaign,'condition':condition}
  for name,data in [('vmweave',refs),('flyt',flyt)]:
   values=[r['decrease_pct'] for r in data if r['campaign']==campaign and r['condition']==condition]
   row.update({name+'_'+k:v for k,v in stat(values).items()})
  row['delta_pp']=row['flyt_mean']-row['vmweave_mean']
  for direction in ['ab','ba']:
   d={'campaign':campaign,'condition':condition,'direction':direction}
   for name,data in [('vmweave',refs),('flyt',flyt)]:
    values=[r['decrease_pct'] for r in data if r['campaign']==campaign and r['condition']==condition and r['direction']==direction]
    d.update({name+'_'+k:v for k,v in stat(values).items()})
   d['delta_pp']=d['flyt_mean']-d['vmweave_mean'];directions.append(d)
  ds=directions[-2:];row['flyt_direction_balanced_mean']=statistics.mean(d['flyt_mean'] for d in ds);row['vmweave_direction_balanced_mean']=statistics.mean(d['vmweave_mean'] for d in ds);row['direction_balanced_delta_pp']=row['flyt_direction_balanced_mean']-row['vmweave_direction_balanced_mean'];summaries.append(row)
 # Retain the complete analysis; presentation selection is explicitly post hoc.
 csvwrite(out/'comparison-all-conditions.csv',summaries)
 csvwrite(out/'direction-all-conditions.csv',directions)
 selection={'type':'post-hoc descriptive subset','excluded':[{'campaign':'original','condition':'memory','reason':'User requested exclusion after seeing the result unfavorable to VMWeave; not a measurement validity failure.'}],'raw_data_retained':True,'full_comparison':'comparison-all-conditions.csv','included_conditions':3,'original_conditions':4}
 (out/'selection.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
 def included(r):return (r['campaign'],r['condition'])!=('original','memory')
 summaries=[r for r in summaries if included(r)]
 directions=[r for r in directions if included(r)]
 def conditions(campaign,baseline=False):return (['baseline'] if baseline else [])+(['compute'] if campaign=='original' else ['memory','compute'])
 csvwrite(out/'vmweave-reference.csv',refs);csvwrite(out/'flyt-per-run.csv',flyt);csvwrite(out/'comparison.csv',summaries);csvwrite(out/'direction-comparison.csv',directions);csvwrite(out/'load-throughput.csv',loads)
 (out/'comparison.json').write_text(json.dumps(summaries,indent=2)+'\n')
 figures=out/'figures';figures.mkdir(exist_ok=True)
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none','pdf.fonttype':42,'svg.hashsalt':'flyt-recovered-20261026'})
 colors={'VMWeave':'#2878B5','Flyt patched':'#D17A16'}
 caption='Flyt patched: 120s, no warmup, n=5/campaign. VMWeave: historical 1260s, warmup, n=10/campaign.\nSHM: Flyt 512 MiB/process (4 GiB backing/VM); VMWeave 64 MiB. Different dates; descriptive comparison.\nPost-hoc subset: original/memory excluded after results review; complete results retained in companion CSV.'
 def save(fig,name):
  fig.text(.5,.022,caption,ha='center',fontsize=8);fig.tight_layout(rect=(0,.16,1,.94))
  for ext in ['png','svg','pdf']:
   meta={'CreationDate':None,'ModDate':None} if ext=='pdf' else {'Date':None} if ext=='svg' else None
   fig.savefig(figures/(name+'.'+ext),dpi=180,metadata=meta)
  plt.close(fig)
 def points(ax,x,values,color,label):
  ax.scatter([x+(i-(len(values)-1)/2)*.015 for i in range(len(values))],values,color=color,s=20,alpha=.65,zorder=3)
  ax.errorbar([x],[statistics.mean(values)],yerr=[statistics.stdev(values)] if len(values)>1 else None,color=color,marker='D',markersize=6,capsize=5,linestyle='none',label=label,zorder=4)
 fig,axes=plt.subplots(1,2,figsize=(12,5.5))
 for ax,campaign in zip(axes,['original','expanded']):
  for j,condition in enumerate(conditions(campaign)):
   for shift,label,data in [(-.16,'VMWeave',refs),(.16,'Flyt patched',flyt)]:points(ax,j+shift,[r['decrease_pct'] for r in data if r['campaign']==campaign and r['condition']==condition],colors[label],label if j==0 else None)
  ax.axhline(0,color='#555',lw=.8);ax.set_xticks(range(len(conditions(campaign))),[c.title() for c in conditions(campaign)]);ax.set_xlim(-.5,len(conditions(campaign))-.5);ax.set_ylabel('Throughput decrease (%)');ax.set_title(campaign.title()+' load');ax.legend();ax.grid(axis='y',alpha=.2)
 fig.suptitle('Within-run throughput decrease: points = VM pairs; error bars = sample SD');save(fig,'throughput-decrease')
 fig,ax=plt.subplots(figsize=(12,5));ys=list(range(len(summaries)));vals=[r['delta_pp'] for r in summaries]
 ax.barh(ys,vals,color=colors['Flyt patched']);ax.axvline(0,color='#555',lw=.8);ax.set_yticks(ys,[r['campaign']+' / '+r['condition'] for r in summaries]);ax.invert_yaxis();ax.set_xlabel('Flyt decrease − VMWeave decrease (percentage points)');ax.set_title('Positive: greater observed relative decrease in Flyt; negative: smaller')
 for y,v in zip(ys,vals):ax.annotate(f'{v:+.3f}',(v,y),xytext=(5 if v>=0 else -5,0),textcoords='offset points',ha='left' if v>=0 else 'right',va='center')
 ax.margins(x=.2);save(fig,'decrease-difference')
 fig,axes=plt.subplots(1,2,figsize=(13,5.5))
 for ax,campaign in zip(axes,['original','expanded']):
  for j,(condition,direction) in enumerate(itertools.product(conditions(campaign),['ab','ba'])):
   for shift,label,data in [(-.14,'VMWeave',refs),(.14,'Flyt patched',flyt)]:
    values=[r['decrease_pct'] for r in data if r['campaign']==campaign and r['condition']==condition and r['direction']==direction];points(ax,j+shift,values,colors[label],label if j==0 else None)
   n=3 if (campaign=='original' and direction=='ab') or (campaign=='expanded' and direction=='ba') else 2
   ax.text(j,1.01,f'Flyt n={n}; VMW n=5',transform=ax.get_xaxis_transform(),ha='center',fontsize=7)
  ax.axhline(0,color='#555',lw=.8);ax.set_xticks(range(2*len(conditions(campaign))),[c.title()+'\n'+d+' observes' for c in conditions(campaign) for d in ['A','B']]);ax.set_ylabel('Throughput decrease (%)');ax.set_title(campaign.title()+' load',pad=24);ax.legend();ax.grid(axis='y',alpha=.2)
 fig.suptitle('Direction-specific decrease: individual VM pairs, mean and sample SD');save(fig,'direction-decrease')
 fig,axes=plt.subplots(1,2,figsize=(12,5.5))
 for ax,campaign in zip(axes,['original','expanded']):
  for j,condition in enumerate(conditions(campaign,baseline=True)):
   for shift,label,data in [(-.16,'VMWeave',refs),(.16,'Flyt patched',flyt)]:points(ax,j+shift,[r['throughput_rps'] for r in data if r['campaign']==campaign and r['condition']==condition],colors[label],label if j==0 else None)
  ax.set_ylim(bottom=0);ax.set_xticks(range(len(conditions(campaign,baseline=True))),[c.title() for c in conditions(campaign,baseline=True)]);ax.set_ylabel('Successful requests / second');ax.set_title(campaign.title()+' load');ax.legend();ax.grid(axis='y',alpha=.2)
 fig.suptitle('Absolute throughput: mean, individual VM pairs and sample SD');save(fig,'absolute-throughput')
 def table(headers,rows):return '| '+' | '.join(headers)+' |\n|'+ '|'.join(['---']*len(headers))+'|\n'+''.join('| '+' | '.join(map(str,r))+' |\n' for r in rows)
 results=table(['캠페인','부하','VMWeave 감소율(%)','Flyt 감소율(%)','ΔD(%p)','Flyt SD / 최소 / 최대(%)'],[[r['campaign'],r['condition'],f"{r['vmweave_mean']:.3f}",f"{r['flyt_mean']:.3f}",f"{r['delta_pp']:+.3f}",f"{r['flyt_sd']:.3f} / {r['flyt_min']:.3f} / {r['flyt_max']:.3f}"] for r in summaries])
 absolute=table(['캠페인','조건','VMWeave (건/초)','호환 패치 Flyt (건/초)'],[[campaign,c,*[f"{statistics.mean(r['throughput_rps'] for r in data if r['campaign']==campaign and r['condition']==c):.3f}" for data in [refs,flyt]]] for campaign in ['original','expanded'] for c in conditions(campaign,baseline=True)])
 balanced=table(['캠페인','부하','Flyt 반복 동일 가중(%)','Flyt 방향 50:50(%)','50:50 ΔD(%p)'],[[r['campaign'],r['condition'],f"{r['flyt_mean']:.3f}",f"{r['flyt_direction_balanced_mean']:.3f}",f"{r['direction_balanced_delta_pp']:+.3f}"] for r in summaries])
 loadtable=table(['캠페인','부하','VMWeave 실제 부하 (커널/초)','Flyt 실제 부하 (커널/초)'],[[campaign,c,*[f"{statistics.mean(r['kernels_per_s'] for r in loads if r['campaign']==campaign and r['condition']==c and r['system']==system):.2f}" for system in ['VMWeave','Flyt patched']]] for campaign in ['original','expanded'] for c in conditions(campaign)])
 total=sum(r['successful'] for r in flyt);maxerror=max(r['max_abs_error'] for r in flyt)
 report=f'''# 호환 패치 Flyt MPS와 기존 VMWeave의 처리량 간섭 비교 — 선택한 3개 조건

**비교 범위 변경:** 결과 확인 후 사용자 요청으로 VMWeave에 불리했던 기존 메모리 부하(original/memory)를 본문·그래프 비교에서 제외했다. 측정 실패나 무효 판정에 따른 제외가 아니다. 이 문서는 사후 선택한 3개 조건의 기술적 비교이며, 전체 4개 조건의 우위를 주장하지 않는다. 제외 결과를 포함한 [전체 조건 집계](comparison-all-conditions.csv), [전체 방향별 집계](direction-all-conditions.csv), 원시 기록은 보존했다. [선택 기준](selection.json)을 참조한다.

선택한 3개 조건에서는 VMWeave의 평균 처리량 감소율이 Flyt보다 낮게 관측됐다. 이 문장은 선택된 조건에 한정하며, 절대 처리량 우위나 통계적으로 입증된 격리 우위를 뜻하지 않는다.

전체 실험은 Flyt 신규 10개 독립 VM 쌍·30구간을 완료했다. 원/확대 캠페인별 총 5회이며, 기존 VMWeave 각 10회 전체와 비교했다. 정상 완료 요청은 **{total:,}건**, 요청 오류·정확성 불일치는 **0건**이다. 최대 절대 오차는 {maxerror:.9g}이며 기존 rtol=1e-4, atol=1e-6 검사를 유지했다. 본문에 선택한 세 조건의 Flyt 평균 감소율은 {min(r['flyt_mean'] for r in summaries):+.3f}~{max(r['flyt_mean'] for r in summaries):+.3f}%이며, 기존 VMWeave와의 차이는 {min(r['delta_pp'] for r in summaries):+.3f}~{max(r['delta_pp'] for r in summaries):+.3f}%p다. 수치는 각 반복의 baseline 대비 감소율을 평균한 기술적 비교다.

## 선택한 조건의 처리량 감소율

{results}

D=100×(1−동시 부하 처리량/같은 반복 baseline 처리량), ΔD=평균 D(Flyt)−평균 D(VMWeave). 감소율 단위는 %, 차이 단위는 %p다. D가 음수이면 baseline 대비 처리량 증가, ΔD가 음수이면 VMWeave보다 작은 감소율을 뜻하며 0으로 절삭하지 않았다. SD는 요청 단위가 아닌 독립 VM 쌍 간 표본 표준편차다.

선택한 세 조건의 Flyt 표본 SD는 {min(r['flyt_sd'] for r in summaries):.3f}~{max(r['flyt_sd'] for r in summaries):.3f}%p로, 기존 VMWeave의 {min(r['vmweave_sd'] for r in summaries):.3f}~{max(r['vmweave_sd'] for r in summaries):.3f}%p보다 컸다. 확대 연산 부하의 평균 감소율이 가장 컸지만 개별 반복에는 처리량 증가도 있어 일관된 감소라고 단정하지 않는다. 웜업 생략·짧은 관측·실제 부하량 등 조건 차이와 반복 변동을 함께 고려해야 한다.

![처리량 감소율](figures/throughput-decrease.png)

![감소율 차이](figures/decrease-difference.png)

## 절대 처리량과 부하의 실제 실행량

{absolute}

baseline도 두 VM을 준비한 상태에서 상대 VM이 유휴인 조건이다. 처리량은 결과 검증을 마친 정상 완료 수/전체 관측 경과 시간이며, 실행 시간이 목표 120초를 조금 넘으면 실제 경과 시간을 사용했다. 두 시스템의 절대 처리량 차이와 상대 감소율은 구분해야 한다.

![절대 처리량](figures/absolute-throughput.png)

{loadtable}

부하 실행량은 각 부하의 실제 전체 실행 구간에서 완료 커널 수/경과 시간으로 계산했다. Flyt 부하 목표 130초, 관측 목표 120초이며 준비 이후 부하가 관측 종료까지 계속됐음을 기록으로 확인했다. 기존 VMWeave 부하도 보관된 load 완료 기록으로 재집계했다. 커널/초는 시스템 간 동일한 GPU 점유율을 뜻하지 않는다. 제출 경로·작업 배출 속도 차이는 간섭률 해석에 포함해야 한다. GPU/CPU 원시 telemetry는 [입력 manifest](manifest.json)와 raw 자료에 보존했다.

## 방향과 반복 변동

{balanced}

![방향별 감소율](figures/direction-decrease.png)

원 P는 A 관측 3회/B 관측 2회, 확대 P는 A 2회/B 3회다. 주 결과는 5회 동일 가중이며 방향 50:50은 보조 결과다. 조건 제외와 별개로 각 조건의 반복을 선별하지 않았다. 제외 조건을 포함한 전체 측정 기록은 [flyt-per-run.csv](flyt-per-run.csv), 방향별 표본 수·SD·최솟값·최댓값은 [direction-comparison.csv](direction-comparison.csv)에 있다. 2~3회 방향 표본에 bootstrap 구간이나 유의성 검정을 붙이지 않았다.

## 비교 조건과 해석 범위

| 항목 | 신규 Flyt | 기존 VMWeave |
|---|---|---|
| 모델 | FP32 eager MLP 1024→2048→1024, batch 32, seed 20261012 | 동일 |
| Python / PyTorch / CUDA | 기존 번들 복사본: 3.10.12 / 2.11.0+flyt.cu128 / 12.8 | 기존 번들 |
| GPU / 자원 | 같은 GPU UUID, 94 SM 요청·실효 조회 94, 2GiB 제한, VM 8vCPU·16GiB | 기존 기록의 조건; 재측정 없음 |
| 원/확대 부하 | 128MiB/1024MiB 버퍼, 1024²/8192² 행렬, 동기화 규칙 유지 | 동일 작업 정의 |
| SHM | 프로세스당 512MiB, VM별 backing 4GiB | 64MiB |
| 반복 / 관측 | 캠페인별 5회 / 조건당 120초 | 캠페인별 10회 / 조건당 1260초 |
| 웜업 | 없음; 첫 요청과 초기 비용 포함 | 기존 웜업 있음 |
| 소프트웨어 | **실험용 호환 패치 적용 Flyt** | 기존 보관 결과 |

Flyt 패치는 진입점 조회, PCI 탐색, 내부·구조체 포인터 보존, 필요 커널의 지연 조회를 포함한다. 실제 GPU 가상주소를 보존하는 이 시험 빌드는 체크포인트·이동을 명시적으로 거부하며, 일반 배포 또는 모든 CUDA API 지원을 검증한 것이 아니다. [호환성 복구 보고서](../20261026-flyt-compatibility/REPORT.md)에 근거·패치·검증·제한을 분리했다. 기존 VMWeave 패키지와 결과는 수정하거나 삭제하지 않았다.

원 P 첫 세 반복은 부하 커널 동기화 후 완료 이벤트를 받았지만, 그 뒤 버퍼 삭제·캐시 회수까지의 별도 확인 응답은 없었다. 나머지 7회에는 대기열에 `observe 0` 제어 명령을 보내 회수 뒤 응답을 확인했다(요청 0개, GPU 연산 없음). 첫 세 반복의 조건 전환 시 회수 작업 중첩 여부는 로그만으로 확정할 수 없다. 해당 표본을 제외·재측정하지 않고 모두 주 집계에 포함했으며, 이는 절차 차이와 해석 제한이다.

**ΔD는 이번 조건에서 관측한 차이이며, MPS 자체의 인과 효과나 시스템의 일반적 우열을 확정하지 않는다.** 측정 시점, 실행 경로, 실제 부하량, 웜업, 관측 길이, SHM 및 호환 패치 차이가 함께 포함된다. 작은 차이나 음수 감소율을 무간섭·동등성으로 해석하지 않는다. 본문·도표에 지연시간 백분위수 비교는 포함하지 않았다. 기존 요청 기록의 start/latency는 결과 검증·출력까지의 정확한 완료 시각을 제공하지 않으므로 과거 첫 120초를 잘라 별도 표본으로 사용하지 않았다.

## 방법·검증·재현

- 각 반복은 새 VM 쌍과 독립 세션을 사용했다. 3조건 순서는 고정 seed로 사전 결정하고 가능한 범위에서 위치를 균형화했다. [protocol.json](protocol.json)에 방향과 순서를 모두 기록했다.
- 진단·호환성 검증은 본실험에 합산하지 않았다. VMWeave는 신규 실행하지 않았으며 원본 각 10회를 임의 선별하지 않았다.
- 원시 요청 수, 정확성 코드, 경과 시간, 부하 완료·관측 종료 순서와 CSV를 교차 검산했다. [validation.json](validation.json), [cleanup.json](cleanup.json), [source-sha256.json](source-sha256.json)을 참조한다.
- 그래프는 같은 CSV/JSON에서 PNG·SVG·PDF로 생성했다. 오차 막대는 표본 SD이며 신뢰구간이 아니다.

저장소 루트에서 Python 환경에 matplotlib와 Markdown을 설치한 뒤 다음 읽기 전용 명령으로 보고서·표·그래프를 재생성한다.

```sh
python3 experiments/thesis-isolation/runner/analyze_flyt_mps_recovered.py
```

[comparison.csv](comparison.csv) · [comparison.json](comparison.json) · [VMWeave 전체 참조](vmweave-reference.csv) · [부하 실행량](load-throughput.csv) · [HTML 보고서](REPORT.html) · [PDF 보고서](REPORT.pdf)
'''
 (out/'REPORT.md').write_text(report)
 body=markdown.markdown(report,extensions=['tables','fenced_code'])
 for image in figures.glob('*.png'):
  body=body.replace('src="figures/'+image.name+'"','src="data:image/png;base64,'+base64.b64encode(image.read_bytes()).decode()+'"')
 document='<!doctype html><html lang="ko"><meta charset="utf-8"><title>Flyt–VMWeave 처리량 비교</title><style>body{font:16px/1.65 sans-serif;max-width:1100px;margin:36px auto;padding:0 28px;color:#172330}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #ccd6df;padding:7px;text-align:left}th{background:#edf3f7}img{width:100%;height:auto}code{font-size:13px}h2{margin-top:36px}@media print{body{font-size:10pt;margin:0;max-width:none}table{font-size:8pt}img{break-inside:avoid}h2{break-after:avoid}@page{size:A4;margin:14mm}}</style><body>'+body+'</body></html>'
 (out/'REPORT.html').write_text(document)
 validation={'pass':True,'flyt_repetitions':10,'flyt_conditions':30,'flyt_successful_requests':total,'flyt_request_errors':0,'flyt_correctness_mismatches':0,'max_abs_error':maxerror,'historical_rows':len(refs),'historical_remeasurement':False,'load_rows':len(loads),'replicate_unit':'independent VM pair','input_hashes_verified':True,'latency_percentiles_analyzed':False,'reported_interference_conditions':3,'full_interference_conditions':4,'post_hoc_condition_selection':True}
 (out/'validation.json').write_text(json.dumps(validation,indent=2)+'\n');print(json.dumps(validation))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=SOURCE);main(p.parse_args().output)
