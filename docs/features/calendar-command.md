# Feature: `zaphod calendar` — Academic Calendar Processing

> **Status: Implemented.** See [user guide](../user-guide/17-calendar.md) for usage. This document records the original design rationale and data contract.

## Summary

Add a `zaphod calendar` CLI command (and corresponding Python module) that
processes a human-authored academic calendar source file into the
`window.TRL_CALENDAR` JSON format consumed by Trillian components.

Currently this tooling lives in the Trillian repo as a Node.js script
(`handoff/process-calendar.mjs`). It belongs in Zaphod because:

- Calendar data is a publishing concern, not a component concern
- The output feeds directly into the Zaphod/Canvas publishing pipeline
- Python is already the correct runtime for Zaphod tooling
- The Zaphod App needs to surface calendar management as a first-class feature
- `handoff/` in Trillian should contain only include templates, not toolchain scripts

---

## Data Contract

Trillian components read `window.TRL_CALENDAR` at runtime. The shape is fixed:

```json
{
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
}
```

- `id` — kebab-case term identifier matching `current_term` in `variables.yaml`
- `days` — computed instruction days (weekdays in [start, end] not in `off`)
- `off` — holidays/closures; `label` is shown as a tooltip in the calendar UI

The Trillian component that reads this (`term-calendar.js`, `main-dashboard.js`)
does no processing — it reads `window.TRL_CALENDAR` as-is. The contract is stable.

---

## Source Format

Human-authored YAML (preferred) or JSON:

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
```

---

## CLI Interface

```
zaphod calendar process <source.yaml>
```

**What it does:**

1. Parses the source YAML/JSON
2. Counts instruction days per term (weekdays in [start, end] minus holidays)
3. Validates against `totalInstructionDays` if present
4. Writes `window.TRL_CALENDAR = {...}` as a JS assignment to stdout or a file
5. Optionally writes a processed JSON file for inspection

**Options:**

```
--out <file>       Write JS output to file (default: stdout)
--json <file>      Also write processed JSON for inspection
--validate-only    Count days and report without writing output
```

**Example output (stdout):**

```
Processing 2025-26 calendar for WWCC
──────────────────────────────────────────────────
✓  summer-2025       47 days  (2025-07-01 → 2025-09-05)
   off  2025-07-04   Independence Day
   off  2025-09-01   Labor Day
✓  fall-2025         52 days  (2025-09-22 → 2025-12-10)
   off  2025-11-11   Veterans Day
   off  2025-11-24   Thanksgiving Break  (×5)
✓  winter-2026       52 days  (2026-01-05 → 2026-03-19)
✓  spring-2026       52 days  (2026-04-01 → 2026-06-12)
──────────────────────────────────────────────────
   Total instruction days: 203  ✓ matches source
```

---

## Module Location

```
zaphod/
  calendar.py          # core logic: parse, count, validate, emit
  cli.py               # adds `calendar` subcommand group
```

`calendar.py` exposes:

```python
def process_calendar(source_path: Path) -> dict:
    """Parse source, count instruction days, return TRL_CALENDAR dict."""

def emit_js(data: dict) -> str:
    """Return window.TRL_CALENDAR = {...}; string."""

def emit_json(data: dict) -> str:
    """Return pretty-printed JSON string."""
```

---

## Canvas Custom JS Integration

The output JS file gets uploaded to Canvas Admin → Custom JS alongside
`dist/trillian.js`. Load order matters — `TRL_CALENDAR` must be assigned
before Trillian initialises. In Canvas Custom JS, scripts load in the order
they are listed, so the calendar JS should appear first.

Alternatively: Zaphod could inject `window.TRL_CALENDAR = {...}` inline into
the published page HTML (as a `<script>` tag in a template header), avoiding
the need for a second Custom JS file. Worth considering for the App phase.

---

## Zaphod App Surface

When the App gains a calendar view:

- Display all terms with instruction day counts
- Highlight today's position within the current term
- Show days remaining in term
- Warn if source file is stale relative to Canvas (instruction day count changed)
- Trigger `zaphod calendar process` and re-upload on edit

---

## Migration from Trillian

1. Implement `zaphod/calendar.py` + CLI command
2. Verify output matches current `handoff/calendar-processed-2025-26.json`
3. Remove `handoff/process-calendar.mjs` from Trillian
4. Update `handoff/` README to note that calendar processing moved to Zaphod
5. Keep `handoff/calendar-processed-2025-26.json` and `calendar-global-2025-26.js`
   in Trillian temporarily as reference — remove once Zaphod CLI is in use

---

## Reference: Current Node.js Implementation

`/Users/dale/trillian/handoff/process-calendar.mjs` — the logic to port.
Core algorithm: iterate days in [start, end], skip weekends and holidays,
count remaining. ~160 lines including CLI output and file writing.
