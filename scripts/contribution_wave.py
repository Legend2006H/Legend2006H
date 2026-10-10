#!/usr/bin/env python3
"""Generate a themed GitHub contribution activity wave as SVG.

Fetches Legend2006H's contribution calendar via the GitHub GraphQL API
(uses GITHUB_TOKEN from the environment) and renders a smooth
"contribution wave" SVG in the Neural Fort saffron/dark theme.

Produces TWO outputs:
  assets/contribution-wave-dark.svg  (dark-mode)
  assets/contribution-wave-light.svg (light-mode)

Usage:
    python3 scripts/contribution_wave.py
    python3 scripts/contribution_wave.py --demo   # synthetic data (no token needed)
"""
import argparse
import datetime as dt
import json
import math
import os
import random
import sys
import urllib.request

# --- Layout constants ---
W, H = 900, 280
PAD_L, PAD_R, PAD_T, PAD_B = 50, 20, 55, 42
PLOT_W = W - PAD_L - PAD_R
PLOT_H = H - PAD_T - PAD_B

USERNAME = "Legend2006H"


# --- Themes ---
THEMES = {
    "dark": {
        "bg": "#0d1117",
        "card_stroke": "#1a1e2e",
        "title_fill": "#e6edf3",
        "label_fill": "#7d8590",
        "grid_stroke": "#21262d",
        "wave_stroke": "#ff8c2e",
        "wave_fill_top": "#ff8c2e",
        "wave_fill_bot": "#ff8c2e",
        "peak_outer": "#ff8c2e",
        "peak_inner": "#ffb37a",
        "accent": "#5b8cff",
        "fort_stroke": "#ff8c2e",
        "fort_fill": "#111820",
    },
    "light": {
        "bg": "#ffffff",
        "card_stroke": "#d0d7de",
        "title_fill": "#1f2328",
        "label_fill": "#656d76",
        "grid_stroke": "#eaeef2",
        "wave_stroke": "#e06910",
        "wave_fill_top": "#e06910",
        "wave_fill_bot": "#e06910",
        "peak_outer": "#e06910",
        "peak_inner": "#d97a28",
        "accent": "#3b5998",
        "fort_stroke": "#e06910",
        "fort_fill": "#f6f8fa",
    },
}


def fetch_calendar(login: str, token: str):
    """Fetch contribution calendar from GitHub GraphQL API."""
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
            "User-Agent": "neural-fort-profile",
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


def demo_days(n: int = 371):
    """Generate synthetic contribution data for preview."""
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


def catmull_rom_path(pts: list) -> str:
    """Convert points to a smooth Catmull-Rom -> cubic Bezier SVG path."""
    if len(pts) < 2:
        return ""
    d = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for i in range(len(pts) - 1):
        p0 = pts[max(0, i - 1)]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[min(len(pts) - 1, i + 2)]
        c1x = p1[0] + (p2[0] - p0[0]) / 6.0
        c1y = p1[1] + (p2[1] - p0[1]) / 6.0
        c2x = p2[0] - (p3[0] - p1[0]) / 6.0
        c2y = p2[1] - (p3[1] - p1[1]) / 6.0
        d.append(
            f"C {c1x:.1f} {c1y:.1f} {c2x:.1f} {c2y:.1f} {p2[0]:.1f} {p2[1]:.1f}"
        )
    return " ".join(d)


def render_svg(total: int, days: list, theme_name: str) -> str:
    """Render the contribution wave SVG string."""
    t = THEMES[theme_name]
    n = len(days)
    counts = [c for _, c in days]
    peak = max(counts) if counts else 0
    scale_max = max(peak * 1.15, 1)

    def xy(i, c):
        x = PAD_L + (i / max(n - 1, 1)) * PLOT_W
        y = PAD_T + PLOT_H - (c / scale_max) * PLOT_H
        return (x, y)

    # Downsample for smoother rendering (every 3rd point)
    sampled = [(i, c) for i, (_, c) in enumerate(days)]
    step = max(1, n // 120)
    sampled_pts = sampled[::step]
    if sampled[-1] not in sampled_pts:
        sampled_pts.append(sampled[-1])

    pts = [xy(i, c) for i, c in sampled_pts]
    line = catmull_rom_path(pts)
    base_y = PAD_T + PLOT_H
    area = f"{line} L {pts[-1][0]:.1f} {base_y} L {pts[0][0]:.1f} {base_y} Z" if line else ""

    # Peak marker
    peak_i = counts.index(peak) if peak else 0
    px, py = xy(peak_i, peak)

    # Month labels
    months_out = []
    seen = set()
    for i, (datestr, _) in enumerate(days):
        month = datestr[:7]
        if month not in seen:
            seen.add(month)
            label = dt.date.fromisoformat(datestr).strftime("%b")
            mx = xy(i, 0)[0]
            months_out.append(f'<text x="{mx:.0f}" y="{H - 14}" '
                              f'font-size="10" fill="{t["label_fill"]}">{label}</text>')

    # Y-axis grid lines
    grid_lines = []
    for frac in (0, 1/3, 2/3, 1):
        gy = PAD_T + PLOT_H * frac
        grid_lines.append(
            f'<line x1="{PAD_L}" y1="{gy:.0f}" x2="{W - PAD_R}" y2="{gy:.0f}" '
            f'stroke="{t["grid_stroke"]}" stroke-width="1"/>'
        )

    # Y-axis labels
    y_labels = []
    for frac, val in [(0, peak), (1/3, int(peak * 2/3)), (2/3, int(peak * 1/3)), (1, 0)]:
        gy = PAD_T + PLOT_H * frac
        y_labels.append(
            f'<text x="{PAD_L - 8}" y="{gy + 3:.0f}" text-anchor="end" '
            f'font-size="9" fill="{t["label_fill"]}">{val}</text>'
        )

    # Build the wave section
    if peak > 0:
        wave_section = f"""
    <path d="{area}" fill="url(#waveFill)"/>
    <path d="{line}" fill="none" stroke="{t["wave_stroke"]}" stroke-width="2" stroke-linecap="round">
      <animate attributeName="stroke-opacity" values="0.7;1;0.7" dur="4s" repeatCount="indefinite"/>
    </path>
    <circle cx="{px:.1f}" cy="{py:.1f}" r="10" fill="{t["peak_outer"]}" opacity="0.2">
      <animate attributeName="r" values="10;14;10" dur="3s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.2;0.05;0.2" dur="3s" repeatCount="indefinite"/>
    </circle>
    <circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{t["peak_inner"]}">
      <animate attributeName="r" values="3;5;3" dur="3s" repeatCount="indefinite"/>
    </circle>"""
    else:
        wave_section = f"""
    <line x1="{PAD_L}" y1="{base_y - 20}" x2="{W - PAD_R}" y2="{base_y - 20}"
          stroke="{t["wave_stroke"]}" stroke-width="2" stroke-dasharray="6 6" opacity="0.5"/>"""

    # Animated scan line over the chart
    scan = f"""
    <rect x="-2" y="{PAD_T}" width="3" height="{PLOT_H}" fill="{t["accent"]}" opacity="0" rx="1">
      <animate attributeName="x" from="{PAD_L}" to="{W - PAD_R}" dur="6s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0;0.3;0.3;0" dur="6s" repeatCount="indefinite"/>
    </rect>"""

    # Fort battlement micro-border at the very bottom
    batt = []
    for i in range(0, W, 20):
        batt.append(f"V 271 H {i+8} V 275 H {i+14} V 271 H {i+20}")
    fort_path = f"M 0 {H} V 271 " + " ".join(batt) + f" V {H} Z"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Contribution activity wave for Legend2006H">
  <defs>
    <linearGradient id="waveFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{t["wave_fill_top"]}" stop-opacity="0.4"/>
      <stop offset="100%" stop-color="{t["wave_fill_bot"]}" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect width="{W}" height="{H}" rx="12" fill="{t["bg"]}" stroke="{t["card_stroke"]}" stroke-width="1"/>

  <!-- Title -->
  <text x="{PAD_L}" y="30" font-family="'Segoe UI', system-ui, -apple-system, sans-serif" font-size="14" font-weight="600" fill="{t["title_fill"]}">
    {total:,} contributions in the last year
  </text>
  <text x="{W - PAD_R}" y="30" text-anchor="end" font-family="'SFMono-Regular', Consolas, monospace" font-size="10" fill="{t["accent"]}">
    NEURAL FORT ANALYTICS
  </text>

  <!-- Grid -->
  {"".join(grid_lines)}
  {"".join(y_labels)}

  <!-- Wave -->
  {wave_section}

  <!-- Scan line -->
  {scan}

  <!-- Month labels -->
  <g font-family="'SFMono-Regular', Consolas, monospace" text-anchor="middle">
    {"".join(months_out)}
  </g>

  <!-- Fort micro-border -->
  <path d="{fort_path}" fill="{t["fort_fill"]}" stroke="{t["fort_stroke"]}" stroke-width="0.5" opacity="0.25"/>
</svg>
"""


def main():
    ap = argparse.ArgumentParser(description="Generate contribution wave SVGs")
    ap.add_argument("--login", default=USERNAME)
    ap.add_argument("--demo", action="store_true", help="Use synthetic data")
    args = ap.parse_args()

    if args.demo:
        total, days = demo_days()
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            sys.exit("Error: GITHUB_TOKEN environment variable is not set")
        total, days = fetch_calendar(args.login, token)

    os.makedirs("assets", exist_ok=True)

    for theme_name in ("dark", "light"):
        svg = render_svg(total, days, theme_name)
        out_path = f"assets/contribution-wave-{theme_name}.svg"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"[OK] {out_path}  ({total:,} contributions, {len(days)} days)")


if __name__ == "__main__":
    main()
