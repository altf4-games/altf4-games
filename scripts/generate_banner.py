"""
Generates a neofetch-style SVG banner (dark_mode.svg / light_mode.svg) for the
GitHub profile README, in the ". label: ......... value" dot-leader layout
with dashed section headers, plus live GitHub stats (repos, stars, followers,
total commits, contributed-to repos, and total lines of code added/removed).

Auth: uses the GITHUB_TOKEN Actions injects automatically into every
workflow run. No personal access token needs to be created or stored.
"""

import os
import time
import html
import datetime
import requests

USERNAME = os.environ.get("GH_USERNAME", "altf4-games")
TOKEN = os.environ.get("GITHUB_TOKEN")

HEADERS = {"User-Agent": f"{USERNAME}-readme-banner"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

FONT_FAMILY = "'Cascadia Code','Fira Code',Consolas,'DejaVu Sans Mono',monospace"
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


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
        "loc_additions": additions,
        "loc_deletions": deletions,
    }


# ---------------------------------------------------------------------------
# Layout helpers (character-count based -- safe because the font is monospace)
# ---------------------------------------------------------------------------

def dotted(label, value, width=46):
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
      ('section', text)                         -- "- Contact" divider
      ('kv', label, value)                      -- dot-leader line
      ('raw', text)                              -- pre-formatted line (stats block)
      ('blank',)                                 -- spacer
    """
    rows = [("header", f"{USERNAME}@github")]

    rows.append(("kv", "OS", "Full-Stack, AI/ML, Game Development"))
    rows.append(("kv", "Host", "Unreal Engine 5 / Unity"))
    rows.append(("kv", "Kernel", "4-Star CodeChef"))
    rows.append(("kv", "Uptime", "200k+ Game Downloads"))
    rows.append(("kv", "Shell", "Competitive Programmer"))
    rows.append(("blank",))

    rows.append(("kv", "Languages.Core", "C, C++, C#, Java, Python, Dart"))
    rows.append(("kv", "Languages.Web", "JavaScript, HTML, CSS"))
    rows.append(("kv", "Languages.Data", "SQL, JSON, YAML"))
    rows.append(("blank",))

    rows.append(("kv", "Frameworks.Web", "React, Next.js, Node.js, FastAPI"))
    rows.append(("kv", "Frameworks.Mobile", "Flutter, React Native"))
    rows.append(("kv", "Frameworks.Game", "Unity, Unreal Engine"))
    rows.append(("kv", "Frameworks.AI", "TensorFlow, Scikit-learn"))
    rows.append(("kv", "Databases", "MongoDB, PostgreSQL, Firebase"))
    rows.append(("blank",))

    rows.append(("kv", "Achievements", "Winner, Most Addictive Game (8th Wall Jam)"))
    rows.append(("kv", "Achievements", "1st Runner-Up, ISTE KJSSE Pixel Wars"))
    rows.append(("kv", "Achievements", "Top 10, I<3 Hackathon Pune Web3 Edition"))
    rows.append(("kv", "Achievements", "Finalist, IDEA Hackathon"))
    rows.append(("kv", "Achievements", "Featured by Markiplier & Jacksepticeye (20M+)"))
    rows.append(("blank",))

    rows.append(("section", "Open Source"))
    rows.append(("kv", "PR Merged", "microsoft/data-formulator #351"))
    rows.append(("kv", "PR Merged", "microsoft/apm #1367"))
    rows.append(("blank",))

    rows.append(("section", "Contact"))
    rows.append(("kv", "LinkedIn", "pradyum-mistry"))
    rows.append(("kv", "Itch.io", "altf4-games"))
    rows.append(("kv", "LeetCode", "pradyum_mistry"))
    rows.append(("kv", "CodeChef", "pradyum_m"))
    rows.append(("blank",))

    rows.append(("section", "GitHub Stats"))
    repos_txt = f"{stats['repos']}"
    contrib_txt = f"{{Contributed: {stats['contributed']}}}"
    stars_txt = f"{stats['stars']:,}"
    commits_txt = f"{stats['commits']:,}"
    followers_txt = f"{stats['followers']:,}"
    loc_total = stats["loc_additions"] + stats["loc_deletions"]

    rows.append(("raw_stats1", repos_txt, contrib_txt, stars_txt))
    rows.append(("raw_stats2", commits_txt, followers_txt))
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
        "value": "#e8eaee",
        "logo": "#8fb8d9",
        "add": "#4fd671",
        "del": "#e5677a",
    },
    "light": {
        "bg": "#f7f7f8",
        "chrome": "#e8e8ea",
        "title_gray": "#5b5f66",
        "header_green": "#1f9c3f",
        "dash": "#a7abb3",
        "label": "#24262b",
        "dots": "#a7abb3",
        "value": "#101216",
        "logo": "#2f6690",
        "add": "#1f9c3f",
        "del": "#c23b4d",
    },
}


def esc(s):
    return html.escape(s, quote=True)


def render_svg(stats, theme_name):
    t = THEMES[theme_name]
    rows = build_lines(stats)

    pad_x = 36
    bar_h = 42
    pad_top = bar_h + 30
    line_h = 21
    logo_line_h = 19
    right_x = pad_x + 470
    right_width_chars = 58
    width = 1180

    right_h = pad_top + len(rows) * line_h + 30
    left_h = pad_top + len(ASCII_LOGO) * logo_line_h + 70
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

    # left column: ascii logo
    y = pad_top
    p.append(f'<text x="{pad_x}" y="{y}" font-size="12" font-weight="bold" fill="{t["logo"]}" xml:space="preserve">')
    for i, line in enumerate(ASCII_LOGO):
        dy = 0 if i == 0 else logo_line_h
        p.append(f'<tspan x="{pad_x}" dy="{dy}">{esc(line) if line else " "}</tspan>')
    p.append("</text>")
    footer_y = y + len(ASCII_LOGO) * logo_line_h + 34
    p.append(f'<text x="{pad_x}" y="{footer_y}" font-size="13" fill="{t["title_gray"]}">github.com/{esc(USERNAME)}</text>')

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
            p.append(
                f'<text x="{right_x}" y="{iy}" font-size="13">'
                f'<tspan fill="{t["label"]}">{esc(prefix)}</tspan>'
                f'<tspan fill="{t["dots"]}">{esc(dots)}</tspan>'
                f'<tspan fill="{t["value"]}">{esc(val)}</tspan>'
                f"</text>"
            )
            iy += line_h
            continue
        if kind == "raw_stats1":
            repos_txt, contrib_txt, stars_txt = row[1], row[2], row[3]
            p.append(
                f'<text x="{right_x}" y="{iy}" font-size="13">'
                f'<tspan fill="{t["label"]}">. Repos: </tspan>'
                f'<tspan fill="{t["dots"]}">{esc("." * 4)}</tspan>'
                f'<tspan fill="{t["value"]}"> {esc(repos_txt)} {esc(contrib_txt)}</tspan>'
                f'<tspan fill="{t["dash"]}"> | </tspan>'
                f'<tspan fill="{t["label"]}">Stars: </tspan>'
                f'<tspan fill="{t["dots"]}">{esc("." * 8)}</tspan>'
                f'<tspan fill="{t["value"]}"> {esc(stars_txt)}</tspan>'
                f"</text>"
            )
            iy += line_h
            continue
        if kind == "raw_stats2":
            commits_txt, followers_txt = row[1], row[2]
            p.append(
                f'<text x="{right_x}" y="{iy}" font-size="13">'
                f'<tspan fill="{t["label"]}">. Commits: </tspan>'
                f'<tspan fill="{t["dots"]}">{esc("." * 16)}</tspan>'
                f'<tspan fill="{t["value"]}"> {esc(commits_txt)}</tspan>'
                f'<tspan fill="{t["dash"]}"> | </tspan>'
                f'<tspan fill="{t["label"]}">Followers: </tspan>'
                f'<tspan fill="{t["dots"]}">{esc("." * 7)}</tspan>'
                f'<tspan fill="{t["value"]}"> {esc(followers_txt)}</tspan>'
                f"</text>"
            )
            iy += line_h
            continue
        if kind == "raw_loc":
            total_txt, add_txt, del_txt = row[1], row[2], row[3]
            p.append(
                f'<text x="{right_x}" y="{iy}" font-size="13">'
                f'<tspan fill="{t["label"]}">. Lines of Code on GitHub: </tspan>'
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
            "followers": 0, "commits": 0, "loc_additions": 0, "loc_deletions": 0,
        }
    print("Stats:", stats)

    os.makedirs("assets", exist_ok=True)
    for theme_name in ("dark", "light"):
        svg = render_svg(stats, theme_name)
        path = f"assets/{theme_name}_mode.svg"
        with open(path, "w") as f:
            f.write(svg)
        print("Saved", path)


if __name__ == "__main__":
    main()
