#!/usr/bin/env python3
"""Generate a github_dark compact Top Languages SVG card from GitHub GraphQL API."""

import html
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple

USERNAME = os.environ.get("GITHUB_USERNAME", "Evgenii-Zinner")
LANGS_COUNT = 6

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(
      ownerAffiliations: OWNER
      isFork: false
      isArchived: false
      privacy: PUBLIC
      first: 100
    ) {
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
              color
            }
          }
        }
      }
    }
  }
}
"""


def get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token
    res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        return res.stdout.strip()
    raise RuntimeError("GITHUB_TOKEN env var not set and `gh auth token` failed.")


def fetch_languages(username: str, token: str) -> List[Tuple[str, int, str]]:
    payload = json.dumps({"query": GRAPHQL_QUERY, "variables": {"login": username}}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "top-langs-svg-generator",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if "errors" in data:
        raise RuntimeError(f"GraphQL error: {data['errors']}")

    totals: Dict[str, int] = {}
    colors: Dict[str, str] = {}
    nodes = data["data"]["user"]["repositories"]["nodes"]
    for repo in nodes:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            color = edge["node"]["color"] or "#8b949e"
            size = edge["size"]
            totals[name] = totals.get(name, 0) + size
            colors[name] = color

    ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:LANGS_COUNT]
    return [(name, size, colors[name]) for name, size in ranked]


def render_svg(langs: List[Tuple[str, int, str]]) -> str:
    width = 300
    height = 165
    pad_x = 25
    bar_y = 58
    bar_w = width - 2 * pad_x
    bar_h = 8

    total_bytes = sum(size for _, size, _ in langs) or 1

    # Stacked progress bar segments
    bar_segments: List[str] = []
    cur_x = 0.0
    for idx, (_, size, color) in enumerate(langs):
        seg_w = (size / total_bytes) * bar_w
        if idx == len(langs) - 1:
            seg_w = max(0.0, bar_w - cur_x)
        bar_segments.append(
            f'<rect x="{cur_x:.2f}" y="0" width="{seg_w:.2f}" height="{bar_h}" fill="{html.escape(color)}" />'
        )
        cur_x += seg_w

    # 2-column compact legend
    legend_items: List[str] = []
    col_x = [pad_x, 160]
    start_y = 88
    row_h = 22
    for idx, (name, size, color) in enumerate(langs):
        pct = (size / total_bytes) * 100.0
        col = idx % 2
        row = idx // 2
        x = col_x[col]
        y = start_y + row * row_h
        label = f"{html.escape(name)} {pct:.2f}%"
        legend_items.append(
            f'<g transform="translate({x}, {y})">'
            f'<circle cx="5" cy="-4" r="5" fill="{html.escape(color)}" />'
            f'<text x="15" y="0" class="lang-name">{label}</text>'
            f"</g>"
        )

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Most Used Languages">
  <style>
    .header {{ font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif; fill: #58a6ff; }}
    .lang-name {{ font: 400 11px 'Segoe UI', Ubuntu, Sans-Serif; fill: #c9d1d9; }}
  </style>
  <rect x="0" y="0" width="{width}" height="{height}" rx="4.5" fill="#0d1117" />
  <text x="{pad_x}" y="35" class="header">Most Used Languages</text>
  <svg x="{pad_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}">
    <clipPath id="bar-clip">
      <rect x="0" y="0" width="{bar_w}" height="{bar_h}" rx="4" />
    </clipPath>
    <g clip-path="url(#bar-clip)">
      {''.join(bar_segments)}
    </g>
  </svg>
  {''.join(legend_items)}
</svg>
"""


def main() -> None:
    token = get_token()
    langs = fetch_languages(USERNAME, token)
    if not langs:
        print("No language data returned.", file=sys.stderr)
        sys.exit(1)

    svg = render_svg(langs)
    out_path = Path(__file__).resolve().parents[2] / "top-langs.svg"
    out_path.write_text(svg, encoding="utf-8")
    print(f"Wrote {out_path} with {len(langs)} languages:")
    total = sum(s for _, s, _ in langs) or 1
    for name, size, _ in langs:
        print(f"  - {name}: {(size / total) * 100:.2f}%")


if __name__ == "__main__":
    main()
