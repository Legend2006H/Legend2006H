#!/usr/bin/env python3
"""Generate a themed GitHub contribution activity graph as SVG.

Fetches the user's contribution calendar via the GitHub GraphQL API
(uses GITHUB_TOKEN from the environment) and renders a smooth
"contribution wave" SVG in the profile's saffron/dark theme.

Usage:
    python3 scripts/activity_graph.py --login Legend2006H --output assets/activity-graph.svg
    python3 scripts/activity_graph.py --demo --output /tmp/demo.svg   # render with synthetic data
"""
import argparse
import datetime as dt
import json
import math
import os
import random
import sys
import urllib.request

W, H = 900, 260
PAD_L, PAD_R, PAD_T, PAD_B = 14, 14, 46, 36
PLOT_W = W - PAD_L - PAD_R
PLOT_H = H - PAD_T - PAD_B


def fetch_calendar(login, token):
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }
    """
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": login}}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-activity-graph",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [
        (d["date"], d["contributionCount"])
        for w in cal["weeks"]
        for d in w["contributionDays"]
    ]
    return cal["totalContributions"], days


def demo_days(n=371):
    today = dt.date.today()
    days = []
    for i in range(n):
        date = today - dt.timedelta(days=n - 1 - i)
        wave = 6 + 5 * math.sin(i / 18.0) + 3 * math.sin(i / 5.0 + 1.3)
        count = max(0, int(wave + random.gauss(0, 2.2)))
        if random.random() < 0.18:
            count = 0
        days.append((date.isoformat(), count))
    return sum(c for _, c in days), days


def smooth_path(pts):
    """Catmull-Rom -> cubic Bezier path through pts [(x, y), ...]."""
    if len(pts) < 2:
        return ""
    d = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for i in range(len(pts) - 1):
        p0 = pts[max(0, i - 1)]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[min(len(pts) - 1, i + 2)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        d.append(f"C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}")
    return " ".join(d)


def render_svg(total, days):
    n = len(days)
    counts = [c for _, c in days]
    peak = max(counts) if counts else 0
    scale_max = max(peak * 1.15, 1)

    def xy(i, c):
        x = PAD_L + (i / max(n - 1, 1)) * PLOT_W
        y = PAD_T + PLOT_H - (c / scale_max) * PLOT_H
        return (x, y)

    pts = [xy(i, c) for i, (_, c) in enumerate(days)]
    line = smooth_path(pts)
    base_y = PAD_T + PLOT_H
    area = f"{line} L {pts[-1][0]:.1f} {base_y} L {pts[0][0]:.1f} {base_y} Z" if line else ""

    peak_i = counts.index(peak) if peak else 0
    px, py = xy(peak_i, peak)

    # month labels at month boundaries
    months = []
    seen = set()
    for i, (datestr, _) in enumerate(days):
        month = datestr[:7]
        if month not in seen:
            seen.add(month)
            label = dt.date.fromisoformat(datestr).strftime("%b")
            months.append((xy(i, 0)[0], label))

    grid = "\n".join(
        f'<line x1="{PAD_L}" y1="{y:.0f}" x2="{W - PAD_R}" y2="{y:.0f}" stroke="#21262d" stroke-width="1"/>'
        for y in (PAD_T, PAD_T + PLOT_H / 3, PAD_T + 2 * PLOT_H / 3, PAD_T + PLOT_H)
    )
    labels = "\n".join(
        f'<text x="{x:.0f}" y="{H - 12}" font-family="Inter, \'Segoe UI\', Verdana, sans-serif" '
        f'font-size="11" fill="#7d8590">{m}</text>'
        for x, m in months
    )

    if peak > 0:
        wave = f"""
    <path d="{area}" fill="url(#waveFill)"/>
    <path d="{line}" fill="none" stroke="#ff8c2e" stroke-width="2.5" stroke-linecap="round"/>
    <circle cx="{px:.1f}" cy="{py:.1f}" r="9" fill="#ff8c2e" opacity="0.25"/>
    <circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#ffb37a"/>"""
    else:
        wave = f"""
    <line x1="{PAD_L}" y1="{base_y - 20}" x2="{W - PAD_R}" y2="{base_y - 20}"
          stroke="#ff8c2e" stroke-width="2" stroke-dasharray="6 6" opacity="0.6"/>"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Contribution activity graph">
  <defs>
    <linearGradient id="waveFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ff8c2e" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="#ff8c2e" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect width="{W}" height="{H}" rx="10" fill="#0d1117" stroke="#21262d"/>
  <text x="{PAD_L}" y="28" font-family="Inter, 'Segoe UI', Verdana, sans-serif" font-size="15" font-weight="600" fill="#e6edf3">{total:,} contributions in the last year</text>
  {grid}
  {wave}
  {labels}
</svg>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", default="Legend2006H")
    ap.add_argument("--output", default="assets/activity-graph.svg")
    ap.add_argument("--demo", action="store_true", help="render with synthetic data")
    args = ap.parse_args()

    if args.demo:
        total, days = demo_days()
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            sys.exit("GITHUB_TOKEN is not set")
        total, days = fetch_calendar(args.login, token)

    svg = render_svg(total, days)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        f.write(svg)
    print(f"wrote {args.output} ({total} contributions, {len(days)} days)")


if __name__ == "__main__":
    main()
