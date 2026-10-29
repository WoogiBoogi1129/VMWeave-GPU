# 내부 Kubernetes SGEMM 처리량 비교

2026-10-29 KST. 사용자가 행렬곱 작업을 선택하여 수행하는 새 실험이다.
기존 별도 Operator(`vmweave-nested-system`)의 유지된 VM·Channel을 사용한다.
중앙 Operator 재실습, Device Plugin 구현, native/passthrough 비교는 포함하지 않는다.

- 동일 Worker VM·GPU·quota(compute 50%, VRAM 2048 MiB), 동일 실행 바이너리·Guest 라이브러리.
- FP32 cuBLAS SGEMM, column-major, alpha=1/beta=0, pedantic math mode 2; N=1024,4096.
- 크기별 Guest 직접 실행/Pod 실행 3쌍. 순서는 Guest→Pod, Pod→Guest, Guest→Pod.
- 각 프로세스에서 최소 3 GEMM 및 2초 warm-up, 각 측정 구간 최소 5초·3 GEMM.
- resident_compute: 입력 GPU 상주, SGEMM+완료 동기화의 Guest 단조 시계 경과 시간.
- transfer_inclusive: 매 작업 A/B H2D+SGEMM+sync+C D2H. 할당·초기화·검산·프로세스/Pod 시작 제외.
- GFLOP/s=2*N^3*완료 GEMM 수/초/1e9. 순수 GPU kernel event 시간 또는 GPU 이론 성능이 아니다.
- 세 구간 후 모든 출력의 finite 검사 및 결정적인 32개 위치 FP64 CPU 참조 검산.
- Pod CPU limit 미설정(Guest 직접 실행과 CPU quota 차이 방지), 메모리 limit 1 GiB.
  Pod UID/GID 1000:실제 vmweave 그룹, broker socket read-only, 비특권 설정 유지.
- 실행마다 호스트 GPU PID·CUDA 자식 대응, 이전 세션 회수, source/binary/library/image hash 수집.
- 외부 workload와 GPU 상태를 기록한다. 동시 GPU 부하나 재배포가 나타나면 고립된 성능 차이로 해석하지 않는다.
- broker/Channel/VM 실패 시 측정을 중단하고 증거 보존. 공유 서비스 변경이나 GPU reset 없이 종료한다.
- 과거 20261028 증거를 수정하지 않는다. 반복 3쌍으로 보편적 성능·유의성을 주장하지 않는다.
