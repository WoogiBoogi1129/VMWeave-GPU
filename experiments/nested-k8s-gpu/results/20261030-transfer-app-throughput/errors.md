# 준비 단계 오류

GPU 측정 전 `barrier.c`를 Guest gcc/glibc 환경에서 컴파일하면서
`RTLD_NEXT undeclared` 오류가 발생했다. 로컬 glibc에서는 문법 검사가 통과했지만
Guest Ubuntu 22.04에서는 해당 GNU 확장을 선언하는 `_GNU_SOURCE`가 필요했다.
매크로를 추가해 새 실험용 관측 라이브러리만 다시 컴파일했다.

최초 [준비 실행 기록](preparation.log)과 [재개 기록](preparation-resumed.log)을 보존한다.
최초 runner는 subprocess 오류의 빌드 출력을 별도 저장하지 않아 traceback만 남았다.
이후 도구에는 `build-failure.log` 저장을 추가했다. 해당 오류 메시지는 별도의
읽기·재컴파일 진단에서 확인했으며, 원본 로그에 존재하는 것처럼 복원하지 않는다.

이 준비 실패에서는 GPU workload나 내부 Job을 시작하지 않았다.
VMWeave 시스템 코드·배포·Guest broker 설정은 변경하지 않았다.
수정 후 Guest와 이미지 안의 실행파일·라이브러리 8개 해시 일치를 확인했다.
