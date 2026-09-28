from pathlib import Path
import gzip,hashlib,json,shutil
b=Path('.local/overhead-20260929');o=Path('experiments/evidence/results/2026-09-29-overhead/preflight');manifest=[]
for run in sorted((b/'runs').glob('*preflight*')):
 d=o/run.name;d.mkdir(parents=True,exist_ok=True)
 for f in run.iterdir():
  if not f.is_file() or (f.name not in ['stdout.txt','stderr.txt','cell.log','cell-start.log','client-manager.log','resource-seed.txt','guest-dependencies.txt','cleanup.json','admission-failure.json'] and f.suffix not in ['.stdout','.stderr']):continue
  data=f.read_bytes();target=d/(f.name+'.gz' if len(data)>2_000_000 else f.name)
  if len(data)>2_000_000:
   with target.open('wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as g:g.write(data)
  else:target.write_bytes(data)
  manifest.append({'session':run.name,'file':str(target.relative_to(o)),'original_bytes':len(data),'original_sha256':hashlib.sha256(data).hexdigest()})
(o/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(o/'README.md').write_text('''# 준비 실행 기록

이 자료는 성능 집계에 포함하지 않는다. 정식 측정은 상위 `r1-*` 이후 디렉터리다.

| 준비 | 관측 / 조치 |
|---|---|
| N | 1초 기능 예비 실행 5종 통과 |
| S 첫 실행 | 첫 query 통과 후 새 프로세스 재접속 실패. 세션 종료 후 재사용하지 않도록 단일 프로세스 batch로 수정 |
| S2 | 단일 프로세스 7조건 검산 통과 |
| T / T2 | CDI 완전한 장치 이름, 이미지 보존, MPS 런타임 볼륨 복원 |
| T3 | SHM 전용 namespace의 입장 제한 확인; plain TCP VM 전용 namespace 사용 |
| T4 | `cricket-client.so`의 SONAME `libcudart.so.12` 연결 누락 수정 |
| T5 | 옛 manager가 종료된 GPU Cell을 재선택. 독립 T 세션마다 실험 전용 manager 초기화 |
| T6 | cubin ELF 전체가 전달되지 않음. section table을 EOF로 옮기는 준비 과정 추가 |
| T7 | module handle 오류. 저장소의 module/function/stream 매핑 패치 3개 적용 |
| T8 | legacy `cuCtxSynchronize`가 원격 API가 아닌 로컬 fallback임을 확인. 모든 경로의 완료 API를 `cudaDeviceSynchronize`로 통일 |
| T9 | TCP 경로 7조건, 전체 출력 검산 모두 PASS; 정식 측정 진입 |

T9는 `socktype=1`(TCP), `connection_is_local=0`을 실제 클라이언트에서 확인했다.
서버는 GPU UUID 및 MPS affinity 지원/188 SM 적용을 기록했다.
실패 로그도 보존하며, 큰 반복 오류 로그는 내용 그대로 gzip 압축했다.
`manifest.json`의 해시는 압축 전 원본 바이트를 기준으로 한다.
''')
