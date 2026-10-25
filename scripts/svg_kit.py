"""
SVG building blocks for the profile README: GitHub-matching dark / light
palettes and the footer card. Everything else (neofetch, Doom, wins, work,
PRs) lives in the terminal animation, scripts/build_terminal_anim.py.
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


def svg_open(w, h, extra_style=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}"><style>text{{font-family:{FONT};white-space:pre}}'
            f'{extra_style}</style>')


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
