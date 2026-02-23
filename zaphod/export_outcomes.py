#!/usr/bin/env python3
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

"""
export_outcomes.py — Step 7: Write outcomes CSV alongside the .imscc file.

Reads:  outcomes/outcomes.yaml

Writes: {output_path}.outcomes.csv  (next to the .imscc — NOT inside the zip)

Canvas does not support learning outcomes inside CC packages — they must be
imported separately via Canvas > Course Settings > Import > Outcomes CSV.
This step generates that file so it travels with the cartridge.

vendor_guid uses the explicit value from outcomes.yaml if set, otherwise
falls back to the outcome code alone (no course_id prefix — the target
course doesn't exist yet at export time so its ID is unknown).

This step makes no changes to the manifest (the CSV is not in the zip).

Standalone:
    python -m zaphod.export_outcomes
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Optional

import yaml

from zaphod.export_types import ExportManifest

COURSE_ROOT = Path.cwd()
OUTCOMES_DIR = COURSE_ROOT / "outcomes"
METADATA_DIR = COURSE_ROOT / "_course_metadata"
EXPORTS_DIR = METADATA_DIR / "exports"
DEFAULT_MANIFEST_PATH = EXPORTS_DIR / ".export_manifest.json"


def get_manifest_path() -> Path:
    env_path = os.environ.get("EXPORT_MANIFEST_PATH")
    return Path(env_path) if env_path else DEFAULT_MANIFEST_PATH


# ============================================================================
# CSV generation
# ============================================================================

BASE_HEADERS = [
    "vendor_guid", "object_type", "title", "description",
    "display_name", "calculation_method", "calculation_int",
    "workflow_state", "parent_guids", "mastery_points",
]


def write_outcomes_csv(output_path: Path) -> int:
    """
    Generate an outcomes CSV at *output_path*.

    Returns the number of outcomes written (0 if none found).
    """
    outcomes_file = OUTCOMES_DIR / "outcomes.yaml"
    if not outcomes_file.is_file():
        return 0

    try:
        data = yaml.safe_load(outcomes_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[export:outcomes:warn] Failed to read outcomes.yaml: {e}")
        return 0

    course_clos = (data or {}).get("course_outcomes", [])
    if not course_clos:
        return 0

    rows = []
    for clo in course_clos:
        code = clo.get("code", "")
        title = clo.get("title", "")
        if not code or not title:
            continue

        vendor_guid = clo.get("vendor_guid") or code
        ratings = sorted(
            clo.get("ratings") or [],
            key=lambda r: float(r.get("points", 0)),
            reverse=True,
        )
        ratings_cells = []
        for r in ratings:
            ratings_cells.append(str(r.get("points", "")))
            ratings_cells.append(r.get("description", ""))

        mastery = clo.get("mastery_points")
        rows.append([
            vendor_guid, "outcome", title,
            clo.get("description", ""), code,
            "", "", "active", "",
            str(mastery) if mastery is not None else "",
        ] + ratings_cells)

    if not rows:
        return 0

    max_len = max(len(r) for r in rows)
    extra = max(1, max_len - len(BASE_HEADERS))
    headers = BASE_HEADERS + ["ratings"] + [""] * (extra - 1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            padded = row + [""] * (len(headers) - len(row))
            writer.writerow(padded)

    return len(rows)


# ============================================================================
# Main step logic
# ============================================================================

def export_outcomes(manifest: ExportManifest) -> Optional[Path]:
    """
    Write outcomes CSV alongside the .imscc output path.

    Returns the CSV path written, or None if no outcomes found.
    """
    csv_path = manifest.output_path.with_suffix(".outcomes.csv")
    n = write_outcomes_csv(csv_path)
    if n:
        print(f"[export:outcomes] {n} outcomes → {csv_path.name}")
        print("[export:outcomes] Import separately: "
              "Canvas > Course Settings > Import > Outcomes CSV")
        return csv_path
    return None


def main() -> None:
    manifest_path = get_manifest_path()
    if not manifest_path.is_file():
        print(f"[export:outcomes] ERROR: manifest not found at {manifest_path}")
        print("[export:outcomes] Run 'zaphod export' first to initialise the export.")
        raise SystemExit(1)

    manifest = ExportManifest.load(manifest_path)
    export_outcomes(manifest)
    # No manifest.save() — this step does not modify the manifest


if __name__ == "__main__":
    main()
