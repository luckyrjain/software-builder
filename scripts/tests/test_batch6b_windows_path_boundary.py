"""Windows path-boundary regressions for the test-creator write guard."""

from scripts import test_creator_write_guard as guard


def test_windows_alternate_data_stream_component_is_unsafe() -> None:
    assert guard._windows_path_component_is_unsafe("tracked.py:hidden")
    assert guard._windows_path_component_is_unsafe("tracked.py::$DATA")
    assert not guard._windows_path_component_is_unsafe("tracked.py")
