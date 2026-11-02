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
```

`projects` is a nonempty list. Every entry requires:

- `id`: a nonempty, globally unique identifier for the document. Use stable,
  machine-friendly values; changing it identifies a different project.
- `name`: a nonempty display name, unique within this document.
- `status`: the current implementation status, such as `planning`, `active`,
  `paused`, or `complete`.
- `priority`: the current priority, such as `low`, `medium`, or `high`.

Optional metadata fields may include `start_date`, `target_date`, and
`description`. Dates use ISO `YYYY-MM-DD` format. Unknown optional values are
omitted rather than invented. Computed percentages and progress totals do not
belong in front matter.

## Project and milestone headings

After the front matter, each project appears exactly once in the same order as
the front-matter list:

```markdown
# Human-readable project name

## Milestones

### M1: Milestone name
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
milestone.

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

If an overall score is later displayed, it must be documented as a derived
value. The initial candidate is an equal 50/50 blend when both metrics exist,
or the available metric when only one exists.

## Example

See the repository's `projects.md` for a complete three-project example.
