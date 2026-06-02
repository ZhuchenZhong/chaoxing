# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
from contextlib import suppress
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, DataTable, Footer, Header, Input, Label, RichLog, Select

from api.config_store import default_cookie_path, ensure_config_file, load_config_from_file, save_config_to_file
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

    #main-view, #config-panel {
        height: 1fr;
    }

    #config-panel {
        display: none;
    }

    .form {
        padding: 1 2;
    }

    .row {
        height: auto;
        margin-bottom: 1;
    }

    .section-title {
        height: auto;
        padding-top: 1;
        margin-bottom: 1;
        text-style: bold;
    }

    .status {
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
        min-width: 10;
    }

    #course-table {
        height: 1fr;
        min-height: 8;
    }

    #run-log {
        height: 11;
        min-height: 8;
    }
    """

    BINDINGS = [
        ("enter", "primary", "登录/刷新"),
        ("space", "toggle_course", "选课"),
        ("f2", "toggle_config", "配置"),
        ("ctrl+l", "logout", "退出登录"),
        ("ctrl+s", "save_config", "保存配置"),
        ("ctrl+q", "quit", "退出"),
    ]

    def __init__(self, config_path: str | Path | None = None):
        super().__init__()
        self.config_path = ensure_config_file(config_path)
        self._running = False
        self._loading = False
        self._logged_in = False
        self._chaoxing: Any | None = None
        self._courses: list[dict[str, Any]] = []
        self._selected_course_ids: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main-view", classes="form"):
            yield Label(f"配置文件: {self.config_path}", classes="status")
            with Horizontal(classes="row"):
                yield Label("手机号")
                yield Input(id="username", placeholder="手机号")
                yield Label("密码")
                yield Input(id="password", placeholder="密码", password=True)
            with Horizontal(classes="row"):
                yield Checkbox("使用 Cookie 登录", id="use-cookies")
                yield Checkbox("记住密码并写入 config.ini", id="remember-password")
            with Horizontal(classes="row"):
                yield Button("登录/刷新", id="login-refresh", variant="primary")
                yield Button("开始刷课", id="run", variant="success")
                yield Button("退出登录", id="logout")
                yield Button("配置", id="config")
                yield Button("退出", id="quit")
            yield Label("未登录。输入账号密码后按 Enter 刷新课程列表。", id="status", classes="status")
            yield DataTable(id="course-table")
            yield RichLog(id="run-log", wrap=True)

        with Vertical(id="config-panel", classes="form"):
            yield Label("配置", classes="section-title")
            yield Label(f"配置文件: {self.config_path}", classes="status")
            with Horizontal(classes="row"):
                yield Button("保存配置", id="save", variant="primary")
                yield Button("清除 Cookie", id="clear-cookies")
                yield Button("返回", id="back")
            yield Label("运行配置", classes="section-title")
            with Horizontal(classes="row"):
                yield Label("课程 ID")
                yield Input(id="course-list", placeholder="通常由主界面选课自动写入；留空则学习全部")
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

            yield Label("题库 / API Key", classes="section-title")
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

            yield Label("通知", classes="section-title")
            with Horizontal(classes="row"):
                yield Label("Provider")
                yield Input(id="notification-provider", placeholder="ServerChan")
            with Horizontal(classes="row"):
                yield Label("URL")
                yield Input(id="notification-url")
            with Horizontal(classes="row"):
                yield Label("Telegram Chat")
                yield Input(id="notification-chat-id")
        yield Footer()

    def on_mount(self) -> None:
        configure_logging(console_enabled=False, tui_sink=self._log_sink)
        self._setup_tables()
        self._load_fields()

    def _setup_tables(self) -> None:
        table = self.query_one("#course-table", DataTable)
        table.cursor_type = "row"
        table.add_column("选", key="selected", width=4)
        table.add_column("课程ID", key="course_id", width=16)
        table.add_column("课程名", key="title")

    def _log_sink(self, message) -> None:
        text = str(message).rstrip()
        if text:
            self.call_from_thread(self._append_log, text)

    def _append_log(self, text: str) -> None:
        self.query_one("#run-log", RichLog).write(text)

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Label).update(text)

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
        self._selected_course_ids = set(common.get("course_list") or [])
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

    def _ordered_selected_course_ids(self) -> list[str]:
        loaded_ids = [str(course.get("courseId", "")) for course in self._courses]
        selected = [course_id for course_id in loaded_ids if course_id in self._selected_course_ids]
        selected.extend(sorted(self._selected_course_ids - set(selected)))
        return selected

    def _sync_course_input(self) -> None:
        self._input("#course-list").value = ",".join(self._ordered_selected_course_ids())

    def _collect_config(self, course_list: list[str] | None = None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        if course_list is None:
            selected_course_list = _csv_items(self._input("#course-list").value)
        else:
            selected_course_list = course_list

        common = {
            "username": self._input("#username").value.strip(),
            "password": self._input("#password").value.strip(),
            "use_cookies": self._checkbox("#use-cookies").value,
            "remember_password": self._checkbox("#remember-password").value,
            "course_list": selected_course_list,
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

    def _save_config(self, course_list: list[str] | None = None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        common, tiku, notification = self._collect_config(course_list=course_list)
        save_config_to_file(self.config_path, common, tiku, notification)
        self._append_log(f"配置已保存: {self.config_path}")
        return common, tiku, notification

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in {"username", "password"}:
            self._login_and_refresh()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "course-table":
            self._toggle_course_at_row(event.cursor_row)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "login-refresh":
            self._login_and_refresh()
        elif button_id == "run":
            self._start_run()
        elif button_id == "logout":
            self._logout()
        elif button_id == "config":
            self._show_config(True)
        elif button_id == "save":
            self._save_config()
        elif button_id == "clear-cookies":
            self._clear_cookies()
        elif button_id == "back":
            self._show_config(False)
        elif button_id == "quit":
            self.exit()

    def action_primary(self) -> None:
        if self.query_one("#config-panel").display:
            self._save_config()
            self._show_config(False)
            return
        focused = self.focused
        if focused and focused.id == "course-table":
            self.action_toggle_course()
            return
        self._login_and_refresh()

    def action_toggle_course(self) -> None:
        if self.query_one("#config-panel").display:
            return
        table = self.query_one("#course-table", DataTable)
        if table.row_count == 0:
            return
        self._toggle_course_at_row(table.cursor_row)

    def action_toggle_config(self) -> None:
        panel = self.query_one("#config-panel")
        self._show_config(not panel.display)

    def action_logout(self) -> None:
        self._logout()

    def _show_config(self, show: bool) -> None:
        self._sync_course_input()
        self.query_one("#main-view").display = not show
        self.query_one("#config-panel").display = show
        if show:
            self._append_log("已打开配置面板")
        else:
            self._append_log("已返回主流程")

    def _run_thread(self, target, *args) -> None:
        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.start()

    def _login_and_refresh(self) -> None:
        if self._loading:
            self._append_log("正在登录并刷新课程")
            return
        if self._running:
            self._append_log("刷课运行中，暂不能刷新课程")
            return

        common, tiku, _ = self._save_config()
        self._loading = True
        self._set_status("正在登录并刷新课程...")
        self._append_log("正在登录并刷新课程")
        self._run_thread(self._load_courses_worker, common, tiku)

    def _load_courses_worker(self, common: dict[str, Any], tiku: dict[str, Any]) -> None:
        try:
            from main import init_chaoxing

            chaoxing = init_chaoxing(common, tiku, allow_prompt=False)
            login_state = chaoxing.login(login_with_cookies=common.get("use_cookies", False))
            if not login_state["status"]:
                self.call_from_thread(self._finish_login_failed, f"登录失败: {login_state['msg']}")
                return
            courses = chaoxing.get_course_list()
            self.call_from_thread(self._finish_login_success, chaoxing, courses)
        except Exception as exc:
            self.call_from_thread(self._finish_login_failed, f"刷新课程失败: {type(exc).__name__}: {exc}")

    def _finish_login_success(self, chaoxing: Any, courses: list[dict[str, Any]]) -> None:
        self._loading = False
        self._logged_in = True
        self._chaoxing = chaoxing
        self._populate_courses(courses)
        self._set_status(f"已登录，已读取 {len(courses)} 门课程。选择课程后点击开始刷课。")

    def _finish_login_failed(self, message: str) -> None:
        self._loading = False
        self._logged_in = False
        self._set_status(message)
        self._append_log(message)

    def _populate_courses(self, courses: list[dict[str, Any]]) -> None:
        self._courses = courses
        loaded_course_ids = {str(course.get("courseId", "")) for course in courses}
        self._selected_course_ids.intersection_update(loaded_course_ids)
        table = self.query_one("#course-table", DataTable)
        table.clear()
        for course in courses:
            course_id = str(course.get("courseId", ""))
            table.add_row(
                self._selection_mark(course_id),
                course_id,
                str(course.get("title", "")),
                key=course_id,
            )
        self._sync_course_input()
        self._append_log(f"已读取课程数量: {len(courses)}")

    def _selection_mark(self, course_id: str) -> str:
        return "[x]" if course_id in self._selected_course_ids else "[ ]"

    def _toggle_course_at_row(self, row_index: int) -> None:
        table = self.query_one("#course-table", DataTable)
        if row_index < 0 or row_index >= table.row_count:
            return
        row = table.get_row_at(row_index)
        course_id = str(row[1])
        if course_id in self._selected_course_ids:
            self._selected_course_ids.remove(course_id)
            self._append_log(f"取消选择课程: {course_id}")
        else:
            self._selected_course_ids.add(course_id)
            self._append_log(f"选择课程: {course_id}")
        table.update_cell(course_id, "selected", self._selection_mark(course_id))
        self._sync_course_input()

    def _start_run(self) -> None:
        if self._running:
            self._append_log("已有任务正在运行")
            return
        if not self._logged_in or not self._courses:
            self._append_log("请先登录并刷新课程列表")
            self._set_status("请先登录并刷新课程列表")
            return

        selected = self._ordered_selected_course_ids()
        if not selected:
            self._append_log("未选择课程，将学习全部已加载课程")
        common, tiku, notification = self._save_config(course_list=selected or [])
        common["course_list"] = selected or None
        self._running = True
        self._set_status("正在刷课...")
        self._run_thread(self._run_worker, common, tiku, notification)

    def _run_worker(self, common: dict[str, Any], tiku: dict[str, Any], notification: dict[str, Any]) -> None:
        try:
            from main import run_study

            run_study(common, tiku, notification, event_sink=self._event_sink, allow_prompt=False)
            self.call_from_thread(self._finish_run, True, "刷课完成")
        except Exception as exc:
            self.call_from_thread(self._append_log, f"运行失败: {type(exc).__name__}: {exc}")
            self.call_from_thread(self._finish_run, False, f"运行失败: {type(exc).__name__}: {exc}")

    def _finish_run(self, success: bool, message: str) -> None:
        self._running = False
        if success:
            self._set_status("刷课完成")
        elif self._logged_in:
            self._set_status("已登录，运行失败")
        else:
            self._set_status("运行失败")
        self._append_log(message)

    def _logout(self) -> None:
        self._logged_in = False
        self._loading = False
        self._chaoxing = None
        self._courses = []
        self._selected_course_ids.clear()
        self.query_one("#course-table", DataTable).clear()
        self._sync_course_input()
        if not self._checkbox("#remember-password").value:
            self._input("#password").value = ""
        self._set_status("已退出登录")
        self._append_log("已退出登录")

    def _clear_cookies(self) -> None:
        with suppress(FileNotFoundError):
            default_cookie_path().unlink()
        self._logout()
        self._append_log(f"Cookie 已清除: {default_cookie_path()}")

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
