#!/usr/bin/env python3
"""
Tests for zaphod/var_filters.py

Covers:
  - _unquote()         — quote-aware argument stripping
  - _ordinal()         — integer to ordinal string
  - parse_filter_chain() — raw filter string → list of (name, arg) tuples
  - apply_filters()    — individual filters, edge cases, chaining
  - interpolate_body() — end-to-end: expression → marked HTML output
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from zaphod.var_filters import _unquote, _ordinal, parse_filter_chain, apply_filters
from zaphod.frontmatter_to_meta import interpolate_body


# =============================================================================
# _unquote
# =============================================================================

class TestUnquote:
    def test_strips_whitespace(self):
        assert _unquote("  hello  ") == "hello"

    def test_strips_single_quotes(self):
        assert _unquote("'foo'") == "foo"

    def test_strips_double_quotes(self):
        assert _unquote('"foo"') == "foo"

    def test_preserves_space_inside_quotes(self):
        assert _unquote("' '") == " "

    def test_preserves_space_inside_double_quotes(self):
        assert _unquote('" "') == " "

    def test_plain_value_unchanged(self):
        assert _unquote("plain") == "plain"

    def test_mismatched_quotes_not_stripped(self):
        assert _unquote("'foo\"") == "'foo\""

    def test_empty_string(self):
        assert _unquote("") == ""

    def test_only_whitespace(self):
        assert _unquote("   ") == ""

    def test_quoted_empty_string(self):
        assert _unquote("''") == ""

    def test_preserves_interior_content(self):
        assert _unquote('"hello world"') == "hello world"


# =============================================================================
# _ordinal
# =============================================================================

class TestOrdinal:
    @pytest.mark.parametrize("n,expected", [
        (1,   "1st"),
        (2,   "2nd"),
        (3,   "3rd"),
        (4,   "4th"),
        (5,   "5th"),
        (10,  "10th"),
        (11,  "11th"),   # teen exception
        (12,  "12th"),   # teen exception
        (13,  "13th"),   # teen exception
        (14,  "14th"),
        (20,  "20th"),
        (21,  "21st"),
        (22,  "22nd"),
        (23,  "23rd"),
        (100, "100th"),
        (101, "101st"),
        (111, "111th"),  # teen exception in hundreds
        (112, "112th"),
        (113, "113th"),
        (121, "121st"),
    ])
    def test_ordinal(self, n, expected):
        assert _ordinal(n) == expected


# =============================================================================
# parse_filter_chain
# =============================================================================

class TestParseFilterChain:
    def test_empty_string(self):
        assert parse_filter_chain("") == []

    def test_single_no_arg(self):
        assert parse_filter_chain(" | upcase") == [("upcase", None)]

    def test_single_with_arg(self):
        assert parse_filter_chain(" | default:x") == [("default", "x")]

    def test_multiple_filters(self):
        assert parse_filter_chain(" | upcase | default:x") == [
            ("upcase", None),
            ("default", "x"),
        ]

    def test_case_insensitive(self):
        assert parse_filter_chain(" | UPCASE") == [("upcase", None)]
        assert parse_filter_chain(" | Default:X") == [("default", "X")]

    def test_filter_with_hex_arg(self):
        assert parse_filter_chain(" | default:#ffffff") == [("default", "#ffffff")]

    def test_replace_arg_preserved(self):
        # arg is everything after the colon — _unquote is applied later in apply_filters
        assert parse_filter_chain(" | replace:_,' '") == [("replace", "_,' '")]

    def test_trailing_pipe_ignored(self):
        assert parse_filter_chain(" | upcase | ") == [("upcase", None)]

    def test_no_leading_pipe(self):
        # raw group 2 from regex starts after the var name — no leading content
        assert parse_filter_chain("") == []

    def test_decimals_arg(self):
        assert parse_filter_chain(" | decimals:2") == [("decimals", "2")]

    def test_three_filter_chain(self):
        assert parse_filter_chain(" | default:foo | replace:o,0 | upcase") == [
            ("default", "foo"),
            ("replace", "o,0"),
            ("upcase", None),
        ]


# =============================================================================
# apply_filters — individual filters
# =============================================================================

class TestApplyFiltersDefault:
    def test_uses_default_when_none(self):
        result = apply_filters(None, [("default", "#fff")], "bg", "bg | default:#fff")
        assert result == "#fff"

    def test_uses_default_when_empty_string(self):
        result = apply_filters("", [("default", "fallback")], "x", "x")
        assert result == "fallback"

    def test_passes_through_when_present(self):
        result = apply_filters("red", [("default", "#fff")], "bg", "bg")
        assert result == "red"

    def test_empty_default_arg(self):
        result = apply_filters(None, [("default", "")], "x", "x")
        assert result == ""


class TestApplyFiltersRequired:
    def test_passes_through_when_present(self, capsys):
        result = apply_filters("hello", [("required", None)], "x", "x")
        assert result == "hello"
        assert capsys.readouterr().out == ""

    def test_warns_when_none(self, capsys):
        apply_filters(None, [("required", None)], "course_name", "course_name | required")
        out = capsys.readouterr().out
        assert "required" in out
        assert "course_name" in out

    def test_returns_none_when_missing(self):
        result = apply_filters(None, [("required", None)], "x", "x")
        assert result is None


class TestApplyFiltersCase:
    def test_upcase(self):
        assert apply_filters("hello", [("upcase", None)], "x", "x") == "HELLO"

    def test_upcase_none_passthrough(self):
        assert apply_filters(None, [("upcase", None)], "x", "x") is None

    def test_downcase(self):
        assert apply_filters("HELLO", [("downcase", None)], "x", "x") == "hello"

    def test_titlecase(self):
        assert apply_filters("hello world", [("titlecase", None)], "x", "x") == "Hello World"

    def test_titlecase_none_passthrough(self):
        assert apply_filters(None, [("titlecase", None)], "x", "x") is None


class TestApplyFiltersReplace:
    def test_basic_replace(self):
        result = apply_filters("hello_world", [("replace", "_,-")], "x", "x")
        assert result == "hello-world"

    def test_replace_with_space(self):
        result = apply_filters("hello_world", [("replace", "_,' '")], "x", "x")
        assert result == "hello world"

    def test_replace_delete(self):
        result = apply_filters("PREFIX-name", [("replace", "PREFIX-,")], "x", "x")
        assert result == "name"

    def test_replace_none_passthrough(self):
        result = apply_filters(None, [("replace", "_,-")], "x", "x")
        assert result is None

    def test_replace_no_match(self):
        result = apply_filters("hello", [("replace", "x,y")], "x", "x")
        assert result == "hello"


class TestApplyFiltersOrdinal:
    def test_valid_integer_string(self):
        assert apply_filters("7", [("ordinal", None)], "x", "x") == "7th"

    def test_first(self):
        assert apply_filters("1", [("ordinal", None)], "x", "x") == "1st"

    def test_invalid_warns_and_passes_through(self, capsys):
        result = apply_filters("eleven", [("ordinal", None)], "n", "n | ordinal")
        assert result == "eleven"
        assert "ordinal" in capsys.readouterr().out

    def test_none_passthrough(self):
        assert apply_filters(None, [("ordinal", None)], "x", "x") is None


class TestApplyFiltersDecimals:
    def test_integer_to_decimal(self):
        assert apply_filters("11", [("decimals", "2")], "x", "x") == "11.00"

    def test_float_rounding(self):
        assert apply_filters("3.14159", [("decimals", "2")], "x", "x") == "3.14"

    def test_zero_decimals(self):
        assert apply_filters("3.9", [("decimals", "0")], "x", "x") == "4"

    def test_invalid_warns_and_passes_through(self, capsys):
        result = apply_filters("abc", [("decimals", "2")], "n", "n | decimals:2")
        assert result == "abc"
        assert "decimals" in capsys.readouterr().out

    def test_none_passthrough(self):
        assert apply_filters(None, [("decimals", "2")], "x", "x") is None


class TestApplyFiltersUnknown:
    def test_unknown_filter_warns_and_passes_through(self, capsys):
        result = apply_filters("hello", [("frobnicate", None)], "x", "x")
        assert result == "hello"
        assert "frobnicate" in capsys.readouterr().out


# =============================================================================
# apply_filters — chaining
# =============================================================================

class TestApplyFiltersChaining:
    def test_default_then_ordinal(self):
        filters = parse_filter_chain(" | default:3 | ordinal")
        assert apply_filters(None, filters, "x", "x") == "3rd"

    def test_present_value_skips_default(self):
        filters = parse_filter_chain(" | default:fallback | upcase")
        assert apply_filters("hello", filters, "x", "x") == "HELLO"

    def test_replace_then_titlecase(self):
        filters = parse_filter_chain(" | replace:_,' ' | titlecase")
        assert apply_filters("javascript_cards", filters, "x", "x") == "Javascript Cards"

    def test_required_then_default(self, capsys):
        # required fires warning; default then provides the value
        filters = parse_filter_chain(" | required | default:unknown")
        result = apply_filters(None, filters, "name", "name | required | default:unknown")
        assert result == "unknown"
        assert "required" in capsys.readouterr().out

    def test_three_filter_chain(self):
        # default provides "hello world"; replace swaps space for -; upcase uppercases
        filters = parse_filter_chain(" | default:hello world | replace:' ',- | upcase")
        assert apply_filters(None, filters, "x", "x") == "HELLO-WORLD"


# =============================================================================
# interpolate_body — end-to-end
# =============================================================================

class TestInterpolateBody:
    def test_plain_var_unchanged_behaviour(self):
        result = interpolate_body("{{var:x}}", {"x": "hello"})
        assert result == "<!-- {{var:x}} -->hello<!-- {{/var:x}} -->"

    def test_missing_var_preserved(self):
        assert interpolate_body("{{var:missing}}", {}) == "{{var:missing}}"

    def test_filter_in_marker(self):
        result = interpolate_body("{{var:x | upcase}}", {"x": "hello"})
        assert "<!-- {{var:x | upcase}} -->" in result
        assert "HELLO" in result
        assert "<!-- {{/var:x | upcase}} -->" in result

    def test_default_resolves_missing(self):
        result = interpolate_body("{{var:color | default:#fff}}", {})
        assert "#fff" in result
        assert "<!-- {{var:color | default:#fff}} -->" in result

    def test_missing_with_no_default_preserved(self):
        result = interpolate_body("{{var:color}}", {})
        assert result == "{{var:color}}"

    def test_ordinal_filter(self):
        result = interpolate_body("{{var:n | ordinal}}", {"n": "7"})
        assert "7th" in result

    def test_chained_filters_in_marker(self):
        result = interpolate_body(
            "{{var:name | replace:_,' ' | titlecase}}",
            {"name": "javascript_cards"},
        )
        assert "Javascript Cards" in result
        assert "<!-- {{var:name | replace:_,' ' | titlecase}} -->" in result

    def test_multiple_vars_in_body(self):
        body = "Session {{var:session}} of {{var:total | default:25}}"
        result = interpolate_body(body, {"session": "11"})
        assert "11" in result
        assert "25" in result

    def test_round_trip_marker_restorable(self):
        """Marker output can be restored by restore_zaphod_markers."""
        from zaphod.frontmatter_to_meta import restore_zaphod_markers
        import re
        # Simulate: publish (interpolate) then import (restore)
        html = interpolate_body("{{var:session | ordinal}}", {"session": "3"})
        # restore_zaphod_markers expects HTML — wrap in a minimal container
        restored = restore_zaphod_markers(html)
        assert restored == "{{var:session | ordinal}}"
