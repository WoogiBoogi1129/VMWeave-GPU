from pathlib import Path
import csv,json,datetime,statistics
P=Path(__file__).resolve().parents[1]
def loadcsv(name):return list(csv.DictReader((P/'analysis'/name).open()))
def number(x):
 if x in [None,'']:return 'N/A'
 v=float(x)
 return f'{v:,.0f}' if abs(v)>=1000 else f'{v:,.3g}'
def generate():
 val=json.loads((P/'analysis/validation.json').read_text());ind=json.loads((P/'analysis/independent-verification.json').read_text());clean=json.loads((P/'evidence/cleanup-complete.json').read_text());restore=json.loads((P/'evidence/restoration.json').read_text())
 assert val['complete'] and ind['passed'] and clean['namespace_removed'] and clean['experiment_vms_removed']
 images=json.loads((P/'evidence/image-cleanup.json').read_text())
 assert json.loads((P/'analysis/metadata-verification.json').read_text())['passed']
 summary=loadcsv('summary.csv');blocks=loadcsv('blocks.csv');ratios=loadcsv('paired-ratios.csv')
 def row(m,id):return next(x for x in summary if x['mode']==m and int(x['id'])==id)
 def value(m,id,metric):return float(row(m,id)[metric+'_mean'])
 def entry(m,id,metric,ci=True):
  r=row(m,id);v=number(r[metric+'_mean']);return v+(' ['+number(r[metric+'_low95'])+', '+number(r[metric+'_high95'])+']' if ci and v!='N/A' else '')
 modes='NVFL';names={'N':'Native + HAMi-core','V':'VMWeave SHM','F':'Flyt TCP/RPC + MPS','L':'Lupine TCP'}
 fastest=min('VFL',key=lambda m:value(m,0,'p50_us'))
 def ratio(id,den,metric):return next(x for x in ratios if int(x['id'])==id and x['comparison']=='V/'+den and x['metric']==metric)
 rF=ratio(0,'F','p50_us');rL=ratio(0,'L','p50_us')
 lines=['# GPU 통신 성능 비교 실험 결과 보고서','',f'캠페인: `communication-20261117` · 보고서 생성(KST): {datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()}','',
 '## 보고 요지','',
 f'GPU 1에서 **4개 구성 × 16조건 × 5블록 = 320개 측정 구간**을 완료했다. 커널 누적 결과·최종 sequence 및 전송 버퍼 검산을 통과했고, 원시 지연 표본 {ind["latency_samples_checked"]:,}개를 별도 구현으로 다시 검증했다. 본 실험은 현재 고정 구성의 CUDA 호출 전달 경로를 비교하며, Fractional GPU 제어와 애플리케이션 벤치마크는 제외했다.','',
 '**해석 조건:** 마지막 블록 중 실험 외 서비스의 스케일 조정·재배치가 관측됐다. 벤치마크 설정과 GPU 1 예약은 고정했지만 공유 노드의 배경 부하는 동일하지 않았다. 아래 값은 이 조건에서의 관찰 결과이며, 신뢰구간만으로 배경 부하의 영향이나 순수 transport 인과 효과를 분리할 수 없다.','',
 f'원격 세 구성 중 최소 커널 완료 지연의 블록 p50 평균은 점추정상 **{names[fastest]}**가 가장 작았다. VMWeave/Flyt의 대응 블록 지연 비율은 **{number(rF["ratio"])}배**(95% CI {number(rF["low95"])}–{number(rF["high95"])})이고, VMWeave/Lupine은 **{number(rL["ratio"])}배**({number(rL["low95"])}–{number(rL["high95"])})였다. **VMWeave/Flyt의 구간은 1을 포함하므로 이 항목의 일관된 우열을 확정하지 않는다.** 지연 비율은 작을수록 VMWeave에 유리하다. 이 수치를 순수 SHM/TCP 전송 비용이나 전체 애플리케이션 속도비로 해석하지 않는다.','',
 f'64 MiB 전송에서 VMWeave의 유효 대역폭은 H2D **{entry("V",6,"GiB_s",False)} GiB/s**, D2H **{entry("V",12,"GiB_s",False)} GiB/s**로, 이번 고정 구성에서는 Flyt와 Lupine보다 낮았다. K=1000의 완료 커널 처리량은 Lupine **{entry("L",15,"kernels_s",False)} kernels/s**, VMWeave **{entry("V",15,"kernels_s",False)} kernels/s**였다. 이 차이에는 각 구현의 제출·처리 방식이 함께 포함된다.','',
 '대응 비율은 블록별 비율의 기하평균이다. 아래 표의 산술평균끼리 나눈 값과 다르며, 신뢰구간도 블록별 로그 비율에서 산출했다.','',
 '## 핵심 실측 결과','',
 '수치는 5개 블록 지표의 산술평균이며 대괄호는 블록 단위 95% t 신뢰구간이다. 호출 표본을 독립 반복으로 취급하지 않았다. 지연 표의 평균은 **블록별 p50의 평균**이며 전체 호출의 평균 지연과 구분한다.','',
 '| 지표 | Native | VMWeave | Flyt TCP | Lupine |','|---|---:|---:|---:|---:|']
 for label,id,metric in [('최소 커널+sync p50 (µs)',0,'p50_us'),('64 MiB H2D (GiB/s)',6,'GiB_s'),('64 MiB D2H (GiB/s)',12,'GiB_s'),('K=1000 커널 처리량 (kernels/s)',15,'kernels_s')]:lines.append('| '+label+' | '+' | '.join(entry(m,id,metric) for m in modes)+' |')
 lines+=['','Flyt의 최소 커널 p50은 블록별 '+', '.join(number(next(x for x in blocks if x['mode']=='F' and int(x['block'])==b and int(x['id'])==0)['p50_us']) for b in range(1,6))+' µs였다. 큰 블록 간 변동 때문에 산술 t 구간의 하한이 음수가 됐으며, 이는 음수 지연을 뜻하지 않고 해당 근사의 한계다. 원래 통계 방식을 유지해 하한을 숨기거나 다른 추정법으로 교체하지 않았다.','','![커널 완료 지연과 처리량](analysis/kernel-path.png)','','### 전송 크기별 유효 대역폭','','아래 값은 실제 완료한 논리 payload / 전체 경과 시간이다. wire byte, 압축 후 byte 또는 NIC 대역폭이 아니다. 한 번에 복사 하나를 제출하고 완료를 확인한다.','','| 방향·크기 | Native | VMWeave | Flyt TCP | Lupine |','|---|---:|---:|---:|---:|']
 sizes=['4 B','4 KiB','64 KiB','1 MiB','16 MiB','64 MiB']
 for d,direction in enumerate(['H2D','D2H']):
  for i,size in enumerate(sizes):lines.append('| '+direction+' '+size+' | '+' | '.join(entry(m,1+d*6+i,'GiB_s',False) for m in modes)+' |')
 lines+=['','단위: GiB/s. 모든 크기의 지연 p50·p95와 신뢰구간은 [전체 집계](analysis/summary.csv)에 수록했다.','','![전송 대역폭](analysis/transfer-bandwidth.png)','','![전송 완료 지연](analysis/transfer-latency.png)','','### 동기화 빈도와 연속 호출','','K=1은 최소 커널 측정을 재사용했다. K회 launch 후 sync 한 번의 완료 수로 처리량을 계산한다. batch 시간/K는 kernel당 환산 완료 비용이며 개별 요청 latency가 아니다.','','| K | Native kernels/s | VMWeave kernels/s | Flyt kernels/s | Lupine kernels/s |','|---:|---:|---:|---:|---:|']
 for id,K in [(0,1),(13,10),(14,100),(15,1000)]:lines.append('| '+str(K)+' | '+' | '.join(entry(m,id,'kernels_s',False) for m in modes)+' |')
 lines+=['','### p95와 CPU 보조 지표','',
 'p95는 해당 세션에 표본이 1,000개 이상일 때만 계산했다. 표본 부족으로 창을 연장하거나 반복 수를 늘리지 않았다. K>1의 p95 표본 단위는 batch다.','','| 구성 | p95 산출 가능 구간 / 80 | CPU 산출 가능 구간 / 80 |','|---|---:|---:|']
 for m in modes:
  rr=[r for r in blocks if r['mode']==m];lines.append(f'| {names[m]} | {sum(bool(r["p95_us"]) for r in rr)} | {sum(bool(r["path_cpu_s"]) for r in rr)} |')
 lines+=['',
 'CPU는 같은 창의 누적 Pod cgroup counter를 1초 간격으로 읽고, Guest/Host 시각 차이를 보정한 경계에서 보간했다. 원격 경로는 QEMU와 서버·MPS가 포함된 서버 Pod를 합산하고 Guest CPU를 다시 더하지 않았다. 공용 daemon/IRQ와 별도 Flyt manager·Mongo는 합산하지 않았다. 양 끝을 감싸는 표본이 없으면 N/A다. 경계 보간 오차가 있는 보조 지표이며 정확한 호출 내부 CPU 시간은 아니다. [블록 원값](analysis/blocks.csv)에 core-seconds/operation과 core-seconds/GiB를 함께 제공한다.','',
 '## 비교 구성 및 측정 경계','',
 '| 항목 | 고정 구성 |','|---|---|',
 '| GPU | index 1, `GPU-772181af-05a4-0c24-de59-8487bd37c142`, RTX PRO 6000 Blackwell Server Edition |',
 '| 예약 | 기존 HAMi DRA, cores=100·memory=97887Mi 전체 capacity. 단순 장치 노출로 예약을 대체하지 않음 |',
 '| 운영 기반 | gpu-4, Kubernetes 1.37.0, driver 580.173.02, HAMi 2.11.0. 별도 DRA의 실제 HAMi-core library hash도 확인 |',
 '| Guest | 공통 Ubuntu 24.04 이미지, 4 vCPU·16 GiB, GPU passthrough 없음. 세션마다 새 부팅 |',
 '| CPU | QEMU/Native 8–11, server 12–15. NUMA 0 CPU 사용. 메모리 strict binding·CPU 독점 예약 없음 |',
 '| V | v0.5.11 공개 digest, 현재 운영 Guest와 같은 bulk-copy=0. Worker 기본 옵션 유지 |',
 '| F | legacy TCP/ONC RPC 호환성 수정 빌드, MPS 188 SM. Flyt SHM과 구분 |',
 '| L | 공식 Lupine v2.1.0, CUDA 12.9.1 이미지, source `4fe630ac2a3dd15e67dd1804c80bbb60db1439de`. HAMi 통합 서버 예약 성능이 아닌 단독 실행 백엔드 |',
 '| 공통 연산 | 동일 C 소스, CUDA 12.8.1 runtime. N/L 동일 실행 파일. V/F는 연결 라이브러리·setup adapter만 다름 |',
 '| 커널 형식 | 동일 PTX 소스. N/V/L은 PTX, F는 ptxas sm_120 cubin과 ELF table 위치 보정. setup/JIT는 시간 밖 |',
 '| 제출 | 한 client·default stream, pageable host buffer, 고정 seed 20261117, 같은 버퍼 재사용 |',
 '| 반복 | 조건당 30초, warmup 최소 10초 및 10회, 독립 5블록. 순서와 source/binary hash 사전 고정 |',
 '| 시간 | client CLOCK_MONOTONIC, launch/copy 직전부터 sync 완료까지. 마지막 batch를 끝낸 실제 창 길이로 처리량 계산 |','',
 '작은 커널은 누적 정수 값과 sequence를 갱신한다. 최종 검산으로 launch 수와 결과를 대조했다. 전송은 6개 크기 각각 전체 바이트를 대조했고 D2H는 마지막 측정 결과를 재복사로 덮지 않고 검사했다. 모든 중간 버퍼를 저장하거나 매 호출 데이터 전체를 검산했다고 주장하지 않는다. 타이머 오버헤드는 기록하되 자동 차감하지 않았다.','',
 'GPU UUID·Claim·실제 장치 수, Guest 장치 미노출, 로드 라이브러리, TCP 연결/SHM attachment와 서버 활동을 확인했다. Flyt의 `shm_enabled`는 빌드 기능 flag이며 실제 세션은 `socktype=1`, `connection_is_local=0`과 연결 로그로 TCP 사용을 확인했다.','',
 '첫 Native 세션은 보조 수집기의 별도 client 체크섬 스냅샷이 없다. 사전 고정·검증한 Native 바이너리 해시와 해당 세션의 실제 CUDA/HAMi 로드 해시는 보존돼 있으며, 누락된 시점의 자료를 사후 생성하지 않았다. [실행 증거 검증](analysis/metadata-verification.json)','',
 '## 준비 중 변경 및 해석 한계','',
 '- HAMi 차트의 CUDA 13.3.1 Lupine 후보는 현재 native libcuda에 없는 심볼로 시작하지 못했다. 공식 CUDA 12.9.1 호환 쌍으로 변경했으며 호스트 드라이버는 변경하지 않았다. 따라서 차트 기본 이미지 그대로의 성능이라고 표시하지 않는다.',
 '- V의 cubin 미지원에 따라 같은 PTX를 사용했다. F는 legacy ELF 요구에 맞춘 cubin이다. 변환은 측정 밖에서 수행하며 GPU machine code 동일성을 주장하지 않는다.',
 '- 실제 호출 경로에는 interception, 직렬화, broker, server dispatch, 내부 staging과 MPS/HAMi 처리가 포함된다. 차이 전체를 transport 하나의 인과 효과로 분해하지 않았다.',
 '- V는 현재 운영 옵션인 bulk-copy=0이다. 다른 VMWeave 옵션이나 최대 async 대역폭으로 일반화하지 않는다.',
 '- TCP도 동일 노드의 VM 가상 NIC/CNI를 사용한다. 물리 NIC를 거치는 노드 간 Remote GPU 결과가 아니다.',
 '- CPU·DRAM·PCIe 등은 다른 학생 작업과 공유한다. 실제 CPU affinity/NUMA 배치와 GPU 상태를 남겼으며 메모리 NUMA 배치를 완전히 통제하지 않았다.',
 '- 5블록 CI는 제한된 반복에서의 변동을 보여주는 지표다. 다중 비교 보정이나 일반 서비스 SLA 검증을 수행하지 않았다.',
 '- 애플리케이션 학습/추론, Fractional 공유, 격리성, 스케줄링, pinned/multistream, transport 튜닝은 수행하지 않았다.','',
 '준비 실패·재시도는 [결정 기록](protocol/preparation-decisions.md)과 `results/pilot-*`에 보존했다. 예비 결과는 320개 본 측정 통계에 합치지 않았다.','',
 '### 마지막 블록의 공유 환경 변화','',
 '최종 대조에서 `aap-lifecycle`/`aap-serving` Deployment 6개의 spec 변화와 기존 Pod 4개의 UID 소멸이 관측돼 자동 후처리가 중단됐다. managedFields에는 11월 18일 13:38–13:44 KST경 서비스 스케일 조정·재배치에 해당하는 기록이 있으며 블록 5와 겹친다. 이 시간은 필드 관리 기록의 시각으로, 사람이나 정확한 변경 주체를 식별하는 감사 로그는 아니다. 실험에서는 해당 서비스를 수정하거나 복원하지 않았다.','',
 'GPU 1 점유·CUDA 검산·고정 이미지/소스 검증과 공유 노드 환경의 동일성은 구분했다. 320개 완료 구간을 그대로 주 분석에 포함하고, 사후 기술 비교로 블록 1–4와 블록 5의 대응 비율을 [환경 변화 민감도 표](analysis/environment-sensitivity.csv)에 제시했다. 이 표에는 새로운 신뢰구간이나 유의성 판정을 추가하지 않았다. 환경 변화가 관측됐다는 이유로 측정값을 선택적으로 제거하거나 추가 GPU 실험을 수행하지 않았다.','',
 '최소 커널 지연의 VMWeave/Flyt 비율은 블록 1–4의 기하평균 1.39배, 블록 5에서는 5.65배였다. VMWeave/Lupine은 각각 0.671배와 0.644배였다. 이는 일부 비교의 블록 간 변동이 크다는 관측이며, 환경 변화가 그 차이를 일으켰다는 인과 증명은 아니다.','',
 '[관측된 설정 변화](evidence/external-configuration-changes.json) · [환경 조건 평가](analysis/environment-quality.json)','',
 '### 실행 중단과 재개','',
 '11월 18일 02:00 KST 이후 실행이 중단됐고, 약 10시간 뒤 재개 점검에서 확인했다. 정확한 OS 종료 신호는 기록되지 않았다. GPU 실행 프로세스는 없었지만 관측 프로세스와 Native Pod·GPU 예약은 남아 있어 재개 시 먼저 정리했다. 이 공백 동안 GPU 예약이 자동 해제되지 않았다는 운영상 한계가 있었다.','',
 '완료한 블록 1–3은 보존했다. 시간 간격이 큰 결과를 같은 대응 블록에 섞지 않도록 블록 4의 첫 시도 전체를 제외하고, 동일한 소스·바이너리·조건·순서로 블록 4부터 재실행했다. 제외한 Flyt 16구간과 Native 8개 기록, 추가 RESULT 없는 Native raw 파일을 [중단 시도 원자료](results/excluded-interruption-20261118/)에 보존했다. 최종 통계에는 완성된 5블록의 320구간만 포함했다.','',
 '재개 후에는 대화 연결과 분리된 임시 user systemd 서비스가 실행을 관리하고, 종료 후처리에서도 실험 할당을 회수하도록 보완했다. 재개 직전 기존 Pod 125개의 UID·재시작·Ready 상태, 공용 설정과 HAMi values는 변하지 않았다. [중단·복구 기록](evidence/interruption-recovery.json) · [재개 전 환경 대조](evidence/resume-preservation.json)','',
 '## 복원 및 자원 정리','',
 f'- 실험 전 Running Pod {restore["preexisting_running_pods"]}개의 UID/재시작 대조: 변경 {len(restore["pod_changes"])}건.',
 f'- 기존 설정·spec 대조: 변경 {len(restore["configuration_changes"])}건. HAMi Helm values 동일: {restore["hami_values_unchanged"]}.',
 f'- 실험 GPU 프로세스 잔류 없음: {restore["experiment_gpu_processes_absent"]}. GPU 1 관측 시 유휴: {restore["gpu1_compute_idle"]}. 전용 namespace 및 VM 삭제: {clean["namespace_removed"] and clean["experiment_vms_removed"]}.',
 '- 실험 VM·Worker·Lupine/Flyt 서버·manager/Mongo·MPS·Claim·실험용 PVC/PV 및 디스크를 정리했다. 기존 학생 VM/Pod와 과거 Draining 채널은 정리 대상에서 제외했다.',
 f'- 이번에 추가한 CRI 이미지 캐시 7개 중 삭제 또는 이미 부재 {sum(x["status"] in ["removed","already_absent"] for x in images)}개, 참조 중이라 유지 {sum(x["status"]=="retained_referenced" for x in images)}개, 삭제 실패 {sum(x["status"]=="remove_failed" for x in images)}개다. 기존 rootless Flyt 이미지 캐시는 보존했다. [이미지 정리 내역](evidence/image-cleanup.json)',
 '- 공용 HAMi/DRA/Operator 설정 변경 없이 기존 등록 경로를 사용했다. 이전에 완료한 HAMi 2.11.0 업그레이드는 유지했다.',
 '- 임시 OCI 복사본·Guest 다운로드 이미지·실험용 SSH 키·Mongo 설정도 제거했다. [작업 공간 정리 내역](evidence/private-workspace-cleanup.json)',
 '- 상태·UID·설정 대조는 요청 단위 서비스 SLA의 무중단 증명과 구분한다.',
 '', '[복원 대조](evidence/restoration.json) · [정리 완료](evidence/cleanup-complete.json) · [독립 수치 검증](analysis/independent-verification.json)','',
 '## 원자료와 재현','',
 '[5블록 전체 값](analysis/blocks.csv) · [집계/CI](analysis/summary.csv) · [대응 V/F·V/L 비율](analysis/paired-ratios.csv) · [Native 대비 추가 시간/대역폭 유지율](analysis/native-deltas.csv) · [고정 프로토콜](protocol/frozen.json)','',
 '빌드 정의, 공통 측정기, 원시 gzip 표본, 이미지 digest·라이브러리 hash와 실행 경로 증거를 같은 디렉터리에 보존했다. `README.md`의 재분석 명령은 GPU 재실행 없이 사용한다. 비밀키와 원본 운영 스냅샷은 공개하지 않았다.','',
 '공식 참고: [HAMi Remote GPU](https://project-hami.io/docs/userguide/nvidia-device/remote-gpu), [Lupine 소스](https://github.com/lupinemachines/lupine/tree/4fe630ac2a3dd15e67dd1804c80bbb60db1439de), [VMWeave v0.5.11](../../deploy/releases/v0.5.11.json).','']
 (P/'REPORT.md').write_text('\n'.join(lines))
 readme=(P/'README.md').read_text();readme=readme.replace('현재 상태: 본 측정 진행 중. 최종 결과는 측정·검증·정리 완료 후 `REPORT.md`에 작성한다. 예비 실행 수치를 본 측정 결과로 사용하지 않는다.','현재 상태: **320개 본 측정 구간·독립 검증·자원 정리 완료**. [결과 보고서](REPORT.md)를 참고한다. 예비 실행은 본 측정 통계에 포함하지 않았다.')
 (P/'README.md').write_text(readme)
 print('REPORT_WRITTEN')
if __name__=='__main__':generate()
