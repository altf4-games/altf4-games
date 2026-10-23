"""
Builds everything the profile README shows, from profile.yml + GitHub data:

  assets/{dark,light}/terminal.svg        animated neofetch card
  assets/{dark,light}/s01..s03.svg        numbered section headers
  assets/{dark,light}/pr-N.svg            one card per merged open-source PR
  assets/{dark,light}/wins.svg            achievements card
  assets/{dark,light}/footer.svg
  README.md  <!-- PRS:START/END -->       the clickable PR card list

Output is deterministic, so the workflow only commits when data changed.
"""

import datetime
import glob
import os
import re

import svg_kit as kit
from profile_data import ROOT, load_profile, oss_data

ASSETS = os.path.join(ROOT, "assets")
README = os.path.join(ROOT, "README.md")
RAW = "./assets"

SECTIONS = [
    ("s01", "01", "now playing", "~/doom", "red"),
    ("s02", "02", "open source", "~/merged-prs", "purple"),
    ("s03", "03", "wins", "~/trophies", "gold"),
]


def write(theme, name, svg):
    os.makedirs(os.path.join(ASSETS, theme), exist_ok=True)
    with open(os.path.join(ASSETS, theme, name), "w", encoding="utf-8") as f:
        f.write(svg + "\n")


def picture(name, alt, width=None):
    w = f' width="{width}"' if width else ""
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{RAW}/dark/{name}">'
            f'<img src="{RAW}/light/{name}" alt="{alt}"{w}></picture>')


def pr_block(prs):
    if not prs:
        return "<sub>No merged PRs yet. Soon.</sub>"
    lines = []
    for i, p in enumerate(prs):
        alt = kit.esc(f"{p['repo']} #{p['number']}: {p['title']}")
        lines.append(f'<a href="{p["url"]}">{picture(f"pr-{i + 1}.svg", alt)}</a>')
    return "\n".join(lines)


def replace_block(text, name, body):
    pattern = re.compile(rf"(<!-- {name}:START -->).*?(<!-- {name}:END -->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"README is missing the {name} markers")
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(2)}", text)


def main():
    profile = load_profile()
    term = profile["terminal"]
    oss = oss_data(profile)
    prs = oss["prs"]

    rows = [(label, str(value).replace("{oss_prs}", str(oss["total"])))
            for label, value in term["rows"]]

    # drop PR cards left over from a longer list
    for old in glob.glob(os.path.join(ASSETS, "*", "pr-*.svg")):
        os.remove(old)

    for theme in kit.THEMES:
        write(theme, "terminal.svg", kit.terminal(
            theme, term["user"], term["host"], rows, term["tagline"], term["location"]))
        for name, num, title, path, accent in SECTIONS:
            write(theme, f"{name}.svg", kit.section(theme, num, title, path, accent))
        for i, p in enumerate(prs):
            merged = datetime.date.fromisoformat(p["merged_at"][:10]).strftime("%b %Y")
            write(theme, f"pr-{i + 1}.svg", kit.pr_card(theme, p, merged))
        write(theme, "wins.svg", kit.wins(theme, profile.get("achievements", [])))
        write(theme, "footer.svg", kit.footer(theme, term["user"], term["host"]))

    with open(README, encoding="utf-8") as f:
        text = f.read()
    text = replace_block(text, "PRS", pr_block(prs))
    with open(README, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Built profile: {len(prs)} PR cards, {oss['total']} merged OSS PRs total")


if __name__ == "__main__":
    main()
