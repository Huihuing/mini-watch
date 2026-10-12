# 선택 심화: Compose 네트워크 격리와 복구

## 의도 및 변경 파일

- .github/workflows/docker-compose.yml: DB 이름 조회 분리 검사, 외부 공유망 연결 중단과 정상 Compose 설정으로 API 재생성 뒤 이름 조회/신규 로그인 이벤트 전송 검사.
- 임시 컨테이너 상태만 바꾸고 compose-general.yaml 자체는 올바른 설정으로 보존합니다. 복구는 docker compose up --force-recreate --no-deps general-api로 수행합니다.

## 실행 단계와 판정

1. 일반 API 컨테이너에서 getent hosts general-db는 성공해야 합니다.
2. 같은 일반 API에서 getent hosts monitor-db는 실패해야 합니다. 이는 서비스별 DB 망 분리를 확인하지만 SQL 로그인 자체는 증명하지 않습니다.
3. docker network disconnect m5d1-events m5d1-general-general-api-1을 실행하여 일반 API만 공유망에서 분리합니다.
4. 일반 API의 getent hosts monitor-api가 실패하는지 확인합니다. 기존 기록은 자동 재전송되지 않으므로 연결 실패 시 이벤트가 소급 전송된다고 가정하지 않습니다.
5. docker compose -f compose-general.yaml up -d --force-recreate --no-deps general-api로 원래 선언된 공유망 연결을 복원합니다.
6. getent hosts monitor-api가 성공하는지 확인한 후 python scripts/smoke_test.py로 **새 로그인 실패·성공**과 감시 API의 기록 수신을 다시 검증합니다.
7. 기존 필수 테스트대로 두 Compose를 -v 없이 down/up하고 이벤트와 메모를 재조회합니다.

검증 증빙은 GitHub Actions의 evidence/db-isolation.txt, disconnect.txt, dns-restored.txt, smoke-after-network-restore.txt 파일로 남깁니다.

## 추가 검증 범위

브라우저 DNS 실패와 네트워크 상태가 아닌 API 내부에서 수행한 실제 getent 결과를 사용합니다. 정상 복구 뒤의 HTTP 호출 및 데이터베이스 조회는 scripts/smoke_test.py로 별도로 검증합니다.

자동 검사 결과와 PR 링크는 실제 실행 후 갱신합니다.
