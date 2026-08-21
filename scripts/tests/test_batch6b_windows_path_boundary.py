"""Windows path-boundary regressions for the test-creator write guard."""

from scripts import test_creator_write_guard as guard


def test_windows_alternate_data_stream_component_is_unsafe() -> None:
    assert guard._windows_path_component_is_unsafe("tracked.py:hidden")
    assert guard._windows_path_component_is_unsafe("tracked.py::$DATA")
    assert not guard._windows_path_component_is_unsafe("tracked.py")


def test_windows_trailing_space_or_period_component_is_unsafe() -> None:
    assert guard._windows_path_component_is_unsafe("tracked.py.")
    assert guard._windows_path_component_is_unsafe("tracked.py ")
    assert not guard._windows_path_component_is_unsafe(".tracked.py")


def test_windows_reserved_device_component_is_unsafe() -> None:
    for component in (
        "CON",
        "prn.txt",
        "AUX.log",
        "nul.tar.gz",
        "NUL  .txt",
        "COM1",
        "COM1 .log",
        "com9.txt",
        "LPT1",
        "lpt9.out",
        "COM¹",
        "LPT³.txt",
        "CONIN$",
        "conout$.txt",
    ):
        assert guard._windows_path_component_is_unsafe(component), component

    assert not guard._windows_path_component_is_unsafe("COM10")
    assert not guard._windows_path_component_is_unsafe("nulled.txt")
