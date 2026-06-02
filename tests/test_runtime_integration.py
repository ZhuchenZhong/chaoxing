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

    def test_cli_default_runs_legacy_cli(self):
        import chaoxing_cli

        with patch("main.main") as legacy_main:
            chaoxing_cli.main([])

        legacy_main.assert_called_once_with(default_tui=False)

    def test_init_config_without_config_does_not_create_default_config(self):
        import main

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.ini"
            with patch.dict(os.environ, {"CHAOXING_HOME": tmp}), patch("sys.argv", ["main.py"]):
                common, tiku, notification = main.init_config()

            self.assertFalse(config_path.exists())
            self.assertIsNone(common["username"])
            self.assertIsNone(common["password"])
            self.assertEqual(common["course_list"], None)
            self.assertEqual(tiku, {})
            self.assertEqual(notification, {})

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

    async def test_tui_course_selection_saves_selected_courses(self):
        from api.config_store import load_config_from_file
        from api.tui import ChaoxingTui

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.ini"
            app = ChaoxingTui(config_path=config_path)
            async with app.run_test():
                app._populate_courses([
                    {"courseId": "101", "title": "Course A"},
                    {"courseId": "202", "title": "Course B"},
                ])
                app._toggle_course_at_row(1)
                app._save_config()

            common, _, _ = load_config_from_file(config_path)
            self.assertEqual(common["course_list"], ["202"])

    async def test_tui_config_panel_toggles_from_main_flow(self):
        from api.tui import ChaoxingTui

        with tempfile.TemporaryDirectory() as tmp:
            app = ChaoxingTui(config_path=Path(tmp) / "config.ini")
            async with app.run_test():
                app._show_config(True)
                self.assertFalse(app.query_one("#main-view").display)
                self.assertTrue(app.query_one("#config-panel").display)

                app._show_config(False)
                self.assertTrue(app.query_one("#main-view").display)
                self.assertFalse(app.query_one("#config-panel").display)

    async def test_tui_logout_clears_session_state(self):
        from textual.widgets import Checkbox, DataTable, Input

        from api.tui import ChaoxingTui

        with tempfile.TemporaryDirectory() as tmp:
            app = ChaoxingTui(config_path=Path(tmp) / "config.ini")
            async with app.run_test():
                app.query_one("#password", Input).value = "secret"
                app.query_one("#remember-password", Checkbox).value = False
                app._populate_courses([{"courseId": "101", "title": "Course A"}])
                app._toggle_course_at_row(0)
                app._logged_in = True

                app._logout()

                self.assertFalse(app._logged_in)
                self.assertEqual(app._courses, [])
                self.assertEqual(app._selected_course_ids, set())
                self.assertEqual(app.query_one("#password", Input).value, "")
                self.assertEqual(app.query_one("#course-list", Input).value, "")
                self.assertEqual(app.query_one("#course-table", DataTable).row_count, 0)
