# Variable Filters

Zaphod's `{{var:name}}` syntax supports an optional filter chain that transforms a
variable's value at publish time. Filters are separated by `|` and applied
left-to-right:

```
{{var:variable_name | filter1 | filter2:arg}}
```

---

## The Basics

Filters transform variable values at publish time. The most useful for most instructors:

**`default:value`** — shows a fallback when the variable isn't set:

```
{{var:instructor | default:TBA}}    -> "TBA" if instructor is not defined
```

**`ordinal`** — formats a number as an ordinal:

```
{{var:session | ordinal}}           -> "7th"
{{var:course_order | ordinal}}      -> "1st", "2nd", "3rd" ...
```

That's all most pages need. The full filter list is below.

---

## Digging Deeper

## Filter Reference

### `default:value`

Use a fallback value when the variable is not defined at any config tier.

```
{{var:bg_color | default:#ffffff}}
{{var:instructor | default:TBA}}
```

Pairs well with `required` to both provide a fallback and surface misconfiguration:
```
{{var:course_code | required | default:UNKNOWN}}
```

---

### `required`

Emit a build-time warning if the variable is not set. The placeholder is left
in place (rendered as empty) rather than crashing the build.

```
{{var:course_name | required}}
```

Output in terminal:
```
⚠️  {{var:course_name | required}}: required variable 'course_name' is not set
```

---

### `upcase` / `downcase` / `titlecase`

Convert the value's case.

```
{{var:course_name | upcase}}       -> JAVASCRIPT CARDS
{{var:course_name | downcase}}     -> javascript cards
{{var:course_name | titlecase}}    -> Javascript Cards
```

---

### `replace:old,new`

Replace a substring. Wrap values in single or double quotes when they contain
commas or spaces:

```
{{var:course_code | replace:_,' '}}     -> replaces _ with space
{{var:course_code | replace:-,_}}       -> replaces - with _
{{var:label | replace:',',' / '}}       -> replaces comma with ' / '
```

Replacement value defaults to empty string (i.e. deletion) if `new` is omitted:
```
{{var:course_code | replace:COURSE-,}}  -> strips prefix
```

---

### `ordinal`

Render an integer as an ordinal string.

```
{{var:course_order | ordinal}}   -> "7th"
{{var:session | ordinal}}        -> "11th"
```

Works for 1st, 2nd, 3rd, 4th … 11th, 12th, 13th … 21st, 22nd, etc.

---

### `decimals:n`

Format a number to `n` decimal places.

```
{{var:gpa | decimals:2}}         -> "3.80"
{{var:progress | decimals:0}}    -> "75"
```

---

## Chaining Examples

Filters compose naturally. Each filter receives the output of the previous one.

```
{{var:course_name | replace:_,' ' | titlecase}}
-> "Javascript Cards"

{{var:missing_var | default:3 | ordinal}}
-> "3rd"

{{var:course_order | ordinal}}
-> "7th"

{{var:gpa | required | decimals:2}}
-> warns if missing, otherwise formats to 2 decimal places
```

---

## Round-Trip Behaviour

When a filtered variable is published to Canvas, the full expression is preserved
in an HTML comment marker:

```html
<!-- {{var:course_name | replace:_,' ' | titlecase}} -->Javascript Cards<!-- {{/var:course_name | replace:_,' ' | titlecase}} -->
```

On import, `restore_zaphod_markers()` restores the original `{{var:...}}` expression
— including the filter chain — so the source file stays clean.

**Caveat:** Comment markers survive Canvas API round-trips but are stripped if a user
edits the page in the Canvas rich content editor (RCE). In that case the import
pipeline falls back to converting the rendered HTML value as plain text.

---

## Type Coercion

All variable values are strings internally. Numeric filters (`ordinal`, `decimals`)
attempt to parse the string value and emit a warning if it cannot be converted:

```
⚠️  {{var:session | ordinal}}: 'ordinal' requires an integer, got 'eleven' — skipped
```

When a filter fails, the value is passed through unchanged rather than crashing
the build.

---

## Variable Resolution Order (unchanged)

Filters are applied *after* the variable is resolved. Resolution order:

| Priority | Source |
|----------|--------|
| Highest  | Page `index.md` frontmatter |
| Middle   | `<course>/shared/variables.yaml` |
| Lowest   | `_all_courses/shared/variables.yaml` |

A `default:` filter only fires when the variable is absent from *all three* tiers.
