#!/usr/bin/env python3
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

"""
var_filters.py — Filter chain parsing and application for {{var:name | filter}} expressions.

Supported filters:

  default:value     — use value if variable is missing or empty
  required          — warn at build time if variable is missing or empty
  upcase            — convert to UPPERCASE
  downcase          — convert to lowercase
  titlecase         — convert to Title Case
  replace:old,new   — replace first occurrence of old with new (strips outer quotes)
  ordinal           — render integer as ordinal: 1→"1st", 2→"2nd", 3→"3rd", etc.
  decimals:n        — format as float with n decimal places

Filters are chained left-to-right with |:
  {{var:session | default:1 | ordinal}}
  {{var:course_name | replace:_,' ' | titlecase}}
  {{var:gpa | decimals:2}}
"""

from __future__ import annotations

from typing import Optional


def _unquote(s: str) -> str:
    """
    Strip leading/trailing whitespace, then outer matching quotes if present.
    Preserves the content inside quotes (including spaces).

    Examples:
      "  hello  "   -> "hello"
      "' '"         -> " "   (space inside single quotes)
      '"foo bar"'   -> "foo bar"
      "plain"       -> "plain"
    """
    s = s.strip()
    if len(s) >= 2 and s[0] in ('"', "'") and s[-1] == s[0]:
        return s[1:-1]
    return s


def parse_filter_chain(raw: str) -> list[tuple[str, Optional[str]]]:
    """
    Parse a raw filter chain string into a list of (filter_name, arg_or_None) tuples.

    Examples:
      ' | default:x | upcase'  -> [('default', 'x'), ('upcase', None)]
      ' | replace:_,- '        -> [('replace', '_,-')]
      ''                        -> []
    """
    filters = []
    for part in raw.split("|"):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            name, _, arg = part.partition(":")
            filters.append((name.strip().lower(), arg.strip()))
        else:
            filters.append((part.lower(), None))
    return filters


def _ordinal(n: int) -> str:
    """
    Return the ordinal string for an integer.

    Examples: 1→'1st', 2→'2nd', 3→'3rd', 4→'4th', 11→'11th', 21→'21st'
    """
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def apply_filters(
    value: Optional[str],
    filters: list[tuple[str, Optional[str]]],
    var_name: str,
    full_expr: str,
) -> Optional[str]:
    """
    Apply a list of (name, arg) filters to a resolved variable value.

    Args:
      value:     raw resolved value, or None if the variable was not found
      filters:   parsed filter chain from parse_filter_chain()
      var_name:  bare variable name (for warning messages)
      full_expr: full expression including filters (for warning messages)

    Returns the final string value, or None if still unresolved after all filters.
    """
    for fname, farg in filters:

        if fname == "default":
            if not value:
                value = farg if farg is not None else ""

        elif fname == "required":
            if not value:
                print(f"⚠️  {{{{var:{full_expr}}}}}: required variable '{var_name}' is not set")

        elif fname == "upcase":
            if value:
                value = value.upper()

        elif fname == "downcase":
            if value:
                value = value.lower()

        elif fname == "titlecase":
            if value:
                value = value.title()

        elif fname == "replace":
            if value and farg is not None:
                old, _, new = farg.partition(",")
                value = value.replace(_unquote(old), _unquote(new))

        elif fname == "ordinal":
            if value:
                try:
                    value = _ordinal(int(value))
                except (ValueError, TypeError):
                    print(
                        f"⚠️  {{{{var:{full_expr}}}}}: 'ordinal' requires an integer, "
                        f"got {value!r} — skipped"
                    )

        elif fname == "decimals":
            if value and farg is not None:
                try:
                    value = f"{float(value):.{int(farg)}f}"
                except (ValueError, TypeError):
                    print(
                        f"⚠️  {{{{var:{full_expr}}}}}: 'decimals' filter error on {value!r} "
                        f"— skipped"
                    )

        else:
            print(f"⚠️  {{{{var:{full_expr}}}}}: unknown filter '{fname}' — skipped")

    return value
