# 역사 문서의 경로 안내

2026-11-05 구조 검사에서 발견한 과거 상대 링크를 안내한다.
원본 보고서·실험 결과·체크섬은 수정하지 않았다. 아래의 현행 경로 안내는 과거 실험의 추가 검증이 아니다.

| 원문·기존 참조 | 찾아볼 위치 또는 상태 |
|---|---|
| [구 RPC README](../../legacy/rpc/README.md)의 `experiments/shm-contract/` | [현재 SHM 계약](../../runtime/shm/shm-contract/README.md) |
| 같은 문서의 `experiments/cuda-dispatch/` | [현재 CUDA dispatch](../../runtime/shm/cuda-dispatch/README.md) |
| 같은 문서의 `experiments/shm-queue/` | [현재 SHM queue](../../runtime/shm/shm-queue/README.md) |
| 같은 문서의 `docs/DEVELOPMENT_STAGES.md` | [보존된 단계 기록](../../legacy/docs/DEVELOPMENT_STAGES.md) |
| 같은 문서의 `docs/ARCHITECTURE.md` | [보존된 아키텍처](../../legacy/docs/ARCHITECTURE.md) |
| 같은 문서의 `docs/PROVENANCE.md` | [보존된 출처](../../legacy/docs/PROVENANCE.md) |
| 같은 문서의 `docs/PATCH_CATALOG.md` | [보존된 patch 목록](../../legacy/docs/PATCH_CATALOG.md) |
| 같은 문서의 `docs/REPRODUCING.md` | [보존된 재현 안내](../../legacy/docs/REPRODUCING.md) |
| 같은 문서의 `docs/WHOLE_GPU_EXPERIMENT.md` | [보존된 whole-GPU 실험](../../legacy/docs/WHOLE_GPU_EXPERIMENT.md) |
| 같은 문서의 `docs/GITHUB_PUBLISHING.md` | [보존된 게시 기록](../../legacy/docs/GITHUB_PUBLISHING.md) |
| 같은 문서의 `docs/ARTIFACT_POLICY.md` | [보존된 artifact 정책](../../legacy/docs/ARTIFACT_POLICY.md) |
| 같은 문서의 `docs/KNOWN_LIMITATIONS.md` | [보존된 당시 제한](../../legacy/docs/KNOWN_LIMITATIONS.md) |
| [구 HAMi 단계](../../legacy/rpc/experiments/hami-standalone/README.md)의 `../../docs/DEVELOPMENT_STAGES.md` | [보존된 단계 기록](../../legacy/docs/DEVELOPMENT_STAGES.md) |
| [경로 최적화 보관 보고서](../../experiments/ai-passthrough/results/20261027-path-optimization-validation/archive/validation/REPORT.md)의 `REPORT.md`, `NEXT-STEPS.md` | [10/27 VM 보고서](../../experiments/ai-passthrough/results/20261027-path-optimization-vm/REPORT.md), [후속 계획](../../experiments/ai-passthrough/results/20261027-path-optimization-vm/NEXT-STEPS.md) |
| [9/28 증거 검토](../../experiments/evidence/SIX_CHAPTER_EVIDENCE_AUDIT_2026-09-28.md)의 `docs/flyt-k8s-track-a2-architecture.svg` | 해당 이름의 그림은 분석한 main에 없음. [현행 구조](../architecture/index.md)는 별도 안내이며 원본 그림의 대체 증거가 아님 |
| [E2 환경 기록](../../experiments/thesis-isolation/config/E2-environment.md)의 `validation.json`, `dependencies.txt` | 해당 `results/20261012-e2-environment/` 파일은 분석한 main에 없음. 검증 성공으로 간주하거나 다른 실행의 자료로 대체하지 않음 |

위 18개 참조는 역사 문서를 보존하면서 안내로 보완했다.
현행 `runtime/shm/cuda-dispatch/README.md`의 잘못된 증거 링크 1개는 실제 파일 위치로 수정했다.
당시 원문 상태를 확인하려면 구조 검토 기준 커밋 `223468c9afc270abe9bb935b08b3244f4481bcc1`을 사용한다.
