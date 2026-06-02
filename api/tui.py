# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, DataTable, Footer, Header, Input, Label, RichLog, Select, TabbedContent, TabPane

from api.config_store import ensure_config_file, load_config_from_file, save_config_to_file
from api.events import StudyEvent
from api.logger import configure_logging


def _csv_items(value: str) -> list[str] | None:
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


class ChaoxingTui(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    TabbedContent {
        height: 1fr;
    }

    .form {
        padding: 1 2;
    }

    .row {
        height: auto;
        margin-bottom: 1;
    }

    Label {
        width: 18;
        padding-top: 1;
    }

    Input, Select {
        width: 1fr;
    }

    Button {
        margin-right: 1;
    }

    #course-table {
        height: 12;
    }

    #run-log {
        height: 1fr;
    }
    """

    BINDINGS = [("ctrl+s", "save_config", "保存配置"), ("ctrl+q", "quit", "退出")]

    def __init__(self, config_path: str | Path | None = None):
        super().__init__()
        self.config_path = ensure_config_file(config_path)
        self._running = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent():
            with TabPane("账号"):
                with Vertical(classes="form"):
                    yield Label(f"配置文件: {self.config_path}")
                    with Horizontal(classes="row"):
                        yield Label("手机号")
                        yield Input(id="username", placeholder="手机号")
                    with Horizontal(classes="row"):
                        yield Label("密码")
                        yield Input(id="password", placeholder="密码", password=True)
                    yield Checkbox("使用 Cookie 登录", id="use-cookies")
                    yield Checkbox("记住密码并写入 config.ini", id="remember-password")

            with TabPane("运行配置"):
                with Vertical(classes="form"):
                    with Horizontal(classes="row"):
                        yield Label("课程 ID")
                        yield Input(id="course-list", placeholder="逗号分隔；留空则学习全部")
                    with Horizontal(classes="row"):
                        yield Label("视频倍速")
                        yield Input(id="speed", placeholder="1.0")
                    with Horizontal(classes="row"):
                        yield Label("并发章节")
                        yield Input(id="jobs", placeholder="4")
                    with Horizontal(classes="row"):
                        yield Label("关闭章节")
                        yield Select(
                            [("重试", "retry"), ("询问", "ask"), ("跳过", "continue")],
                            id="notopen-action",
                            allow_blank=False,
                        )

            with TabPane("题库"):
                with Vertical(classes="form"):
                    with Horizontal(classes="row"):
                        yield Label("Provider")
                        yield Input(id="tiku-provider", placeholder="TikuYanxi")
                    with Horizontal(classes="row"):
                        yield Label("Tokens")
                        yield Input(id="tiku-tokens")
                    with Horizontal(classes="row"):
                        yield Label("提交答题")
                        yield Select([("否", "false"), ("是", "true")], id="tiku-submit", allow_blank=False)
                    with Horizontal(classes="row"):
                        yield Label("覆盖率")
                        yield Input(id="tiku-cover-rate", placeholder="0.9")
                    with Horizontal(classes="row"):
                        yield Label("搜题延迟")
                        yield Input(id="tiku-delay", placeholder="1.0")

            with TabPane("通知"):
                with Vertical(classes="form"):
                    with Horizontal(classes="row"):
                        yield Label("Provider")
                        yield Input(id="notification-provider", placeholder="ServerChan")
                    with Horizontal(classes="row"):
                        yield Label("URL")
                        yield Input(id="notification-url")
                    with Horizontal(classes="row"):
                        yield Label("Telegram Chat")
                        yield Input(id="notification-chat-id")

            with TabPane("课程与运行"):
                with Vertical(classes="form"):
                    with Horizontal(classes="row"):
                        yield Button("保存配置", id="save", variant="primary")
                        yield Button("刷新课程", id="load-courses")
                        yield Button("开始运行", id="run", variant="success")
                        yield Button("退出", id="quit")
                    yield DataTable(id="course-table")
                    yield RichLog(id="run-log", wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        configure_logging(console_enabled=False, tui_sink=self._log_sink)
        self._setup_tables()
        self._load_fields()

    def _setup_tables(self) -> None:
        table = self.query_one("#course-table", DataTable)
        table.add_columns("课程ID", "课程名")

    def _log_sink(self, message) -> None:
        text = str(message).rstrip()
        if text:
            self.call_from_thread(self._append_log, text)

    def _append_log(self, text: str) -> None:
        self.query_one("#run-log", RichLog).write(text)

    def _input(self, selector: str) -> Input:
        return self.query_one(selector, Input)

    def _checkbox(self, selector: str) -> Checkbox:
        return self.query_one(selector, Checkbox)

    def _select(self, selector: str) -> Select:
        return self.query_one(selector, Select)

    def _load_fields(self) -> None:
        common, tiku, notification = load_config_from_file(self.config_path)
        self._input("#username").value = str(common.get("username", ""))
        self._input("#password").value = str(common.get("password", ""))
        self._checkbox("#use-cookies").value = bool(common.get("use_cookies", False))
        self._checkbox("#remember-password").value = bool(common.get("remember_password", False))
        self._input("#course-list").value = ",".join(common.get("course_list") or [])
        self._input("#speed").value = str(common.get("speed", 1.0))
        self._input("#jobs").value = str(common.get("jobs", 4))
        self._select("#notopen-action").value = common.get("notopen_action", "retry")

        self._input("#tiku-provider").value = str(tiku.get("provider", ""))
        self._input("#tiku-tokens").value = str(tiku.get("tokens", ""))
        self._select("#tiku-submit").value = str(tiku.get("submit", "false")).lower()
        self._input("#tiku-cover-rate").value = str(tiku.get("cover_rate", "0.9"))
        self._input("#tiku-delay").value = str(tiku.get("delay", "1.0"))

        self._input("#notification-provider").value = str(notification.get("provider", ""))
        self._input("#notification-url").value = str(notification.get("url", ""))
        self._input("#notification-chat-id").value = str(notification.get("tg_chat_id", ""))

    def _collect_config(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        common = {
            "username": self._input("#username").value.strip(),
            "password": self._input("#password").value.strip(),
            "use_cookies": self._checkbox("#use-cookies").value,
            "remember_password": self._checkbox("#remember-password").value,
            "course_list": _csv_items(self._input("#course-list").value),
            "speed": self._input("#speed").value.strip() or "1.0",
            "jobs": self._input("#jobs").value.strip() or "4",
            "notopen_action": self._select("#notopen-action").value or "retry",
        }
        tiku = {
            "provider": self._input("#tiku-provider").value.strip(),
            "tokens": self._input("#tiku-tokens").value.strip(),
            "submit": self._select("#tiku-submit").value or "false",
            "cover_rate": self._input("#tiku-cover-rate").value.strip() or "0.9",
            "delay": self._input("#tiku-delay").value.strip() or "1.0",
        }
        notification = {
            "provider": self._input("#notification-provider").value.strip(),
            "url": self._input("#notification-url").value.strip(),
            "tg_chat_id": self._input("#notification-chat-id").value.strip(),
        }
        return common, tiku, notification

    def action_save_config(self) -> None:
        self._save_config()

    def _save_config(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        common, tiku, notification = self._collect_config()
        save_config_to_file(self.config_path, common, tiku, notification)
        self._append_log(f"配置已保存: {self.config_path}")
        return common, tiku, notification

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self._save_config()
        elif event.button.id == "load-courses":
            common, tiku, _ = self._save_config()
            self._run_thread(self._load_courses_worker, common, tiku)
        elif event.button.id == "run":
            if self._running:
                self._append_log("已有任务正在运行")
                return
            common, tiku, notification = self._save_config()
            self._running = True
            self._run_thread(self._run_worker, common, tiku, notification)
        elif event.button.id == "quit":
            self.exit()

    def _run_thread(self, target, *args) -> None:
        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.start()

    def _load_courses_worker(self, common: dict[str, Any], tiku: dict[str, Any]) -> None:
        try:
            from main import init_chaoxing

            chaoxing = init_chaoxing(common, tiku, allow_prompt=False)
            login_state = chaoxing.login(login_with_cookies=common.get("use_cookies", False))
            if not login_state["status"]:
                self.call_from_thread(self._append_log, f"登录失败: {login_state['msg']}")
                return
            courses = chaoxing.get_course_list()
            self.call_from_thread(self._populate_courses, courses)
        except Exception as exc:
            self.call_from_thread(self._append_log, f"刷新课程失败: {type(exc).__name__}: {exc}")

    def _populate_courses(self, courses: list[dict[str, Any]]) -> None:
        table = self.query_one("#course-table", DataTable)
        table.clear()
        for course in courses:
            table.add_row(str(course.get("courseId", "")), str(course.get("title", "")))
        self._append_log(f"已读取课程数量: {len(courses)}")

    def _run_worker(self, common: dict[str, Any], tiku: dict[str, Any], notification: dict[str, Any]) -> None:
        try:
            from main import run_study

            run_study(common, tiku, notification, event_sink=self._event_sink, allow_prompt=False)
        except Exception as exc:
            self.call_from_thread(self._append_log, f"运行失败: {type(exc).__name__}: {exc}")
        finally:
            self.call_from_thread(self._set_running, False)

    def _set_running(self, value: bool) -> None:
        self._running = value

    def _event_sink(self, event: StudyEvent) -> None:
        if event.kind == "job_progress":
            title = event.title or event.key
            self.call_from_thread(
                self._append_log,
                f"{title}: {event.completed}/{event.total}",
            )
        elif event.message:
            self.call_from_thread(self._append_log, event.message)


def run_tui(config_path: str | Path | None = None):
    ChaoxingTui(config_path=config_path).run()
