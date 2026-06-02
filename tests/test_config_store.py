# -*- coding: utf-8 -*-
from __future__ import annotations

import configparser
import os
import tempfile
import unittest
from pathlib import Path


class ConfigStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("CHAOXING_HOME")
        os.environ["CHAOXING_HOME"] = self.tmp.name

    def tearDown(self):
        if self.old_home is None:
            os.environ.pop("CHAOXING_HOME", None)
        else:
            os.environ["CHAOXING_HOME"] = self.old_home
        self.tmp.cleanup()

    def test_default_config_is_created_under_user_home(self):
        from api.config_store import ensure_config_file

        path = ensure_config_file()

        self.assertEqual(path.parent, Path(self.tmp.name).resolve())
        self.assertTrue(path.exists())
        self.assertEqual(path.name, "config.ini")

    def test_save_config_clears_password_when_not_remembered(self):
        from api.config_store import load_config_from_file, save_config_to_file

        path = Path(self.tmp.name) / "config.ini"
        save_config_to_file(
            path,
            {
                "username": "18800000000",
                "password": "secret",
                "remember_password": False,
                "course_list": ["101", "202"],
                "speed": 2,
                "jobs": 6,
                "notopen_action": "continue",
            },
            {"provider": "TikuYanxi", "cover_rate": 0.8},
            {"provider": "ServerChan", "url": "https://example.test"},
        )

        parser = configparser.ConfigParser()
        parser.read(path, encoding="utf8")

        self.assertEqual(parser.get("common", "password"), "")
        self.assertEqual(parser.get("common", "course_list"), "101,202")
        common, tiku, notification = load_config_from_file(path)
        self.assertEqual(common["course_list"], ["101", "202"])
        self.assertEqual(common["speed"], 2.0)
        self.assertEqual(common["jobs"], 6)
        self.assertEqual(common["notopen_action"], "continue")
        self.assertEqual(tiku["cover_rate"], 0.8)
        self.assertEqual(notification["provider"], "ServerChan")

    def test_save_config_keeps_password_when_remembered(self):
        from api.config_store import save_config_to_file

        path = Path(self.tmp.name) / "config.ini"
        save_config_to_file(
            path,
            {"username": "18800000000", "password": "secret", "remember_password": True},
            {},
            {},
        )

        parser = configparser.ConfigParser()
        parser.read(path, encoding="utf8")
        self.assertEqual(parser.get("common", "password"), "secret")
        self.assertEqual(parser.get("common", "remember_password"), "true")

    def test_fallback_config_paths_follow_user_home(self):
        from api.config_store import default_config_path, default_cookie_path, default_log_path

        root = Path(self.tmp.name).resolve()
        self.assertEqual(default_config_path(), root / "config.ini")
        self.assertEqual(default_cookie_path(), root / "cookies" / "default.txt")
        self.assertEqual(default_log_path(), root / "logs" / "chaoxing.log")


if __name__ == "__main__":
    unittest.main()
