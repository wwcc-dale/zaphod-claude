import os
import re
import math
import argparse


def slugify(text: str, max_words: int = 6) -> str:
    """
    Turn a title into a short, dashed slug:
    "What Is UX and Who Are We Designing For?"
    -> "what-is-ux-and-who-are-we-designing-for"
    """
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [w for w in text.split() if w]
    words = words[:max_words]
    return "-".join(words) if words else "session"


def extract_meta(body: str):
    """
    Extract Outcomes and Topics lines from the section body.

    Expected markdown lines like:
    **Outcomes:** 2, 4
    **Topics:** 6

    Returns (outcomes_list_or_None, topics_list_or_None, cleaned_body).
    """
    outcomes = None
    topics = None
    lines = body.splitlines()
    cleaned_lines = []

    outcomes_re = re.compile(r"^\s*\*\*Outcomes:\*\*\s*(.+)", re.IGNORECASE)
    topics_re = re.compile(r"^\s*\*\*Topics:\*\*\s*(.+)", re.IGNORECASE)

    def split_list(value: str):
        # Split on commas, trim whitespace, drop empties
        return [v.strip() for v in value.split(",") if v.strip()]

    for line in lines:
        m_o = outcomes_re.match(line)
        m_t = topics_re.match(line)
        if m_o:
            outcomes = split_list(m_o.group(1))
            continue  # drop this line from body
        if m_t:
            topics = split_list(m_t.group(1))
            continue  # drop this line from body
        cleaned_lines.append(line)

    cleaned_body = "\n".join(cleaned_lines)
    return outcomes, topics, cleaned_body


def split_markdown(source_file, destination_path, items_per_module, fence_regex):
    try:
        with open(source_file, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Source file '{source_file}' not found.")
        return

    os.makedirs(destination_path, exist_ok=True)

    pattern = re.compile(fence_regex)
    matches = list(pattern.finditer(content))

    if not matches:
        print(f"No matches found using regex: {fence_regex}")
        return

    for i, match in enumerate(matches):
        # Group 1: session number
        try:
            session_n_str = match.group(1)
            session_n = int(session_n_str)
        except (IndexError, ValueError, TypeError):
            session_n = i + 1

        # Group 2: title text
        try:
            session_name = match.group(2).strip()
        except (IndexError, AttributeError):
            session_name = match.group(0).lstrip("#").strip()

        # Credit calculation
        credit_num = math.ceil(session_n / items_per_module)

        # Folder name with dashed slug, no explicit "session-n"
        short_slug = slugify(session_name)
        folder_name = f"{i+1:02d}-{short_slug}.assignment"
        target_dir = os.path.join(destination_path, folder_name)

        # Section content
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end]

        # Extract Outcomes/Topics and remove those lines from the body
        outcomes, topics, cleaned_body = extract_meta(body)

        # Build frontmatter
        frontmatter_lines = [
            "---",
            f"name: {session_name}",
            "type: \"Assignment\"",
            "published: true",
            "modules:",
            f" - \"Credit {credit_num}\"",
        ]

        if outcomes:
            frontmatter_lines.append("outcomes:")
            for o in outcomes:
                frontmatter_lines.append(f" - \"{o}\"")

        if topics:
            frontmatter_lines.append("topics:")
            for t in topics:
                frontmatter_lines.append(f" - \"{t}\"")

        frontmatter_lines.append("---")
        frontmatter = "\n".join(frontmatter_lines) + "\n\n"

        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, "index.md")
        with open(file_path, "w", encoding="utf-8") as out_f:
            out_f.write(frontmatter + cleaned_body)

    print(f"Successfully processed {len(matches)} sections into '{destination_path}'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zaphod Markdown Splitter")
    parser.add_argument("source", help="Path to source markdown file")
    parser.add_argument("destination", help="Base directory for output")
    # Accept ASCII hyphen, en dash (U+2013), em dash (U+2014)
    parser.add_argument(
        "--regex",
        default=r"## Session (\d+)\s*[-\u2013\u2014]\s*(.*)",
        help="Regex with Group 1 as number and Group 2 as name",
    )
    parser.add_argument(
        "--items",
        type=int,
        default=5,
        help="Sessions per credit (default: 5)",
    )

    args = parser.parse_args()
    split_markdown(args.source, args.destination, args.items, args.regex)
