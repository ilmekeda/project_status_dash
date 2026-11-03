# UI continuity contract

The current `manual-preview/` is the visual baseline for the final dashboard.
Phase 5 must preserve its look and feel: layout, typography, spacing, colors,
cards, responsive behavior, emoji/icon language, sort controls, milestone
timestamps, ownership/visibility labels, and timezone controls.

## Required migration rule

The final frontend must not be a separate redesign. Before Phase 5 is accepted:

1. Move or copy the current `manual-preview/index.html`, `styles.css`, and
   `app.js` into the frontend implementation, or make those files the shared
   frontend source directly.
2. Replace only the hardcoded project values with the normalized local
   `projects.json` data model.
3. Keep a sample JSON fixture containing the current accepted projects so the
   manual preview and the generated-data preview can be compared.
4. Preserve the current interactions: ordered multi-sort, derived milestone
   weight, anvil/lightest indicators, founder/contributor labels,
   public/private labels, UTC milestone timestamps, detected timezone, active
   timezone display, and user-selected timezone conversion.

## Data boundary

The parser owns Markdown validation and derived metrics. The frontend owns
presentation and interaction. A mapping layer is permitted only when needed to
adapt normalized JSON to the existing UI view model; it must not change the
visual contract or silently invent values.

The frontend view model must include, at minimum:

- project identity, status, priority, role, visibility, and date fields;
- derived milestone and task totals;
- milestone completion state and UTC `completed_at` values;
- outstanding task text;
- derived `weight = milestones_total` and its lightest/intermediate/heaviest
  classification.

## Acceptance evidence

Phase 5 acceptance requires:

- the same sample fixture renders the current manual preview and the frontend
  with no intentional visual differences;
- all current controls still work against generated JSON;
- responsive behavior is checked at desktop and phone widths;
- the Docker preview serves the frontend from bind-mounted source files;
- Markdown regeneration changes data without requiring a visual redesign or
  router-specific runtime.

Any intentional visual change must be documented here before it is treated as
the new baseline.
