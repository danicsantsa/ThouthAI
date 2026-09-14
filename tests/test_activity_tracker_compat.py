import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / 'activity_tracker.py'

spec = importlib.util.spec_from_file_location('activity_tracker', MODULE_PATH)
activity_tracker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activity_tracker)


def test_platform_support_check_exists():
    assert hasattr(activity_tracker, 'activity_tracking_available')
    assert isinstance(activity_tracker.activity_tracking_available(), bool)


def test_non_linux_reports_unavailable_when_not_gnome():
    if activity_tracker.platform.system() != 'Linux':
        assert activity_tracker.activity_tracking_available() is False
