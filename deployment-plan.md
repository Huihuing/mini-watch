# Day2 클라우드 배포 계획 및 적용 기록

> 저장소: https://github.com/Huihuing/mini-watch (private)  
> 기준: 기존 Day1 Docker Compose 완료 코드 (main, 77bfef858fe515aa105f694293316b2812349602)  
> 작업 브랜치: `day2-deploy`  
> 배포 상태: **실제 Render/Supabase/Sentry 연결 및 서비스 주소 검증은 미완료**. 이 문서는 배포를 위한 소스·설정 준비 결과다. DB 자격 증명, DSN, 토큰, 실제 서비스 URL을 커밋하지 않는다.

## 1. 변경한 구성과 파일

기존 `compose-general.yaml`, `compose-monitor.yaml`, `gateways/`, 로그인·게시글·이벤트·관찰 메모 API 및 Next UI는 로컬 실습용으로 유지한다. Render에서는 Compose를 실행하지 않고 앱 세 개를 **각각 Docker Web Service**로 배포한다.

| 앱 | Render Root Directory | Dockerfile Path / Build Context | Health Check Path | 배포 설정/상태 |
| --- | --- | --- | --- | --- |
| 감시 Flask API | `monitor/backend` | `./Dockerfile` / `.` | `/health` | Docker, Hobby/Free, `day2-deploy`, Auto-Deploy: On Commit, 미배포 |
| 일반 Flask | `general` | `./Dockerfile` / `.` | `/health` | Docker, Hobby/Free, `day2-deploy`, Auto-Deploy: On Commit, 미배포 |
| 감시 Next.js | `monitor/next-frontend` | `./Dockerfile` / `.` | `/` | Docker, Hobby/Free, `day2-deploy`, Auto-Deploy: On Commit, 미배포 |

세 앱 모두 Docker Command를 빈칸으로 두고 Dockerfile의 CMD를 쓴다. Flask Dockerfile은 `waitress-serve --host=0.0.0.0 --port=$PORT app:app`으로 실행하고, 로컬 `python app.py` 개발 실행은 남겨뒀다. Next는 `npm ci` / `npm run build` / `npm run start`를 사용한다. Next의 `app/page.js`는 빌드 시 외부 API를 호출하지 않으며, 데이터는 클라이언트의 실제 요청 때 읽는다.

### 파일별 변경 이유

- `general/app.py`, `monitor/backend/app.py`: /health, Sentry 초기화, 로그인 필요·기능 플래그를 확인하는 /api/sentry-test.
- 두 `Dockerfile`, `requirements.txt`: Waitress 및 Sentry SDK. 기존 Flask routes를 바꾸지 않고 동일한 `app:app` 서빙.
- 두 `db.py`, `.env.example`: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSLMODE`와 SSL 연결 설정.
- 두 `auth_helpers.py`: `SECRET_KEY`, `SESSION_COOKIE_SECURE` 환경 설정, HTTPOnly/Lax 세션 쿠키 유지.
- `general/request_logging.py`, `monitor/backend/routes/events.py`: 기록 수신 주소·요청 토큰 `EVENT_TOKEN`, HTTP 401/200 이벤트의 기존 분류·DB 저장 유지.
- `monitor/next-frontend/app/api/[...path]/route.js`: Next 서버 → 감시 Flask 프록시. Cookie·X-CSRF-Token·Set-Cookie·HTTP status 전달.
- 두 `observability.py`: Sentry 환경/릴리스 태그, 인증정보 등 요청 데이터 제거.
- `general/sql/deploy.sql`, `monitor/backend/sql/deploy.sql`: 외부 DB용 비파괴 스키마.
- 두 `create_user.py`: 외부 DB에는 대화형 비밀번호 생성, 로컬 Compose의 `--demo`는 `DB_HOST=general-db` 또는 `monitor-db`에만 허용.
- 두 Compose 및 GitHub CI: 로컬 전용 동일한 학습 토큰 주입, 기존 자동 통합 테스트는 `--demo`로 수업 계정을 설정한다.

## 2. Supabase DB 두 개

무료 프로젝트 이용 가능 범위를 먼저 확인하고, **일반용**과 **감시용**을 분리한다. 일반용은 기존 2교시 프로젝트를 재사용할 수 있다. 감시용은 다른 프로젝트를 지정한다. 프로젝트가 다른 경우 둘 다 DB_NAME이 `postgres`여도 서로 다른 데이터베이스다. Supabase Free에서 한도를 넘어서야 한다면 결제를 요구하지 말고 미완료로 남긴다.

각 프로젝트의 **Connect → Session pooler**의 연결 정보를 해당 Flask 환경 변수에 매핑한다.

| 환경 변수 | Render/Supabase 연결값 | 로컬 Compose |
| --- | --- | --- |
| `DB_HOST` | 각 프로젝트의 Session pooler host | `general-db` / `monitor-db` |
| `DB_PORT` | `5432` | `5432` |
| `DB_NAME` | `postgres` | `general_db` / `monitor_db` |
| `DB_USER` | 해당 프로젝트의 `postgres.PROJECT_REF` | `sample` |
| `DB_PASSWORD` | 해당 DB의 비공개 비밀번호 | 로컬 학습용 샘플 |
| `DB_SSLMODE` | `require` | 기본 `prefer` |

Supabase SQL Editor에서 **일반 프로젝트에는 `general/sql/deploy.sql`**, **감시 프로젝트에는 `monitor/backend/sql/deploy.sql`**을 각각 실행한다. 일반: `users`, `posts`; 감시: `users`, `http_events`, `notes`. 비파괴 `IF NOT EXISTS` SQL이며 테이블이나 데이터를 삭제하지 않는다. 일반 게시글 INSERT/UPDATE/DELETE는 기존 `repositories/posts.py`, 메모 CRUD는 `monitor/backend/repositories/notes.py`가 실제 PostgreSQL로 실행한다.

Flask가 DB에 직접 연결하는 수업용 구성으로, 해당 프로젝트에서는 Supabase Data API를 비활성화한다. 별도 Data API/RLS 정책이나 브라우저에서의 DB 직접 연결은 만들지 않는다.

### 외부 DB 계정 준비 (Windows CMD)

각 Flask 폴더에서 별도로 아래 명령을 실행한다.

```cmd
cd general
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
REM .env 파일에 일반 Supabase Session pooler 값/32자 이상 SECRET_KEY 입력
python create_user.py
deactivate

cd ..\monitor\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
REM .env 파일에 별도 감시 Supabase Session pooler 값/SECRET_KEY 입력
python create_user.py
deactivate
```

계정 기본 아이디는 `student`와 `operator`다. 각 프로그램이 새 비밀번호(12자 이상)를 두 번 받으며 `generate_password_hash`로 저장한다. 기존 아이디가 있으면 갱신하지 않는다. 외부 DB에는 수업 공개 비밀번호를 사용하지 않는다. Render Free 셸에서 계정 생성하는 것을 전제로 하지 않는다.

## 3. 환경 변수와 요청 전달

**감시 Flask**: `DB_*` 6개, `SECRET_KEY`, `SESSION_COOKIE_SECURE=true`, `EVENT_TOKEN`, `SENTRY_DSN`(선택), `SENTRY_ENVIRONMENT=mini-monitor`, `APP_VERSION=day2-v1`, `ENABLE_SENTRY_TEST=false`.

**일반 Flask**: 감시 Flask와 같은 `EVENT_TOKEN`, 일반용으로 다른 `SECRET_KEY`, 자체 `DB_*`, `SESSION_COOKIE_SECURE=true`, `MONITOR_URL=https://<감시-API>.onrender.com/api/events`, `SENTRY_ENVIRONMENT=mini-general`, `APP_VERSION`, `SENTRY_DSN`(선택), `ENABLE_SENTRY_TEST=false`.

**감시 Next**: `MONITOR_API_URL=https://<감시-API>.onrender.com` (**/api를 덧붙이지 않음**). 실 비밀번호, SESSION/DB 키, EVENT_TOKEN은 Next 환경/브라우저 `NEXT_PUBLIC_*`에 절대 두지 않는다. `MONITOR_API_URL`은 Next 서버에서만 읽는다.

네트워크 흐름:

```text
브라우저 ── 같은 출처 /api ──> Next Route Handler ── HTTPS ──> monitor Flask ──> monitor Supabase
브라우저 ── HTTPS ──> general Flask ── HTTPS + X-Event-Token ──> monitor Flask ──> monitor Supabase
```

Next 프록시는 Cookie, X-CSRF-Token과 요청 본문을 전달하고 상태코드 및 여러 Set-Cookie를 원래 브라우저 응답에 유지한다. `POST /api/events`는 Next에서 막고, 감시 Flask에서도 인증 토큰을 검사한다. 로그인 실패 `login_failure/401`, 성공 `login_success/200`은 기존 `event_rules.py`로 분류된다.

쿠키는 로컬 `http://localhost`에서 `SESSION_COOKIE_SECURE=false`, HTTPS 배포에서 `true`로 설정한다. `/health`는 Flask 프로세스 응답만 뜻하며 DB 연결·로그인·쓰기 성공을 보장하지 않는다.

## 4. Sentry 및 실습 오류 수정

두 Flask 모두 앱 가져오기 시 `configure_errors('mini-general')` / `configure_errors('mini-monitor')`를 호출한다. Flask 개발 실행과 Waitress `app:app` 실행 양쪽에서 초기화된다. `SENTRY_DSN`이 빈 문자열이면 전송하지 않는다. `SENTRY_ENVIRONMENT`, `APP_VERSION`에서 환경과 배포 버전을 읽는다.

`before_send`에서는 request의 `data`, `cookies`, `headers`, `query_string`과 최상위 `user`를 제거한다. `send_default_pii=False`, `include_local_variables=False`, `max_request_body_size='never'`도 적용한다. Sentry로 전송되기 전의 보안을 위한 설정이며 사용자 데이터가 절대 수집되지 않는다는 보장은 아니다.

수업 `starter/general/app.py`의 `sentry_test()`에는 `result = 1 / 0`가 있어 `ZeroDivisionError`가 발생한다. 본인 변경에서는 **이 부분을 `return {'result': 1, 'status': 'ok'}`로 수정**했다. 파일: `general/app.py`, 오류 수정 도입 커밋: `570f51cf5cd0` (전체 SHA는 커밋 링크에서 확인). 감시 앱의 동일한 실습 경로도 `monitor/backend/app.py`에서 수정했다(도입 커밋 `1161b7715867`).

오류 확인 과정에서만 `ENABLE_SENTRY_TEST=true`를 **비공개 환경 변수**에 임시 설정하고 로그인된 계정으로 `GET /api/sentry-test`를 호출한다. 정상 응답을 확인한 뒤 다시 `false`로 돌린다. Sentry의 `Resolve`는 오류 상태 표시일 뿐, 코드 수정이나 재배포를 대신하지 않는다. 수정 전·후 코드 비교는 교사 제공 starter의 0 나누기와 현행 `general/app.py` 간 diff로 확인할 수 있다. 실제 Sentry 이벤트 수신 검증은 진행하지 않았다.

## 5. 배포·검사·오류 진단 절차

1. 본인 GitHub `day2-deploy` 브랜치를 push하고 감시·일반의 Supabase DB를 분리해 SQL Editor에서 해당 deploy.sql을 적용, `python create_user.py`로 실습 계정을 생성한다.
2. Render에서 감시 Flask Docker Web Service 생성 → 비밀 Environment 입력 → `/health` HTTP 200 확인. 다음 일반 Flask `MONITOR_URL`과 Next `MONITOR_API_URL`을 감시 Flask의 실제 HTTPS 주소로 설정한다.
3. 일반 Flask와 감시 Next Docker Web Service 생성, 배포된 커밋이 `day2-deploy`의 최신 커밋인지 확인한다. 일반 화면 로그인 실패와 성공을 만들고 감시 화면 로그인 → 기록 불러오기 → `login_failure 401`, `login_success 200` 확인.
4. 게시글·메모 등록/수정/삭제와 새로고침 뒤 조회, 각 Supabase DB 행 확인. 커밋 → push → Render On Commit 자동 배포 → 배포 커밋 확인 → 이전 저장 데이터 재조회.
5. 오류 실습 테스트 플래그를 임시로 켜고 로그인 후 `/api/sentry-test` 정상 JSON 반환 확인, 테스트 플래그 `false` 복원. Sentry 프로젝트를 쓰지 않아도 코드 평가에는 지장이 없다.

오류 진단:

| 상황 | 우선 확인 |
| --- | --- |
| 감시 API 주소가 잘못됨 | Next 서버의 `MONITOR_API_URL`, Route Handler의 502/503 JSON 및 Render 감시 API `/health`; 일반은 `MONITOR_URL`, `X-Event-Token` 및 Flask 기록 전송 경고 로그 |
| DB 연결 실패 | 실제 DB 기능 요청, 두 Flask의 `DB_HOST/PORT/NAME/USER/PASSWORD/SSLMODE`, Supabase 프로젝트·Session pooler 상태, Render DB 연결 오류 로그; /health OK만으로 DB 정상 판정하지 않음 |
| 잘못된 입력 | Flask 인증·노트 입력 검증에서 400/401/403 JSON을 반환하는지 확인. HTTP 503 DB 오류 또는 Next 502 접속 오류와 구분 |
| 감시 화면 호출 실패 | Next Route Handler는 설정 누락 503, 외부 호출 실패 502와 안내 JSON 반환. `api/client.js`는 `result.error`를 표시하며 사용자에게 다시 불러오기를 제공 |

배포 주소(일반/감시 API/화면): **미배포 — 실제 URL 없음**. Sentry 오류 수신·외부 DB 행 조회도 미검증. 기존 Day1 GitHub Actions 로그는 **Day1 로컬 Docker 성공 기록**이며 이번 클라우드 배포 증빙은 아니다.

## 6. 로컬 Compose와 Git 기록

기존 `m5d1-events` 공유 네트워크 / `localhost:8081`, `localhost:8082` 두 Docker Compose는 그대로 사용한다. 로컬은 서비스 이름 `monitor-api:5000`과 학습용 `EVENT_TOKEN`을 사용하며 Render는 외부 HTTPS와 비공개 토큰으로 통신한다. CI 로컬 DB 계정 준비는 `create_user.py --demo`, 외부 계정은 대화형 `create_user.py`를 사용한다. `--demo`는 지정한 로컬 DB 호스트에서만 동작한다.

Day1 검증 커밋: `77bfef858fe515aa105f694293316b2812349602`. Day2 코드 커밋은 이 문서에 연결된 `day2-deploy` Git 히스토리에서 확인한다. `.env`, 실제 비밀번호·토큰·DSN, `node_modules`, `.next`, Python 가상환경 등은 절대로 제출하지 않는다. GitHub 비공개 저장소로 계속 유지한다.
