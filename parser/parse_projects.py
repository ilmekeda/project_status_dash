#!/usr/bin/env python3
"""Validate projects.md and emit deterministic normalized project JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from markdown_it import MarkdownIt


DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
TIMESTAMP_RE = re.compile(r"^\*\*Completed at:\*\* ([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)$")
MILESTONE_RE = re.compile(r"^([^:]+):\s*(.+)$")
CHECKBOX_RE = re.compile(r"^\[([ xX?-])\]\s+(.+)$")


class ValidationError(ValueError):
    """Actionable source validation failure."""


def location(path: Path, line: int | None = None) -> str:
    return f"{path}:{line}" if line is not None else str(path)


def fail(path: Path, message: str, line: int | None = None) -> None:
    raise ValidationError(f"{location(path, line)}: {message}")


def parse_front_matter(text: str, path: Path) -> tuple[dict[str, Any], str, int]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        fail(path, "document must start with YAML front matter")
    try:
        closing = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        fail(path, "front matter is missing its closing --- delimiter")
    try:
        metadata = yaml.safe_load("\n".join(lines[1:closing]))
    except yaml.YAMLError as exc:
        fail(path, f"invalid YAML front matter: {exc}")
    if not isinstance(metadata, dict):
        fail(path, "front matter must be a mapping")
    body = "\n".join(lines[closing + 1 :])
    if text.endswith("\n"):
        body += "\n"
    return metadata, body, closing + 1


def validate_date(value: Any, field: str, path: Path) -> str:
    value_text = str(value)
    if not DATE_RE.fullmatch(value_text):
        fail(path, f"{field} must use ISO YYYY-MM-DD format")
    try:
        date.fromisoformat(value_text)
    except ValueError:
        fail(path, f"{field} is not a valid calendar date")
    return value_text


def validate_metadata(metadata: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    if metadata.get("schema_version") != 1:
        fail(path, "schema_version must be 1")
    projects = metadata.get("projects")
    if not isinstance(projects, list) or not projects:
        fail(path, "projects must be a nonempty list")
    required = ("id", "name", "status", "priority", "role", "visibility", "last_updated")
    ids: set[str] = set()
    names: set[str] = set()
    result: list[dict[str, Any]] = []
    for index, project in enumerate(projects, start=1):
        if not isinstance(project, dict):
            fail(path, f"projects[{index}] must be a mapping")
        missing = [field for field in required if not project.get(field)]
        if missing:
            fail(path, f"projects[{index}] is missing required field(s): {', '.join(missing)}")
        project_id = str(project["id"])
        name = str(project["name"])
        if project_id in ids:
            fail(path, f"duplicate project id {project_id!r}")
        if name in names:
            fail(path, f"duplicate project name {name!r}")
        ids.add(project_id)
        names.add(name)
        if project["role"] not in {"founder", "contributor"}:
            fail(path, f"project {project_id!r} role must be founder or contributor")
        if project["visibility"] not in {"public", "private"}:
            fail(path, f"project {project_id!r} visibility must be public or private")
        normalized = dict(project)
        for field in ("last_updated", "start_date", "end_date", "target_date"):
            if field in project and project[field] is not None:
                normalized[field] = validate_date(project[field], field, path)
        result.append(normalized)
    return result


def heading_text(tokens: list[Any], index: int) -> str:
    if index + 1 >= len(tokens) or tokens[index + 1].type != "inline":
        return ""
    return tokens[index + 1].content.strip()


def parse_completion_timestamp(raw_line: str, path: Path, line_number: int) -> str:
    match = TIMESTAMP_RE.fullmatch(raw_line.strip())
    if not match:
        fail(path, "completed milestone timestamp must be **Completed at:** YYYY-MM-DDTHH:MM:SSZ", line_number)
    value = match.group(1)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail(path, "completed milestone timestamp is not valid ISO 8601", line_number)
    if parsed.tzinfo != timezone.utc:
        fail(path, "completed milestone timestamp must be UTC and end in Z", line_number)
    return value


def direct_tasks(tokens: list[Any], start: int, end: int, path: Path, body_start: int) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for index in range(start, end):
        token = tokens[index]
        if token.type != "list_item_open" or token.level != 1:
            continue
        inline = next((tokens[j] for j in range(index + 1, min(index + 5, end)) if tokens[j].type == "inline"), None)
        if inline is None:
            continue
        match = CHECKBOX_RE.match(inline.content.strip())
        line_number = body_start + (token.map[0] if token.map else 0) + 1
        if not match:
            if inline.content.lstrip().startswith("["):
                fail(path, "invalid checkbox state in milestone task", line_number)
            continue
        state, task_text = match.groups()
        if state == "-":
            fail(path, "invalid checkbox state; use [x] or [ ]", line_number)
        tasks.append({"text": task_text.strip(), "completed": state.lower() == "x"})
    return tasks


def reject_tasks_outside_milestones(
    tokens: list[Any],
    project_start: int,
    project_end: int,
    milestone_ranges: list[tuple[int, int]],
    path: Path,
    body_start: int,
) -> None:
    for index in range(project_start, project_end):
        token = tokens[index]
        if token.type != "list_item_open" or token.level != 1:
            continue
        if any(start <= index < end for start, end in milestone_ranges):
            continue
        inline = next((tokens[j] for j in range(index + 1, min(index + 5, project_end)) if tokens[j].type == "inline"), None)
        if inline and inline.content.strip().startswith("["):
            line = body_start + (token.map[0] if token.map else 0) + 1
            fail(path, "checkbox task is outside a milestone section", line)


def parse_body(body: str, metadata: list[dict[str, Any]], path: Path, body_start: int) -> list[dict[str, Any]]:
    lines = body.splitlines()
    tokens = MarkdownIt().parse(body)
    h1_indices = [i for i, token in enumerate(tokens) if token.type == "heading_open" and token.tag == "h1"]
    if len(h1_indices) != len(metadata):
        fail(path, f"expected {len(metadata)} project headings, found {len(h1_indices)}")
    projects: list[dict[str, Any]] = []
    for project_index, project_meta in enumerate(metadata):
        h1_index = h1_indices[project_index]
        heading = heading_text(tokens, h1_index)
        project_id = str(project_meta["id"])
        if heading != project_meta["name"]:
            line = body_start + (tokens[h1_index].map[0] if tokens[h1_index].map else 0) + 1
            fail(path, f"project {project_id!r} heading {heading!r} does not match metadata name {project_meta['name']!r}", line)
        next_h1 = h1_indices[project_index + 1] if project_index + 1 < len(h1_indices) else len(tokens)
        h2_indices = [i for i in range(h1_index + 1, next_h1) if tokens[i].type == "heading_open" and tokens[i].tag == "h2"]
        milestones_heading = [i for i in h2_indices if heading_text(tokens, i) == "Milestones"]
        if len(milestones_heading) != 1:
            fail(path, f"project {project_id!r} must contain exactly one ## Milestones heading")
        h3_indices = [i for i in range(milestones_heading[0] + 1, next_h1) if tokens[i].type == "heading_open" and tokens[i].tag == "h3"]
        if not h3_indices:
            fail(path, f"project {project_id!r} must contain at least one milestone")
        milestone_ids: set[str] = set()
        milestones: list[dict[str, Any]] = []
        milestone_ranges: list[tuple[int, int]] = []
        for milestone_index, h3_index in enumerate(h3_indices):
            raw_heading = heading_text(tokens, h3_index)
            match = MILESTONE_RE.fullmatch(raw_heading)
            line = body_start + (tokens[h3_index].map[0] if tokens[h3_index].map else 0) + 1
            if not match:
                fail(path, f"milestone heading must be '<id>: <name>'", line)
            milestone_id, milestone_name = (part.strip() for part in match.groups())
            if not milestone_id or not milestone_name:
                fail(path, "milestone id and name must be nonempty", line)
            if milestone_id in milestone_ids:
                fail(path, f"duplicate milestone id {milestone_id!r} in project {project_id!r}", line)
            milestone_ids.add(milestone_id)
            next_h3 = h3_indices[milestone_index + 1] if milestone_index + 1 < len(h3_indices) else next_h1
            milestone_ranges.append((h3_index + 1, next_h3))
            tasks = direct_tasks(tokens, h3_index + 1, next_h3, path, body_start)
            complete = bool(tasks) and all(task["completed"] for task in tasks)
            timestamp_line = tokens[h3_index].map[1] if tokens[h3_index].map else 0
            timestamp = None
            if timestamp_line < len(lines) and lines[timestamp_line].strip().startswith("**Completed at:"):
                timestamp = parse_completion_timestamp(lines[timestamp_line], path, body_start + timestamp_line + 1)
            if complete and timestamp is None:
                fail(path, f"completed milestone {milestone_id!r} must have a UTC completion timestamp", line)
            if not complete and timestamp is not None:
                fail(path, f"incomplete milestone {milestone_id!r} must not have a completion timestamp", line)
            milestones.append({"id": milestone_id, "name": milestone_name, "completed": complete, "completed_at": timestamp, "tasks": tasks})
        reject_tasks_outside_milestones(tokens, h1_index + 1, next_h1, milestone_ranges, path, body_start)
        projects.append({**project_meta, "weight": {"milestones_total": len(milestones), "classification": "unknown"}, "milestones": milestones})
    weights = [project["weight"]["milestones_total"] for project in projects]
    minimum, maximum = min(weights), max(weights)
    for project in projects:
        count = project["weight"]["milestones_total"]
        project["weight"]["classification"] = "lightest" if count == minimum else "heaviest" if count == maximum else "middle"
        tasks = [task for milestone in project["milestones"] for task in milestone["tasks"]]
        completed_tasks = sum(task["completed"] for task in tasks)
        completed_milestones = sum(milestone["completed"] for milestone in project["milestones"])
        project["metrics"] = {
            "tasks": {"completed": completed_tasks, "total": len(tasks), "percentage": completed_tasks / len(tasks) * 100 if tasks else None},
            "milestones": {"completed": completed_milestones, "total": len(project["milestones"]), "percentage": completed_milestones / len(project["milestones"]) * 100 if project["milestones"] else None},
        }
    return projects


def parse_projects(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    metadata, body, body_start = parse_front_matter(text, path)
    projects = parse_body(body, validate_metadata(metadata, path), path, body_start)
    return {"schema_version": 1, "projects": projects}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Markdown source file")
    parser.add_argument("-o", "--output", type=Path, help="JSON output path; stdout when omitted")
    args = parser.parse_args()
    try:
        result = parse_projects(args.input)
    except (OSError, ValidationError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
