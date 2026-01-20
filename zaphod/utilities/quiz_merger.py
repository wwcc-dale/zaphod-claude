#!/usr/bin/env python3
import os
import re
import glob
from collections import defaultdict

QUIZ_EXT = ".quiz.txt"
DELETE_EXT = ".quiz.delete"

# Match: <prefix>-<stem>.quiz.txt or <prefix>-<stem>-<n>.quiz.txt
suffix_re = re.compile(
    r"^(?P<prefix>\d+)-(?P<stem>.+?)(?:-(?P<suffix>\d+))?" + re.escape(QUIZ_EXT) + r"$"
)

def split_frontmatter_and_body(text: str):
    """
    Returns (frontmatter, body).
    If no frontmatter found, frontmatter is '' and body is the whole text.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return "", text

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        # malformed frontmatter; treat as no frontmatter
        return "", text

    frontmatter = "".join(lines[: end_idx + 1])
    body = "".join(lines[end_idx + 1 :])
    return frontmatter, body

def main():
    groups = defaultdict(list)

    # Group files by (prefix, stem)
    for path in glob.glob(f"*{QUIZ_EXT}"):
        m = suffix_re.match(path)
        if not m:
            continue
        prefix = m.group("prefix")
        stem = m.group("stem")
        suffix = m.group("suffix")
        numeric_suffix = int(suffix) if suffix is not None else 0  # 0 = no digit
        groups[(prefix, stem)].append((numeric_suffix, path))

    for (prefix, stem), items in groups.items():
        # Sort: no digit (0) first, then 2, 3, ...
        items.sort(key=lambda t: (t[0] != 0, t[0]))

        out_name = f"{prefix}-{stem}{QUIZ_EXT}"

        frontmatter_written = False
        merged_parts = []

        for idx, (suffix_num, path) in enumerate(items):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            fm, body = split_frontmatter_and_body(content)

            if idx == 0:
                # First file: keep its frontmatter and body
                if fm:
                    merged_parts.append(fm)
                    frontmatter_written = True
                merged_parts.append(body.lstrip("\n"))
            else:
                # Subsequent files: omit frontmatter
                if not frontmatter_written and fm:
                    # Safety: if first had no frontmatter, use next one's
                    merged_parts.insert(0, fm)
                    frontmatter_written = True
                merged_parts.append("\n\n")
                merged_parts.append(body.lstrip("\n"))

        merged_text = "".join(merged_parts)

        print(f"Merging {len(items)} files into {out_name}")
        with open(out_name, "w", encoding="utf-8") as out_f:
            out_f.write(merged_text)

        # Post-process sources:
        # - Keep the base file (no numeric suffix) as the merged name
        # - Rename any file with numeric suffix to .quiz.delete
        for suffix_num, path in items:
            if suffix_num == 0:
                # Base file name may already be out_name; if different, rename to merged name
                if path != out_name:
                    print(f"Renaming base {path} -> {out_name}")
                    os.replace(path, out_name)
            else:
                base_without_ext = path[: -len(QUIZ_EXT)]
                delete_name = base_without_ext + DELETE_EXT
                print(f"Renaming {path} -> {delete_name}")
                os.replace(path, delete_name)

if __name__ == "__main__":
    main()
