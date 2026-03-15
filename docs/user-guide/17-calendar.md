# Academic Calendar Processing

> `zaphod calendar process` converts a human-authored academic calendar source file into the data format consumed by Trillian Canvas components.

---

## The Basics

`zaphod calendar process` takes a YAML file describing your academic year (term dates and holidays) and produces a JavaScript data file that Trillian's Canvas components (progress dashboards, term calendars) read at runtime.

## YAML Source Format

```yaml
year: "2025-26"
school: WWCC
totalInstructionDays: 203   # optional — triggers validation warning if computed differs

terms:
  - id: summer-2025
    name: Summer Quarter
    short: "Summer '25"
    start: "2025-07-01"
    end: "2025-09-05"
    holidays:
      - date: "2025-07-04"
        label: Independence Day
      - date: "2025-09-01"
        label: Labor Day

  - id: fall-2025
    name: Fall Quarter
    short: "Fall '25"
    start: "2025-09-22"
    end: "2025-12-10"
    holidays:
      - date: "2025-11-11"
        label: Veterans Day
      - { date: "2025-11-24", label: Thanksgiving Break }
      - { date: "2025-11-25", label: Thanksgiving Break }
      - { date: "2025-11-26", label: Thanksgiving Break }
      - { date: "2025-11-27", label: Thanksgiving Break }
      - { date: "2025-11-28", label: Thanksgiving Break }

  - id: winter-2026
    name: Winter Quarter
    short: "Winter '26"
    start: "2026-01-05"
    end: "2026-03-19"
    holidays:
      - date: "2026-01-19"
        label: Martin Luther King Jr. Day
      - date: "2026-02-16"
        label: Presidents' Day

  - id: spring-2026
    name: Spring Quarter
    short: "Spring '26"
    start: "2026-04-01"
    end: "2026-06-12"
    holidays:
      - date: "2026-05-25"
        label: Memorial Day
```

**Fields:**
- `year` — Academic year label (used in output and display)
- `school` — Institution identifier
- `totalInstructionDays` — Optional. If present, Zaphod warns if the computed total differs
- `terms[].id` — Kebab-case identifier; should match `current_term` in `variables.yaml`
- `terms[].start` / `terms[].end` — ISO 8601 dates (inclusive)
- `terms[].holidays` — List of dates excluded from instruction day count

**Basic invocation:**

```bash
zaphod calendar process calendar-source-2025-26.yaml
```

This prints the day-count report to the terminal and writes a markdown include to `_all_courses/shared/calendar-data.md`. Use `{{include:calendar-data}}` in your Canvas pages to embed the component.

---

## Digging Deeper

## PDF Support (WWCC format)

For institutions using the WWCC academic calendar PDF format, Zaphod can extract term data directly:

```bash
zaphod calendar process "2025-26 wwcc calendar.pdf"
```

This uses `pdfplumber` to parse the PDF. The PDF reader handles the WWCC layout specifically — other PDF formats are not currently supported.

---

## All Output Flags

| Option | Description |
|--------|-------------|
| `--out <file>` | Write JS output to file (default: stdout) |
| `--json <file>` | Also write processed JSON |
| `--include <path>` | Override include output path |
| `--no-include` | Skip writing the markdown include |
| `--validate-only` | Print day-count report only, no output written |

---

## The Three Outputs

### 1. JS Global (`window.TRL_CALENDAR`)

The primary output. A JavaScript assignment that Trillian components read at runtime:

```js
window.TRL_CALENDAR = {
  "year": "2025-26",
  "school": "WWCC",
  "terms": [
    {
      "id": "winter-2026",
      "name": "Winter Quarter",
      "short": "Winter '26",
      "start": "2026-01-05",
      "end": "2026-03-19",
      "days": 52,
      "off": [
        { "date": "2026-01-19", "label": "Martin Luther King Jr. Day" },
        { "date": "2026-02-16", "label": "Presidents' Day" }
      ]
    }
  ]
};
```

Note that `days` is computed by Zaphod (not taken from the source file), and holidays are renamed from `holidays` to `off` in the output.

Write to a file with `--out`:
```bash
zaphod calendar process calendar-source-2025-26.yaml --out calendar-2025-26.js
```

By default the JS is printed to stdout.

### 2. JSON file

Use `--json` to write the processed data structure as pretty-printed JSON — useful for debugging or feeding into other tools:

```bash
zaphod calendar process calendar-source-2025-26.yaml --json calendar-2025-26.json
```

### 3. Markdown Include (`_all_courses/shared/calendar-data.md`)

Zaphod automatically writes a `trl-calendar-data` markdown include to `_all_courses/shared/calendar-data.md`. This include emits the Trillian component markup that loads `window.TRL_CALENDAR` into a Canvas page.

Use it in your Canvas page templates or page content:

```markdown
{{include:calendar-data}}
```

Skip this step with `--no-include`, or override the output path with `--include <path>`.

---

## `totalInstructionDays` Validation

If your source file includes `totalInstructionDays`, Zaphod compares it against the computed sum:

```
✓  Total instruction days: 203  (matches source)
```

If they differ:
```
⚠  Total instruction days: 201  (source declares 203 — check for missing holidays or date errors)
```

This is a warning, not an error — Zaphod writes output regardless. Use `--validate-only` to run the check without writing any files.

---

## Connecting to Trillian

Trillian components (`term-calendar.js`, `main-dashboard.js`) read `window.TRL_CALENDAR` at page load. The data contract is stable — components do no processing, they read the pre-computed values directly.

**Load order matters.** In Canvas Custom JS, `window.TRL_CALENDAR` must be assigned before Trillian initialises. List the calendar JS file before `trillian.js` in your Canvas Admin → Custom JS settings.

The `current_term` variable in `shared/variables.yaml` (e.g. `current_term: winter-2026`) tells Trillian which term is active. The value should match one of the `id` fields in your calendar data.

---

## Step-by-Step Workflow for a New Academic Year

### 1. Create the source file

Copy last year's YAML and update the dates and holidays:

```bash
cp calendar-source-2024-25.yaml calendar-source-2025-26.yaml
# Edit dates in your text editor
```

### 2. Validate the day counts

```bash
zaphod calendar process calendar-source-2025-26.yaml --validate-only
```

Review the output and fix any discrepancies before proceeding.

### 3. Generate the JS output

```bash
zaphod calendar process calendar-source-2025-26.yaml \
  --out calendar-2025-26.js \
  --json calendar-2025-26.json
```

### 4. Upload to Canvas

Upload `calendar-2025-26.js` to Canvas Admin → Custom JavaScript and CSS. Make sure it appears before `trillian.js` in the load order.

### 5. Update `current_term`

In `_all_courses/shared/variables.yaml` (or the relevant course's `shared/variables.yaml`):

```yaml
current_term: winter-2026
```

### 6. Sync your courses

```bash
zaphod sync
```

Pages using `{{include:calendar-data}}` will pick up the updated include automatically.

---

## CLI Reference

```bash
zaphod calendar process <source> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--out <file>` | Write JS output to file (default: stdout) |
| `--json <file>` | Also write processed JSON |
| `--include <path>` | Override include output path |
| `--no-include` | Skip writing the markdown include |
| `--validate-only` | Print day-count report only, no output written |

See [CLI Reference](12-cli-reference.md#zaphod-calendar-process) for the full command reference.

---

**Next:** [CLI Reference](12-cli-reference.md)
