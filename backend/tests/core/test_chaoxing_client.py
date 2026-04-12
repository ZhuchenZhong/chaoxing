from urllib.parse import parse_qs

import httpx
import pytest

from chaoxing.core.chaoxing.client import ChaoxingClient, ChaoxingLoginResult
from chaoxing.core.chaoxing.constants import COURSE_LIST_URL
from chaoxing.core.chaoxing.exceptions import (
    ChaoxingCookieExpiredError,
    ChaoxingParseError,
    ChaoxingRequestError,
)
from chaoxing.core.session import SessionManager


class MockedSessionManager(SessionManager):
    def __init__(self, handler) -> None:
        super().__init__()
        self._handler = handler

    async def get_client(self, account_id: str) -> httpx.AsyncClient:
        async with self._lock:
            client = self._clients.get(account_id)
            if client is None or client.is_closed:
                client = httpx.AsyncClient(transport=httpx.MockTransport(self._handler))
                self._clients[account_id] = client
            return client


class StubCipher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def encrypt(self, value: str) -> str:
        self.calls.append(value)
        return f"enc::{value}"


@pytest.mark.asyncio
async def test_validate_cookie_session_returns_false_without_uid_cookie() -> None:
    session_manager = SessionManager()
    client = ChaoxingClient(account_id="account-1", session_manager=session_manager)

    assert await client.validate_cookie_session() is False

    await session_manager.close_all()


@pytest.mark.asyncio
async def test_login_with_password_sends_expected_legacy_payload() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["payload"] = parse_qs(request.content.decode(), keep_blank_values=True)
        return httpx.Response(
            200,
            json={"status": True},
            headers=[
                ("set-cookie", "_uid=42; Path=/"),
                ("set-cookie", "route=node-1; Path=/"),
            ],
        )

    session_manager = MockedSessionManager(handler)
    cipher = StubCipher()
    client = ChaoxingClient(account_id="account-1", session_manager=session_manager, cipher=cipher)

    result = await client.login_with_password(username="alice", password="secret")

    assert cipher.calls == ["alice", "secret"]
    assert captured["url"] == "https://passport2.chaoxing.com/fanyalogin"
    assert captured["payload"] == {
        "fid": ["-1"],
        "uname": ["enc::alice"],
        "password": ["enc::secret"],
        "refer": ["https%3A%2F%2Fi.chaoxing.com"],
        "t": ["true"],
        "forbidotherlogin": ["0"],
        "validate": [""],
        "doubleFactorLogin": ["0"],
        "independentId": ["0"],
    }
    assert result == ChaoxingLoginResult(
        account_id="account-1",
        auth_type="password",
        message="登录成功",
        cookies={"_uid": "42", "route": "node-1"},
    )

    await session_manager.close_all()


@pytest.mark.asyncio
async def test_login_with_cookies_clears_account_cookies_when_validation_fails() -> None:
    session_manager = MockedSessionManager(
        lambda request: httpx.Response(200, text="login required")
    )
    await session_manager.set_cookies("account-1", {"_uid": "old", "route": "stale"})
    client = ChaoxingClient(account_id="account-1", session_manager=session_manager)

    with pytest.raises(ChaoxingCookieExpiredError):
        await client.login_with_cookies({"_uid": "42", "route": "node-1"})

    assert await session_manager.get_cookies("account-1") == {}

    await session_manager.close_all()


@pytest.mark.asyncio
async def test_get_course_chapters_preserves_legacy_decode_shape() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            text="""
            <div class="chapter_unit">
              <li>
                <div id="cur123">
                  <a class="clicktitle"> 第一章 </a>
                  <input class="knowledgeJobCount" value="2" />
                  <span class="bntHoverTips">已完成</span>
                </div>
              </li>
              <li>
                <div id="cur456">
                  <a class="clicktitle"> 第二章 </a>
                  <span class="bntHoverTips">需要解锁</span>
                </div>
              </li>
            </div>
            """,
        )

    session_manager = MockedSessionManager(handler)
    client = ChaoxingClient(account_id="account-1", session_manager=session_manager)

    result = await client.get_course_chapters(course_id="100", clazz_id="200", cpi="300")

    assert captured["url"] == (
        "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/"
        "studentcourse?courseid=100&clazzid=200&cpi=300&ut=s"
    )
    assert result == {
        "hasLocked": True,
        "points": [
            {
                "id": "123",
                "title": "第一章",
                "jobCount": "2",
                "has_finished": True,
                "need_unlock": False,
            },
            {
                "id": "456",
                "title": "第二章",
                "jobCount": 1,
                "has_finished": False,
                "need_unlock": True,
            },
        ],
    }

    await session_manager.close_all()


@pytest.mark.asyncio
async def test_get_course_chapters_raises_parse_error_for_parser_failure(monkeypatch) -> None:
    def boom(_: str) -> dict[str, object]:
        raise ValueError("bad chapter html")

    import chaoxing.core.chaoxing.client as chaoxing_client_module

    monkeypatch.setattr(chaoxing_client_module, "decode_course_point", boom)
    session_manager = MockedSessionManager(lambda request: httpx.Response(200, text="<div></div>"))
    client = ChaoxingClient(account_id="account-1", session_manager=session_manager)

    with pytest.raises(ChaoxingParseError) as exc_info:
        await client.get_course_chapters(course_id="100", clazz_id="200", cpi="300")

    assert str(exc_info.value) == "Chaoxing course chapter response could not be parsed"
    assert exc_info.value.detail == {
        "url": "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/studentcourse"
    }

    await session_manager.close_all()


@pytest.mark.asyncio
async def test_get_courses_preserves_request_order_and_merges_folder_courses() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            {
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
                "payload": parse_qs(request.content.decode(), keep_blank_values=True)
                if request.method == "POST"
                else None,
            }
        )

        if request.method == "POST" and request.url.path.endswith("/visit/courselistdata"):
            form = parse_qs(request.content.decode(), keep_blank_values=True)
            if form["courseFolderId"] == ["0"]:
                return httpx.Response(
                    200,
                    text="""
                    <div class="course" id="root-1" info="root-info" roleid="5">
                      <input class="clazzId" value="2001" />
                      <input class="courseId" value="1001" />
                      <a href="/course?cpi=root-cpi&foo=bar"></a>
                      <span class="course-name" title="Root Course"></span>
                      <p class="margint10" title="Root Desc"></p>
                      <p class="color3" title="Root Teacher"></p>
                    </div>
                    """,
                )

            if form["courseFolderId"] == ["77"]:
                return httpx.Response(
                    200,
                    text="""
                    <div class="course" id="folder-1" info="folder-info" roleid="7">
                      <input class="clazzId" value="2002" />
                      <input class="courseId" value="1002" />
                      <a href="/course?cpi=folder-cpi&foo=bar"></a>
                      <span class="course-name" title="Folder Course"></span>
                      <p class="color3" title="Folder Teacher"></p>
                    </div>
                    """,
                )

        if request.method == "GET" and request.url.path.endswith("/visit/interaction"):
            return httpx.Response(
                200,
                text="""
                <ul class="file-list">
                  <li fileid="77">
                    <input class="rename-input" value="Folder A" />
                  </li>
                </ul>
                """,
            )

        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    session_manager = MockedSessionManager(handler)
    client = ChaoxingClient(account_id="account-1", session_manager=session_manager)

    result = await client.get_courses()

    assert [(entry["method"], entry["url"]) for entry in requests] == [
        ("POST", COURSE_LIST_URL),
        ("GET", "https://mooc2-ans.chaoxing.com/mooc2-ans/visit/interaction"),
        ("POST", COURSE_LIST_URL),
    ]
    assert requests[0]["payload"] == {
        "courseType": ["1"],
        "courseFolderId": ["0"],
        "query": [""],
        "superstarClass": ["0"],
    }
    assert requests[2]["payload"] == {
        "courseType": ["1"],
        "courseFolderId": ["77"],
        "query": [""],
        "superstarClass": ["0"],
    }
    assert result == [
        {
            "id": "root-1",
            "info": "root-info",
            "roleid": "5",
            "clazzId": "2001",
            "courseId": "1001",
            "cpi": "root-cpi",
            "title": "Root Course",
            "desc": "Root Desc",
            "teacher": "Root Teacher",
        },
        {
            "id": "folder-1",
            "info": "folder-info",
            "roleid": "7",
            "clazzId": "2002",
            "courseId": "1002",
            "cpi": "folder-cpi",
            "title": "Folder Course",
            "desc": "",
            "teacher": "Folder Teacher",
        },
    ]

    await session_manager.close_all()


@pytest.mark.asyncio
async def test_get_courses_raises_request_error_for_non_2xx_root_response() -> None:
    session_manager = MockedSessionManager(lambda request: httpx.Response(502, text="bad gateway"))
    client = ChaoxingClient(account_id="account-1", session_manager=session_manager)

    with pytest.raises(ChaoxingRequestError) as exc_info:
        await client.get_courses()

    assert str(exc_info.value) == "Chaoxing course list request failed"
    assert exc_info.value.detail == {"url": COURSE_LIST_URL, "status": 502}

    await session_manager.close_all()


@pytest.mark.asyncio
async def test_get_job_list_decodes_task_cards_and_defaults() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        num = request.url.params.get("num")
        if request.url.path.endswith("/knowledge/cards") and num == "0":
            return httpx.Response(
                200,
                text=(
                    'mArg={"defaults":{"knowledgeid":"9138","ktoken":"kt-1","cpi":"cpi-1"},'
                    '"attachments":[{"job":true,"type":"video","jobid":"job-1",'
                    '"otherInfo":"nodeId_9138-abc&courseId=1","mid":"mid-1","objectId":"obj-1",'
                    '"aid":"aid-1","playTime":0,"property":{"name":"Video 1","rt":"1"}},'
                    '{"job":true,"type":"workid","jobid":"work-1","otherInfo":"nodeId_9138-abc",'
                    '"mid":"mid-2","enc":"enc-1","aid":"aid-2"}]};'
                ),
            )
        if request.url.path.endswith("/knowledge/cards"):
            return httpx.Response(200, text='mArg={"defaults":{"knowledgeid":"9138"},"attachments":[]};')
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    session_manager = MockedSessionManager(handler)
    client = ChaoxingClient(account_id="account-1", session_manager=session_manager)

    jobs, job_info = await client.get_job_list(
        {"clazzId": "2001", "courseId": "1001", "cpi": "cpi-1"},
        {"id": "9138"},
    )

    assert requests[0].endswith(
        "/mooc-ans/knowledge/cards?clazzid=2001&courseid=1001&knowledgeid=9138&ut=s&cpi=cpi-1&v=2025-0424-1038-3&mooc2=1&num=0"
    )
    assert job_info["knowledgeid"] == "9138"
    assert jobs == [
        {
            "type": "video",
            "jobid": "job-1",
            "name": "Video 1",
            "otherinfo": "nodeId_9138-abc",
            "mid": "mid-1",
            "objectid": "obj-1",
            "aid": "aid-1",
            "playTime": 0,
            "rt": "1",
            "attDuration": "",
            "attDurationEnc": "",
            "videoFaceCaptureEnc": "",
        },
        {
            "type": "workid",
            "jobid": "work-1",
            "otherinfo": "nodeId_9138-abc",
            "mid": "mid-2",
            "enc": "enc-1",
            "aid": "aid-2",
        },
    ]

    await session_manager.close_all()


@pytest.mark.asyncio
async def test_get_video_progress_returns_json_payload() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"isPassed": True, "playingTime": 120})

    session_manager = MockedSessionManager(handler)
    client = ChaoxingClient(account_id="account-1", session_manager=session_manager)

    result = await client.get_video_progress(course_id="1001", dtoken="dt-1")

    assert captured["url"] == (
        "https://mooc1.chaoxing.com/mooc-ans/mycourse/studentcourse/getVideoProgress"
        "?courseid=1001&dtoken=dt-1"
    )
    assert result == {"isPassed": True, "playingTime": 120}

    await session_manager.close_all()


@pytest.mark.asyncio
async def test_log_video_progress_uses_legacy_log_endpoint() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"isPassed": False})

    session_manager = MockedSessionManager(handler)
    await session_manager.set_cookies("account-1", {"_uid": "42"})
    client = ChaoxingClient(account_id="account-1", session_manager=session_manager)

    result = await client.log_video_progress(
        course_id="1001",
        clazz_id="2001",
        cpi="cpi-1",
        dtoken="dt-1",
        playing_time=60,
        duration=300,
        jobid="job-1",
        objectid="obj-1",
        otherinfo="nodeId_9138-abc",
        enc="enc-1",
        dtype="Video",
        rt="1",
    )

    # URL includes _t timestamp param when rt is provided; verify fixed params only
    url = captured["url"]
    assert "mooc-ans/multimedia/log/a/cpi-1/dt-1" in url
    params = captured["params"]
    assert params["clazzId"] == "2001"
    assert params["playingTime"] == "60"
    assert params["duration"] == "300"
    assert params["clipTime"] == "0_300"
    assert params["objectId"] == "obj-1"
    assert params["otherInfo"] == "nodeId_9138-abc"
    assert params["courseId"] == "1001"
    assert params["jobid"] == "job-1"
    assert params["userid"] == "42"
    assert params["enc"] == "enc-1"
    assert params["dtype"] == "Video"
    assert params["rt"] == "1"
    assert "_t" in params  # timestamp added when rt is present
    # log_video_progress returns (isPassed, status_code) tuple
    passed, status_code = result
    assert passed is False
    assert status_code == 200

    await session_manager.close_all()


@pytest.mark.asyncio
async def test_refresh_video_status_uses_fid_cookie() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"status": "success", "dtoken": "dt-1"})

    session_manager = MockedSessionManager(handler)
    await session_manager.set_cookies("account-1", {"fid": "fid-1"})
    client = ChaoxingClient(account_id="account-1", session_manager=session_manager)

    result = await client.refresh_video_status("obj-1")

    assert captured["url"] == "https://mooc1.chaoxing.com/ananas/status/obj-1?k=fid-1&flag=normal"
    assert result == {"status": "success", "dtoken": "dt-1"}

    await session_manager.close_all()


@pytest.mark.asyncio
async def test_get_quiz_questions_parses_form_fields_and_question_options() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            text="""
            <form>
              <input name="courseId" value="1001" />
              <input name="classId" value="2001" />
              <div class="singleQuesId" data="123">
                <div class="TiMu" data="0"></div>
                <div class="Zy_TItle"><p> Test question? </p></div>
                <ul>
                  <li aria-label="A. Yes 选择"></li>
                  <li aria-label="B. No 选择"></li>
                </ul>
              </div>
            </form>
            """,
        )

    session_manager = MockedSessionManager(handler)
    client = ChaoxingClient(account_id="account-1", session_manager=session_manager)

    result = await client.get_quiz_questions(
        work_id="37778125",
        jobid="work-37778125",
        course_id="1001",
        clazz_id="2001",
        knowledgeid="913820156",
        ktoken="kt-1",
        cpi="cpi-1",
        enc="enc-1",
    )

    assert "/mooc-ans/api/work?api=1&workId=37778125&jobid=work-37778125" in captured["url"]
    assert result["courseId"] == "1001"
    assert result["answerwqbid"] == "123,"
    assert result["questions"] == [
        {
            "id": "123",
            "title": "Test question?",
            "options": ["A. Yes", "B. No"],
            "type": "0",
            "answerField": {"answer123": "", "answertype123": "0"},
        }
    ]

    await session_manager.close_all()


@pytest.mark.asyncio
async def test_submit_quiz_answers_posts_form_payload_and_returns_success() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["payload"] = parse_qs(request.content.decode(), keep_blank_values=True)
        return httpx.Response(200, json={"status": True, "msg": "提交成功"})

    session_manager = MockedSessionManager(handler)
    client = ChaoxingClient(account_id="account-1", session_manager=session_manager)

    result = await client.submit_quiz_answers(
        {
            "courseId": "1001",
            "classId": "2001",
            "answer123": "A",
            "answertype123": "0",
            "pyFlag": "",
        }
    )

    assert captured["url"] == "https://mooc1.chaoxing.com/mooc-ans/work/addStudentWorkNew"
    assert captured["payload"] == {
        "courseId": ["1001"],
        "classId": ["2001"],
        "answer123": ["A"],
        "answertype123": ["0"],
        "pyFlag": [""],
    }
    assert result is True

    await session_manager.close_all()
