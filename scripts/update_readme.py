"""
Fills the auto-generated blocks in README.md:

  <!-- PRS:START --> ... <!-- PRS:END -->                   latest merged OSS PRs
  <!-- ACHIEVEMENTS:START --> ... <!-- ACHIEVEMENTS:END -->  from profile.yml

Everything outside the markers is left untouched, so the rest of the README
can be edited by hand. If the PR fetch fails the existing block is kept.
"""

import os
import re
import datetime

from profile_data import ROOT, load_profile, fetch_prs

README = os.path.join(ROOT, "README.md")


def replace_block(text, name, body):
    pattern = re.compile(rf"(<!-- {name}:START -->).*?(<!-- {name}:END -->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"README is missing the {name} markers")
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(2)}", text)


def fmt_stars(n):
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def prs_block(prs):
    if not prs:
        return "_No merged PRs yet — soon._"
    lines = ["| Repo | PR | Merged |", "|---|---|---|"]
    for p in prs:
        title = p["title"].replace("|", "\\|")
        if len(title) > 60:
            title = title[:57].rstrip() + "..."
        merged = datetime.date.fromisoformat(p["merged_at"][:10]).strftime("%b %Y")
        lines.append(
            f"| [**{p['repo']}**](https://github.com/{p['repo']}) ⭐ {fmt_stars(p['stars'])} "
            f"| [#{p['number']}]({p['url']}) {title} | {merged} |"
        )
    return "\n".join(lines)


def achievements_block(items):
    return "\n".join(f"- 🏆 {a}" for a in items)


def main():
    profile = load_profile()
    with open(README, encoding="utf-8") as f:
        text = f.read()

    cfg = profile.get("prs", {})
    prs = fetch_prs(cfg.get("limit", 6), cfg.get("exclude_repos", []))
    if prs is None:
        print("PR fetch failed; keeping existing PR block")
    else:
        text = replace_block(text, "PRS", prs_block(prs))
    text = replace_block(text, "ACHIEVEMENTS", achievements_block(profile.get("achievements", [])))

    with open(README, "w", encoding="utf-8") as f:
        f.write(text)
    print("README updated")


if __name__ == "__main__":
    main()
