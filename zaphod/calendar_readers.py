"""
calendar_readers.py — Pluggable readers for academic calendar source formats.

Each reader parses a source file and returns a normalised source dict
that process_calendar() in calendar.py can consume.

Normalised source dict shape:
  {
    "year":   "2025-26",
    "school": "WWCC",
    "totalInstructionDays": 203,   # optional
    "terms": [
      {
        "id":    "summer-2025",
        "name":  "Summer Quarter",
        "short": "Summer '25",
        "start": "2025-07-01",
        "end":   "2025-09-05",
        "holidays": [
          {"date": "2025-07-04", "label": "Independence Day"},
        ]
      },
      ...
    ]
  }

To add a new reader:
  1. Subclass CalendarReader
  2. Implement can_read() and read()
  3. Append an instance to READERS at the bottom of this file
"""

import json
import re
from abc import ABC, abstractmethod
from datetime import date, timedelta
from itertools import groupby
from pathlib import Path

import yaml


# =============================================================================
# Abstract base
# =============================================================================

class CalendarReader(ABC):
    @abstractmethod
    def can_read(self, path: Path) -> bool:
        """Return True if this reader handles the given file."""

    @abstractmethod
    def read(self, path: Path) -> dict:
        """Parse path and return a normalised source dict."""


# =============================================================================
# YAML / JSON reader
# =============================================================================

class YamlJsonReader(CalendarReader):
    def can_read(self, path: Path) -> bool:
        return path.suffix.lower() in (".yaml", ".yml", ".json")

    def read(self, path: Path) -> dict:
        raw = path.read_text(encoding="utf-8")
        if path.suffix.lower() in (".yaml", ".yml"):
            return yaml.safe_load(raw)
        return json.loads(raw)


# =============================================================================
# WWCC PDF reader
# =============================================================================

# Keywords that signal in-service days, graduations, or other non-holiday
# events — these are excluded from the holidays list.
_SKIP_KEYWORDS = {
    "in-service", "in service", "conference", "graduation",
    "contracts", "optional", "begins", "ends", "commencement",
}

# Maps month name → month number
_MONTH_NUMBERS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

# Quarter keyword → term key ("summer", "fall", "winter", "spring")
_QUARTER_TERMS = {
    "summer": "summer",
    "fall":   "fall",
    "winter": "winter",
    "spring": "spring",
}


def _is_skip_entry(label: str) -> bool:
    low = label.lower()
    return any(kw in low for kw in _SKIP_KEYWORDS)


def _is_term_boundary(label: str) -> tuple[str, str] | None:
    """
    Return (term_key, "start"|"end") if the label describes a quarter
    boundary, else None.
    """
    low = label.lower()
    for qname, tkey in _QUARTER_TERMS.items():
        if qname in low:
            if "begin" in low:
                return tkey, "start"
            if "end" in low:
                return tkey, "end"
    return None


def _expand_date_range(month: int, year: int, day_str: str) -> list[str]:
    """
    Parse day_str like "4", "24-28", "11-12" into ISO date strings.
    Returns a list (usually one item, multiple for ranges).
    """
    day_str = day_str.strip().rstrip("-")
    if "-" in day_str:
        parts = day_str.split("-")
        try:
            start_d, end_d = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return []
        return [
            date(year, month, d).isoformat()
            for d in range(start_d, end_d + 1)
        ]
    try:
        return [date(year, month, int(day_str)).isoformat()]
    except ValueError:
        return []


class WwccPdfReader(CalendarReader):
    """
    Reader for the WWCC 212-Day Instructional Calendar PDF.

    Extracts the "Important Dates" sidebar using pdfplumber, splits
    into left/right columns by x-coordinate, and builds a normalised
    source dict with term boundaries and holidays.
    """

    # x-coordinate threshold separating left and right columns
    _COL_SPLIT_X = 560

    # x / top bounds of the Important Dates region
    _REGION_X_MIN  = 480
    _REGION_TOP_MIN = 270  # slightly above "Important Dates" header

    def can_read(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def read(self, path: Path) -> dict:
        try:
            import pdfplumber
        except ImportError:
            raise ImportError(
                "pdfplumber is required for PDF calendar parsing.\n"
                "  pip install pdfplumber"
            )

        with pdfplumber.open(str(path)) as pdf:
            page = pdf.pages[0]
            return self._parse_page(page, path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_page(self, page, path: Path) -> dict:
        words = page.extract_words()

        year_str, school = self._extract_header(words)
        year1, year2 = self._parse_academic_year(year_str)
        total = self._extract_total_days(words)

        left_lines, right_lines = self._extract_columns(words)

        # Collect all dated events from both columns
        all_events = self._parse_column(left_lines, year1, year2, side="left")
        all_events += self._parse_column(right_lines, year1, year2, side="right")

        terms = self._build_terms(all_events, year1, year2)
        result = {"year": year_str, "school": school, "terms": terms}
        if total:
            result["totalInstructionDays"] = total
        return result

    def _extract_header(self, words: list[dict]) -> tuple[str, str]:
        """Return (academic_year, school_name) from page words."""
        year_str = "unknown"
        school = "unknown"
        for w in words:
            # Academic year: "2025-26" or "2025-2026"
            if re.match(r'^\d{4}-\d{2,4}$', w["text"]):
                year_str = self._normalise_year(w["text"])
            # School name: short uppercase word in the title area
            if w["text"].isupper() and len(w["text"]) >= 2 and w["top"] < 150:
                school = w["text"]
        return year_str, school

    @staticmethod
    def _normalise_year(raw: str) -> str:
        """'2025-2026' → '2025-26';  '2025-26' unchanged."""
        m = re.match(r'^(\d{4})-(\d{4})$', raw)
        if m:
            return f"{m.group(1)}-{m.group(2)[2:]}"
        return raw

    def _parse_academic_year(self, year_str: str) -> tuple[int, int]:
        """'2025-26' → (2025, 2026)"""
        try:
            parts = year_str.split("-")
            year1 = int(parts[0])
            suffix = parts[1]
            year2 = year1 + 1 if len(suffix) <= 2 else int(suffix)
            return year1, year2
        except (ValueError, IndexError):
            return 2025, 2026

    def _extract_total_days(self, words: list[dict]) -> int | None:
        """Find 'Instructional Days' label and return the adjacent number."""
        for i, w in enumerate(words):
            if w["text"] == "Days" and i > 0 and words[i - 1]["text"] == "Instructional":
                # The number follows on the same or next word
                for j in range(i + 1, min(i + 4, len(words))):
                    try:
                        return int(words[j]["text"])
                    except ValueError:
                        continue
        return None

    def _extract_columns(self, words: list[dict]) -> tuple[list[str], list[str]]:
        """
        Isolate the Important Dates region and split into left / right
        column lines based on x-coordinate.
        """
        region = [
            w for w in words
            if w["x0"] >= self._REGION_X_MIN and w["top"] >= self._REGION_TOP_MIN
        ]
        # Skip the "Important Dates" header words themselves
        region = [w for w in region if w["text"] not in ("Important", "Dates")]

        region.sort(key=lambda w: (round(w["top"] / 5) * 5, w["x0"]))

        left_words: list[dict] = []
        right_words: list[dict] = []
        for w in region:
            if w["x0"] < self._COL_SPLIT_X:
                left_words.append(w)
            else:
                right_words.append(w)

        return self._words_to_lines(left_words), self._words_to_lines(right_words)

    def _words_to_lines(self, words: list[dict]) -> list[str]:
        """Group words into text lines by approximate y position."""
        lines = []
        words.sort(key=lambda w: (round(w["top"] / 5) * 5, w["x0"]))
        for _, group in groupby(words, key=lambda w: round(w["top"] / 5) * 5):
            line = " ".join(w["text"] for w in group).strip()
            if line:
                lines.append(line)
        return lines

    def _parse_column(
        self, lines: list[str], year1: int, year2: int, side: str
    ) -> list[dict]:
        """
        Parse a single column's lines into a list of event dicts:
          {"dates": ["2025-07-04"], "label": "Independence Day",
           "type": "holiday" | "term_start" | "term_end" | "skip"}
        """
        # Left col: Jul–Dec → year1;  Right col: Jan–Jun → year2
        # But we track month context to assign the correct year.
        events = []
        current_month = None
        current_year = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Month header (standalone word, no digits)
            low = line.lower()
            if low in _MONTH_NUMBERS and not re.search(r'\d', line):
                current_month = _MONTH_NUMBERS[low]
                current_year = year1 if current_month >= 7 else year2
                continue

            if current_month is None:
                continue  # haven't hit a month header yet

            # Parse "day(s) - label" or "day(s) label"
            m = re.match(r'^(\d[\d\-]*)\s*[-–]\s*(.+)$', line)
            if not m:
                # Try without separator: "25- Christmas" → already handled by
                # tokeniser, but guard against bare month names or noise
                m = re.match(r'^(\d[\d\-]*)\s+(.+)$', line)
            if not m:
                continue

            day_str = m.group(1).strip("-")
            label   = m.group(2).strip()

            dates = _expand_date_range(current_month, current_year, day_str)
            if not dates:
                continue

            boundary = _is_term_boundary(label)
            if boundary:
                events.append({"dates": dates, "label": label,
                                "type": f"term_{boundary[1]}", "term": boundary[0]})
            elif _is_skip_entry(label):
                events.append({"dates": dates, "label": label, "type": "skip"})
            else:
                events.append({"dates": dates, "label": label, "type": "holiday"})

        return events

    def _build_terms(
        self, events: list[dict], year1: int, year2: int
    ) -> list[dict]:
        """Assemble term dicts from boundary events, attaching holidays."""
        # Collect term boundaries
        boundaries: dict[str, dict[str, str]] = {}
        for ev in events:
            if ev["type"] in ("term_start", "term_end"):
                key = ev["term"]
                side = ev["type"].split("_")[1]  # "start" or "end"
                boundaries.setdefault(key, {})[side] = ev["dates"][0]

        # Term ordering and metadata
        term_order = [
            ("summer", f"summer-{year1}", "Summer Quarter", f"Summer '{str(year1)[2:]}"),
            ("fall",   f"fall-{year1}",   "Fall Quarter",   f"Fall '{str(year1)[2:]}"),
            ("winter", f"winter-{year2}", "Winter Quarter", f"Winter '{str(year2)[2:]}"),
            ("spring", f"spring-{year2}", "Spring Quarter", f"Spring '{str(year2)[2:]}"),
        ]

        terms = []
        for tkey, tid, tname, tshort in term_order:
            b = boundaries.get(tkey, {})
            start = b.get("start")
            end   = b.get("end")
            if not start or not end:
                continue

            # Attach holidays that fall within this term's date range
            holidays = []
            seen: set[str] = set()
            for ev in events:
                if ev["type"] != "holiday":
                    continue
                for d in ev["dates"]:
                    if start <= d <= end and d not in seen:
                        holidays.append({"date": d, "label": ev["label"]})
                        seen.add(d)

            holidays.sort(key=lambda h: h["date"])

            terms.append({
                "id":       tid,
                "name":     tname,
                "short":    tshort,
                "start":    start,
                "end":      end,
                "holidays": holidays,
            })

        return terms


# =============================================================================
# Registry and factory
# =============================================================================

READERS: list[CalendarReader] = [
    YamlJsonReader(),
    WwccPdfReader(),
]


def get_reader(path: Path) -> CalendarReader:
    """Return the first registered reader that can handle path."""
    for reader in READERS:
        if reader.can_read(path):
            return reader
    raise ValueError(
        f"No calendar reader available for '{path.suffix}' files.\n"
        f"Supported: {[r.__class__.__name__ for r in READERS]}"
    )
