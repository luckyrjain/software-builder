#!/usr/bin/env python3
"""Fetch KubeSense error logs with full body text via the REST/SPL API.

Fallback when MCP `search-logs` with `body` fails. Primary path: read the official `kubesense-mcp`
/ `kubesense-logs` skills and use MCP tools (see incident-rca/dependencies.md).

Requires KUBESENSE_API_KEY. Optional KUBESENSE_BASE_URL (default: https://kubesense.example.com).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

DEFAULT_BASE_URL = "https://kubesense.example.com"

REDACT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r'("Authorization"\s*:\s*")[^"]*(")', re.IGNORECASE), r'\1[REDACTED]\2'),
    (re.compile(r'("Bearer\s+)[^"\\]+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(Authorization=\[REDACTED\])\s+\S+', re.IGNORECASE), r'\1'),
    (re.compile(r'(Authorization=)[^,\]} ]+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(Basic\s+)[A-Za-z0-9+/=]{8,}', re.IGNORECASE), r'\1[REDACTED]'),
    # api_key / x-api-key / apikey — JSON-quoted and key=value forms. reference/log-redaction.md's
    # Phase 5 checklist has named this pattern from the start; the function just didn't cover it.
    (re.compile(r'("(?:x-)?api[_-]?key"\s*:\s*")[^"]*(")', re.IGNORECASE), r'\1[REDACTED]\2'),
    (re.compile(r'((?:x-)?api[_-]?key\s*=\s*)\S+', re.IGNORECASE), r'\1[REDACTED]'),
    # password / passwd / pwd — same two forms.
    (re.compile(r'("(?:password|passwd|pwd)"\s*:\s*")[^"]*(")', re.IGNORECASE), r'\1[REDACTED]\2'),
    (re.compile(r'((?:password|passwd|pwd)\s*=\s*)\S+', re.IGNORECASE), r'\1[REDACTED]'),
    # PEM blocks (private keys, certificates) — collapse the whole block, not just the header.
    (
        re.compile(
            r'(-----BEGIN [A-Z ]*(?:PRIVATE KEY|CERTIFICATE)-----)[\s\S]*?'
            r'(-----END [A-Z ]*(?:PRIVATE KEY|CERTIFICATE)-----)'
        ),
        r'\1\n[REDACTED]\n\2',
    ),
)


@dataclass(frozen=True)
class WorkloadLocation:
    cluster: str
    namespace: str | None


@dataclass(frozen=True)
class LogRow:
    timestamp: str
    workload: str
    level: str
    pod_name: str
    namespace: str | None
    message: str
    body_redacted: str


class KubesenseError(RuntimeError):
    pass


def _base_url(explicit: str | None = None) -> str:
    url = (explicit or os.environ.get("KUBESENSE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    return url


def _api_key(explicit: str | None = None) -> str:
    key = explicit or os.environ.get("KUBESENSE_API_KEY")
    if not key:
        raise KubesenseError(
            "KUBESENSE_API_KEY is not set. Create a key in KubeSense Settings → API Key Management."
        )
    return key


def redact_secrets(text: str) -> str:
    redacted = text
    for _ in range(3):
        for pattern, replacement in REDACT_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
    return redacted


def extract_message(body: str) -> str:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body[:500] + ("…" if len(body) > 500 else "")

    if isinstance(parsed, dict):
        for key in ("message", "errorDescription", "msg", "@message"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return body[:500] + ("…" if len(body) > 500 else "")


def _request_json(
    method: str,
    url: str,
    api_key: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise KubesenseError(f"HTTP {exc.code} for {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise KubesenseError(f"Request failed for {url}: {exc}") from exc

    if payload.get("error"):
        raise KubesenseError(payload.get("message") or "KubeSense API error")
    return payload


def fetch_hierarchy(base_url: str, api_key: str) -> list[dict[str, Any]]:
    payload = _request_json("GET", f"{base_url}/api/logs/kube/heirarchy", api_key)
    data = payload.get("data")
    if not isinstance(data, list):
        raise KubesenseError("Unexpected hierarchy response shape")
    return data


def _walk_hierarchy(
    node: dict[str, Any],
    path: list[tuple[str, str]],
    workload: str,
    matches: list[WorkloadLocation],
) -> None:
    node_type = node.get("type", "")
    name = node.get("name", "")
    child_path = path + [(node_type, name)] if name else path

    if node_type == "workload" and name == workload:
        cluster = next((n for t, n in path if t == "cluster"), None)
        namespace = next((n for t, n in path if t == "namespace"), None)
        if cluster:
            matches.append(WorkloadLocation(cluster=cluster, namespace=namespace))

    for child in node.get("childs") or []:
        if isinstance(child, dict):
            _walk_hierarchy(child, child_path, workload, matches)


def find_workload_locations(hierarchy: list[dict[str, Any]], workload: str) -> list[WorkloadLocation]:
    matches: list[WorkloadLocation] = []
    for root in hierarchy:
        if isinstance(root, dict):
            _walk_hierarchy(root, [], workload, matches)
    return matches


def choose_cluster(
    locations: list[WorkloadLocation],
    cluster: str | None,
    namespace: str | None,
) -> WorkloadLocation:
    if not locations:
        raise KubesenseError("Workload not found in KubeSense hierarchy")

    if cluster:
        for loc in locations:
            if loc.cluster == cluster and (namespace is None or loc.namespace == namespace):
                return loc
        raise KubesenseError(f"Workload not found in cluster {cluster!r}")

    filtered = locations
    if namespace:
        filtered = [loc for loc in locations if loc.namespace == namespace]
        if not filtered:
            raise KubesenseError(f"Workload not found in namespace {namespace!r}")

    prod_matches = [loc for loc in filtered if "prod" in loc.cluster.lower()]
    if len(prod_matches) == 1:
        return prod_matches[0]
    if len(filtered) == 1:
        return filtered[0]

    options = ", ".join(
        f"{loc.cluster}" + (f"/{loc.namespace}" if loc.namespace else "")
        for loc in filtered
    )
    raise KubesenseError(
        f"Multiple clusters match workload; pass --cluster. Options: {options}"
    )


def _spl_escape(value: str) -> str:
    """Escape a value for embedding in a double-quoted SPL string literal.

    Callers may pass workload/namespace values parsed from untrusted incident
    data (log lines, error messages) — escape backslashes first, then quotes,
    so an embedded `"` can't close the literal early and inject additional
    SPL clauses.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_spl_query(
    workload: str,
    level: str,
    namespace: str | None,
    limit: int,
) -> str:
    filters = [
        f'workload = "{_spl_escape(workload)}"',
        f'level = "{_spl_escape(level)}"',
    ]
    if namespace:
        filters.append(f'namespace = "{_spl_escape(namespace)}"')
    filter_clause = " and ".join(filters)
    return (
        "fields @timestamp, workload, level, body, pod_name, namespace "
        f"| filter {filter_clause} "
        "| sort @timestamp desc "
        f"| limit {limit}"
    )


def execute_spl(
    base_url: str,
    api_key: str,
    query: str,
    clusters: list[str],
    from_time: str,
    to_time: str,
) -> dict[str, Any]:
    payload = _request_json(
        "POST",
        f"{base_url}/api/logs/spl/execute",
        api_key,
        {
            "query": query,
            "clusters": clusters,
            "from_time": from_time,
            "to_time": to_time,
        },
    )
    data = payload.get("data")
    if not isinstance(data, dict):
        raise KubesenseError("Unexpected SPL response shape")
    return data


def spl_rows_to_logs(spl_data: dict[str, Any]) -> list[LogRow]:
    columns = spl_data.get("columns") or []
    rows = spl_data.get("rows") or []
    if not columns or not isinstance(rows, list):
        return []

    index = {name: i for i, name in enumerate(columns)}

    def col(row: list[Any], name: str, default: str = "") -> str:
        pos = index.get(name)
        if pos is None or pos >= len(row):
            return default
        value = row[pos]
        return "" if value is None else str(value)

    logs: list[LogRow] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        body = col(row, "body")
        logs.append(
            LogRow(
                timestamp=col(row, "timestamp") or col(row, "@timestamp"),
                workload=col(row, "workload"),
                level=col(row, "level"),
                pod_name=col(row, "pod_name"),
                namespace=col(row, "namespace") or None,
                message=redact_secrets(extract_message(body)),
                body_redacted=redact_secrets(body),
            )
        )
    return logs


def unique_sample_messages(logs: list[LogRow], max_messages: int = 5) -> list[str]:
    samples: list[str] = []
    seen: set[str] = set()
    for log in logs:
        normalized = " ".join(log.message.split()).lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        samples.append(log.message[:500])
        if len(samples) >= max_messages:
            break
    return samples


def build_evidence_fragment(
    logs: list[LogRow],
    *,
    service: str,
    from_time: str,
    to_time: str,
    cluster: str,
    namespace: str | None,
    limit: int,
) -> dict[str, Any]:
    namespace_suffix = f" --namespace {namespace}" if namespace else ""
    query_ref = (
        f"kubesense-spl: scripts/kubesense_logs.py {service}"
        f" --cluster {cluster}{namespace_suffix}"
        f" --from {from_time} --to {to_time} --limit {limit} --evidence"
    )
    detected_at = logs[0].timestamp if logs else from_time
    return {
        "error_signals": [
            {
                "source": "kubesense-spl",
                "service": service,
                "signal_type": "log_error",
                "detected_at": detected_at,
                "magnitude": f"{len(logs)} ERROR logs in window (SPL limit {limit})",
                "sample_messages": unique_sample_messages(logs),
                "raw_summary": (
                    f"KubeSense SPL returned {len(logs)} ERROR rows for workload {service}"
                    f" on cluster {cluster}"
                    + (f" namespace {namespace}" if namespace else "")
                ),
            }
        ],
        "query_references": [query_ref],
    }


def spl_cli_available() -> bool:
    return bool(os.environ.get("KUBESENSE_API_KEY"))


def default_time_window(hours: float) -> tuple[str, str]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    return (
        start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def fetch_error_logs(
    workload: str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    cluster: str | None = None,
    namespace: str | None = None,
    level: str = "ERROR",
    from_time: str | None = None,
    to_time: str | None = None,
    limit: int = 10,
    hours: float = 1.0,
) -> tuple[list[LogRow], WorkloadLocation, str, str]:
    url = _base_url(base_url)
    key = _api_key(api_key)

    if from_time is None or to_time is None:
        default_from, default_to = default_time_window(hours)
        from_time = from_time or default_from
        to_time = to_time or default_to

    hierarchy = fetch_hierarchy(url, key)
    location = choose_cluster(
        find_workload_locations(hierarchy, workload),
        cluster,
        namespace,
    )

    spl_data = execute_spl(
        url,
        key,
        build_spl_query(workload, level, location.namespace or namespace, limit),
        [location.cluster],
        from_time,
        to_time,
    )
    return spl_rows_to_logs(spl_data), location, from_time, to_time


def format_text_logs(logs: list[LogRow]) -> str:
    if not logs:
        return "No logs matched the query."

    lines: list[str] = []
    for index, log in enumerate(logs, start=1):
        lines.append(f"--- log {index} ---")
        lines.append(f"timestamp: {log.timestamp}")
        lines.append(f"workload:  {log.workload}")
        lines.append(f"level:     {log.level}")
        lines.append(f"pod:       {log.pod_name}")
        if log.namespace:
            lines.append(f"namespace: {log.namespace}")
        lines.append(f"message:   {redact_secrets(log.message)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch KubeSense logs with body text via the SPL REST API.",
    )
    parser.add_argument("workload", help="Kubernetes workload name (e.g. autodebit-service)")
    parser.add_argument("--cluster", help="KubeSense cluster name (auto-detected when unambiguous)")
    parser.add_argument("--namespace", help="Kubernetes namespace filter")
    parser.add_argument("--level", default="ERROR", help="Log level filter (default: ERROR)")
    parser.add_argument("--from", dest="from_time", help="Start time ISO-8601 UTC")
    parser.add_argument("--to", dest="to_time", help="End time ISO-8601 UTC")
    parser.add_argument(
        "--hours",
        type=float,
        default=1.0,
        help="Lookback window when --from/--to omitted (default: 1)",
    )
    parser.add_argument("--limit", type=int, default=10, help="Max rows (default: 10)")
    parser.add_argument("--base-url", help=f"KubeSense host (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    parser.add_argument(
        "--evidence",
        action="store_true",
        help="Emit incident-rca evidence fragment (error_signals + query_references)",
    )
    parser.add_argument(
        "--list-clusters",
        action="store_true",
        help="List clusters/namespaces for the workload and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_url = _base_url(args.base_url)

    try:
        api_key = _api_key(None)
        if args.list_clusters:
            hierarchy = fetch_hierarchy(base_url, api_key)
            locations = find_workload_locations(hierarchy, args.workload)
            if not locations:
                print(f"No clusters found for workload {args.workload!r}", file=sys.stderr)
                return 1
            for loc in locations:
                suffix = f" namespace={loc.namespace}" if loc.namespace else ""
                print(f"{loc.cluster}{suffix}")
            return 0

        logs, location, from_time, to_time = fetch_error_logs(
            args.workload,
            base_url=base_url,
            api_key=api_key,
            cluster=args.cluster,
            namespace=args.namespace,
            level=args.level,
            from_time=args.from_time,
            to_time=args.to_time,
            limit=args.limit,
            hours=args.hours,
        )
    except KubesenseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.evidence:
        payload = build_evidence_fragment(
            logs,
            service=args.workload,
            from_time=from_time,
            to_time=to_time,
            cluster=location.cluster,
            namespace=location.namespace or args.namespace,
            limit=args.limit,
        )
        print(json.dumps(payload, indent=2))
    elif args.json:
        payload = [
            {
                "timestamp": log.timestamp,
                "workload": log.workload,
                "level": log.level,
                "pod_name": log.pod_name,
                "namespace": log.namespace,
                "message": redact_secrets(log.message),
                "body": log.body_redacted,
            }
            for log in logs
        ]
        print(json.dumps(payload, indent=2))
    else:
        print(format_text_logs(logs), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
