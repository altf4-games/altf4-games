"""
Shared SVG building blocks for the profile README: GitHub-matching dark /
light palettes and the individual cards (terminal, section headers, PR rows,
experience, research, wins, footer). Every function returns an SVG string for one theme.

Monospace layout maths assume ~0.6em per character, which holds for the
JetBrains Mono / Fira Code / DejaVu Sans Mono fallback chain below.
"""

import html

W = 900
FONT = "'JetBrains Mono','Fira Code',Consolas,'DejaVu Sans Mono',monospace"

THEMES = {
    "dark": {
        "bg": "#0d1117", "chrome": "#161b22", "stroke": "#30363d",
        "text": "#e6edf3", "muted": "#8b949e", "faint": "#484f58",
        "blue": "#38bdf8", "red": "#ff7b72", "gold": "#e3b341",
        "green": "#7ee787", "purple": "#a371f7", "chip": "#21262d",
        "blocks": ["#30363d", "#ff7b72", "#7ee787", "#e3b341",
                   "#38bdf8", "#a371f7", "#56d4dd", "#c9d1d9"],
    },
    "light": {
        "bg": "#ffffff", "chrome": "#f6f8fa", "stroke": "#d0d7de",
        "text": "#1f2328", "muted": "#59636e", "faint": "#afb8c1",
        "blue": "#0969da", "red": "#cf222e", "gold": "#9a6700",
        "green": "#1a7f37", "purple": "#8250df", "chip": "#eff2f5",
        "blocks": ["#afb8c1", "#cf222e", "#1a7f37", "#9a6700",
                   "#0969da", "#8250df", "#1b7c83", "#59636e"],
    },
}

def esc(s):
    return html.escape(str(s), quote=True)


def chars(s, size):
    """Approximate rendered width of monospace text."""
    return len(s) * size * 0.6


def clip(s, n):
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def short_num(n):
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def svg_open(w, h, extra_style=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}"><style>text{{font-family:{FONT};white-space:pre}}'
            f'{extra_style}</style>')


def fade_in(begin, dur=0.3):
    return (f'<animate attributeName="opacity" from="0" to="1" begin="{begin:.2f}s" '
            f'dur="{dur}s" fill="freeze"/>')


# ---------------------------------------------------------------------------
# Terminal (neofetch) card
# ---------------------------------------------------------------------------

def wrap(text, width):
    """Greedy word wrap to lines of at most `width` characters."""
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    return lines + ([cur] if cur else [])


def terminal(theme, user, host, rows, art_rows, command="neofetch"):
    """art_rows: [[(char, '#rrggbb'), ...], ...] — the colored ASCII logo."""
    t = THEMES[theme]
    prompt = f"{user}@{host}"
    art_w = 360
    cols = max((len(r) for r in art_rows), default=1)
    art_fs = art_w / (cols * 0.6)
    art_lh = art_fs * 1.12
    art_top = 88
    art_bottom = art_top + len(art_rows) * art_lh
    h = int(art_bottom + 64)

    p = [svg_open(W, h, "@keyframes blink{50%{opacity:0}}.cur{animation:blink 1s step-end infinite}")]
    p.append(f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="12" fill="{t["bg"]}" stroke="{t["stroke"]}"/>')
    p.append(f'<path d="M1 12a11 11 0 0 1 11-11h{W - 24}a11 11 0 0 1 11 11v22H1z" fill="{t["chrome"]}"/>')
    for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        p.append(f'<circle cx="{22 + i * 20}" cy="18" r="6" fill="{c}"/>')
    p.append(f'<text x="{W / 2}" y="23" fill="{t["muted"]}" text-anchor="middle" font-size="13">{esc(prompt)}: ~</text>')

    def prompt_tspans():
        return (f'<tspan fill="{t["green"]}">{esc(prompt)}</tspan><tspan fill="{t["text"]}">:</tspan>'
                f'<tspan fill="{t["blue"]}">~</tspan><tspan fill="{t["text"]}">$ </tspan>')

    # typed command
    typed = "".join(
        f'<tspan fill="transparent">{esc(ch)}<set attributeName="fill" to="{t["text"]}" '
        f'begin="{0.4 + i * 0.07:.2f}s" fill="freeze"/></tspan>'
        for i, ch in enumerate(command))
    p.append(f'<text x="24" y="62" font-size="15">{prompt_tspans()}{typed}</text>')
    start = 0.6 + len(command) * 0.07

    # ASCII logo, revealed top to bottom like a slow terminal
    for i, row in enumerate(art_rows):
        groups, j = [], 0
        while j < len(row):
            k = j
            while k < len(row) and row[k][1] == row[j][1]:
                k += 1
            groups.append((row[j][1], "".join(ch for ch, _ in row[j:k])))
            j = k
        spans = "".join(f'<tspan fill="{c}">{esc(txt)}</tspan>' for c, txt in groups)
        y = art_top + i * art_lh + art_fs
        p.append(f'<text x="28" y="{y:.1f}" font-size="{art_fs:.2f}" opacity="0">{spans}'
                 f'{fade_in(start + i * 0.025, 0.15)}</text>')
    logo_end = start + len(art_rows) * 0.025

    # info column, vertically centred on the logo
    rx_ = 412
    block_h = 40 + len(rows) * 25 + 24
    y0 = art_top + max(0, (art_bottom - art_top - block_h) / 2) + 14
    p.append(f'<text x="{rx_}" y="{y0:.0f}" font-size="16" font-weight="bold" fill="{t["gold"]}" opacity="0">'
             f'{esc(prompt)}{fade_in(start)}</text>')
    p.append(f'<rect x="{rx_}" y="{y0 + 12:.0f}" width="{chars(prompt, 16):.0f}" height="1.5" fill="{t["faint"]}" opacity="0">'
             f'{fade_in(start)}</rect>')
    y = y0 + 42
    for i, (label, value) in enumerate(rows):
        p.append(f'<text x="{rx_}" y="{y:.0f}" font-size="14.5" opacity="0">'
                 f'<tspan fill="{t["blue"]}" font-weight="bold">{esc(label)}</tspan>'
                 f'<tspan fill="{t["text"]}">: {esc(value)}</tspan>{fade_in(start + 0.2 + i * 0.12)}</text>')
        y += 25
    rows_end = max(start + 0.2 + len(rows) * 0.12, logo_end)
    for i, c in enumerate(t["blocks"]):
        p.append(f'<rect x="{rx_ + i * 32}" y="{y - 4:.0f}" width="28" height="14" rx="2" fill="{c}" opacity="0">'
                 f'{fade_in(rows_end + i * 0.05)}</rect>')

    p.append(f'<text x="24" y="{h - 22}" font-size="15" opacity="0">{prompt_tspans()}{fade_in(rows_end + 0.4)}</text>')
    cx = 24 + chars(prompt + ":~$ ", 15)
    p.append(f'<g opacity="0">{fade_in(rows_end + 0.4, 0.01)}'
             f'<rect class="cur" x="{cx:.0f}" y="{h - 36}" width="9" height="18" fill="{t["blue"]}"/></g>')
    p.append("</svg>")
    return "\n".join(p)


# ---------------------------------------------------------------------------
# Section header:  01  NOW PLAYING ───────────────── ~/now-playing
# ---------------------------------------------------------------------------

def section(theme, num, title, path, accent):
    t = THEMES[theme]
    h = 76
    c = t[accent]
    title_x = 24 + chars(num, 40) + 18
    title_end = title_x + chars(title.upper(), 15) * 1.25
    path_x = W - 24 - chars(path, 13)
    return "\n".join([
        svg_open(W, h),
        f'<text x="24" y="54" font-size="40" fill="{t["text"]}">{esc(num)}</text>',
        f'<text x="{title_x:.0f}" y="50" font-size="15" letter-spacing="3.5" fill="{c}">{esc(title.upper())}</text>',
        f'<rect x="{title_end + 14:.0f}" y="45" width="{path_x - title_end - 28:.0f}" height="1.5" fill="{t["faint"]}"/>',
        f'<text x="{path_x:.0f}" y="50" font-size="13" fill="{t["muted"]}">{esc(path)}</text>',
        "</svg>",
    ])


# ---------------------------------------------------------------------------
# One merged-PR card (each is its own image so it can be its own link)
# ---------------------------------------------------------------------------

MERGE_ICON = ("M5 3.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0zm0 2.122a2.25 2.25 0 1 0-1.5 0v.878"
              "A2.25 2.25 0 0 0 5.75 8.5h1.5v2.128a2.251 2.251 0 1 0 1.5 0V8.5h1.5a2.25 2.25 0 0 0 "
              "2.25-2.25v-.878a2.25 2.25 0 1 0-1.5 0v.878a.75.75 0 0 1-.75.75h-4.5A.75.75 0 0 1 5 6.25"
              "v-.878zm3.75 7.378a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0zm3-8.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5z")


def pr_card(theme, pr, merged_label):
    t = THEMES[theme]
    h = 78
    owner, _, name = pr["repo"].partition("/")
    stars = f"★ {short_num(pr['stars'])}"
    chip_w = chars(stars, 12) + 18
    num = f"#{pr['number']}"
    repo_x = 64
    num_x = repo_x + chars(pr["repo"], 15) + 10
    return "\n".join([
        svg_open(W, h),
        f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 9}" rx="10" fill="{t["bg"]}" stroke="{t["stroke"]}"/>',
        f'<circle cx="34" cy="35" r="16" fill="{t["purple"]}" fill-opacity="0.15"/>',
        f'<path d="{MERGE_ICON}" fill="{t["purple"]}" transform="translate(24 25) scale(1.25)"/>',
        f'<text x="{repo_x}" y="30" font-size="15"><tspan fill="{t["muted"]}">{esc(owner)}/</tspan>'
        f'<tspan fill="{t["text"]}" font-weight="bold">{esc(name)}</tspan></text>',
        f'<text x="{num_x:.0f}" y="30" font-size="14" fill="{t["purple"]}">{esc(num)}</text>',
        f'<text x="{repo_x}" y="53" font-size="13" fill="{t["muted"]}">{esc(clip(pr["title"], 70))}</text>',
        f'<rect x="{W - 20 - chip_w:.0f}" y="15" width="{chip_w:.0f}" height="22" rx="11" fill="{t["chip"]}"/>',
        f'<text x="{W - 20 - chip_w / 2:.0f}" y="30" font-size="12" fill="{t["gold"]}" text-anchor="middle">{esc(stars)}</text>',
        f'<text x="{W - 20}" y="54" font-size="12" fill="{t["muted"]}" text-anchor="end">merged {esc(merged_label)}</text>',
        "</svg>",
    ])


# ---------------------------------------------------------------------------
# Experience timeline
# ---------------------------------------------------------------------------

def experience(theme, items):
    t = THEMES[theme]
    row_h = 84
    h = 16 + len(items) * row_h
    p = [svg_open(W, h)]
    p.append(f'<rect x="31" y="22" width="2" height="{h - 50}" fill="{t["stroke"]}"/>')
    for i, e in enumerate(items):
        y = 12 + i * row_h
        colour = t["blue"] if i == 0 else t["faint"]
        p.append(f'<circle cx="32" cy="{y + 14}" r="7" fill="{t["bg"]}" stroke="{colour}" stroke-width="3"/>')
        p.append(f'<text x="58" y="{y + 19}" font-size="16"><tspan fill="{t["text"]}" font-weight="bold">'
                 f'{esc(e["role"])}</tspan><tspan fill="{t["muted"]}"> @ </tspan>'
                 f'<tspan fill="{t["blue"]}">{esc(e["org"])}</tspan></text>')
        p.append(f'<text x="{W - 20}" y="{y + 19}" font-size="12" fill="{t["muted"]}" text-anchor="end">{esc(e["when"])}</text>')
        p.append(f'<text x="58" y="{y + 44}" font-size="13" fill="{t["muted"]}">{esc(clip(e["what"], 95))}</text>')
    p.append("</svg>")
    return "\n".join(p)


# ---------------------------------------------------------------------------
# Research / IP item (its own image so a paper can link to its DOI)
# ---------------------------------------------------------------------------

def research_card(theme, item):
    t = THEMES[theme]
    lines = wrap(item["title"], 80)[:2]
    h = 58 + len(lines) * 21
    kind = item["kind"].upper()
    colour = {"PAPER": t["green"], "MANUSCRIPT": t["blue"]}.get(kind, t["gold"])
    p = [svg_open(W, h)]
    p.append(f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 9}" rx="10" fill="{t["bg"]}" stroke="{t["stroke"]}"/>')
    bw = chars(kind, 11) * 1.15 + 20
    p.append(f'<rect x="20" y="16" width="{bw:.0f}" height="22" rx="11" fill="{colour}" fill-opacity="0.15"/>')
    p.append(f'<text x="{20 + bw / 2:.0f}" y="31" font-size="11" letter-spacing="1.2" font-weight="bold" '
             f'fill="{colour}" text-anchor="middle">{esc(kind)}</text>')
    p.append(f'<text x="{32 + bw:.0f}" y="31" font-size="12" fill="{t["muted"]}">{esc(item["venue"])}</text>')
    if item.get("url"):
        p.append(f'<text x="{W - 20}" y="31" font-size="12" fill="{t["blue"]}" text-anchor="end">read ↗</text>')
    for i, line in enumerate(lines):
        p.append(f'<text x="20" y="{62 + i * 21}" font-size="15" font-weight="bold" fill="{t["text"]}">{esc(line)}</text>')
    p.append("</svg>")
    return "\n".join(p)


# ---------------------------------------------------------------------------
# Wins card
# ---------------------------------------------------------------------------

TROPHY = ("M7 2h10v2h3v3a4 4 0 0 1-4 4h-.3A5 5 0 0 1 13 13.9V17h3v3H8v-3h3v-3.1A5 5 0 0 1 8.3 11H8"
          "a4 4 0 0 1-4-4V4h3V2zm-1 4v1a2 2 0 0 0 1.2 1.8A5 5 0 0 1 7 8V6H6zm11 0v2c0 .3 0 .6-.1.8"
          "A2 2 0 0 0 18 7V6h-1z")


def wins(theme, items):
    t = THEMES[theme]
    row_h = 74
    h = 20 + len(items) * row_h
    p = [svg_open(W, h)]
    for i, w in enumerate(items):
        y = 10 + i * row_h
        badge = w["badge"].upper()
        colour = t["gold"] if badge.startswith("WIN") else t["blue"]
        p.append(f'<rect x=".5" y="{y + .5}" width="{W - 1}" height="{row_h - 10}" rx="10" fill="{t["bg"]}" stroke="{t["stroke"]}"/>')
        p.append(f'<rect x=".5" y="{y + .5}" width="4" height="{row_h - 10}" rx="2" fill="{colour}"/>')
        p.append(f'<circle cx="40" cy="{y + 32}" r="18" fill="{colour}" fill-opacity="0.15"/>')
        p.append(f'<path d="{TROPHY}" fill="{colour}" transform="translate(28 {y + 20})"/>')
        p.append(f'<text x="74" y="{y + 28}" font-size="16" font-weight="bold" fill="{t["text"]}">{esc(w["title"])}</text>')
        p.append(f'<text x="74" y="{y + 50}" font-size="13" fill="{t["muted"]}">{esc(w["event"])}</text>')
        bw = chars(badge, 11) * 1.15 + 20
        p.append(f'<rect x="{W - 20 - bw:.0f}" y="{y + 20}" width="{bw:.0f}" height="24" rx="12" '
                 f'fill="{colour}" fill-opacity="0.15"/>')
        p.append(f'<text x="{W - 20 - bw / 2:.0f}" y="{y + 36}" font-size="11" letter-spacing="1.2" '
                 f'font-weight="bold" fill="{colour}" text-anchor="middle">{esc(badge)}</text>')
    p.append("</svg>")
    return "\n".join(p)


# ---------------------------------------------------------------------------
# Footer:  user@host:~$ exit   # or just press Alt+F4
# ---------------------------------------------------------------------------

def footer(theme, user, host):
    t = THEMES[theme]
    h = 56
    prompt = f"{user}@{host}"
    return "\n".join([
        svg_open(W, h, "@keyframes blink{50%{opacity:0}}.cur{animation:blink 1s step-end infinite}"),
        f'<rect x="0" y="8" width="{W}" height="1.5" fill="{t["faint"]}"/>',
        f'<text x="{W / 2}" y="40" font-size="14" text-anchor="middle">'
        f'<tspan fill="{t["green"]}">{esc(prompt)}</tspan><tspan fill="{t["text"]}">:~$ exit </tspan>'
        f'<tspan fill="{t["muted"]}"># or just press </tspan><tspan fill="{t["red"]}" font-weight="bold">Alt+F4</tspan></text>',
        "</svg>",
    ])
