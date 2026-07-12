"""
Generates a neofetch-style SVG banner (dark_mode.svg / light_mode.svg) for the
GitHub profile README, in the ". label: ......... value" dot-leader layout
with dashed section headers, plus live GitHub stats (repos, stars, followers,
total commits, contributed-to repos, total lines of code added/removed, PRs,
and profile views — all rendered inside the SVG itself).

Auth: uses the GITHUB_TOKEN Actions injects automatically into every
workflow run. No personal access token needs to be created or stored.
"""

import os
import time
import html
import datetime
import requests
from html.parser import HTMLParser as _HTMLParser

USERNAME = os.environ.get("GH_USERNAME", "altf4-games")
TOKEN = os.environ.get("GITHUB_TOKEN")

HEADERS = {"User-Agent": f"{USERNAME}-readme-banner"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

FONT_FAMILY = "'Cascadia Code','Fira Code',Consolas,'DejaVu Sans Mono',monospace"
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


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
# GitHub data fetching
# ---------------------------------------------------------------------------

def get_user():
    r = SESSION.get(f"https://api.github.com/users/{USERNAME}", timeout=15)
    r.raise_for_status()
    return r.json()


def get_owned_repos():
    repos, page = [], 1
    while True:
        r = SESSION.get(
            f"https://api.github.com/users/{USERNAME}/repos",
            params={"per_page": 100, "page": page, "type": "owner"},
            timeout=15,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def graphql(query, variables):
    if not TOKEN:
        return None
    r = SESSION.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        timeout=20,
    )
    if r.status_code != 200:
        return None
    data = r.json()
    if "errors" in data:
        return None
    return data.get("data")


def total_commits_all_time(created_at):
    """GitHub's contributionsCollection only covers one year per call, so we
    loop from account creation to today and sum each year, same approach
    used by most 'lifetime commit count' README generators."""
    if not TOKEN:
        return 0
    start_year = int(created_at[:4])
    this_year = datetime.datetime.utcnow().year
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          restrictedContributionsCount
        }
      }
    }
    """
    total = 0
    for year in range(start_year, this_year + 1):
        frm = f"{year}-01-01T00:00:00Z"
        to = f"{year}-12-31T23:59:59Z"
        data = graphql(query, {"login": USERNAME, "from": frm, "to": to})
        if not data:
            continue
        coll = data["user"]["contributionsCollection"]
        total += coll["totalCommitContributions"] + coll["restrictedContributionsCount"]
    return total


def contributed_repo_count():
    query = """
    query($login: String!) {
      user(login: $login) {
        repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) {
          totalCount
        }
      }
    }
    """
    data = graphql(query, {"login": USERNAME})
    if not data:
        return 0
    return data["user"]["repositoriesContributedTo"]["totalCount"]


def total_prs_merged():
    """Count total merged pull requests authored by the user."""
    query = """
    query($login: String!) {
      user(login: $login) {
        pullRequests(states: MERGED) {
          totalCount
        }
      }
    }
    """
    data = graphql(query, {"login": USERNAME})
    if not data:
        return 0
    return data["user"]["pullRequests"]["totalCount"]



def lines_of_code(owned_repos):
    """Sums additions/deletions across owned, non-fork repos using the
    per-contributor stats endpoint. GitHub computes these lazily -- a fresh
    request can return 202 while it builds the cache, so we retry briefly
    and just skip a repo if it isn't ready in time."""
    additions = deletions = 0
    for repo in owned_repos:
        if repo.get("fork"):
            continue
        full_name = repo["full_name"]
        url = f"https://api.github.com/repos/{full_name}/stats/contributors"
        for attempt in range(3):
            r = SESSION.get(url, timeout=20)
            if r.status_code == 202:
                time.sleep(2)
                continue
            if r.status_code != 200:
                break
            for entry in r.json() or []:
                if entry.get("author", {}).get("login") == USERNAME:
                    for week in entry.get("weeks", []):
                        additions += week.get("a", 0)
                        deletions += week.get("d", 0)
            break
    return additions, deletions


def collect_stats():
    user = get_user()
    owned_repos = get_owned_repos()
    stars = sum(r.get("stargazers_count", 0) for r in owned_repos)
    additions, deletions = lines_of_code(owned_repos)

    return {
        "repos": user.get("public_repos", len(owned_repos)),
        "contributed": contributed_repo_count(),
        "stars": stars,
        "followers": user.get("followers", 0),
        "commits": total_commits_all_time(user.get("created_at", "2020-01-01T00:00:00Z")),
        "prs": total_prs_merged(),
        "loc_additions": additions,
        "loc_deletions": deletions,
    }


# ---------------------------------------------------------------------------
# Layout helpers (character-count based -- safe because the font is monospace)
# ---------------------------------------------------------------------------

def dotted(label, value, width=70):
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


def build_lines(stats):
    """Returns a list of 'rows'. Each row is either:
      ('header', text)                          -- top username line
      ('section', text)                         -- dashed section divider
      ('kv', label, value)                      -- dot-leader line
      ('raw_stats1/2', ...)                     -- compact multi-value stats line
      ('raw_loc', ...)                          -- lines-of-code line
      ('blank',)                                -- spacer
    """
    rows = [("header", f"{USERNAME}@github")]

    # ── neofetch-style system block ───────────────────────────────────────────
    rows.append(("kv", "OS",       "Arch (btw) / Linux / Windows 11"))
    rows.append(("kv", "Host",     "KJSCE, Mumbai (local) | Barclays (remote)"))
    rows.append(("kv", "Kernel",   "B.Tech Computer Engineering — CGPA 9.63/10"))
    rows.append(("kv", "Uptime",   "22 yrs, 10 yrs of coding"))
    rows.append(("kv", "Packages", "npm · pip · pub · gradle"))
    rows.append(("kv", "Shell",    "zsh / bash / powershell"))
    rows.append(("kv", "DE",       "VS Code (Dark+)"))
    rows.append(("kv", "Terminal", "Alacritty / Windows Terminal"))
    rows.append(("kv", "CPU",      "Brain @ overclocked, severely sleep-deprived"))
    rows.append(("kv", "GPU",      "Imagination Engine (unlimited VRAM)"))
    rows.append(("kv", "Memory",   "16GB RAM, mostly filled with LeetCode"))
    rows.append(("blank",))

    # ── Languages ─────────────────────────────────────────────────────────────
    rows.append(("section", "Languages"))
    rows.append(("kv", "Languages.Programming", "C, C++, C#, Java, Python, Dart, SQL"))
    rows.append(("kv", "Languages.Web",         "JavaScript, TypeScript, HTML, CSS"))
    rows.append(("blank",))

    # ── Frameworks & Tools ────────────────────────────────────────────────────
    rows.append(("section", "Frameworks & Tools"))
    rows.append(("kv", "Frameworks.Web",    "React, Next.js, Three.js, Express, FastAPI"))
    rows.append(("kv", "Frameworks.App",      "Flutter, React Native, Unity, Unreal Engine 5"))
    rows.append(("kv", "Frameworks.AI",       "TensorFlow, TFLite, Scikit-learn, MediaPipe"))
    rows.append(("kv", "Databases",           "MongoDB, PostgreSQL, Redis, Firebase"))
    rows.append(("kv", "DevOps",              "Git, Docker, AWS, Socket.io, Judge0"))
    rows.append(("blank",))

    # ── Open Source ───────────────────────────────────────────────────────────
    rows.append(("section", "Open Source & Research"))
    rows.append(("kv", "Hobbies.OSS",      "microsoft/data-formulator #351, microsoft/apm #1367"))
    rows.append(("kv", "Hobbies.Research", "CVR'26 Springer — Gesture-Based Assistive Tool"))
    rows.append(("kv", "Hobbies.IP",       "Sanketika ISL Dataset"))
    rows.append(("blank",))

    # ── Achievements ──────────────────────────────────────────────────────────
    rows.append(("section", "Achievements"))
    rows.append(("kv", "Hobbies.CP",        "CodeChef 4-Star | 500+ LC"))
    rows.append(("kv", "Hobbies.Hackathon", "Winner — Most Addictive Game (8th Wall Jam)"))
    rows.append(("kv", "Hobbies.Hackathon", "1st Runner-Up ISTE Pixel Wars | 5x Finalist"))
    rows.append(("kv", "Hobbies.Software",  "Featured by Markiplier & Jacksepticeye (30M+)"))
    rows.append(("blank",))

    # ── Contact ───────────────────────────────────────────────────────────────
    rows.append(("section", "Contact"))
    rows.append(("kv", "Contact.LinkedIn", "pradyum-mistry"))
    rows.append(("kv", "Contact.Itch.io",  "altf4-games"))
    rows.append(("kv", "Contact.LeetCode", "pradyum_mistry"))
    rows.append(("kv", "Contact.CodeChef", "pradyum_m"))
    rows.append(("blank",))

    # ── GitHub Stats ──────────────────────────────────────────────────────────
    rows.append(("section", "GitHub Stats"))
    repos_txt   = f"{stats['repos']}"
    contrib_txt = f"{{Contributed: {stats['contributed']}}}"
    stars_txt   = f"{stats['stars']:,}"
    commits_txt = f"{stats['commits']:,}"
    followers_txt = f"{stats['followers']:,}"
    prs_txt     = f"{stats['prs']:,}"
    loc_total   = stats["loc_additions"] + stats["loc_deletions"]

    rows.append(("raw_stats1", repos_txt, contrib_txt, stars_txt))
    rows.append(("raw_stats2", commits_txt, followers_txt, prs_txt))
    rows.append(("raw_loc", f"{loc_total:,}", f"{stats['loc_additions']:,}++", f"{stats['loc_deletions']:,}--"))

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
    if label.startswith("Languages"):
        return t.get("accent_lang", t["label"])
    if label.startswith("Frameworks") or label in ("Databases", "DevOps"):
        return t.get("accent_fw", t["label"])
    if label.startswith("Hobbies"):
        return t.get("accent_oss", t["label"])
    if label.startswith("Contact"):
        return t.get("accent_contact", t["label"])
    if label in ("OS", "Host", "Kernel", "Uptime", "Packages", "Shell", "DE", "Terminal", "CPU", "GPU", "Memory"):
        return t.get("accent_sys", t["label"])
    return t["label"]


def render_svg(stats, theme_name):
    t = THEMES[theme_name]
    rows = build_lines(stats)

    pad_x = 36
    bar_h = 42
    pad_top = bar_h + 30
    line_h = 21
    logo_line_h = 19
    right_x = pad_x + 470
    right_width_chars = 70   # wider — fits longer values without truncation
    width = 1280             # slightly wider canvas to accommodate extra chars

    art_col_width = right_x - pad_x - 10   # ~460 px available
    art_file = "ascii-art_light.html" if theme_name == "light" else "ascii-art.html"
    art_rows = load_ascii_art(art_file)
    if not art_rows and theme_name == "light":
        art_rows = load_ascii_art("ascii-art.html")
    if art_rows:
        svg_els, _fs, _lh = ascii_art_svg(art_rows, pad_x, pad_top, art_col_width, esc)
        art_h = len(art_rows) * _lh
        left_h = pad_top + art_h + 70
    else:
        left_h = pad_top + len(ASCII_LOGO) * logo_line_h + 70

    right_h = pad_top + len(rows) * line_h + 30
    height = int(max(right_h, left_h))

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
    title = f"{USERNAME}@github: ~"
    p.append(
        f'<text x="{width / 2}" y="{cy + 5}" text-anchor="middle" font-size="13" '
        f'fill="{t["title_gray"]}">{esc(title)}</text>'
    )

    # left column: colored ASCII art (falls back to text logo if file missing)
    y = pad_top
    if art_rows:
        svg_els, _fs, _lh = ascii_art_svg(art_rows, pad_x, y, art_col_width, esc)
        p.extend(svg_els)
        art_bottom = y + art_h
    else:
        p.append(f'<text x="{pad_x}" y="{y}" font-size="12" font-weight="bold" fill="{t["logo"]}" xml:space="preserve">')
        for i, line in enumerate(ASCII_LOGO):
            dy = 0 if i == 0 else logo_line_h
            p.append(f'<tspan x="{pad_x}" dy="{dy}">{esc(line) if line else " "}</tspan>')
        p.append("</text>")
        art_bottom = y + len(ASCII_LOGO) * logo_line_h
    footer_y = art_bottom + 26
    p.append(f'<text x="{pad_x}" y="{footer_y:.0f}" font-size="13" fill="{t["title_gray"]}">github.com/{esc(USERNAME)}</text>')

    # right column: info block
    iy = pad_top
    for row in rows:
        kind = row[0]
        if kind == "blank":
            iy += line_h
            continue
        if kind == "header":
            text = row[1]
            dash_len = max(3, right_width_chars - len(text) - 1)
            p.append(
                f'<text x="{right_x}" y="{iy}" font-size="14">'
                f'<tspan font-weight="bold" fill="{t["header_green"]}">{esc(text)}</tspan>'
                f'<tspan fill="{t["dash"]}"> {esc("-" * dash_len)}</tspan>'
                f"</text>"
            )
            iy += line_h
            continue
        if kind == "section":
            text = f"- {row[1]}"
            dash_len = max(3, right_width_chars - len(text) - 1)
            p.append(
                f'<text x="{right_x}" y="{iy}" font-size="13">'
                f'<tspan font-weight="bold" fill="{t["value"]}">{esc(text)}</tspan>'
                f'<tspan fill="{t["dash"]}"> {esc("-" * dash_len)}</tspan>'
                f"</text>"
            )
            iy += line_h
            continue
        if kind == "kv":
            label, value = row[1], row[2]
            prefix, dots, val = dotted(label, value, width=right_width_chars)
            lbl_color = get_label_color(label, t)
            p.append(
                f'<text x="{right_x}" y="{iy}" font-size="13">'
                f'<tspan fill="{lbl_color}">{esc(prefix)}</tspan>'
                f'<tspan fill="{t["dots"]}">{esc(dots)}</tspan>'
                f'<tspan fill="{t["value"]}">{esc(val)}</tspan>'
                f"</text>"
            )
            iy += line_h
            continue
        if kind == "raw_stats1":
            repos_txt, contrib_txt, stars_txt = row[1], row[2], row[3]
            sc = t.get("accent_stats", t["label"])
            p.append(
                f'<text x="{right_x}" y="{iy}" font-size="13">'
                f'<tspan fill="{sc}">. Repos: </tspan>'
                f'<tspan fill="{t["dots"]}">{esc("." * 4)}</tspan>'
                f'<tspan fill="{t["value"]}"> {esc(repos_txt)} {esc(contrib_txt)}</tspan>'
                f'<tspan fill="{t["dash"]}"> | </tspan>'
                f'<tspan fill="{sc}">Stars: </tspan>'
                f'<tspan fill="{t["dots"]}">{esc("." * 8)}</tspan>'
                f'<tspan fill="{t["value"]}"> {esc(stars_txt)}</tspan>'
                f"</text>"
            )
            iy += line_h
            continue
        if kind == "raw_stats2":
            commits_txt, followers_txt, prs_txt = row[1], row[2], row[3]
            sc = t.get("accent_stats", t["label"])
            p.append(
                f'<text x="{right_x}" y="{iy}" font-size="13">'
                f'<tspan fill="{sc}">. Commits: </tspan>'
                f'<tspan fill="{t["dots"]}">{esc("." * 10)}</tspan>'
                f'<tspan fill="{t["value"]}"> {esc(commits_txt)}</tspan>'
                f'<tspan fill="{t["dash"]}"> | </tspan>'
                f'<tspan fill="{sc}">Followers: </tspan>'
                f'<tspan fill="{t["dots"]}">{esc("." * 4)}</tspan>'
                f'<tspan fill="{t["value"]}"> {esc(followers_txt)}</tspan>'
                f'<tspan fill="{t["dash"]}"> | </tspan>'
                f'<tspan fill="{sc}">PRs: </tspan>'
                f'<tspan fill="{t["dots"]}">{esc("." * 4)}</tspan>'
                f'<tspan fill="{t["value"]}"> {esc(prs_txt)}</tspan>'
                f"</text>"
            )
            iy += line_h
            continue
        if kind == "raw_loc":
            total_txt, add_txt, del_txt = row[1], row[2], row[3]
            sc = t.get("accent_stats", t["label"])
            p.append(
                f'<text x="{right_x}" y="{iy}" font-size="13">'
                f'<tspan fill="{sc}">. Lines of Code on GitHub: </tspan>'
                f'<tspan fill="{t["value"]}">{esc(total_txt)} (</tspan>'
                f'<tspan fill="{t["add"]}"> {esc(add_txt)}</tspan>'
                f'<tspan fill="{t["value"]}">, </tspan>'
                f'<tspan fill="{t["del"]}">{esc(del_txt)}</tspan>'
                f'<tspan fill="{t["value"]}"> )</tspan>'
                f"</text>"
            )
            iy += line_h
            continue

    p.append("</svg>")
    return "\n".join(p)


def main():
    if TOKEN:
        stats = collect_stats()
    else:
        # local/dry-run fallback so the script is runnable without a token
        stats = {
            "repos": 0, "contributed": 0, "stars": 0,
            "followers": 0, "commits": 0, "prs": 0,
            "loc_additions": 0, "loc_deletions": 0,
        }
    print("Stats:", stats)

    os.makedirs("assets", exist_ok=True)
    for theme_name in ("dark", "light"):
        svg = render_svg(stats, theme_name)
        path = f"assets/{theme_name}_mode.svg"
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print("Saved", path)


if __name__ == "__main__":
    main()
