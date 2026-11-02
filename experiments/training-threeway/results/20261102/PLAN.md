# PyTorch 학습 기반 통신·연산 통합 성능 비교

사전 계획: 2026-11-02 KST. 정식 측정 전에 작성.

비교군은 GPU Passthrough VM, Flyt SHM, 최적화된 VMWeave v0.5.5다.
동일 GPU 0 (`GPU-772181af-05a4-0c24-de59-8487bd37c142`, PCI 0000:40:00.0)를
순차 사용한다. 기존 GPU 1의 VM, GPU 2/3의 서비스는 유지한다.
대상 GPU에 다른 compute client/할당이 있으면 진행하지 않는다.

## 조건과 측정 경계

- small 32→64→8, large 2048→4096→1024 FP32 Linear/ReLU/Linear, MSE, SGD.
- batch 32/1024 × resident/h2d = 8조건. batch 1024의 roundtrip 2조건 추가.
- h2d: 매 step 입력·목표값을 사전 할당 GPU 버퍼에 동기 복사.
- roundtrip: h2d에 모델 출력 CPU 회수를 추가. 일반 학습의 필수 동작이 아닌 양방향 진단.
- 모든 방식에서 sync 간격 16 step. 데이터 생성·최초 할당·warmup·검산 제외.
- 동일 seed와 CPU 생성 초기 가중치/입력. TF32 off, 1 CPU thread, eager SGD.
- 출력 검산과 finite 검사, final sync 뒤 완료된 step만 계수.
- resident도 호출 전달·동기화를 포함하며 순수 GPU kernel 시간이 아니다.
- 옵션 ON/OFF, 추론, 자원 제어·장애 격리는 이번 범위 밖이다.

## 실행 단계

1. 보존된 호환 Flyt/공개 VMWeave 바이너리의 신원과 설정 확인.
2. 모든 조건 1/10 step loss/output/전체 gradient/weight 비교. small CPU 참조 추가.
   rtol=1e-4, atol=1e-6. 지원 실패는 기록하고 우열을 보고 조건을 대체하지 않는다.
3. 대표 조건 독립 5개 예비 블록. 정식 step 수·반복 수를 protocol.json으로 확정.
4. 정식 10개 블록을 출발안으로 삼는다. 시스템 순서를 균형화하고 조건 순서를 회전한다.
   세 시스템의 같은 조건은 동일 step 수. 예비 데이터는 정식 통계에서 제외.
5. 10조건 × 3방식 × 10블록 = 300회 목표. 실제 유효 조건/횟수를 보고한다.

## 환경과 증거

VM 8vCPU/16GiB, remoting compute100/VRAM8192MiB, GPU 로컬 NUMA CPU 배치.
Guest CPU 예산을 맞추되 원격 backend CPU는 추가 비용으로 별도 계상한다.
Worker/Broker/애플리케이션의 공개 최적화 옵션과 캐시를 명시적으로 고정한다.
GPU 클록·온도·다른 GPU/호스트 서비스 변화는 관측하고, 통제하지 못한 요인은 제한으로 쓴다.
프로비저닝·초기화는 성능 타이머 밖이다. 독립 프로세스/세션과 VM 재사용을 구분한다.

주 지표: samples/s, step/전체 완료시간, paired log-ratio 기하평균과 블록 단위 95% CI.
보조: CPU seconds/step, GPU/호스트 메모리와 GPU 활동, 논리 전송량.
짧은 지연/실제 원격 호출 수 상세 계측은 별도 진단에서만 수행한다.
통신·연산 overlap 때문에 시간 차이를 순수 memcpy/IPC 시간으로 단정하지 않는다.
기술 실패·준비 실패·중단은 원자료로 남긴다. 느린 결과는 제거하지 않는다.
정확성/설정 불일치 시 정식 측정을 중단해 원인을 기록한다.

## 안전한 전환·종료

시험 namespace와 새 PV/PVC/VM만 생성한다. VFIO 전환 전에 GPU0의 compute client와
IOMMU group, 열린 장치 FD를 확인한다. 대상 GPU의 드라이버 전환에 필요한 모니터링
변경은 사전 스냅샷과 복구 검증을 동반하며 기존 애플리케이션은 재시작하지 않는다.
모든 시험 세션을 종료하고 GPU0 NVIDIA 바인딩·설정 복원 및 기존 VM/서비스 상태를 검증한다.
기존 미커밋 파일과 이전 원시 결과는 수정하지 않는다. 이번 산출물만 main에 반영한다.

## 사전 검증 후 실행기 수정 — 정식 성능 측정 전

Flyt의 9번째 프로세스 초기화에서 mmap EINVAL/MAP_FAILED 후 프로세스가 종료됐다.
각 프로세스에 512MiB를 순차 배정하는 manager와 4GiB BAR의 조합에서 8개를 초과했다.
출력의 offset은 signed32로 인쇄되어 4GiB에서 0으로 보이지만 실제 offset은 u64다.
학습 연산 전 초기화 실패이며 해당 실패 로그를 `qualification/initial/flyt/small-1024-roundtrip`에 보존한다.
바이너리나 backing 크기를 변경하지 않고, 정식·예비 측정은 **세 방식 모두 최대 5조건마다
새 VMI/백엔드로 재시작**한다. 각 조건은 여전히 새 학습 프로세스이며, 성능 타이머는
초기화·재기동을 제외한다. 블록 내 하위 방문들은 독립 블록으로 늘려 세지 않는다.
Flyt의 미완료 2조건은 새 방문에서 qualification/recovery로 검증한다.

## 보조 전송 정확성 검증 계획 — 정식 측정 전 확정

성능 루프는 고정 입력을 반복하므로, 입력 값이 바뀌는 H2D도 별도 검증한다.
정식 campaign 종료 후 별도 새 세션에서 small(batch32) / large(batch1024)의 입력·목표값
크기에 맞춰 4번씩 다른 CPU payload를 복사하고, GPU에서 2배 연산 후 D2H 값을 비교한다.
세 방식 총 24검사와 방식 간 출력 hash 일치를 확인한다. 성능 소스·타이머·작업량은 바꾸지 않고
이 검증을 성능 표본에 합치지 않는다. 실패하면 관련 전송 성능의 유효성을 재검토하고 결론을 유보한다.
