"""
Shared data layer for the profile generators.

  load_profile()   -> contents of profile.yml (neofetch rows, achievements, ...)
  fetch_prs()      -> merged PRs the user authored in repos they don't own
  collect_stats()  -> live GitHub stats (repos, stars, followers, commits, PRs)

Network helpers return None on failure so callers can keep the previous
output instead of overwriting it with empty data.

Auth: uses the GITHUB_TOKEN Actions injects automatically into every
workflow run. No personal access token needs to be created or stored.
"""

import os
import datetime
import requests
import yaml

USERNAME = os.environ.get("GH_USERNAME", "altf4-games")
TOKEN = os.environ.get("GITHUB_TOKEN")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": f"{USERNAME}-readme"})
if TOKEN:
    SESSION.headers["Authorization"] = f"Bearer {TOKEN}"


def load_profile(path=None):
    with open(path or os.path.join(ROOT, "profile.yml"), encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------

def graphql(query, variables):
    if not TOKEN:
        return None
    try:
        r = SESSION.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            timeout=20,
        )
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    data = r.json()
    if "errors" in data:
        print("GraphQL errors:", data["errors"])
        return None
    return data.get("data")


def fetch_prs(limit=6, exclude_repos=()):
    """Latest merged PRs authored by USERNAME in repos owned by someone else.
    Returns a list of dicts sorted newest-merged first, or None on failure."""
    query = """
    query($q: String!) {
      search(query: $q, type: ISSUE, first: 50) {
        nodes {
          ... on PullRequest {
            number title url mergedAt
            repository { nameWithOwner stargazerCount }
          }
        }
      }
    }
    """
    q = f"author:{USERNAME} is:pr is:merged -user:{USERNAME} sort:updated-desc"
    data = graphql(query, {"q": q})
    if data is None:
        return None
    excluded = {r.lower() for r in exclude_repos}
    prs = []
    for n in data["search"]["nodes"]:
        if not n or not n.get("mergedAt"):
            continue
        repo = n["repository"]["nameWithOwner"]
        if repo.lower() in excluded:
            continue
        prs.append({
            "repo": repo,
            "number": n["number"],
            "title": n["title"],
            "url": n["url"],
            "merged_at": n["mergedAt"],
            "stars": n["repository"]["stargazerCount"],
        })
    prs.sort(key=lambda p: p["merged_at"], reverse=True)
    return prs[:limit]


def _get(url, **params):
    r = SESSION.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def total_commits_all_time(created_at):
    """contributionsCollection only covers one year per call, so sum each
    year from account creation to today."""
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
    for year in range(int(created_at[:4]), datetime.datetime.now(datetime.UTC).year + 1):
        data = graphql(query, {
            "login": USERNAME,
            "from": f"{year}-01-01T00:00:00Z",
            "to": f"{year}-12-31T23:59:59Z",
        })
        if data:
            c = data["user"]["contributionsCollection"]
            total += c["totalCommitContributions"] + c["restrictedContributionsCount"]
    return total


def collect_stats():
    """Returns a stats dict, or None if the API is unreachable."""
    if not TOKEN:
        return None
    try:
        user = _get(f"https://api.github.com/users/{USERNAME}")
        repos, page = [], 1
        while True:
            batch = _get(f"https://api.github.com/users/{USERNAME}/repos",
                         per_page=100, page=page, type="owner")
            if not batch:
                break
            repos.extend(batch)
            page += 1
    except requests.RequestException as e:
        print("Stats fetch failed:", e)
        return None

    counts = graphql("""
    query($login: String!) {
      user(login: $login) {
        pullRequests(states: MERGED) { totalCount }
        repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) {
          totalCount
        }
      }
    }
    """, {"login": USERNAME}) or {}
    u = counts.get("user") or {}

    return {
        "repos": user.get("public_repos", len(repos)),
        "stars": sum(r.get("stargazers_count", 0) for r in repos),
        "followers": user.get("followers", 0),
        "commits": total_commits_all_time(user.get("created_at", "2020-01-01T00:00:00Z")),
        "prs": (u.get("pullRequests") or {}).get("totalCount", 0),
        "contributed": (u.get("repositoriesContributedTo") or {}).get("totalCount", 0),
    }
