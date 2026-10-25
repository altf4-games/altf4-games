"""
Builds the pieces of the profile README that follow live data:

  assets/{dark,light}/footer.svg   footer card
  README.md  RESUME block          resume badge, linked to the resume URL the
                                   portfolio site currently serves

Everything else (neofetch, Doom, wins, work, merged PRs) is the terminal
animation made by scripts/build_terminal_anim.py.

Output is deterministic, so the workflow only commits when something changed.
"""

import base64
import glob
import html
import os
import re
import urllib.parse

import svg_kit as kit
from profile_data import ROOT, fetch_resume_url, load_profile

ASSETS = os.path.join(ROOT, "assets")
README = os.path.join(ROOT, "README.md")

# Document glyph for the badge (shields.io has no generic one).
DOC_PATH = ("M6 2a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6H6zm7 1.5L18.5 9H13V3.5z"
            "M8 13h8v1.5H8V13zm0 3h8v1.5H8V16z")


def icon(path, colour):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
           f'<path fill="#{colour}" d="{path}"/></svg>')
    return urllib.parse.quote("data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode(), safe="")


def badge(url, label, path, light_colour):
    base = f"https://img.shields.io/badge/{label}-%s?style=flat-square&logo=%s"
    dark = base % ("0d1117", icon(path, "ffffff"))
    light = base % ("ffffff", icon(path, light_colour))
    return (f'<a href="{html.escape(url, quote=True)}"><picture>'
            f'<source media="(prefers-color-scheme: dark)" srcset="{dark}">'
            f'<img src="{light}" alt="{label.title()}"></picture></a>')


def write(theme, name, svg):
    os.makedirs(os.path.join(ASSETS, theme), exist_ok=True)
    with open(os.path.join(ASSETS, theme, name), "w", encoding="utf-8") as f:
        f.write(svg + "\n")


def update_resume_badge(url):
    with open(README, encoding="utf-8") as f:
        text = f.read()
    pattern = re.compile(r"(<!-- RESUME:START -->).*?(<!-- RESUME:END -->)", re.S)
    if not pattern.search(text):
        raise SystemExit("README is missing the RESUME markers")
    body = badge(url, "RESUME", DOC_PATH, "1f2328")
    text = pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(2)}", text)
    with open(README, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    profile = load_profile()
    term = profile["terminal"]

    # cards that moved into the terminal animation
    for old in glob.glob(os.path.join(ASSETS, "*", "*.svg")):
        if os.path.basename(old) != "footer.svg":
            os.remove(old)

    for theme in kit.THEMES:
        write(theme, "footer.svg", kit.footer(theme, term["user"], term["host"]))

    resume = fetch_resume_url(profile["portfolio"])
    if resume:
        update_resume_badge(resume)
        print("Resume badge ->", resume)
    else:
        print("Resume fetch failed; keeping the current badge")


if __name__ == "__main__":
    main()
