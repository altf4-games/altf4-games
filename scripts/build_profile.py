"""
Builds everything the profile README shows, from profile.yml + GitHub data:

  assets/{dark,light}/section-*.svg       numbered section headers
  assets/{dark,light}/pr-N.svg            one card per merged open-source PR
  assets/{dark,light}/research-N.svg      papers / IP
  assets/{dark,light}/footer.svg
  README.md  PRS / RESEARCH blocks (cards that need their own link)

Output is deterministic, so the workflow only commits when data changed.
"""

import datetime
import glob
import os
import re
from html.parser import HTMLParser

import svg_kit as kit
from profile_data import ROOT, load_profile, oss_data

ASSETS = os.path.join(ROOT, "assets")
README = os.path.join(ROOT, "README.md")
RAW = "./assets"
ART = {"dark": "ascii-art.html", "light": "ascii-art_light.html"}   # Kiryu, as drawn

# Header files are named after the section, not its number, so reordering
# never serves a stale header from GitHub's image cache.
# neofetch, Doom, experience and wins live in the terminal animation
# (scripts/build_terminal_anim.py), so only these two get headers.
SECTIONS = [
    ("open source", "~/merged-prs", "purple"),
    ("research", "~/papers", "green"),
]


def section_file(title):
    return "section-" + title.replace(" ", "-") + ".svg"


class _AsciiParser(HTMLParser):
    """Collects (char, color) pairs row by row from the <span style=color> art."""

    def __init__(self):
        super().__init__()
        self.rows = [[]]
        self._color = "#888888"
        self._in_body = False

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self._in_body = True
        elif tag == "br" and self._in_body:
            self.rows.append([])
        elif tag == "span":
            style = dict(attrs).get("style", "")
            if "color:" in style:
                self._color = style.split("color:")[1].split(";")[0].strip()

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and self._in_body:
            self.rows.append([])

    def handle_data(self, data):
        if self._in_body:
            self.rows[-1].extend((ch, self._color) for ch in data if ch != "\n")


def load_art(theme):
    parser = _AsciiParser()
    with open(os.path.join(ROOT, ART[theme]), encoding="utf-8") as f:
        parser.feed(f.read())
    return [r for r in parser.rows if r]


def write(theme, name, svg):
    os.makedirs(os.path.join(ASSETS, theme), exist_ok=True)
    with open(os.path.join(ASSETS, theme, name), "w", encoding="utf-8") as f:
        f.write(svg + "\n")


def picture(name, alt, width=None):
    w = f' width="{width}"' if width else ""
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{RAW}/dark/{name}">'
            f'<img src="{RAW}/light/{name}" alt="{kit.esc(alt)}"{w}></picture>')


def linked(url, pic):
    return f'<a href="{url}">{pic}</a>' if url else pic


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
    research = profile.get("research", [])

    # drop numbered cards left over from a longer list, and cards that moved
    # into the terminal animation
    for pattern in ("pr-*.svg", "research-*.svg", "section-*.svg",
                    "neofetch.svg", "experience.svg", "wins.svg"):
        for old in glob.glob(os.path.join(ASSETS, "*", pattern)):
            os.remove(old)

    for theme in kit.THEMES:
        for i, (title, path, accent) in enumerate(SECTIONS):
            write(theme, section_file(title), kit.section(theme, f"{i + 1:02d}", title, path, accent))
        for i, p in enumerate(prs):
            merged = datetime.date.fromisoformat(p["merged_at"][:10]).strftime("%b %Y")
            write(theme, f"pr-{i + 1}.svg", kit.pr_card(theme, p, merged))
        for i, item in enumerate(research):
            write(theme, f"research-{i + 1}.svg", kit.research_card(theme, item))
        write(theme, "footer.svg", kit.footer(theme, term["user"], term["host"]))

    pr_html = "\n".join(
        linked(p["url"], picture(f"pr-{i + 1}.svg", f"{p['repo']} #{p['number']}: {p['title']}"))
        for i, p in enumerate(prs)) or "<sub>No merged PRs yet. Soon.</sub>"
    research_html = "\n".join(
        linked(item.get("url"), picture(f"research-{i + 1}.svg", f"{item['kind']}: {item['title']}"))
        for i, item in enumerate(research))

    with open(README, encoding="utf-8") as f:
        text = f.read()
    text = replace_block(text, "PRS", pr_html)
    text = replace_block(text, "RESEARCH", research_html)
    with open(README, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Built profile: {len(prs)} PR cards ({oss['total']} merged OSS PRs), "
          f"{len(research)} research items")


if __name__ == "__main__":
    main()
