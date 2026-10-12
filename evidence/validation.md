# Docker Compose 통합 실행 증빙 (2026-10-12)

**출처:** https://github.com/Huihuing/mini-watch/actions/runs/38213949100
**검사한 소스 커밋:** 32fd27ea6965d535f47c6f3ca1451e8fb9de34de
**실행 환경:** GitHub Actions ubuntu-latest의 실제 Docker 컨테이너 (Windows 로컬 실행 아님)
**Actions 최종 결과:** success. 아티팩트 이름: docker-compose-evidence, ID: 11730074656.

## 명령과 실제 출력 발췌

### 설정 검사

~~~bash
docker network create m5d1-events
docker compose -f compose-monitor.yaml config --quiet
docker compose -f compose-general.yaml config --quiet
python -m compileall -q general monitor/backend scripts/smoke_test.py
~~~

위 명령을 CI에서 성공적으로 실행했습니다. config --quiet / compileall -q는 성공 시 출력이 없습니다.

### 실행 서비스 (docker compose -f ... ps)

~~~text
general-api      Up   5000/tcp
general-db       Up (healthy) 5432/tcp
general-gateway  Up   127.0.0.1:8081->80/tcp

monitor-api      Up   5000/tcp
monitor-db       Up (healthy) 5432/tcp
monitor-gateway  Up   127.0.0.1:8082->80/tcp
monitor-web      Up   3000/tcp
~~~

원본 출력: 아티팩트 ps-general.txt, ps-monitor.txt.

### 외부 네트워크 (docker network inspect m5d1-events)

원본 아티팩트 network-inspect.json의 Containers에는 아래 두 컨테이너만 포함되었습니다.

~~~text
m5d1-general-general-api-1
m5d1-monitor-monitor-api-1
~~~

일반/감시 DB는 공유 망에 참여하지 않습니다.

### 이름 조회 (docker compose -f compose-general.yaml exec -T general-api getent hosts monitor-api)

~~~text
172.18.0.2      monitor-api
~~~

이는 컨테이너의 DNS 이름이 해석된다는 증빙이며 HTTP 호출 성공이나 DB SQL 성공과 구분합니다. 실제 HTTP와 DB 기능은 아래 smoke 테스트에서 별도로 확인했습니다.

### 새 로그인 기록 및 메모 (python scripts/smoke_test.py)

~~~text
PASS 일반 로그인 실패 HTTP 401
PASS 일반 로그인 성공 HTTP 200
PASS 일반 게시글 화면 HTTP 200
PASS 감시 DB 신규 로그인 이벤트 401 + 200
PASS 감시 메모 저장 및 새 요청 조회
PASS 검증 상태 파일 작성: evidence/smoke-state.json
~~~

이 테스트가 저장한 신규 이벤트 ID는 3, 4이고 메모 ID는 1입니다(해당 CI 실행 기준). 메모 제목은 'Docker 점검', 내용은 '로그인 실패와 성공을 확인했다'입니다.

### 볼륨 유지 확인

~~~bash
docker compose -f compose-general.yaml down
docker compose -f compose-monitor.yaml down
docker compose -f compose-monitor.yaml up -d
docker compose -f compose-general.yaml up -d
python scripts/smoke_test.py --after-restart
~~~

실제 출력:

~~~text
PASS 재생성 후 이전 로그인 실패·성공 이벤트와 메모 유지
~~~

절대 down -v를 호출하지 않았습니다. 재생성 뒤 이벤트 ID 3, 4 및 메모 ID 1을 다시 조회했습니다.

## 원본 파일과 한계

GitHub Actions 실행 페이지의 **docker-compose-evidence** 아티팩트(11개 파일)에 ps, 컨테이너 로그, inspect JSON, DNS, 재생성 전후 출력 및 검사 ID가 보존되어 있습니다. 이 문서의 내용은 그 아티팩트에서 확인한 값만 적었습니다. 화면을 직접 클릭한 GUI 테스트와 Windows PC 로컬 실행 증빙은 아직 수집하지 않았습니다.
