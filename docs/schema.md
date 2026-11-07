# Project Markdown schema

This document defines schema version `1` for the human-edited `projects.md` source.

## Document shape

The file starts with YAML front matter delimited by `---` lines. The front matter
must contain:

```yaml
schema_version: 1
projects:
  - id: stable_project_id
    name: Human-readable project name
    status: active
    priority: high
    role: founder
    visibility: private
    last_updated: 2026-11-02
    start_date: 2026-01-15
```

`projects` is a nonempty list. Every entry requires:

- `id`: a nonempty, globally unique identifier for the document. Use stable,
  machine-friendly values; changing it identifies a different project.
- `name`: a nonempty display name, unique within this document.
- `status`: the current implementation status, such as `planning`, `active`,
  `paused`, or `complete`.
- `priority`: the current priority, such as `low`, `medium`, or `high`.
- `role`: the person's relationship to the project, either `founder` or
  `contributor`.
- `visibility`: whether the project is `public` or `private`.
- `last_updated`: the date when the project's source information was last
  reviewed or changed, using ISO `YYYY-MM-DD` format.

Optional metadata fields may include `start_date`, `end_date`, `target_date`,
and `description`. Dates use ISO `YYYY-MM-DD` format. `role`, `visibility`, and
`last_updated` are required for each project so the dashboard can show
ownership, access level, and data freshness. An absent `end_date` means the
project has no recorded end date; the dashboard displays it as ongoing or not
ended.
Unknown optional values are omitted rather than invented. Computed percentages
and progress totals do not belong in front matter.

## Dashboard indicators and sorting

The dashboard derives project weight from the number of milestones in that
project (`weight = milestones_total`). The project with the most milestones is
the heaviest; the project with the fewest is the lightest. It should show an
emoji weight indicator alongside the count: `🪶` for the least and `⚖️` for an
intermediate count. The heaviest project uses a custom anvil icon because no
standard Unicode anvil emoji exists. Status may use `🟢` for active,
`📝` for planning, `⏸️` for paused, and `✅` for complete.

Project cards must support multi-sort: users can choose an ordered list of
sort keys and direction for `priority`, derived `weight`, `last_updated`, `start_date`
(shown as “started”), `end_date` (shown as “ended”), and active status. Active
status is derived from `status: active`; missing dates sort after known dates.

The dashboard should show ownership and visibility on each card: `👤 Founder`
or `🤝 Contributor`, and `🌐 Public` or `🔒 Private`. These values come directly
from front matter and are not inferred from task progress.

## Project and milestone headings

After the front matter, each project appears exactly once in the same order as
the front-matter list:

```markdown
# Human-readable project name

## Milestones

### M1: Milestone name
**Completed at:** 2026-11-02T15:30:00Z
- [x] Completed task
- [ ] Outstanding task
```

The level-one heading text must exactly equal the corresponding metadata
`name`. A heading without exactly one metadata entry, or metadata without
exactly one body heading, is invalid. The `## Milestones` heading is required
for each project.

Each milestone heading has the form `### <milestone-id>: <milestone name>`.
The ID is nonempty and unique within its project; IDs may be reused in another
project. Milestone names must be nonempty. A project must contain at least one
milestone. A milestone whose tasks are all complete must contain exactly one
`**Completed at:** <timestamp>` line immediately after its heading. The
timestamp must be an ISO 8601 UTC timestamp ending in `Z`, for example
`2026-11-02T15:30:00Z`. Incomplete milestones omit this line.

## Tasks and non-task Markdown

Only checkbox list items within a milestone section count as tasks:

- `- [x]` means complete.
- `- [ ]` means incomplete.

The checkbox marker is case-insensitive for `x`, and task text must be
nonempty. Other checkbox states (for example `[-]` or `[?]`) are invalid when
they appear where a task is expected. A checkbox outside `## Milestones` or a
milestone section is non-task Markdown and does not contribute to progress;
the parser should report it as a validation error or warning rather than count
it silently.

Paragraphs, blockquotes, nested explanatory lists, links, and headings below a
milestone may document blockers, notes, decisions, or references. They are
preserved as descriptive content but are not tasks unless they are direct
checkbox list items in that milestone. A milestone with no counted tasks is
valid source structure only if the implementation explicitly supports empty
milestones; its completion metric is undefined, not automatically complete.

## Validation and derived metrics

Validation must reject duplicate project IDs, duplicate project names, missing
or mismatched project headings, malformed metadata, duplicate milestone IDs
within a project, missing milestone names, invalid task states, and ambiguous
project or milestone sections. Error messages should identify the project and
line where possible.

The parser, not the Markdown source, calculates progress. It reports task and
milestone metrics separately:

- Task progress is `completed tasks / total tasks`.
- A nonempty milestone is complete only when every counted task is complete.
- Milestone progress is `completed milestones / total milestones`.
- An empty milestone is not complete and contributes an undefined/not-applicable
  completion result according to the normalized JSON schema.
- A zero denominator produces `null` rather than a percentage.

All date-time values are stored in UTC. Date-only fields such as
`last_updated` and `start_date` represent UTC calendar dates. The UI may render
UTC timestamps in a user's selected timezone, but must always show which
timezone is active and allow changing it.

If an overall score is later displayed, it must be documented as a derived
value. The initial candidate is an equal 50/50 blend when both metrics exist,
or the available metric when only one exists.

## Normalized JSON output

`parser/parse_projects.py` emits a deterministic JSON document with
`schema_version: 1` and a `projects` array. Each project preserves the
front-matter identity, status, priority, role, visibility, and date fields,
then adds:

- `milestones`: ordered milestone objects with `id`, `name`, `completed`,
  `completed_at` (UTC string or `null`), and ordered `tasks`;
- `metrics.tasks` and `metrics.milestones`, each with `completed`, `total`, and
  `percentage` (`null` for a zero denominator);
- `weight.milestones_total`, equal to the number of milestones, and
  `weight.classification` (`lightest`, `middle`, or `heaviest`).

Task and milestone ordering follows the Markdown source. JSON keys are sorted
and output uses stable indentation so identical input produces identical output.

## Example

See the repository's `projects.md` for a complete three-project example.
