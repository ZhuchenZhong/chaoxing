from __future__ import annotations

import json
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from .font_decoder import FontDecoder

logger = logging.getLogger(__name__)


def decode_course_list(html_text: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html_text, "html.parser")
    course_list: list[dict[str, str]] = []

    for course in soup.select("div.course"):
        if course.select_one("a.not-open-tip") or course.select_one("div.not-open-tip"):
            continue

        anchor = course.select_one("a")
        clazz_input = course.select_one("input.clazzId")
        course_input = course.select_one("input.courseId")
        title_node = course.select_one("span.course-name")
        teacher_node = course.select_one("p.color3")

        if not all([anchor, clazz_input, course_input, title_node, teacher_node]):
            continue

        cpi_match = re.search(r"cpi=([^&]+)", anchor.attrs.get("href", ""))
        if cpi_match is None:
            continue

        desc_node = course.select_one("p.margint10")
        course_list.append(
            {
                "id": course.attrs["id"],
                "info": course.attrs["info"],
                "roleid": course.attrs["roleid"],
                "clazzId": clazz_input.attrs["value"],
                "courseId": course_input.attrs["value"],
                "cpi": cpi_match.group(1),
                "title": title_node.attrs["title"],
                "desc": desc_node.attrs["title"] if desc_node else "",
                "teacher": teacher_node.attrs["title"],
            }
        )

    return course_list


def decode_course_folder(html_text: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html_text, "html.parser")
    folder_list: list[dict[str, str]] = []

    for folder in soup.select("ul.file-list > li"):
        folder_id = folder.attrs.get("fileid")
        rename_input = folder.select_one("input.rename-input")
        if not folder_id or rename_input is None:
            continue
        folder_list.append({"id": folder_id, "rename": rename_input.attrs["value"]})

    return folder_list


def decode_course_point(html_text: str) -> dict[str, Any]:
    soup = BeautifulSoup(html_text, "html.parser")
    result: dict[str, Any] = {"hasLocked": False, "points": []}

    for chapter_unit in soup.select("div.chapter_unit"):
        for raw_point in chapter_unit.select("li"):
            point = raw_point.find("div", id=re.compile(r"^cur\d+$"))
            if point is None:
                continue

            point_id = re.sub(r"^cur", "", point.attrs["id"])
            title_node = point.select_one("a.clicktitle")
            hover_tips = point.select_one("span.bntHoverTips")
            job_count_node = point.select_one("input.knowledgeJobCount")
            hover_text = hover_tips.get_text(strip=True) if hover_tips else ""

            point_detail = {
                "id": point_id,
                "title": title_node.get_text(strip=True) if title_node else "",
                "jobCount": job_count_node.attrs["value"] if job_count_node else 1,
                "has_finished": "已完成" in hover_text,
                "need_unlock": "解锁" in hover_text,
            }
            if point_detail["need_unlock"]:
                result["hasLocked"] = True
            result["points"].append(point_detail)

    return result


def decode_course_card(html_text: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if "章节未开放" in html_text:
        return [], {"notOpen": True}

    match = re.search(r"mArg=\{(.*?)\};", html_text, re.S)
    if match is None:
        return [], {}

    cards_data = json.loads("{" + match.group(1) + "}")
    defaults = cards_data.get("defaults", {})
    job_info = {
        "ktoken": defaults.get("ktoken", ""),
        "mtEnc": defaults.get("mtEnc", ""),
        "reportTimeInterval": defaults.get("reportTimeInterval", 60),
        "defenc": defaults.get("defenc", ""),
        "cardid": defaults.get("cardid", ""),
        "cpi": defaults.get("cpi", ""),
        "qnenc": defaults.get("qnenc", ""),
        "knowledgeid": defaults.get("knowledgeid", ""),
    }

    jobs: list[dict[str, Any]] = []
    for card in cards_data.get("attachments", []):
        if card.get("isPassed"):
            continue

        if "otherInfo" in card and isinstance(card["otherInfo"], str):
            card["otherInfo"] = card["otherInfo"].split("&")[0]

        card_type = str(card.get("type", "")).lower()
        if card_type == "video":
            mid = card.get("mid")
            if not mid:
                continue
            jobs.append(
                {
                    "type": "video",
                    "jobid": card.get("jobid", ""),
                    "name": card.get("property", {}).get("name", ""),
                    "otherinfo": card.get("otherInfo", ""),
                    "mid": mid,
                    "objectid": card.get("objectId", ""),
                    "aid": card.get("aid", ""),
                    "playTime": card.get("playTime", 0),
                    "rt": card.get("property", {}).get("rt", ""),
                    "attDuration": card.get("attDuration", ""),
                    "attDurationEnc": card.get("attDurationEnc", ""),
                    "videoFaceCaptureEnc": card.get("videoFaceCaptureEnc", ""),
                }
            )
            continue

        if card_type == "workid":
            jobs.append(
                {
                    "type": "workid",
                    "jobid": card.get("jobid", ""),
                    "otherinfo": card.get("otherInfo", ""),
                    "mid": card.get("mid", ""),
                    "enc": card.get("enc", ""),
                    "aid": card.get("aid", ""),
                }
            )
            continue

        if card_type == "document":
            jobs.append(
                {
                    "type": "document",
                    "jobid": card.get("jobid", ""),
                    "otherinfo": card.get("otherInfo", ""),
                    "jtoken": card.get("jtoken", ""),
                    "mid": card.get("mid", ""),
                    "enc": card.get("enc", ""),
                    "aid": card.get("aid", ""),
                    "objectid": card.get("property", {}).get("objectid", ""),
                }
            )
            continue

        if card_type == "read" and not card.get("property", {}).get("read", False):
            jobs.append(
                {
                    "title": card.get("property", {}).get("title", ""),
                    "type": "read",
                    "id": card.get("property", {}).get("id", ""),
                    "jobid": card.get("jobid", ""),
                    "jtoken": card.get("jtoken", ""),
                    "mid": card.get("mid", ""),
                    "otherinfo": card.get("otherInfo", ""),
                    "enc": card.get("enc", ""),
                    "aid": card.get("aid", ""),
                }
            )

    return jobs, job_info


def decode_questions_info(html_text: str) -> dict[str, Any]:
    soup = BeautifulSoup(html_text, "html.parser")
    form = soup.find("form")
    if form is None:
        return {}

    # Attempt font decoding for obfuscated text
    font_decoder: FontDecoder | None = None
    try:
        fd = FontDecoder(html_text)
        if fd._font_map:
            font_decoder = fd
    except Exception:
        pass

    payload: dict[str, Any] = {}
    for input_tag in form.find_all("input"):
        name = input_tag.attrs.get("name")
        if not name or name.startswith("answer"):
            continue
        payload[name] = input_tag.attrs.get("value", "")

    questions: list[dict[str, Any]] = []
    for question_node in form.select("div.singleQuesId"):
        question_id = question_node.attrs.get("data", "")
        type_node = question_node.select_one("div.TiMu")
        title_node = question_node.select_one("div.Zy_TItle")
        option_nodes = question_node.select("ul li")

        question_type = type_node.attrs.get("data", "") if type_node else ""

        # Extract and decode title
        raw_title = title_node.get_text() if title_node else ""
        raw_title = re.sub(r"[\r\t\n]", "", raw_title).strip()
        if font_decoder and raw_title:
            try:
                raw_title = font_decoder.decode(raw_title)
            except Exception:
                pass

        # Extract and decode options
        options: list[str] = []
        for option_node in option_nodes:
            option = option_node.attrs.get("aria-label") or option_node.get_text()
            option = re.sub(r"[\r\t\n]", "", option).strip()
            if font_decoder and option:
                try:
                    option = font_decoder.decode(option)
                except Exception:
                    pass
            if option.endswith("选择"):
                option = option[:-2].rstrip()
            if option:
                options.append(option)

        questions.append(
            {
                "id": question_id,
                "title": raw_title,
                "options": options,
                "type": question_type,
                "answerField": {
                    f"answer{question_id}": "",
                    f"answertype{question_id}": question_type,
                },
            }
        )

    payload["questions"] = questions
    payload["answerwqbid"] = ",".join(question["id"] for question in questions) + (
        "," if questions else ""
    )
    return payload
