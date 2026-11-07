import json
import tempfile
import unittest
from pathlib import Path

from parser.parse_projects import ValidationError, parse_projects


BASE = """---
schema_version: 1
projects:
  - id: alpha
    name: Alpha
    status: active
    priority: high
    role: founder
    visibility: public
    last_updated: 2026-11-02
---

# Alpha

## Milestones

### M1: Build
**Completed at:** 2026-11-02T15:30:00Z
- [x] One
- [x] Two

### M2: Empty
"""


def write_source(text: str) -> Path:
    handle = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
    handle.write(text)
    handle.close()
    return Path(handle.name)


class ParseProjectsTests(unittest.TestCase):
    def test_valid_project_metrics_and_utc_timestamp(self):
        result = parse_projects(write_source(BASE))
        project = result["projects"][0]
        self.assertEqual(project["metrics"]["tasks"], {"completed": 2, "total": 2, "percentage": 100.0})
        self.assertEqual(project["metrics"]["milestones"], {"completed": 1, "total": 2, "percentage": 50.0})
        self.assertEqual(project["milestones"][0]["completed_at"], "2026-11-02T15:30:00Z")
        self.assertIsNone(project["milestones"][1]["completed_at"])
        self.assertEqual(project["weight"]["milestones_total"], 2)

    def test_output_is_deterministic(self):
        path = write_source(BASE)
        first = json.dumps(parse_projects(path), sort_keys=True)
        second = json.dumps(parse_projects(path), sort_keys=True)
        self.assertEqual(first, second)

    def test_completed_milestone_requires_timestamp(self):
        source = BASE.replace("**Completed at:** 2026-11-02T15:30:00Z\n", "").replace("- [ ] Two", "- [x] Two")
        with self.assertRaisesRegex(ValidationError, "must have a UTC completion timestamp"):
            parse_projects(write_source(source))

    def test_incomplete_milestone_cannot_have_timestamp(self):
        source = BASE.replace("### M2: Empty", "### M2: Empty\n**Completed at:** 2026-11-02T15:30:00Z")
        with self.assertRaisesRegex(ValidationError, "must not have a completion timestamp"):
            parse_projects(write_source(source))

    def test_partial_milestone_is_incomplete_without_timestamp(self):
        source = BASE.replace("### M2: Empty", "### M2: Partial\n- [x] Started\n- [ ] Remaining")
        project = parse_projects(write_source(source))["projects"][0]
        self.assertFalse(project["milestones"][1]["completed"])
        self.assertIsNone(project["milestones"][1]["completed_at"])

    def test_zero_task_denominator_is_null(self):
        source = BASE.replace("### M1: Build\n**Completed at:** 2026-11-02T15:30:00Z\n- [x] One\n- [x] Two\n\n", "### M1: Empty\n")
        project = parse_projects(write_source(source))["projects"][0]
        self.assertEqual(project["metrics"]["tasks"], {"completed": 0, "total": 0, "percentage": None})

    def test_invalid_checkbox_state_is_rejected(self):
        source = BASE.replace("- [x] One", "- [-] One")
        with self.assertRaisesRegex(ValidationError, "invalid checkbox state"):
            parse_projects(write_source(source))

    def test_invalid_role_is_rejected(self):
        source = BASE.replace("role: founder", "role: owner")
        with self.assertRaisesRegex(ValidationError, "role must be founder or contributor"):
            parse_projects(write_source(source))

    def test_duplicate_project_ids_are_rejected(self):
        source = BASE.replace(
            "---\n\n# Alpha",
            "  - id: alpha\n    name: Beta\n    status: active\n    priority: high\n    role: founder\n    visibility: public\n    last_updated: 2026-11-02\n---\n\n# Alpha",
        )
        with self.assertRaisesRegex(ValidationError, "duplicate project id"):
            parse_projects(write_source(source))

    def test_mismatched_project_heading_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "does not match metadata name"):
            parse_projects(write_source(BASE.replace("# Alpha", "# Wrong")))

    def test_task_outside_milestone_is_rejected(self):
        source = BASE.replace("## Milestones", "- [ ] Outside\n\n## Milestones")
        with self.assertRaisesRegex(ValidationError, "outside a milestone"):
            parse_projects(write_source(source))

    def test_invalid_timestamp_timezone_is_rejected(self):
        source = BASE.replace("2026-11-02T15:30:00Z", "2026-11-02T15:30:00-04:00")
        with self.assertRaisesRegex(ValidationError, "completed milestone timestamp"):
            parse_projects(write_source(source))


if __name__ == "__main__":
    unittest.main()
