#!/usr/bin/env python3
"""Validate the P5 as-built PRD requirement/traceability contract."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

STATUS = frozenset({"Observed", "Inferred", "Unknown"})
CONFIDENCE = frozenset({"HIGH", "MEDIUM", "LOW", "UNKNOWN"})
REQUIREMENT_ID = re.compile(r"\b(?:FR|BR|NFR)-\d+\b")

REQUIRED_HEADINGS = (
    "## 4. Functional requirements",
    "## 5. Business rules and invariants",
    "## 12. Non-functional requirements",
    "## 19. Requirement traceability",
    "## 20. Open product-intent questions",
)

REQUIREMENT_SECTIONS = (
    "## 4. Functional requirements",
    "## 5. Business rules and invariants",
    "## 12. Non-functional requirements",
)


def _split_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def _section(text: str, heading: str) -> str:
    start = text.find(heading)
    if start < 0:
        return ""
    next_heading = text.find("\n## ", start + len(heading))
    return text[start:] if next_heading < 0 else text[start:next_heading]


def _table_rows(section: str) -> tuple[list[str], list[list[str]]]:
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if not lines:
        return [], []
    header = _split_cells(lines[0])
    rows: list[list[str]] = []
    for line in lines[1:]:
        cells = _split_cells(line)
        if _is_separator(cells):
            continue
        rows.append(cells)
    return header, rows


def validate_prd(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"cannot read {path}: {exc}"]

    for heading in REQUIRED_HEADINGS:
        if heading not in text:
            errors.append(f"missing required PRD section: {heading}")

    if "Observed / Inferred / Unknown" in text:
        errors.append("unresolved PRD status placeholder: choose Observed, Inferred, or Unknown")

    requirement_ids: set[str] = set()
    for heading in REQUIREMENT_SECTIONS:
        section = _section(text, heading)
        if not section:
            continue
        header, rows = _table_rows(section)
        lowered = [cell.lower() for cell in header]
        for required_column in ("id", "status", "confidence"):
            if required_column not in lowered:
                errors.append(f"{heading} table missing column: {required_column}")
        if "status" not in lowered or "confidence" not in lowered or "id" not in lowered:
            continue
        id_index = lowered.index("id")
        status_index = lowered.index("status")
        confidence_index = lowered.index("confidence")
        evidence_index = lowered.index("evidence") if "evidence" in lowered else None
        for row in rows:
            if len(row) <= max(id_index, status_index, confidence_index):
                continue
            req_id = row[id_index]
            if not REQUIREMENT_ID.fullmatch(req_id):
                continue
            requirement_ids.add(req_id)
            status = row[status_index]
            confidence = row[confidence_index]
            if status not in STATUS:
                errors.append(f"{req_id}: invalid status {status!r}")
            if confidence not in CONFIDENCE:
                errors.append(f"{req_id}: invalid confidence {confidence!r}")
            if evidence_index is not None and len(row) > evidence_index:
                evidence = row[evidence_index]
                if status == "Observed" and evidence.upper() in {"", "UNKNOWN"}:
                    errors.append(f"{req_id}: Observed requirement must cite evidence")

    trace_section = _section(text, "## 19. Requirement traceability")
    header, rows = _table_rows(trace_section)
    lowered = [cell.lower() for cell in header]
    required_trace_columns = (
        "requirement id",
        "requirement status",
        "evidence source(s)",
        "confidence",
    )
    for column in required_trace_columns:
        if column not in lowered:
            errors.append(f"traceability table missing column: {column}")

    traced: dict[str, list[str]] = {}
    if all(column in lowered for column in required_trace_columns):
        id_index = lowered.index("requirement id")
        status_index = lowered.index("requirement status")
        evidence_index = lowered.index("evidence source(s)")
        confidence_index = lowered.index("confidence")
        for row in rows:
            if len(row) <= max(id_index, status_index, evidence_index, confidence_index):
                continue
            req_id = row[id_index]
            if not REQUIREMENT_ID.fullmatch(req_id):
                continue
            if req_id in traced:
                errors.append(f"duplicate traceability row: {req_id}")
                continue
            traced[req_id] = row
            status = row[status_index]
            evidence = row[evidence_index]
            confidence = row[confidence_index]
            if status not in STATUS:
                errors.append(f"{req_id}: invalid traceability status {status!r}")
            if confidence not in CONFIDENCE:
                errors.append(f"{req_id}: invalid traceability confidence {confidence!r}")
            if status == "Observed" and evidence.upper() in {"", "UNKNOWN"}:
                errors.append(f"{req_id}: Observed traceability row must cite evidence")

    for req_id in sorted(requirement_ids - set(traced)):
        errors.append(f"missing traceability row: {req_id}")
    for req_id in sorted(set(traced) - requirement_ids):
        errors.append(f"traceability row has no requirement definition: {req_id}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate domain-comprehension PRD.md")
    parser.add_argument("prd", type=Path, help="Path to generated PRD.md")
    args = parser.parse_args()

    errors = validate_prd(args.prd)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"ok: {args.prd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
