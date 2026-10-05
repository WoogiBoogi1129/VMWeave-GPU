# CPU/GPU 시계열

- `cpu.jsonl`(공개 시 `.xz`): 호스트 epoch UTC, run ID, Pod UID별 cgroup v2
  누적 CPU `usage_usec`와 메모리 사용량. 약 1초 간격으로 수집한다.
- `gpu.csv`(공개 시 `.xz`): 실험 대상 GPU UUID 한 개의 nvidia-smi 약 1초 표본.
  timestamp는 호스트 현지 시각 **Asia/Seoul (UTC+09:00)**이다.
  GPU 이용률·사용 메모리·전력·SM clock·온도를 포함한다.
- Guest stdout의 epoch와 호스트 epoch는 각 실행의 `clock-map.json` 및
  `identity.json`의 offset으로 연결한다. NTP는 Guest에서 측정 전에 비활성화했다.
  SHM 내부 구간은 이 epoch 보정으로 계산하지 않고 각 프로세스의 monotonic 시간을 사용한다.

CPU 집계는 측정 창 안에 있는 첫/마지막 표본의 누적 사용량 차이로 계산한다.
커버리지를 함께 보고하며, 구간의 양 끝까지 완전히 보간한 값이 아니다.
T는 launcher+cell+manager, S는 launcher+Worker의 중복 없는 Pod cgroup 합이다.
노드 전체 서비스 CPU를 포함한 값은 아니다.

GPU 로그는 첫 시각부터 종료까지의 연속 수집을 목표로 했으며, 기록 이전 예비 실행을
소급해서 채우지 않았다. 정식 주 비교와 후속 실험은 수집 시작 이후 실행했다.
GPU 시계열은 상태·부하 확인 자료이며 순수 DMA 시간이나 PCIe 대역폭 계측을 대체하지 않는다.

압축 파일은 `xz -dc 파일.xz`로 읽을 수 있다. 상위 디렉터리의 `archive-manifest.json`과
`SHA256SUMS`에서 압축 전후 해시를 확인한다.
