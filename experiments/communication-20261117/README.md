# GPU 통신 경로 비교 — 2026-11-17 캠페인

GPU 1에서 Native, VMWeave SHM, Flyt TCP/ONC RPC + MPS, Lupine TCP 단독 실행 백엔드를 비교한다. Fractional GPU 제어·다중 tenant·애플리케이션 벤치마크는 범위에서 제외한다.

현재 상태: **320개 본 측정 구간·독립 검증·자원 정리 완료**. [결과 보고서](REPORT.md)를 참고한다. 예비 실행은 본 측정 통계에 포함하지 않았다.

- [고정 프로토콜](protocol/frozen.json), [준비 중 호환성 결정](protocol/preparation-decisions.md)
- [공통 측정기](src/probe.c), [공통 커널](src/sequence.ptx)
- [실행기](scripts/campaign.py), [분석기](scripts/analyze.py), [독립 검증기](scripts/verify_results.py)
- `results/b<block>-<backend>/`: 원시 지연 표본, 완료 수·경과 시간, 검산 결과, 동시 관측 자료
- `evidence/`: 이미지·GPU 예약·로드 라이브러리·VM 경로·할당 회수 증거
- `results/excluded-interruption-20261118/`: 중단된 블록 4의 첫 시도. 최종 통계에서 제외하고 동일 조건으로 블록 전체를 재실행했다. [복구 기록](evidence/interruption-recovery.json)

`cNN.u64.gz`는 gzip으로 무손실 압축한 little-endian uint64 나노초 배열이다. 배열 index가 표본 번호이며, 조건·블록·backend는 디렉터리와 `execution.json`에서 결합한다. 표본 하나는 복사+동기화 또는 K개 커널+동기화의 완료 시간이다. 처리량 분모는 표본 합계가 아니라 `elapsed_ns` 전체 측정 창이다.

측정 없이 재분석하려면 Python과 NumPy/Matplotlib를 설치한 환경에서 실행한다.

```sh
python -m pip install -r experiments/communication-20261117/analysis-requirements.txt
python experiments/communication-20261117/scripts/analyze.py
python experiments/communication-20261117/scripts/verify_results.py
python experiments/communication-20261117/scripts/verify_metadata.py
python experiments/communication-20261117/scripts/environment_review.py
python experiments/communication-20261117/scripts/report.py
```

실제 GPU 실행 스크립트는 이 노드의 전용 캠페인용이다. 이름·UUID·namespace·사전 백업과 allocator 상태를 검토하지 않고 다른 클러스터에서 실행하지 않는다. SSH 개인키, MongoDB 비밀번호, 기존 workload 원본 스냅샷은 저장소에 포함하지 않는다.

Flyt server는 이 노드에 보존되어 있던 2026-09-29 TCP 호환성 빌드다. `localhost/...@sha256:...`는 외부 레지스트리에서 pull 가능한 주소가 아니다. [당시 빌드/패치 기록](../evidence/results/2026-09-29-overhead/source/)과 이번 image/binary 해시를 함께 참고한다. 이 보고서 공개는 별도의 Flyt OCI 이미지 배포를 뜻하지 않는다.
