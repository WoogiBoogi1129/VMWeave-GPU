# GPU 통신 경로 비교 — VMWeave 0.5.12 갱신

현재 비교 보고서는 **VMWeave만 새로 측정한 결과**를 반영한다.
[최신 결과 보고서](REPORT.md) · [이전 0.5.11 보고서](REPORT-v0.5.11.md)

- 주 비교: Native·Flyt·Lupine 기존 240구간 + 새 VMWeave 배치 ON 80구간.
- 보조 비교: 동일 0.5.12 바이너리의 배치 OFF 커널 20구간. 새 본 측정은 총 100구간이다.
- VMWeave는 Broker 최적화와 앱 bulk/direct를 활성화했다. **배치 ON은 제품 기본값이 아니다.**
- 새 VMWeave와 기존 N/F/L은 다른 시점의 결과다. 대응 블록 CI를 적용하지 않는다.
  배치 OFF/ON만 이번 실험 내 대응 비교다.
- Fractional 제어·다중 tenant·애플리케이션 벤치마크는 제외했다.

## 자료 선택과 보존

[선택 명세](analysis/selection.json)가 현재 집계에 포함한 자료를 지정한다.
기존 `results/b<block>-N|F|L/`와 집계 값은 보존했다.
`results/b<block>-V/`의 이전 VMWeave 원자료도 그대로 남아 있지만 현재 집계에서는 제외된다.
원본 파일의 해시는 [이력 manifest](history/v0.5.11/preserved-original-files.json),
이전 분석 결과는 `history/v0.5.11/analysis/`에 보관했다.

새 원자료는 `refresh-20261118/results/b<block>-ON|OFF/`,
새 프로토콜은 [frozen.json](refresh-20261118/protocol/frozen.json)에 있다.
각 블록마다 새 VM을 부팅하며, 블록 안에서 OFF/ON 순서를 교대하고 새 CUDA 세션을 사용한다.
예비 실행 `pilot-ON`은 통계에서 제외한다. 실행과 정리 증거는 `refresh-20261118/evidence/`에 있다.

`cNN.u64.gz`는 little-endian uint64 나노초 표본을 gzip 압축한 파일이다.
각 표본은 복사+sync 또는 K개 커널+sync의 완료 시간이다.
처리량 분모는 표본 합계가 아니라 마지막 완료까지의 실제 `elapsed_ns`다.

## 현재 보고서 재분석

GPU를 실행하지 않고 분석·독립 검증·그래프·보고서를 재생성한다.

```sh
python -m pip install -r experiments/communication-20261117/analysis-requirements.txt
python experiments/communication-20261117/scripts/refresh_vmweave.py
python experiments/communication-20261117/scripts/verify_refresh.py
python experiments/communication-20261117/scripts/report_refresh.py
```

공개 묶음의 무결성은 이 디렉터리에서 `sha256sum -c SHA256SUMS`로 검사한다.
분석 산출물을 다시 생성했다면 검토 후 `scripts/seal_refresh.py`로 새 manifest를 만든다.
이 명령은 이전 버전의 manifest까지 포함하며 GPU 작업을 실행하지 않는다.

**기존 `analyze.py`, `verify_results.py`, `report.py`는 과거 4방식 캠페인용이다.**
원본 프로토콜의 소스 해시 보존을 위해 수정하지 않았으며, 현재 보고서에는 위 새 명령을 사용한다.
과거 분석을 다시 실행하려면 별도 복사본에서 수행해야 현재 분석 산출물을 덮지 않는다.

실제 GPU 실행 스크립트는 이 노드의 실험 전용 자원 이름·GPU UUID·allocator에 묶여 있다.
검토 없이 재실행하지 않는다. SSH 개인키와 원본 운영 스냅샷은 공개 디렉터리에 포함하지 않는다.

Flyt는 기존 legacy TCP/ONC RPC + MPS 호환 빌드이며 gRPC CUDA 데이터 경로가 아니다.
Lupine도 기존 단독 TCP 백엔드 측정 조건을 유지했다.
과거 캠페인의 중단·재개와 외부 환경 변화는 [이전 보고서](REPORT-v0.5.11.md)에 보존한다.
