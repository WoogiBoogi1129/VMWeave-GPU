# 전송 및 애플리케이션 처리량 추가 실험

2026-10-30 KST. 기존 SGEMM은 재측정하지 않는다. 유지 중인 Worker VM과
동일 broker/Channel/GPU를 사용하며 제품 코드·Operator·quota를 변경하지 않는다.
독립 프로세스는 조건별 3쌍, 순서는 Guest→Pod / Pod→Guest / Guest→Pod다.

## 전송

- H2D와 D2H, pageable host memory, 4 KiB / 1 MiB / 16 MiB / 64 MiB.
- CUDA 할당 및 관측 barrier 이후 크기·방향별 3회 warm-up.
- 각 구간 최소 2초 및 20회, 매 복사 후 device synchronize로 완료 확인.
- API 반환과 복사+동기화 완료 시간을 각각 CLOCK_MONOTONIC으로 기록.
- 유효 대역폭 = 논리 전송 bytes × 완료 횟수 / 구간 경과시간 / 10^9 GB/s.
- 초기화·할당·warm-up·검산은 제외. 각 구간 후 전체 bytes 비교.
- broker/SHM/외부 Worker를 포함한 경로 지표이며 순수 PCIe 대역폭이 아니다.

## 애플리케이션

- 기존 10/26 Rodinia의 동결된 NW 및 SRAD 바이너리와 Native 출력 해시를 재사용.
- NW: 길이 2048, penalty 10의 서열 정렬. SRAD: 2048×2048, ROI 0..127,
  lambda 0.5, diffusion 2회인 합성 이미지 처리.
- 프로세스마다 전체 작업 2회 warm-up 뒤 2회 측정. 독립 프로세스는 3개씩.
- 측정 경계: 입력 CPU 준비 이후 GPU 할당·전송·알고리즘·결과 회수·동기화.
  초기 CUDA 설정·입력 생성·출력 덤프·최종 해제·Pod 시작은 제외.
- 작업 처리량 = 2 / 두 작업 완료시간 합. 이미지/s 또는 정렬 작업/s.
  전체 서비스·AI 모델 추론/학습 처리량을 주장하지 않는다.
- 관측용 preload는 최초 cudaMalloc 뒤 barrier만 추가한다. 기존 알고리즘과
  제품 Guest 라이브러리는 그대로 사용한다. Native 참조와 warm-up 포함 출력 전체 해시 비교.

## 관측·보존

각 프로세스 전후 세션 idle, 실행 중 외부 GPU PID와 해당 Worker 자식 대응 확인.
별도 GPU monitor, 전후 controller/spec/Pod/Channel/Node inventory 보존.
실패 시 raw 증거 보존 후 중단하며 성공 표본으로 대체하지 않는다.
새 이미지·작업명·결과 경로를 사용하고 기존 증거 해시를 유지한다.
원본 자료·계산기·CSV·그래프·보고서를 함께 공개한다.
