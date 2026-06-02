# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class RuntimeIntegrationTest(unittest.TestCase):
    def test_filter_courses_non_interactive_blank_means_all_courses(self):
        from main import filter_courses

        courses = [
            {"courseId": "1", "title": "A"},
            {"courseId": "2", "title": "B"},
        ]

        self.assertEqual(filter_courses(courses, None, allow_prompt=False), courses)
        self.assertEqual(filter_courses(courses, [], allow_prompt=False), courses)

    def test_filter_courses_keeps_requested_order_from_course_list(self):
        from main import filter_courses

        courses = [
            {"courseId": "1", "title": "A"},
            {"courseId": "2", "title": "B"},
        ]

        self.assertEqual(filter_courses(courses, ["2"], allow_prompt=False), [courses[1]])

    def test_cli_tui_command_imports_tui_runner(self):
        import chaoxing_cli

        with patch("api.tui.run_tui") as run_tui:
            chaoxing_cli.main(["tui"])

        run_tui.assert_called_once()

    def test_tui_module_imports(self):
        module = importlib.import_module("api.tui")

        self.assertTrue(hasattr(module, "ChaoxingTui"))

    def test_rich_display_completes_started_task(self):
        from rich.console import Console

        from api.events import StudyEvent
        from api.rich_ui import RichStudyDisplay

        console = Console(record=True, force_terminal=False)
        with RichStudyDisplay(console=console) as display:
            display(StudyEvent(kind="job_start", title="Video", key="v1", total=10, completed=2))
            display(StudyEvent(kind="job_progress", title="Video", key="v1", total=10, completed=5))
            display(StudyEvent(kind="job_done", title="Video", key="v1", status="SUCCESS"))

        output = console.export_text()
        self.assertIn("任务完成: Video", output)


if __name__ == "__main__":
    unittest.main()


class TuiSaveIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_tui_mounts_and_saves_config_ini(self):
        from textual.widgets import Checkbox, Input

        from api.config_store import load_config_from_file
        from api.tui import ChaoxingTui

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.ini"
            app = ChaoxingTui(config_path=config_path)
            async with app.run_test():
                app.query_one("#username", Input).value = "18800000000"
                app.query_one("#password", Input).value = "secret"
                app.query_one("#course-list", Input).value = "101,202"
                app.query_one("#remember-password", Checkbox).value = False
                app._save_config()

            common, _, _ = load_config_from_file(config_path)
            self.assertEqual(common["username"], "18800000000")
            self.assertEqual(common["password"], "")
            self.assertEqual(common["course_list"], ["101", "202"])
