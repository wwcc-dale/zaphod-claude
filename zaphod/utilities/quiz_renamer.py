#!/usr/bin/env python3
import os
import re
import glob

def slugify(text: str) -> str:
    text = text.strip()
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"[\/\s]+", "-", text)
    text = re.sub(r"[^a-zA-Z0-9\-]", "", text)
    text = re.sub(r"-{2,}", "-", text)
    text = text.strip("-")
    return text

def extract_title(path: str) -> str | None:
    with open(path, "r", encoding="utf-8") as f:
        in_frontmatter = False
        for line in f:
            line = line.rstrip("\n")
            if line.strip() == "---":
                if not in_frontmatter:
                    in_frontmatter = True
                    continue
                else:
                    break
            if in_frontmatter and line.lstrip().startswith("title:"):
                title = line.split(":", 1)[1].strip()
                if (title.startswith('"') and title.endswith('"')) or (
                    title.startswith("'") and title.endswith("'")
                ):
                    title = title[1:-1]
                return title
    return None

def main():
    used = {}

    for path in sorted(glob.glob("*.quiz.txt")):
        title = extract_title(path)
        if not title:
            base = os.path.splitext(os.path.basename(path))[0]
            target = base + ".quiz.txt"
        else:
            m = re.match(r"\s*Session\s+(\d+)\s*[–-]?\s*(.*)", title)
            if m:
                session_num = m.group(1)
                rest = m.group(2).strip()
            else:
                session_num = "0"
                rest = title

            rest_slug = slugify(rest) if rest else "session"
            target_base = f"{session_num}-{rest_slug}"
            target_name = target_base

            counter = used.get(target_base, 0)
            if counter > 0:
                target_name = f"{target_base}-{counter+1}"
            used[target_base] = counter + 1

            target = target_name + ".quiz.txt"

        src = path
        dst = target

        if src == dst:
            continue  # already correctly named

        if os.path.exists(dst):
            raise FileExistsError(f"Target already exists: {dst}")

        print(f"Renaming {src} -> {dst}")
        os.rename(src, dst)

if __name__ == "__main__":
    main()
