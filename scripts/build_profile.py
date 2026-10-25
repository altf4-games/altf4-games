"""
Builds the footer card the profile README shows:

  assets/{dark,light}/footer.svg

Everything else (neofetch, Doom, wins, work, merged PRs) is the terminal
animation made by scripts/build_terminal_anim.py.

Output is deterministic, so the workflow only commits when something changed.
"""

import glob
import os

import svg_kit as kit
from profile_data import ROOT, load_profile

ASSETS = os.path.join(ROOT, "assets")


def write(theme, name, svg):
    os.makedirs(os.path.join(ASSETS, theme), exist_ok=True)
    with open(os.path.join(ASSETS, theme, name), "w", encoding="utf-8") as f:
        f.write(svg + "\n")


def main():
    term = load_profile()["terminal"]

    # cards that moved into the terminal animation
    for old in glob.glob(os.path.join(ASSETS, "*", "*.svg")):
        if os.path.basename(old) != "footer.svg":
            os.remove(old)

    for theme in kit.THEMES:
        write(theme, "footer.svg", kit.footer(theme, term["user"], term["host"]))
    print("Built footer")


if __name__ == "__main__":
    main()
