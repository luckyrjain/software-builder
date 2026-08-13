#!/usr/bin/env python3
"""Validate the P5 as-built PRD requirement/traceability contract."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

STATUS = frozenset({"Observed", "Inferred", "Unknown"})
CONFIDENCE = frozenset({"HIGH", "MEDIUM", "LOW", "UNKNOWN"})
REQUIREMENT_ID = re.compile(r"(?:FR|BR|NFR)-\d+")

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
    """Split a GFM table row without treating an escaped pipe as a delimiter."""
    raw = line.strip()
    if raw.startswith("|"):
        raw = raw[1:]
    if raw.endswith("|") and not raw.endswith("\\|"):
        raw = raw[:-1]
    cells = re.split(r"(?<!\\)\|", raw)
    return [cell.replace("\\|", "|").strip() for cell in cells]


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

    definitions: dict[str, tuple[str, str]] = {}
    for heading in REQUIREMENT_SECTIONS:
        section = _section(text, heading)
        if not section:
            continue
        header, rows = _table_rows(section)
        lowered = [cell.lower() for cell in header]
        for required_column in ("id", "status", "confidence", "evidence"):
            if required_column not in lowered:
                errors.append(f"{heading} table missing column: {required_column}")
        if not all(column in lowered for column in ("id", "status", "confidence", "evidence")):
            continue
        id_index = lowered.index("id")
        status_index = lowered.index("status")
        confidence_index = lowered.index("confidence")
        evidence_index = lowered.index("evidence")
        required_width = max(id_index, status_index, confidence_index, evidence_index)
        for row in rows:
            if len(row) <= required_width:
                continue
            req_id = row[id_index]
            if not REQUIREMENT_ID.fullmatch(req_id):
                continue
            status = row[status_index]
            confidence = row[confidence_index]
            evidence = row[evidence_index]
            if req_id in definitions:
                errors.append(f"duplicate requirement definition: {req_id}")
            else:
                definitions[req_id] = (status, confidence)
            if status not in STATUS:
                errors.append(f"{req_id}: invalid status {status!r}")
            if confidence not in CONFIDENCE:
                errors.append(f"{req_id}: invalid confidence {confidence!r}")
            if status == "Observed" and evidence.upper() in {"", "UNKNOWN"}:
                errors.append(f"{req_id}: Observed requirement must cite evidence")

    trace_section = _section(text, "## 19. Requirement traceability")
    header, rows = _table_rows(trace_section)
    lowered = [cell.lower() for cell in header]
    required_trace_columns = (
        "requirement id",
        "requirement status",
        "evidence source(s)",
        "evidence type",
        "confidence",
    )
    for column in required_trace_columns:
        if column not in lowered:
            errors.append(f"traceability table missing column: {column}")

    traced: dict[str, tuple[str, str]] = {}
    if all(column in lowered for column in required_trace_columns):
        id_index = lowered.index("requirement id")
        status_index = lowered.index("requirement status")
        evidence_index = lowered.index("evidence source(s)")
        evidence_type_index = lowered.index("evidence type")
        confidence_index = lowered.index("confidence")
        required_width = max(id_index, status_index, evidence_index, evidence_type_index, confidence_index)
        for row in rows:
            if len(row) <= required_width:
                continue
            req_id = row[id_index]
            if not REQUIREMENT_ID.fullmatch(req_id):
                continue
            status = row[status_index]
            evidence = row[evidence_index]
            evidence_type = row[evidence_type_index]
            confidence = row[confidence_index]
            if req_id in traced:
                errors.append(f"duplicate traceability row: {req_id}")
                continue
            traced[req_id] = (status, confidence)
            if status not in STATUS:
                errors.append(f"{req_id}: invalid traceability status {status!r}")
            if confidence not in CONFIDENCE:
                errors.append(f"{req_id}: invalid traceability confidence {confidence!r}")
            if not evidence_type.strip():
                errors.append(f"{req_id}: traceability evidence type must not be empty")
            if status == "Observed" and evidence.upper() in {"", "UNKNOWN"}:
                errors.append(f"{req_id}: Observed traceability row must cite evidence")

    for req_id in sorted(set(definitions) - set(traced)):
        errors.append(f"missing traceability row: {req_id}")
    for req_id in sorted(set(traced) - set(definitions)):
        errors.append(f"traceability row has no requirement definition: {req_id}")
    for req_id in sorted(set(definitions) & set(traced)):
        definition_status, definition_confidence = definitions[req_id]
        trace_status, trace_confidence = traced[req_id]
        if definition_status != trace_status:
            errors.append(
                f"{req_id}: traceability status {trace_status!r} does not match definition status {definition_status!r}"
            )
        if definition_confidence != trace_confidence:
            errors.append(
                f"{req_id}: traceability confidence {trace_confidence!r} does not match definition confidence {definition_confidence!r}"
            )

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
