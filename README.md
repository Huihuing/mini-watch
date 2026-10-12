# Mini Watch — Day 06 Docker Compose 과제

## 기준과 직접 변경한 내용

- 수업의 공개 [mini-watch day06-start](https://github.com/zeroskill2400/mini-watch/tree/day06-start) 앱 소스를 바탕으로 이 저장소를 구성했습니다. 개인 저장소에는 README만 있었으므로 이번에 앱 소스도 함께 추가했습니다.
- 일반 Flask 게시판/로그인과 감시 Flask 이벤트/메모 API 및 Next.js 감시 화면을 포함합니다.
- Flask 앱의 실행 주소를 127.0.0.1:5100/5200에서 0.0.0.0:5000으로 변경했습니다.
- 일반 Flask의 기록 전송 URL을 환경변수 MONITOR_URL로 제어하도록 변경했습니다.
- 기존 Next.js 개발용 localhost:5200 API rewrite를 제거하고 Nginx gateway가 /api/ 경로를 감시 API로 전달하도록 했습니다.
- general, monitor 각각 Dockerfile / .dockerignore / PostgreSQL 초기 SQL / gateway 설정을 포함합니다.
- 서로 다른 compose-general.yaml, compose-monitor.yaml을 완성하고 동일한 외부 네트워크 m5d1-events에 두 API만 연결합니다.
- scripts/smoke_test.py로 새 로그인 이벤트·메모 생성·재조회·재생성 후 보존 여부를 검사할 수 있습니다.

## 요구 사항과 네트워크

| Compose 프로젝트 | 서비스 | 연결 네트워크 | 호스트 공개 포트 |
| --- | --- | --- | --- |
| m5d1-general | general-db | general-data-net | 없음 |
| m5d1-general | general-api | general-front-net, general-data-net, events-net | 없음 |
| m5d1-general | general-gateway | general-front-net | 127.0.0.1:8081 |
| m5d1-monitor | monitor-db | monitor-data-net | 없음 |
| m5d1-monitor | monitor-api | monitor-front-net, monitor-data-net, events-net | 없음 |
| m5d1-monitor | monitor-web | monitor-front-net | 없음 |
| m5d1-monitor | monitor-gateway | monitor-front-net | 127.0.0.1:8082 |

두 Compose에서 events-net은 external: true, name: m5d1-events로 지정합니다. 서비스에 같은 network alias만 적더라도 실제로 서로 다른 Compose 내부 네트워크를 사용한다면 이름이 조회되지 않습니다. **외부 네트워크의 실제 이름을 공유하고 두 API가 모두 참여**해야 monitor-api로 통신할 수 있습니다. DB는 내부 DB 전용 네트워크에만 참여합니다.

API → DB: general-db:5432 / monitor-db:5432.
일반 API → 감시 API: http://monitor-api:5000/api/events.
호스트에서는 http://localhost:8081 및 http://localhost:8082에 접속합니다.

## 실행 방법 (Windows PowerShell, Docker Desktop 실행 필요)

프로젝트 루트에서 각각의 Compose를 따로 실행합니다. Docker Desktop Linux 컨테이너 모드가 필요합니다.

~~~powershell
docker network create m5d1-events
docker compose -f compose-monitor.yaml config --quiet
docker compose -f compose-general.yaml config --quiet

# 감시를 먼저 실행
docker compose -f compose-monitor.yaml up -d --build
curl.exe -i http://localhost:8082/api/auth/me

# 감시 API가 준비되어 HTTP 200을 반환한 다음 일반 실행
docker compose -f compose-general.yaml up -d --build

docker compose -f compose-monitor.yaml exec monitor-api python create_user.py
docker compose -f compose-general.yaml exec general-api python create_user.py
~~~

실습용 계정: 일반 student / Learn123! ; 감시 operator / Learn123! (실제 운영에 사용하지 마세요).
일반 서비스 /login 에서 로그인하고 게시글 화면으로 이동합니다. 감시 화면에서 로그인한 다음 '기록 불러오기'와 '목록 불러오기'를 사용합니다.

PostgreSQL 초기 SQL은 DB 볼륨이 최초 생성되는 시점에만 실행됩니다. 컨테이너를 다시 만드는 것과 데이터를 삭제하는 것은 다릅니다. 특히 down -v는 사용하지 마세요.

## Compose·네트워크 검사 (실제 결과를 기록할 명령)

~~~powershell
New-Item -ItemType Directory -Force evidence | Out-Null
docker compose -f compose-monitor.yaml ps | Tee-Object evidence/ps-monitor.txt
docker compose -f compose-general.yaml ps | Tee-Object evidence/ps-general.txt
docker compose -f compose-monitor.yaml logs --tail=80 monitor-api | Tee-Object evidence/log-monitor.txt
docker compose -f compose-general.yaml logs --tail=80 general-api | Tee-Object evidence/log-general.txt
docker network inspect m5d1-events | Out-File -Encoding utf8 evidence/network-inspect.txt
docker compose -f compose-general.yaml exec general-api getent hosts monitor-api | Tee-Object evidence/dns-monitor-api.txt
docker compose -f compose-general.yaml exec general-api getent hosts general-db
docker compose -f compose-general.yaml exec general-api getent hosts monitor-db
~~~

general-db는 조회되어야 하며 monitor-db는 일반 API의 네트워크에서 이름이 확인되지 않아야 합니다. 이름 조회 성공은 DNS/네트워크 확인일 뿐, HTTP 요청 성공이나 DB SQL 성공까지 의미하지 않습니다.

config --quiet는 성공하면 별도의 출력이 없습니다. 오류가 있다면 먼저 해당 YAML 설정을 수정하세요. ps, inspect, getent 출력은 실행 환경마다 달라지므로 예시 문자열을 실제 결과처럼 적지 않습니다.

## 실제 로그인·메모 및 DB 영속성 검증

아래 Python 스크립트는 표준 라이브러리만 사용합니다. 두 Compose가 켜져 있고 수업 계정을 만든 상태에서 실행하세요.

~~~powershell
python scripts/smoke_test.py | Tee-Object evidence/smoke-before.txt

# 두 Compose를 별도 종료; -v 절대 사용하지 않음
docker compose -f compose-general.yaml down
docker compose -f compose-monitor.yaml down

# 감시 먼저 재생성, 그 다음 일반
docker compose -f compose-monitor.yaml up -d
docker compose -f compose-general.yaml up -d

python scripts/smoke_test.py --after-restart | Tee-Object evidence/smoke-after.txt
~~~

첫 실행은 감시 이벤트 ID를 먼저 기억한 뒤 일반의 새 비밀번호 오류 HTTP 401, 로그인 성공 HTTP 200, 게시글 접속, 신규 login_failure/login_success 전달, 'Docker 점검' 메모 등록과 재조회를 검사합니다. evidence/smoke-state.json에 ID를 저장합니다. 재시작 후 검사는 같은 이벤트 ID와 메모 ID 및 내용을 다시 조회합니다.

브라우저에서도 일반의 실패/성공을 직접 만들고, 감시에서 login_failure 401 및 login_success 200 기록을 확인하세요. 메모 내용은 **로그인 실패와 성공을 확인했다**입니다. 저장 후 화면을 새로고침하고 목록 불러오기로 유지되는지 확인하고, 화면 캡처를 evidence 폴더에 남기세요.

### 실제 실행 결과 — GitHub Actions (2026-10-12)

Ubuntu GitHub Actions 호스팅 러너에서 [통합 테스트 #1](https://github.com/Huihuing/mini-watch/actions/runs/38213949100)을 실행했고 최종 **success**를 확인했습니다. 이는 로컬 Windows PC 실행 화면이 아니라 **실제 CI Docker 환경**의 검증 결과입니다.

| 확인 항목 | 실제 결과 |
| --- | --- |
| config --quiet (두 Compose) / Python compileall | PASS |
| Flask 두 이미지, Next.js production 이미지, DB/gateway 빌드·실행 | PASS |
| PostgreSQL 두 DB healthcheck | healthy / healthy |
| Docker ps에서 PC에 공개된 포트 | 두 gateway의 127.0.0.1:8081, 127.0.0.1:8082만 |
| docker network inspect m5d1-events | 일반 API와 감시 API 컨테이너 2개만 참여 |
| 일반 API에서 getent hosts monitor-api | 172.18.0.2 monitor-api (러너마다 IP 다름) |
| 신규 로그인 실패·성공 | login_failure 401 및 login_success 200 확인 |
| 감시 메모 새 HTTP 요청으로 재조회 | PASS |
| 두 Compose를 down (-v 없이) → up 재생성 후 이벤트·메모 유지 | PASS |

명령과 캡처한 실제 출력 발췌는 [evidence/validation.md](evidence/validation.md), 전체 ps/network inspect/API logs/테스트 결과는 해당 Actions 실행의 **docker-compose-evidence** 아티팩트에서 확인할 수 있습니다. API 검사 스크립트는 신규 로그인 이벤트와 메모를 실제 DB에서 다시 조회하며, 단순히 코드 내용만 검사하지 않습니다.

주의: CI는 브라우저 UI 스크린샷을 자동 수집하지 않습니다. 수업 제출 시 Windows PC에서 일반/감시 화면을 실제로 열고 감시 목록의 이벤트 및 메모 새로고침 화면을 추가 캡처하면 증빙이 더 충실해집니다.

## 최종 종료

~~~powershell
docker compose -f compose-general.yaml down
docker compose -f compose-monitor.yaml down
# m5d1-events는 다음 실행에서 재사용 가능하며 볼륨은 보존됨
~~~

## Git 작업 기록

- 앱/Compose 구축 커밋: 32fd27ea6965d535f47c6f3ca1451e8fb9de34de
- 변경 요지: Day06 소스 통합, Flask 컨테이너 주소/기록 전송 수정, 외부 공유망·DB 볼륨·헬스체크 구성, Nginx/Next.js production 구성, 검증 스크립트/README 추가.
- 저장소: https://github.com/Huihuing/mini-watch (비공개).

- [Docker 앱 구현 커밋](https://github.com/Huihuing/mini-watch/commit/32fd27ea6965d535f47c6f3ca1451e8fb9de34de) / [실제 CI 검증 #1](https://github.com/Huihuing/mini-watch/actions/runs/38213949100)
