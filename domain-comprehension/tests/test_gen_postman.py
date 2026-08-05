"""Tests for templates/postman/gen_postman.py"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "templates" / "postman"))

from gen_postman import (  # noqa: E402
    build_environment,
    generate_env_file,
    main,
    patch_collection,
)


def _defaults() -> dict:
    return {
        "active_env": "qa",
        "envs": {
            "qa": {
                "baseUrl": "https://qa-api.example.com/bff/svc",
                "appVersion": "1.0.0",
                "versionCode": "100",
            },
            "uat": {
                "baseUrl": "https://uat-api.example.com/bff/svc",
                "appVersion": "2.0.0",
                "versionCode": "200",
            },
        },
    }


def test_build_environment_structure() -> None:
    env = build_environment("qa", _defaults()["envs"]["qa"])
    assert env["name"] == "qa"
    assert env["_postman_variable_scope"] == "environment"
    values_by_key = {v["key"]: v for v in env["values"]}
    assert values_by_key["baseUrl"]["value"] == "https://qa-api.example.com/bff/svc"
    assert values_by_key["baseUrl"]["enabled"] is True
    assert values_by_key["appVersion"]["type"] == "default"


def test_generate_env_file_writes_valid_json(tmp_path: Path) -> None:
    out_path = generate_env_file(_defaults(), "qa", tmp_path)
    assert out_path == tmp_path / "postman_environment.qa.json"
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["name"] == "qa"


def test_generate_env_file_unknown_env_raises(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        generate_env_file(_defaults(), "staging", tmp_path)


def test_patch_collection_updates_existing_variable() -> None:
    collection = {
        "variable": [
            {"key": "appVersion", "value": "0.0.0", "type": "string"},
            {"key": "baseUrl", "value": "unchanged", "type": "string"},
        ]
    }
    patched = patch_collection(_defaults(), collection)
    by_key = {v["key"]: v for v in patched["variable"]}
    assert by_key["appVersion"]["value"] == "1.0.0"
    assert by_key["baseUrl"]["value"] == "unchanged"


def test_patch_collection_adds_missing_variable() -> None:
    collection = {"variable": [{"key": "appVersion", "value": "0.0.0", "type": "string"}]}
    patched = patch_collection(_defaults(), collection)
    keys = {v["key"] for v in patched["variable"]}
    assert "versionCode" in keys
    by_key = {v["key"]: v for v in patched["variable"]}
    assert by_key["versionCode"]["value"] == "100"


def test_patch_collection_missing_active_env_raises() -> None:
    defaults = {"envs": {"qa": {"appVersion": "1.0.0"}}}
    with pytest.raises(KeyError):
        patch_collection(defaults, {"variable": []})


def test_patch_collection_unknown_active_env_raises() -> None:
    defaults = {"active_env": "staging", "envs": {"qa": {"appVersion": "1.0.0"}}}
    with pytest.raises(KeyError):
        patch_collection(defaults, {"variable": []})


def test_main_all_generates_every_env_file(tmp_path: Path) -> None:
    defaults_path = tmp_path / "environment.defaults.json"
    defaults_path.write_text(json.dumps(_defaults()), encoding="utf-8")
    exit_code = main(["--all", "--defaults", str(defaults_path), "--out-dir", str(tmp_path)])
    assert exit_code == 0
    assert (tmp_path / "postman_environment.qa.json").is_file()
    assert (tmp_path / "postman_environment.uat.json").is_file()


def test_main_patch_collection(tmp_path: Path) -> None:
    defaults_path = tmp_path / "environment.defaults.json"
    defaults_path.write_text(json.dumps(_defaults()), encoding="utf-8")
    collection_path = tmp_path / "postman_collection.json"
    collection_path.write_text(json.dumps({"variable": []}), encoding="utf-8")

    exit_code = main(
        [
            "--patch-collection",
            "--defaults",
            str(defaults_path),
            "--collection",
            str(collection_path),
        ]
    )
    assert exit_code == 0
    patched = json.loads(collection_path.read_text(encoding="utf-8"))
    by_key = {v["key"]: v for v in patched["variable"]}
    assert by_key["appVersion"]["value"] == "1.0.0"


def test_main_no_flags_prints_help_and_returns_1(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "usage" in captured.out.lower()


def test_main_missing_defaults_file_returns_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--all", "--defaults", str(tmp_path / "nope.json"), "--out-dir", str(tmp_path)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err
