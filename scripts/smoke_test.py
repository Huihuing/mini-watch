#!/usr/bin/env python3
"""Run the real localhost gateway login/event/note smoke test (Python stdlib only)."""
import argparse
import json
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "evidence" / "smoke-state.json"


class Client:
    def __init__(self, url):
        self.url = url
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def call(self, method, path, payload=None, token=None):
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["X-CSRF-Token"] = token
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = Request(self.url + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=15) as resp:
                return resp.status, resp.read().decode("utf-8")
        except HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")


def json_call(client, method, path, payload=None, token=None, expected=200):
    status, content = client.call(method, path, payload, token)
    if status != expected:
        raise AssertionError(f"{method} {client.url}{path}: expected HTTP {expected}, got {status}: {content[:500]}")
    return json.loads(content)


def login(client, username, password):
    state = json_call(client, "GET", "/api/auth/me")
    result = json_call(client, "POST", "/api/auth/login",
                       {"username": username, "password": password},
                       state["csrf_token"])
    assert result.get("user", {}).get("username") == username
    return result["csrf_token"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--after-restart", action="store_true")
    args = parser.parse_args()
    monitor = Client("http://localhost:8082")
    general = Client("http://localhost:8081")

    token = login(monitor, "operator", "Learn123!")
    if args.after_restart:
        saved = json.loads(STATE.read_text(encoding="utf-8"))
        events = json_call(monitor, "GET", "/api/events")["events"]
        event_ids = {item["id"] for item in events}
        assert set(saved["event_ids"]).issubset(event_ids), "이전 이벤트가 없어졌습니다."
        notes = json_call(monitor, "GET", "/api/notes")["notes"]
        assert any(n["id"] == saved["note_id"] and n["title"] == "Docker 점검"
                   and n["body"] == "로그인 실패와 성공을 확인했다" for n in notes), "이전 메모가 없어졌습니다."
        print("PASS 재생성 후 이전 로그인 실패·성공 이벤트와 메모 유지")
        return

    previous = json_call(monitor, "GET", "/api/events")["events"]
    highest_id = max((item["id"] for item in previous), default=0)
    auth = json_call(general, "GET", "/api/auth/me")
    json_call(general, "POST", "/api/auth/login",
              {"username": "student", "password": "wrong-on-purpose"},
              auth["csrf_token"], expected=401)
    print("PASS 일반 로그인 실패 HTTP 401")

    json_call(general, "POST", "/api/auth/login",
              {"username": "student", "password": "Learn123!"},
              auth["csrf_token"])
    print("PASS 일반 로그인 성공 HTTP 200")
    page_status, page = general.call("GET", "/")
    assert page_status == 200 and "게시글" in page, "게시글 화면 접근 실패"
    print("PASS 일반 게시글 화면 HTTP 200")

    actual = json_call(monitor, "GET", "/api/events")["events"]
    fresh = [e for e in actual if e["id"] > highest_id]
    failure = next((e for e in fresh if e["event_type"] == "login_failure"
                    and e["status_code"] == 401), None)
    success = next((e for e in fresh if e["event_type"] == "login_success"
                    and e["status_code"] == 200), None)
    assert failure and success, "방금 전송한 login_failure(401) 또는 login_success(200)가 없습니다."
    print("PASS 감시 DB 신규 로그인 이벤트 401 + 200")

    created = json_call(monitor, "POST", "/api/notes",
                        {"title": "Docker 점검", "body": "로그인 실패와 성공을 확인했다"},
                        token, expected=201)["note"]
    note_id = created["id"]
    refreshed = json_call(monitor, "GET", "/api/notes")["notes"]
    assert any(n["id"] == note_id and n["title"] == "Docker 점검"
               and n["body"] == "로그인 실패와 성공을 확인했다" for n in refreshed)
    print("PASS 감시 메모 저장 및 새 요청 조회")

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"event_ids": [failure["id"], success["id"]],
                                 "note_id": note_id}, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"PASS 검증 상태 파일 작성: {STATE.relative_to(ROOT)}")
    print("다음 단계: compose down (절대 -v 없음), up -d 후 --after-restart 실행")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, URLError, OSError, KeyError, ValueError) as exc:
        raise SystemExit(f"FAIL: {exc}")
