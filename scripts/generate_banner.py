"""
Generates the neofetch-style intro banner (assets/dark_mode.svg and
assets/light_mode.svg) for the GitHub profile README: colored ASCII art on
the left, ". label: ......... value" rows on the right.

The rows come from profile.yml, so editing the intro never needs a code
change. Live data (PRs, stats) lives in the README blocks and the Doom GIF,
which keeps this banner static and stops it producing a commit every run.
"""

import os
import html
from html.parser import HTMLParser as _HTMLParser

from profile_data import USERNAME, ROOT, load_profile

FONT_FAMILY = "'Cascadia Code','Fira Code',Consolas,'DejaVu Sans Mono',monospace"


# ---------------------------------------------------------------------------
# Colored ASCII-art loader  (parses ascii-art.html if present in repo root)
# ---------------------------------------------------------------------------

class _AsciiParser(_HTMLParser):
    """Minimal SAX-style parser: collects (char, color) pairs row-by-row."""
    def __init__(self):
        super().__init__()
        self.rows = [[]]
        self._color = "#888888"
        self._in_body = False   # only collect data inside <body>

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self._in_body = True
            return
        if tag == "br":
            if self._in_body:
                self.rows.append([])
            return
        if tag == "span":
            style = dict(attrs).get("style", "")
            if "color:" in style:
                self._color = style.split("color:")[1].split(";")[0].strip()

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and self._in_body:
            self.rows.append([])

    def handle_data(self, data):
        if not self._in_body:
            return
        for ch in data:
            if ch == "\n":
                continue
            self.rows[-1].append((ch, self._color))



def load_ascii_art(path="ascii-art.html"):
    path = os.path.join(ROOT, path)
    """Returns list-of-rows, each row = [(char, '#rrggbb'), ...], or None."""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        parser = _AsciiParser()
        parser.feed(content)
        rows = [r for r in parser.rows if r]   # drop empty rows
        return rows or None
    except Exception:
        return None


def ascii_art_svg(art_rows, x, start_y, col_width, esc_fn):
    """Render colored ASCII art rows as SVG text elements.
    Scales font-size to fit col_width. Returns (elements, font_size, line_h)."""
    if not art_rows:
        return [], 8, 9
    max_cols = max(len(r) for r in art_rows)
    # char_width ≈ 0.60 × font-size for monospace
    font_size = max(5, min(10, int(col_width / (max_cols * 0.60))))
    line_h = font_size * 1.15
    elements = []
    for row_idx, row in enumerate(art_rows):
        y = start_y + row_idx * line_h
        # group consecutive same-color chars → smaller SVG output
        groups = []
        i = 0
        while i < len(row):
            ch, color = row[i]
            j = i + 1
            while j < len(row) and row[j][1] == color:
                j += 1
            groups.append((color, "".join(c for c, _ in row[i:j])))
            i = j
        tspans = "".join(
            f'<tspan fill="{color}">{esc_fn(chars)}</tspan>'
            for color, chars in groups
        )
        elements.append(
            f'<text x="{x}" y="{y:.1f}" font-size="{font_size}" '
            f'font-family="monospace" xml:space="preserve">{tspans}</text>'
        )
    return elements, font_size, line_h


# ---------------------------------------------------------------------------
# Layout helpers (character-count based -- safe because the font is monospace)
# ---------------------------------------------------------------------------

def dotted(label, value, width=62):
    prefix = f". {label}: "
    dots_needed = max(3, width - len(prefix) - len(value))
    return prefix, "." * dots_needed, " " + value


ASCII_LOGO = [
    r"  ___   _    ___________ ___ ",
    r" / _ \ | |  |_   _|  ___/   |",
    r"/ /_\ \| |    | | | |_ / /| |",
    r"|  _  || |    | | |  _/ /_| |",
    r"| | | || |____| | | | \___  |",
    r"\_| |_/\_____/\_/ \_|     |_/",
    r"",
    r"",
    r" _____   ___  ___  ___ _____ _____ ",
    r"|  __ \ / _ \ |  \/  ||  ___/  ___|",
    r"| |  \// /_\ \| .  . || |__ \ `--. ",
    "| | __ |  _  || |\\/| ||  __| `--. \\",
    r"| |_\ \| | | || |  | || |___/\__/ /",
    r" \____/\_| |_/\_|  |_/\____/\____/ ",
]


def build_lines(profile):
    """Returns a list of 'rows'. Each row is either:
      ('header', text)          -- top username line
      ('kv', label, value)      -- dot-leader line
      ('colors',)               -- neofetch colour-block strip
      ('blank',)                -- spacer
    """
    rows = [("header", f"{USERNAME}@github")]
    for label, value in profile.get("neofetch", []):
        rows.append(("kv", str(label), str(value)))
    rows.append(("blank",))
    rows.append(("colors",))
    return rows


# ---------------------------------------------------------------------------
# SVG rendering
# ---------------------------------------------------------------------------

THEMES = {
    "dark": {
        "bg": "#0b0e14",
        "chrome": "#171a21",
        "title_gray": "#8b909c",
        "header_green": "#5fd75f",
        "dash": "#4b5262",
        "label": "#d7dae0",
        "dots": "#4b5262",
        "value": "#9ca3af",       # Grayish shade for RHS values
        "logo": "#8fb8d9",
        "add": "#4fd671",
        "del": "#e5677a",
        "accent_sys": "#56d4dd",       # Cyan/Teal for system hardware & shell
        "accent_lang": "#c678dd",      # Purple/Magenta for languages
        "accent_fw": "#e5c07b",        # Gold/Amber for frameworks & devops
        "accent_oss": "#61afef",       # Bright Azure Blue for OSS & achievements
        "accent_contact": "#e06c75",   # Coral/Rose for contact links
        "accent_stats": "#98c379",     # Vibrant Green for live GitHub stats
    },
    "light": {
        "bg": "#f7f7f8",
        "chrome": "#e8e8ea",
        "title_gray": "#5b5f66",
        "header_green": "#1f9c3f",
        "dash": "#a7abb3",
        "label": "#24262b",
        "dots": "#a7abb3",
        "value": "#4b5563",       # Grayish shade for RHS values
        "logo": "#2f6690",
        "add": "#1f9c3f",
        "del": "#c23b4d",
        "accent_sys": "#0969da",       # Deep Royal Blue for system
        "accent_lang": "#8250df",      # Deep Violet for languages
        "accent_fw": "#9a6700",        # Warm Gold/Bronze for frameworks
        "accent_oss": "#0550ae",       # Deep Azure for OSS & achievements
        "accent_contact": "#cf222e",   # Crimson Rose for contact links
        "accent_stats": "#1a7f37",     # Forest Green for live GitHub stats
    },
}


def esc(s):
    return html.escape(s, quote=True)


def get_label_color(label, t):
    return t.get("accent_sys", t["label"])


NEOFETCH_BLOCKS = ["#282c34", "#e06c75", "#98c379", "#e5c07b",
                   "#61afef", "#c678dd", "#56b6c2", "#dcdfe4"]


def render_svg(profile, theme_name):
    t = THEMES[theme_name]
    rows = build_lines(profile)

    pad_x = 36
    bar_h = 42
    pad_top = bar_h + 30
    line_h = 22
    logo_line_h = 19
    right_x = pad_x + 470
    right_width_chars = 62
    width = 1100

    art_col_width = right_x - pad_x - 10   # ~460 px available
    art_file = "ascii-art_light.html" if theme_name == "light" else "ascii-art.html"
    art_rows = load_ascii_art(art_file)
    if not art_rows and theme_name == "light":
        art_rows = load_ascii_art("ascii-art.html")
    if art_rows:
        svg_els, _fs, _lh = ascii_art_svg(art_rows, pad_x, pad_top, art_col_width, esc)
        art_h = len(art_rows) * _lh
        left_h = pad_top + art_h + 40
    else:
        art_h = len(ASCII_LOGO) * logo_line_h
        left_h = pad_top + art_h + 40

    # vertically centre the info block against the art
    right_block_h = len(rows) * line_h
    height = int(max(pad_top + right_block_h + 30, left_h))
    iy = pad_top + max(0, (art_h - right_block_h) / 2) + 10

    p = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="{FONT_FAMILY}">'
    )
    p.append(f'<rect x="0" y="0" width="{width}" height="{height}" rx="16" fill="{t["bg"]}"/>')
    p.append(f'<rect x="0" y="0" width="{width}" height="{bar_h}" rx="16" fill="{t["chrome"]}"/>')
    p.append(f'<rect x="0" y="{bar_h // 2}" width="{width}" height="{bar_h // 2}" fill="{t["chrome"]}"/>')
    cy = bar_h // 2
    for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        p.append(f'<circle cx="{22 + i * 22}" cy="{cy}" r="6" fill="{c}"/>')
    title = f"{USERNAME}@github: ~ $ neofetch"
    p.append(
        f'<text x="{width / 2}" y="{cy + 5}" text-anchor="middle" font-size="13" '
        f'fill="{t["title_gray"]}">{esc(title)}</text>'
    )

    # left column: colored ASCII art (falls back to text logo if file missing)
    y = pad_top
    if art_rows:
        p.extend(svg_els)
    else:
        p.append(f'<text x="{pad_x}" y="{y}" font-size="12" font-weight="bold" fill="{t["logo"]}" xml:space="preserve">')
        for i, line in enumerate(ASCII_LOGO):
            dy = 0 if i == 0 else logo_line_h
            p.append(f'<tspan x="{pad_x}" dy="{dy}">{esc(line) if line else " "}</tspan>')
        p.append("</text>")

    # right column: info block
    for row in rows:
        kind = row[0]
        if kind == "blank":
            iy += line_h
            continue
        if kind == "header":
            text = row[1]
            p.append(
                f'<text x="{right_x}" y="{iy:.0f}" font-size="15" font-weight="bold" '
                f'fill="{t["header_green"]}">{esc(text)}</text>'
            )
            iy += 8
            p.append(f'<text x="{right_x}" y="{iy + 6:.0f}" font-size="13" fill="{t["dash"]}">'
                     f'{esc("-" * len(text))}</text>')
            iy += line_h
            continue
        if kind == "kv":
            label, value = row[1], row[2]
            prefix, dots, val = dotted(label, value, width=right_width_chars)
            p.append(
                f'<text x="{right_x}" y="{iy:.0f}" font-size="13" xml:space="preserve">'
                f'<tspan fill="{get_label_color(label, t)}">{esc(prefix)}</tspan>'
                f'<tspan fill="{t["dots"]}">{esc(dots)}</tspan>'
                f'<tspan fill="{t["value"]}">{esc(val)}</tspan>'
                f"</text>"
            )
            iy += line_h
            continue
        if kind == "colors":
            for i, c in enumerate(NEOFETCH_BLOCKS):
                p.append(f'<rect x="{right_x + i * 30}" y="{iy - 14:.0f}" width="28" height="18" fill="{c}"/>')
            iy += line_h
            continue

    p.append(f'<text x="{width - pad_x}" y="{height - 16}" text-anchor="end" font-size="12" '
             f'fill="{t["title_gray"]}">github.com/{esc(USERNAME)}</text>')
    p.append("</svg>")
    return "\n".join(p)


def main():
    profile = load_profile()
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    for theme_name in ("dark", "light"):
        path = os.path.join(ROOT, "assets", f"{theme_name}_mode.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_svg(profile, theme_name))
        print("Saved", path)


if __name__ == "__main__":
    main()
