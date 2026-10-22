# v0.5.2 공개 및 운영 적용 — 2026-10-22

릴리스 소스는 `4f2ad748aa9fb9892e3e72ab18e559d6d8f81800`이다.
구현 브랜치를 main에 fast-forward 병합하고 원격 main 및 `v0.5.2` 태그를 게시했다.
기존 실험·계획 등의 무관한 미커밋 작업은 이번 릴리스에 포함하지 않았다.

## 공개 산출물

이미지 7종(operator, helper, worker, hook, guest-artifacts, hami, hami-dra)과
Operator OCI Helm chart `0.5.2`를 게시했다.
[릴리스 lock](../../../../deploy/releases/v0.5.2.json)에 digest·소스·CI URL을 기록한다.
모든 이미지 revision label을 확인했으며, 이는 암호학적 provenance 증명은 아니다.
다운로드한 차트의 11개 파일은 소스와 일치한다(Chart.yaml은 YAML 의미 비교,
나머지 파일은 byte 비교). Guest package SHA256SUMS 및 source revision도 확인했다.

공개 Guest ELF로 math cache 테스트 16개와 기존 상태 캐시 테스트 20개를 통과했다.
main 및 tag의 관련 CI를 모두 확인했다. 배포 차트 테스트 16개도 통과했다.

## 운영 적용 범위

- Operator: `vmweave-system/vmweave`, chart 0.5.2, Helm revision 10.
- 기존 VM: `vmweave-test-a/vmweave-k8s-01`. VM UID와 PVC 참조를 보존했다.
- Guest 파일은 공개 v0.5.2 package로 설치하고, 정상 정지/할당 회수 후 새 채널로 재기동했다.
- 새 profile `persistent-50-2048-v052`, request `vmweave-k8s-01-v052`로 Worker를 고정한다.
  이전 v051 profile/request는 롤백을 위해 유지한다.
- Helper·Hook·Worker는 공개 v0.5.2 digest를 사용한다.
- DRA Driver는 upstream chart 0.1.1과 기존 설정을 유지하며 v0.5.2 이미지로 갱신했다(Helm revision 5).
- 외부 의존성 Classic upstream HAMi 2.10.0과 다른 서비스는 변경하지 않는다.

기능 기본값은 비활성이다. 운영 애플리케이션 전체에 설정을 강제로 주입하지 않는다.
검증 프로세스에서만 `VMWEAVE_STATE_CACHE=1 VMWEAVE_BLAS_MATH_CACHE=1`을 사용한다.
활성화가 필요한 애플리케이션은 해당 환경 변수를 설정한 새 프로세스로 실행한다.

운영 검증은 공개 바이너리 해시, 기본/캐시 활성 GPU copy·PTX kernel, 실제 BLAS
mode 0↔2와 조회·중복·다중 handle·thread·잘못된 enum·새 객체 생성 검사이다.
운영 Worker/broker에는 장애를 주입하지 않는다. 장애 검증과 성능 수치는
[배포 전 격리 검증](../20261022-math-cache/report.md)을 참조한다.
운영 성능을 다시 측정한 것으로 해석하지 않는다.

## 롤백

옵션만 되돌리려면 `VMWEAVE_BLAS_MATH_CACHE`를 unset/0으로 설정한 새 프로세스를 사용한다.
전체 배포 롤백 시에는 이전 Guest 패키지를 설치하고 VM을 정상 정지한다.
채널이 Stopped이고 할당이 회수된 뒤, 이전 v051 request/profile 및 이미지 digest로
채널을 다시 구성한다. VM/PVC는 삭제하지 않는다.
Operator는 Helm revision 9, DRA는 revision 4로 되돌린다.
Guest·VM·채널·values 백업과 단계별 복구 절차는
`.local/math-release-20261022/{live-guest-before.tgz,*-before.json,rollback.md}`에 보존한다.
Helm `--atomic`은 Guest 파일/채널 변경을 자동 롤백하지 않으므로 별도 복구가 필요하다.

완료 상태와 실제 실행 식별값은 함께 보존한 JSON 증거를 기준으로 판단한다.


## 완료 증거

- [완료 상태](status.json), [운영 GPU·패키지 식별값](live-verification.json), [실제 math cache hit](live-math.json)
- [기본 GPU 실행](live-gpu-default.json), [옵션 활성 GPU 실행](live-gpu-cache.json)
- [실행 이미지](running-images.json), [Helm 상태](helm-after.json), [임시 자원 회수](cleanup.json)
- [CI](ci.json), [차트 대조](chart-contents.json), [공개 math 회귀](published-math-tests.log), [공개 상태 캐시 회귀](published-state-tests.log)

운영 환경에서 GPU 및 math 설정 검증을 통과했다. 임시 admin Pod를 삭제했고,
운영 VM/채널 Ready를 확인했다. 이는 서비스 전체 SLA나 DRA 할당 workload 재검증은 아니다.
