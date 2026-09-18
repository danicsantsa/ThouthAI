import importlib
import os
import sys
import unittest
from unittest.mock import patch

import activity_tracker
import capturesuite_qt_new
import track_all
import tracking_gui
from PySide6.QtWidgets import QApplication
from session_mode_logic import evaluate_session_mode


class SessionModeTests(unittest.TestCase):
    def test_normalize_session_mode(self):
        self.assertEqual(tracking_gui.normalize_session_mode("standard"), "standard")
        self.assertEqual(tracking_gui.normalize_session_mode("focus"), "focus")
        self.assertEqual(tracking_gui.normalize_session_mode("hyperfocus"), "hyperfocus")
        self.assertEqual(tracking_gui.normalize_session_mode("FOKUS"), "focus")
        self.assertEqual(tracking_gui.normalize_session_mode(None), "standard")

    def test_focus_alerts_on_distraction(self):
        result = evaluate_session_mode("focus", "Nicht-Arbeit", idle_seconds=45, app_name="youtube")
        self.assertTrue(result["alert"])
        self.assertIn("Ablenkungsquelle", result["reason"])
        self.assertEqual(result["status"], "warning")

        hyper = evaluate_session_mode("hyperfocus", "Nicht-Arbeit", idle_seconds=5, app_name="spotify", allowed_app="code")
        self.assertTrue(hyper["alert"])
        self.assertTrue(hyper["soft_pause"])
        self.assertEqual(hyper["status"], "critical")

        allowed = evaluate_session_mode("hyperfocus", "Arbeit", idle_seconds=0, app_name="code", allowed_app="code")
        self.assertFalse(allowed["alert"])
        self.assertFalse(allowed["soft_pause"])

    def test_default_camera_prefers_linux_working_index(self):
        original_argv = sys.argv[:]
        try:
            sys.argv = ["track_all.py", "--user", "TestUser"]
            args = track_all.parse_args()
            self.assertEqual(args.camera, 1)
        finally:
            sys.argv = original_argv

    def test_hyperfocus_app_blocking_and_refocus(self):
        self.assertTrue(activity_tracker.app_matches_allowed("code", "code"))
        self.assertTrue(activity_tracker.app_matches_allowed("Visual Studio Code", "code"))
        self.assertFalse(activity_tracker.app_matches_allowed("spotify", "code"))

        with patch("activity_tracker.subprocess.run") as mock_run:
            mock_run.return_value = None
            activity_tracker.activate_allowed_hyperfocus_app("code")
            self.assertTrue(mock_run.called)

    def test_qt_hyperfocus_mode_starts_with_standard_and_toggle(self):
        app = QApplication.instance() or QApplication([])
        window = capturesuite_qt_new.MainWindow()
        window.show()
        app.processEvents()
        self.assertTrue(window.mode_buttons["standard"].isChecked())
        self.assertFalse(window.app_picker.isVisible())
        self.assertEqual(window.session_tag.text(), "Modus: Standard")
        window._on_mode_changed("hyperfocus")
        self.assertTrue(window.mode_buttons["hyperfocus"].isChecked())
        self.assertTrue(window.app_picker.isVisible())
        self.assertEqual(window.session_tag.text(), "Modus: Hyperfokus")
        window._on_mode_changed("standard")
        self.assertFalse(window.app_picker.isVisible())

    def test_mode_switch_stops_session_timer(self):
        app = QApplication.instance() or QApplication([])
        window = capturesuite_qt_new.MainWindow()
        window.show()
        app.processEvents()

        window._on_start()
        self.assertTrue(window.timer.isActive())
        self.assertEqual(window.state_text.text(), "Sitzung läuft")

        window._on_mode_changed("focus")
        self.assertFalse(window.timer.isActive())
        self.assertEqual(window.state_text.text(), "Bereit")

    def test_standard_mode_does_not_start_tracking_process(self):
        proc = tracking_gui.TrackingProcess()
        settings = {"user": "Tester", "camera": 1, "rotate": 0, "check_interval": 3, "db_flush_interval": 2,
                    "work_apps": "code", "non_work_apps": "spotify", "session_mode": "standard"}
        proc.start(settings, mode="standard")
        self.assertIsNone(proc.proc)
        self.assertEqual(proc.state, "idle")

    def test_focus_and_hyperfocus_start_tracking_worker(self):
        app = QApplication.instance() or QApplication([])
        window = capturesuite_qt_new.MainWindow()
        window.show()
        app.processEvents()

        window._on_mode_changed("focus")
        window._on_start()
        self.assertEqual(window.session_mode, "focus")
        self.assertIsNotNone(window.tracker.proc)
        self.assertEqual(window.tracker.state, "running")
        window.tracker.stop()

        window._on_mode_changed("hyperfocus")
        window.selected_apps = ["code"]
        window._on_start()
        self.assertEqual(window.session_mode, "hyperfocus")
        self.assertIsNotNone(window.tracker.proc)
        self.assertEqual(window.tracker.state, "running")
        window.tracker.stop()

    def test_hyperfocus_dialog_lists_real_apps(self):
        apps = capturesuite_qt_new.AppSelectionDialog._discover_apps()
        self.assertTrue(len(apps) >= 4)
        self.assertNotEqual(apps, ["Notion", "VS Code", "Word", "PDF-Reader"])

    def test_hyperfocus_dialog_shows_only_four_visible_apps(self):
        app = QApplication.instance() or QApplication([])
        dialog = capturesuite_qt_new.AppSelectionDialog(None, checked_apps={"VS Code"})
        app.processEvents()
        self.assertEqual(len(dialog.primary_checks), 4)
        self.assertGreaterEqual(len(dialog.checks), 4)
        self.assertLess(len(dialog.primary_checks), len(dialog.checks))

    def test_hyperfocus_box_is_hidden(self):
        app = QApplication.instance() or QApplication([])
        window = capturesuite_qt_new.MainWindow()
        window.show()
        app.processEvents()

        self.assertFalse(window.hyperfocus_hint_box.isVisible())
        window._on_mode_changed("hyperfocus")
        self.assertFalse(window.hyperfocus_hint_box.isVisible())
        self.assertEqual(window.hyperfocus_message.text(), "")

    def test_hyperfocus_camera_guidance_references_live_observation(self):
        app = QApplication.instance() or QApplication([])
        window = capturesuite_qt_new.MainWindow()
        window.show()
        app.processEvents()

        text = window._camera_observation_message(face_detected=True, looking_away=False, blink_detected=False)
        self.assertIn("Kamera", text)
        self.assertIn("Blick", text)
        self.assertNotIn("Pause", text)
        self.assertNotIn("Lernen", text)

        away_text = window._camera_observation_message(face_detected=True, looking_away=True, blink_detected=False)
        self.assertIn("abgelenkt", away_text.lower())

    def test_default_database_mode_uses_supabase_unless_explicitly_disabled(self):
        original_env = os.environ.get("ATUM_USE_SUPABASE")
        os.environ.pop("ATUM_USE_SUPABASE", None)
        try:
            import db_client
            importlib.reload(db_client)
            self.assertTrue(db_client.USE_SUPABASE)
        finally:
            if original_env is None:
                os.environ.pop("ATUM_USE_SUPABASE", None)
            else:
                os.environ["ATUM_USE_SUPABASE"] = original_env
            importlib.reload(db_client)


if __name__ == "__main__":
    unittest.main()
