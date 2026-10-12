# 선택 심화 실제 검증 로그 (2026-10-12)

- 실행: https://github.com/Huihuing/mini-watch/actions/runs/38214942407
- PR: https://github.com/Huihuing/mini-watch/pull/2
- 검증 커밋: c78f7033720fc478eb903e6eb7fb11fad32a0e27
- 최종 CI 상태: success
- GitHub Actions 아티팩트: docker-compose-evidence (ID 11731341810)
- 환경: GitHub Actions ubuntu-latest Docker. 로컬 Windows PC의 실제 실행 결과로 오인하지 마세요.

## DB 네트워크 분리

명령:

~~~bash
docker compose -f compose-general.yaml exec -T general-api getent hosts general-db
docker compose -f compose-general.yaml exec -T general-api getent hosts monitor-db
~~~

실제 출력/판정:

~~~text
172.22.0.2      general-db
PASS general-db resolves, monitor-db does not
~~~

monitor-db 조회는 실패하여 stdout이 빈 파일로 저장됐으며, 코드상 실패 exit code를 성공 조건으로 취급하여 판정했습니다. 이것은 DNS 망 격리 확인이며 DB 인증이나 SQL 성공을 증명하지는 않습니다.

## 공유망 분리·복구와 새 로그인 기록 전달

명령의 핵심:

~~~bash
docker network disconnect m5d1-events m5d1-general-general-api-1
docker compose -f compose-general.yaml exec -T general-api getent hosts monitor-api
docker compose -f compose-general.yaml up -d --force-recreate --no-deps general-api
docker compose -f compose-general.yaml up -d --force-recreate --no-deps general-gateway
docker compose -f compose-general.yaml exec -T general-api getent hosts monitor-api
python scripts/smoke_test.py
~~~

실제 분리 판정:

~~~text
PASS monitor-api DNS lookup fails after m5d1-events disconnect
~~~

복구 후 실제 DNS 출력:

~~~text
172.18.0.2      monitor-api
~~~

복구 후 HTTP/DB 기능 검증 파일 smoke-after-network-restore.txt의 실제 출력:

~~~text
PASS 일반 로그인 실패 HTTP 401
PASS 일반 로그인 성공 HTTP 200
PASS 일반 게시글 화면 HTTP 200
PASS 감시 DB 신규 로그인 이벤트 401 + 200
PASS 감시 메모 저장 및 새 요청 조회
PASS 검증 상태 파일 작성: evidence/smoke-state.json
~~~

마지막으로 두 Compose를 각각 down (-v 없음) / up 후 검증한 실제 출력:

~~~text
PASS 재생성 후 이전 로그인 실패·성공 이벤트와 메모 유지
~~~

첫 심화 PR #1에서는 Nginx upstream 캐시 때문에 HTTP 502가 발생했는데 파이프라인이 실패를 숨겼습니다. PR #2에서 gateway도 재생성하고 set -o pipefail로 수정했으며 위 증빙은 **PR #2의 수정 후 실행에서만** 발췌했습니다.
