from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from .constants import COURSE_LIST_URL
from .crypto import AESCipher
from .exceptions import (
    ChaoxingAuthError,
    ChaoxingCookieExpiredError,
    ChaoxingParseError,
    ChaoxingRequestError,
)
from .parsers import (
    decode_course_card,
    decode_course_folder,
    decode_course_list,
    decode_course_point,
    decode_questions_info,
)
from .rate_limiter import AsyncRateLimiter

LOGIN_URL = "https://passport2.chaoxing.com/fanyalogin"
COURSE_LIST_PAYLOAD = {
    "courseType": 1,
    "courseFolderId": 0,
    "query": "",
    "superstarClass": 0,
}
COURSE_LIST_REFERER = (
    "https://mooc2-ans.chaoxing.com/mooc2-ans/visit/interaction?"
    "moocDomain=https://mooc1-1.chaoxing.com/mooc-ans"
)
COURSE_INTERACTION_URL = "https://mooc2-ans.chaoxing.com/mooc2-ans/visit/interaction"
COURSE_CHAPTERS_URL = "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/studentcourse"
IMAGE_VIEW_URL = "https://mooc1-api.chaoxing.com/ananas/job/insertimage"
BOOK_VIEW_URL = "https://mooc1-api.chaoxing.com/ananas/job/insertbook"
AUDIO_VIEW_URL = "https://mooc1-api.chaoxing.com/ananas/job/insertaudio"
VIDEO_VIEW_URL = "https://mooc1-api.chaoxing.com/ananas/job/insertvideo"
READING_COMPLETE_URL = "https://mooc1.chaoxing.com/mooc-ans/work/addStudentWork"
DOCUMENT_COMPLETE_URL = "https://mooc1.chaoxing.com/ananas/job/document"
KNOWLEDGE_CARDS_URL = "https://mooc1.chaoxing.com/mooc-ans/knowledge/cards"
VIDEO_PROGRESS_URL = "https://mooc1.chaoxing.com/mooc-ans/mycourse/studentcourse"
VIDEO_LOG_URL = "https://mooc1.chaoxing.com/mooc-ans/multimedia/log"
VIDEO_STATUS_URL = "https://mooc1.chaoxing.com/ananas/status"
QUIZ_WORK_URL = "https://mooc1.chaoxing.com/mooc-ans/api/work"
QUIZ_SUBMIT_URL = "https://mooc1.chaoxing.com/mooc-ans/work/addStudentWorkNew"


@dataclass(slots=True)
class ChaoxingLoginResult:
    account_id: str
    auth_type: Literal["password", "cookies"]
    message: str
    cookies: dict[str, str]


class ChaoxingClient:
    def __init__(
        self,
        account_id: str,
        session_manager: Any,
        cipher: AESCipher | None = None,
    ) -> None:
        self.account_id = account_id
        self.session_manager = session_manager
        self.cipher = cipher or AESCipher()
        self.rate_limiter = AsyncRateLimiter(0.5)
        self.video_log_limiter = AsyncRateLimiter(2.0)

    async def _replace_cookies(self, cookies: Mapping[str, str]) -> dict[str, str]:
        await self.session_manager.close_client(self.account_id)
        await self.session_manager.set_cookies(self.account_id, cookies)
        return await self.session_manager.get_cookies(self.account_id)

    async def _clear_cookies(self) -> None:
        await self.session_manager.close_client(self.account_id)

    async def _get_cookie_value(self, *names: str) -> str:
        cookies = await self.session_manager.get_cookies(self.account_id)
        for name in names:
            value = cookies.get(name)
            if value:
                return value
        return ""

    @staticmethod
    def _is_login_response(response_text: str) -> bool:
        lowered = response_text.lower()
        login_markers = (
            "passport2.chaoxing.com",
            "<title>login</title>",
            "login required",
            'name="uname"',
            'name="password"',
            "fanyalogin",
        )
        return any(marker in lowered for marker in login_markers)

    @staticmethod
    def _ensure_success_response(
        response: httpx.Response,
        *,
        error_message: str,
        url: str,
    ) -> None:
        if response.status_code < 200 or response.status_code >= 300:
            raise ChaoxingRequestError(
                error_message,
                detail={"url": url, "status": response.status_code},
            )

    @classmethod
    def _ensure_not_expired_session(cls, response_text: str) -> None:
        if cls._is_login_response(response_text):
            raise ChaoxingCookieExpiredError("cookies 已失效，请更新 cookies 或提供账号密码")

    @staticmethod
    def _parse_or_raise(
        parser: Callable[[str], Any],
        response_text: str,
        *,
        error_message: str,
        url: str,
    ) -> Any:
        try:
            return parser(response_text)
        except Exception as exc:
            raise ChaoxingParseError(error_message, detail={"url": url}) from exc

    @staticmethod
    def _response_indicates_success(response: httpx.Response) -> bool:
        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError):
            return "success" in response.text.lower()

        if isinstance(data, dict):
            status = data.get("status")
            success = data.get("success")
            if isinstance(status, bool):
                return status
            if isinstance(success, bool):
                return success
        return False

    async def login_with_password(self, username: str, password: str) -> ChaoxingLoginResult:
        await self._clear_cookies()
        client = await self.session_manager.get_client(self.account_id)
        payload = {
            "fid": "-1",
            "uname": self.cipher.encrypt(username),
            "password": self.cipher.encrypt(password),
            "refer": "https%3A%2F%2Fi.chaoxing.com",
            "t": "true",
            "forbidotherlogin": 0,
            "validate": "",
            "doubleFactorLogin": 0,
            "independentId": 0,
        }

        try:
            response = await client.post(LOGIN_URL, data=payload)
        except httpx.HTTPError as exc:
            raise ChaoxingRequestError(
                "Chaoxing password login request failed",
                detail={"url": LOGIN_URL},
            ) from exc

        self._ensure_success_response(
            response,
            error_message="Chaoxing password login request failed",
            url=LOGIN_URL,
        )

        try:
            response_data = response.json()
        except ValueError as exc:
            raise ChaoxingParseError(
                "Chaoxing password login response was not valid JSON",
                detail={"url": LOGIN_URL},
            ) from exc

        if response_data.get("status") is not True:
            raise ChaoxingAuthError(response_data.get("msg2") or "Chaoxing password login failed")

        return ChaoxingLoginResult(
            account_id=self.account_id,
            auth_type="password",
            message="登录成功",
            cookies=await self.session_manager.get_cookies(self.account_id),
        )

    async def login_with_cookies(
        self, cookies: Mapping[str, str]
    ) -> ChaoxingLoginResult:
        stored_cookies = await self._replace_cookies(cookies)
        if not await self.validate_cookie_session():
            await self._clear_cookies()
            raise ChaoxingCookieExpiredError("cookies 已失效，请更新 cookies 或提供账号密码")

        return ChaoxingLoginResult(
            account_id=self.account_id,
            auth_type="cookies",
            message="登录成功",
            cookies=stored_cookies,
        )

    async def validate_cookie_session(self) -> bool:
        cookies = await self.session_manager.get_cookies(self.account_id)
        if "_uid" not in cookies and "UID" not in cookies:
            return False

        client = await self.session_manager.get_client(self.account_id)
        try:
            response = await client.post(COURSE_LIST_URL, data=COURSE_LIST_PAYLOAD)
        except httpx.HTTPError:
            return False

        if response.status_code != 200:
            return False

        return not self._is_login_response(response.text)

    async def get_courses(self) -> list[dict]:
        client = await self.session_manager.get_client(self.account_id)
        try:
            response = await client.post(
                COURSE_LIST_URL,
                headers={"Referer": COURSE_LIST_REFERER},
                data=COURSE_LIST_PAYLOAD,
            )
        except httpx.HTTPError as exc:
            raise ChaoxingRequestError(
                "Chaoxing course list request failed",
                detail={"url": COURSE_LIST_URL},
            ) from exc

        self._ensure_success_response(
            response,
            error_message="Chaoxing course list request failed",
            url=COURSE_LIST_URL,
        )
        self._ensure_not_expired_session(response.text)
        courses = self._parse_or_raise(
            decode_course_list,
            response.text,
            error_message="Chaoxing course list response could not be parsed",
            url=COURSE_LIST_URL,
        )

        try:
            interaction_response = await client.get(COURSE_INTERACTION_URL)
        except httpx.HTTPError as exc:
            raise ChaoxingRequestError(
                "Chaoxing course folder request failed",
                detail={"url": COURSE_INTERACTION_URL},
            ) from exc

        self._ensure_success_response(
            interaction_response,
            error_message="Chaoxing course folder request failed",
            url=COURSE_INTERACTION_URL,
        )
        self._ensure_not_expired_session(interaction_response.text)
        folders = self._parse_or_raise(
            decode_course_folder,
            interaction_response.text,
            error_message="Chaoxing course folder response could not be parsed",
            url=COURSE_INTERACTION_URL,
        )

        for folder in folders:
            try:
                folder_response = await client.post(
                    COURSE_LIST_URL,
                    data={**COURSE_LIST_PAYLOAD, "courseFolderId": folder["id"]},
                )
            except httpx.HTTPError as exc:
                raise ChaoxingRequestError(
                    "Chaoxing course list request failed",
                    detail={"url": COURSE_LIST_URL},
                ) from exc

            self._ensure_success_response(
                folder_response,
                error_message="Chaoxing course list request failed",
                url=COURSE_LIST_URL,
            )
            self._ensure_not_expired_session(folder_response.text)
            courses.extend(
                self._parse_or_raise(
                    decode_course_list,
                    folder_response.text,
                    error_message="Chaoxing course list response could not be parsed",
                    url=COURSE_LIST_URL,
                )
            )

        return courses

    async def get_course_chapters(
        self, course_id: str, clazz_id: str, cpi: str
    ) -> dict | list:
        client = await self.session_manager.get_client(self.account_id)
        try:
            response = await client.get(
                COURSE_CHAPTERS_URL,
                params={"courseid": course_id, "clazzid": clazz_id, "cpi": cpi, "ut": "s"},
            )
        except httpx.HTTPError as exc:
            raise ChaoxingRequestError(
                "Chaoxing course chapter request failed",
                detail={"url": COURSE_CHAPTERS_URL},
            ) from exc

        self._ensure_success_response(
            response,
            error_message="Chaoxing course chapter request failed",
            url=COURSE_CHAPTERS_URL,
        )
        self._ensure_not_expired_session(response.text)
        return self._parse_or_raise(
            decode_course_point,
            response.text,
            error_message="Chaoxing course chapter response could not be parsed",
            url=COURSE_CHAPTERS_URL,
        )

    async def get_job_list(
        self,
        course: Mapping[str, str],
        point: Mapping[str, str],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        client = await self.session_manager.get_client(self.account_id)
        jobs: list[dict[str, Any]] = []
        job_info: dict[str, Any] = {}

        base_params = {
            "clazzid": course["clazzId"],
            "courseid": course["courseId"],
            "knowledgeid": point["id"],
            "ut": "s",
            "cpi": course["cpi"],
            "v": "2025-0424-1038-3",
            "mooc2": 1,
        }
        for num in range(7):
            await self.rate_limiter.limit_rate()
            response = await client.get(KNOWLEDGE_CARDS_URL, params={**base_params, "num": num})
            self._ensure_success_response(
                response,
                error_message="Chaoxing knowledge card request failed",
                url=KNOWLEDGE_CARDS_URL,
            )
            self._ensure_not_expired_session(response.text)
            parsed_jobs, parsed_info = self._parse_or_raise(
                decode_course_card,
                response.text,
                error_message="Chaoxing knowledge card response could not be parsed",
                url=KNOWLEDGE_CARDS_URL,
            )
            jobs.extend(parsed_jobs)
            job_info.update(parsed_info)

        return jobs, job_info

    async def get_video_progress(
        self,
        course_id: str,
        dtoken: str,
    ) -> dict[str, Any]:
        client = await self.session_manager.get_client(self.account_id)
        response = await client.get(
            f"{VIDEO_PROGRESS_URL}/getVideoProgress",
            params={"courseid": course_id, "dtoken": dtoken},
        )
        self._ensure_success_response(
            response,
            error_message="Chaoxing video progress request failed",
            url=VIDEO_PROGRESS_URL,
        )
        self._ensure_not_expired_session(response.text)
        try:
            return response.json()
        except ValueError:
            return {"isPassed": "success" in response.text.lower()}

    async def log_video_progress(
        self,
        *,
        course_id: str,
        clazz_id: str,
        cpi: str,
        dtoken: str,
        playing_time: int,
        duration: int,
        jobid: str,
        objectid: str,
        otherinfo: str,
        enc: str,
        dtype: str = "Video",
        rt: str | None = None,
        video_face_capture_enc: str | None = None,
        att_duration: str | None = None,
        att_duration_enc: str | None = None,
    ) -> bool:
        await self.video_log_limiter.limit_rate(random_time=True, random_max=2.0)
        client = await self.session_manager.get_client(self.account_id)
        userid = await self._get_cookie_value("_uid", "UID")
        params: dict[str, Any] = {
            "clazzId": clazz_id,
            "playingTime": playing_time,
            "duration": duration,
            "clipTime": f"0_{duration}",
            "objectId": objectid,
            "otherInfo": otherinfo,
            "courseId": course_id,
            "jobid": jobid,
            "userid": userid,
            "isdrag": "3",
            "view": "pc",
            "enc": enc,
            "dtype": dtype,
        }
        if rt:
            params["rt"] = rt
        if video_face_capture_enc:
            params["videoFaceCaptureEnc"] = video_face_capture_enc
        if att_duration:
            params["attDuration"] = att_duration
        if att_duration_enc:
            params["attDurationEnc"] = att_duration_enc

        response = await client.get(f"{VIDEO_LOG_URL}/a/{cpi}/{dtoken}", params=params)
        self._ensure_success_response(
            response,
            error_message="Chaoxing video log request failed",
            url=VIDEO_LOG_URL,
        )
        self._ensure_not_expired_session(response.text)
        try:
            data = response.json()
        except ValueError:
            return "success" in response.text.lower()
        return bool(data.get("isPassed"))

    async def refresh_video_status(self, objectid: str) -> dict[str, Any] | None:
        client = await self.session_manager.get_client(self.account_id)
        fid = await self._get_cookie_value("fid")
        response = await client.get(
            f"{VIDEO_STATUS_URL}/{objectid}",
            params={"k": fid, "flag": "normal"},
        )
        self._ensure_success_response(
            response,
            error_message="Chaoxing video status request failed",
            url=VIDEO_STATUS_URL,
        )
        self._ensure_not_expired_session(response.text)
        try:
            data = response.json()
        except ValueError as exc:
            raise ChaoxingParseError(
                "Chaoxing video status response was not valid JSON",
                detail={"url": VIDEO_STATUS_URL},
            ) from exc
        return data if data.get("status") == "success" else None

    async def get_quiz_questions(
        self,
        *,
        work_id: str,
        jobid: str,
        course_id: str,
        clazz_id: str,
        knowledgeid: str,
        ktoken: str,
        cpi: str,
        enc: str,
    ) -> dict[str, Any]:
        client = await self.session_manager.get_client(self.account_id)
        response = await client.get(
            QUIZ_WORK_URL,
            params={
                "api": "1",
                "workId": work_id,
                "jobid": jobid,
                "originJobId": jobid,
                "needRedirect": "true",
                "skipHeader": "true",
                "knowledgeid": knowledgeid,
                "ktoken": ktoken,
                "cpi": cpi,
                "ut": "s",
                "clazzId": clazz_id,
                "type": "",
                "enc": enc,
                "mooc2": "1",
                "courseid": course_id,
            },
        )
        self._ensure_success_response(
            response,
            error_message="Chaoxing quiz question request failed",
            url=QUIZ_WORK_URL,
        )
        self._ensure_not_expired_session(response.text)
        return self._parse_or_raise(
            decode_questions_info,
            response.text,
            error_message="Chaoxing quiz question response could not be parsed",
            url=QUIZ_WORK_URL,
        )

    async def submit_quiz_answers(self, payload: Mapping[str, Any]) -> bool:
        client = await self.session_manager.get_client(self.account_id)
        response = await client.post(QUIZ_SUBMIT_URL, data=dict(payload))
        self._ensure_success_response(
            response,
            error_message="Chaoxing quiz submission request failed",
            url=QUIZ_SUBMIT_URL,
        )
        self._ensure_not_expired_session(response.text)
        return self._response_indicates_success(response)

    async def mark_document_complete(
        self,
        jobid: str,
        dtoken: str,
        course_id: str | None = None,
    ) -> bool:
        client = await self.session_manager.get_client(self.account_id)
        response = await client.post(
            DOCUMENT_COMPLETE_URL,
            data={"jobid": jobid, "dtoken": dtoken, "courseid": course_id or ""},
        )
        self._ensure_success_response(
            response,
            error_message="Chaoxing document completion request failed",
            url=DOCUMENT_COMPLETE_URL,
        )
        self._ensure_not_expired_session(response.text)
        return self._response_indicates_success(response)

    async def mark_page_viewed(
        self,
        course_id: str | None,
        knowledgeid: str | None,
        jobid: str,
    ) -> bool:
        client = await self.session_manager.get_client(self.account_id)
        response = await client.post(
            IMAGE_VIEW_URL,
            data={
                "courseId": course_id or "",
                "knowledgeid": knowledgeid or "",
                "jobid": jobid,
            },
        )
        self._ensure_success_response(
            response,
            error_message="Chaoxing page view request failed",
            url=IMAGE_VIEW_URL,
        )
        self._ensure_not_expired_session(response.text)
        return self._response_indicates_success(response)

    async def mark_reading_complete(
        self,
        jobid: str,
        knowledgeid: str | None = None,
        course_id: str | None = None,
    ) -> bool:
        client = await self.session_manager.get_client(self.account_id)
        response = await client.post(
            READING_COMPLETE_URL,
            data={
                "jobid": jobid,
                "knowledgeid": knowledgeid or "",
                "courseid": course_id or "",
            },
        )
        self._ensure_success_response(
            response,
            error_message="Chaoxing reading completion request failed",
            url=READING_COMPLETE_URL,
        )
        self._ensure_not_expired_session(response.text)
        return self._response_indicates_success(response)

    async def mark_emptypage_complete(
        self,
        jobid: str,
        course_id: str | None = None,
    ) -> bool:
        client = await self.session_manager.get_client(self.account_id)
        response = await client.post(
            READING_COMPLETE_URL,
            data={"jobid": jobid, "courseid": course_id or ""},
        )
        self._ensure_success_response(
            response,
            error_message="Chaoxing emptypage completion request failed",
            url=READING_COMPLETE_URL,
        )
        self._ensure_not_expired_session(response.text)
        return self._response_indicates_success(response)

    async def mark_book_viewed(
        self,
        course_id: str | None,
        bookid: str | None,
        jobid: str,
    ) -> bool:
        client = await self.session_manager.get_client(self.account_id)
        response = await client.post(
            BOOK_VIEW_URL,
            data={"courseId": course_id or "", "bookid": bookid or "", "jobid": jobid},
        )
        self._ensure_success_response(
            response,
            error_message="Chaoxing book view request failed",
            url=BOOK_VIEW_URL,
        )
        self._ensure_not_expired_session(response.text)
        return self._response_indicates_success(response)

    async def mark_embedded_media_viewed(
        self,
        course_id: str | None,
        clazz_id: str | None,
        job_id: str,
        media_id: str | None,
        media_type: str = "insertaudio",
    ) -> bool:
        client = await self.session_manager.get_client(self.account_id)
        url = VIDEO_VIEW_URL if media_type == "insertvideo" else AUDIO_VIEW_URL
        data = {"jobid": job_id, "courseId": course_id or "", "clazzid": clazz_id or ""}
        if media_id:
            data["mediaid"] = media_id

        response = await client.post(url, data=data)
        self._ensure_success_response(
            response,
            error_message="Chaoxing embedded media view request failed",
            url=url,
        )
        self._ensure_not_expired_session(response.text)
        return self._response_indicates_success(response)
