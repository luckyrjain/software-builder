#!/usr/bin/env python3
"""Regenerate postman_environment.<env>.json files and patch collection variables
from environment.defaults.json. See ../../reference/api-tooling-integration.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULTS_PATH = HERE / "environment.defaults.json"
COLLECTION_PATH = HERE / "postman_collection.json"

# Collection variables this script is allowed to patch — anything else in
# postman_collection.json is hand-authored and left untouched.
PATCHABLE_COLLECTION_KEYS = ("appVersion", "versionCode")


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def build_environment(env_name: str, env_config: dict[str, Any]) -> dict[str, Any]:
    """Build a Postman environment JSON structure for one env block."""
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"postman-env-{env_name}")),
        "name": env_name,
        "values": [
            {"key": key, "value": str(value), "type": "default", "enabled": True}
            for key, value in env_config.items()
        ],
        "_postman_variable_scope": "environment",
    }


def generate_env_file(defaults: dict[str, Any], env_name: str, out_dir: Path) -> Path:
    envs = defaults.get("envs", {})
    if env_name not in envs:
        raise KeyError(f"no '{env_name}' block in environment.defaults.json envs")
    env_json = build_environment(env_name, envs[env_name])
    out_path = out_dir / f"postman_environment.{env_name}.json"
    _write_json(out_path, env_json)
    return out_path


def patch_collection(defaults: dict[str, Any], collection: dict[str, Any]) -> dict[str, Any]:
    """Sync PATCHABLE_COLLECTION_KEYS in collection['variable'] from the active env's defaults."""
    active_env = defaults.get("active_env")
    if not active_env:
        raise KeyError("environment.defaults.json missing 'active_env'")
    envs = defaults.get("envs", {})
    if active_env not in envs:
        raise KeyError(f"active_env '{active_env}' has no block in envs")
    active_values = envs[active_env]

    variables = collection.setdefault("variable", [])
    existing_by_key = {v.get("key"): v for v in variables if isinstance(v, dict)}
    for key in PATCHABLE_COLLECTION_KEYS:
        if key not in active_values:
            continue
        value = str(active_values[key])
        if key in existing_by_key:
            existing_by_key[key]["value"] = value
        else:
            variables.append({"key": key, "value": value, "type": "string"})
    return collection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", help="Generate postman_environment.<env>.json for one env")
    parser.add_argument("--all", action="store_true", help="Generate for every env in environment.defaults.json")
    parser.add_argument(
        "--patch-collection",
        action="store_true",
        help="Sync appVersion/versionCode into postman_collection.json from active_env",
    )
    parser.add_argument("--defaults", type=Path, default=DEFAULTS_PATH, help="Path to environment.defaults.json")
    parser.add_argument("--collection", type=Path, default=COLLECTION_PATH, help="Path to postman_collection.json")
    parser.add_argument(
        "--out-dir", type=Path, default=HERE, help="Directory to write postman_environment.<env>.json files"
    )
    args = parser.parse_args(argv)

    if not args.env and not args.all and not args.patch_collection:
        parser.print_help()
        return 1

    if not args.defaults.is_file():
        print(f"error: {args.defaults} not found", file=sys.stderr)
        return 1
    defaults = _load_json(args.defaults)

    if args.env:
        try:
            path = generate_env_file(defaults, args.env, args.out_dir)
        except KeyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"wrote {path}")

    if args.all:
        for env_name in defaults.get("envs", {}):
            path = generate_env_file(defaults, env_name, args.out_dir)
            print(f"wrote {path}")

    if args.patch_collection:
        if not args.collection.is_file():
            print(f"error: {args.collection} not found", file=sys.stderr)
            return 1
        collection = _load_json(args.collection)
        try:
            collection = patch_collection(defaults, collection)
        except KeyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        _write_json(args.collection, collection)
        print(f"patched {args.collection}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
