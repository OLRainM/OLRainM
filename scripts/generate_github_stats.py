#!/usr/bin/env python3
"""Generate GitHub stats SVGs from the public GitHub API."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

USERNAME = os.environ.get("GITHUB_USERNAME", "OLRainM")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "assets"
API_ROOT = "https://api.github.com"

LANG_COLORS = {
    "Go": "#00ADD8",
    "Python": "#3572A5",
    "TypeScript": "#3178C6",
    "JavaScript": "#F1E05A",
    "Vue": "#41B883",
    "HTML": "#E34C26",
    "CSS": "#563D7C",
    "Shell": "#89E051",
    "C": "#555555",
    "C++": "#F34B7D",
    "Java": "#B07219",
    "Rust": "#DEA584",
    "Markdown": "#083FA1",
}


def api_get(path: str):
    url = f"{API_ROOT}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-readme",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def api_get_paginated(path: str, per_page: int = 100, max_pages: int = 5):
    items = []
    for page in range(1, max_pages + 1):
        separator = "&" if "?" in path else "?"
        chunk = api_get(f"{path}{separator}per_page={per_page}&page={page}")
        if not chunk:
            break
        items.extend(chunk)
        if len(chunk) < per_page:
            break
    return items


def escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def format_number(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}m"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


def collect_stats():
    user = api_get(f"/users/{USERNAME}")
    repos = [
        repo
        for repo in api_get_paginated(f"/users/{USERNAME}/repos?type=owner&sort=updated")
        if not repo.get("fork")
    ]

    stars = sum(repo.get("stargazers_count", 0) for repo in repos)
    forks = sum(repo.get("forks_count", 0) for repo in repos)
    language_bytes = Counter()
    for repo in repos:
        language = repo.get("language")
        if language:
            language_bytes[language] += max(repo.get("size", 0), 1)

    return {
        "name": user.get("name") or USERNAME,
        "public_repos": user.get("public_repos", 0),
        "followers": user.get("followers", 0),
        "following": user.get("following", 0),
        "stars": stars,
        "forks": forks,
        "repo_count": len(repos),
        "languages": language_bytes.most_common(6),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def render_stats_card(stats: dict) -> str:
    rows = [
        ("Public Repos", stats["public_repos"]),
        ("Stars Earned", stats["stars"]),
        ("Forks", stats["forks"]),
        ("Followers", stats["followers"]),
        ("Following", stats["following"]),
    ]
    row_svg = []
    for index, (label, value) in enumerate(rows):
        y = 78 + index * 28
        row_svg.append(
            f'<text x="28" y="{y}" fill="#8B949E" font-size="14">{escape(label)}</text>'
            f'<text x="372" y="{y}" fill="#C9D1D9" font-size="14" text-anchor="end" font-weight="600">{escape(format_number(value))}</text>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="230" role="img" aria-label="{escape(USERNAME)} GitHub stats">
  <style>text {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif; }}</style>
  <rect width="400" height="230" rx="12" fill="#0D1117" stroke="#30363D"/>
  <text x="28" y="38" fill="#58A6FF" font-size="16" font-weight="700">{escape(USERNAME)}'s GitHub Stats</text>
  <text x="28" y="58" fill="#8B949E" font-size="12">Updated {escape(stats["updated_at"])}</text>
  {"".join(row_svg)}
</svg>
"""


def render_langs_card(stats: dict) -> str:
    languages = stats["languages"]
    if not languages:
        body = '<text x="28" y="92" fill="#8B949E" font-size="14">No public language data yet.</text>'
    else:
        total = sum(count for _, count in languages) or 1
        bar_parts = []
        x = 28
        legend = []
        for index, (name, count) in enumerate(languages):
            width = max(round(344 * count / total), 4)
            color = LANG_COLORS.get(name, "#58A6FF")
            bar_parts.append(f'<rect x="{x}" y="72" width="{width}" height="12" fill="{color}"/>')
            x += width
            col = index % 2
            row = index // 2
            lx = 28 + col * 180
            ly = 110 + row * 24
            percent = count / total * 100
            legend.append(
                f'<circle cx="{lx}" cy="{ly - 4}" r="5" fill="{color}"/>'
                f'<text x="{lx + 14}" y="{ly}" fill="#C9D1D9" font-size="13">{escape(name)} {percent:.1f}%</text>'
            )
        body = "".join(bar_parts) + "".join(legend)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="230" role="img" aria-label="Most used languages">
  <style>text {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif; }}</style>
  <rect width="400" height="230" rx="12" fill="#0D1117" stroke="#30363D"/>
  <text x="28" y="38" fill="#58A6FF" font-size="16" font-weight="700">Most Used Languages</text>
  <text x="28" y="58" fill="#8B949E" font-size="12">Based on public non-fork repositories</text>
  {body}
</svg>
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        stats = collect_stats()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"GitHub API error: {exc.code} {exc.reason}") from exc

    (OUTPUT_DIR / "github-stats.svg").write_text(render_stats_card(stats), encoding="utf-8")
    (OUTPUT_DIR / "github-langs.svg").write_text(render_langs_card(stats), encoding="utf-8")
    print(f"Wrote stats cards to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
