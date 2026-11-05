"""Render assets/streak.svg and assets/extra-stats.svg from the GitHub contribution calendar.

Run by .github/workflows/streak.yml. Needs GITHUB_TOKEN and GITHUB_USER in the environment.
"""

import json
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

USER = os.environ.get("GITHUB_USER", "akhil-nasim")
TOKEN = os.environ["GITHUB_TOKEN"]
ASSETS = Path(__file__).resolve().parent.parent / "assets"

# Same palette as the github-readme-stats cards in README.md
BG = "#0d1117"
ACCENT = "#58a6ff"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
DIVIDER = "#30363d"


def graphql(query: str, variables: dict) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        body = json.load(resp)
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]


def fetch_days() -> dict[date, int]:
    created = graphql(
        "query($login: String!) { user(login: $login) { createdAt } }", {"login": USER}
    )["user"]["createdAt"]
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar { weeks { contributionDays { date contributionCount } } }
        }
      }
    }"""
    days: dict[date, int] = {}
    now = datetime.now(timezone.utc)
    for year in range(int(created[:4]), now.year + 1):
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = min(datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc), now)
        data = graphql(query, {"login": USER, "from": start.isoformat(), "to": end.isoformat()})
        weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        for week in weeks:
            for day in week["contributionDays"]:
                days[date.fromisoformat(day["date"])] = day["contributionCount"]
    return days


def streaks(days: dict[date, int]) -> dict:
    today = max(days)
    ordered = sorted(days)
    total = sum(days.values())
    first = next((d for d in ordered if days[d]), today)

    longest = (0, today, today)
    run_start = None
    for d in ordered:
        if days[d]:
            run_start = run_start or d
            length = (d - run_start).days + 1
            if length > longest[0]:
                longest = (length, run_start, d)
        else:
            run_start = None

    # Today without contributions yet doesn't break the streak
    end = today if days[today] else today - timedelta(days=1)
    start = end
    while days.get(start - timedelta(days=1)):
        start -= timedelta(days=1)
    current = (end - start).days + 1 if days.get(end) else 0

    active = [d for d in ordered if days[d]]
    best = max(ordered, key=lambda d: days[d])
    return {
        "active": len(active),
        "average": total / ((today - first).days + 1),
        "best": (days[best], best),
        "total": total,
        "first": first,
        "current": (current, start, end),
        "longest": longest,
    }


def fmt(d: date) -> str:
    return d.strftime("%b %-d, %Y")


def span(length: int, start: date, end: date) -> str:
    if not length:
        return ""
    return fmt(start) if start == end else f"{fmt(start)} - {fmt(end)}"


def render(s: dict) -> str:
    cur_len, cur_start, cur_end = s["current"]
    long_len, long_start, long_end = s["longest"]
    font = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195">
  <style>
    .num {{ font: 700 28px {font}; }}
    .label {{ font: 600 14px {font}; }}
    .date {{ font: 400 12px {font}; fill: {MUTED}; }}
  </style>
  <rect width="495" height="195" rx="4.5" fill="{BG}"/>
  <line x1="165" y1="28" x2="165" y2="167" stroke="{DIVIDER}"/>
  <line x1="330" y1="28" x2="330" y2="167" stroke="{DIVIDER}"/>

  <text x="82.5" y="79" class="num" fill="{TEXT}" text-anchor="middle">{s["total"]:,}</text>
  <text x="82.5" y="115" class="label" fill="{TEXT}" text-anchor="middle">Total Contributions</text>
  <text x="82.5" y="137" class="date" text-anchor="middle">{fmt(s["first"])} - Present</text>

  <g transform="translate(247.5, 71)">
    <circle r="40" fill="none" stroke="{ACCENT}" stroke-width="5" stroke-dasharray="226 25.3" transform="rotate(-72)" stroke-linecap="round"/>
    <path d="M0 -55 c4 5 8 9 8 15 a8 8 0 0 1 -16 0 c0 -4 2 -7 4 -9 c0 3 2 5 4 5 c0 -4 -2 -7 0 -11z" fill="{ACCENT}"/>
    <text y="10" class="num" fill="{TEXT}" text-anchor="middle">{cur_len}</text>
  </g>
  <text x="247.5" y="140" class="label" fill="{ACCENT}" text-anchor="middle">Current Streak</text>
  <text x="247.5" y="160" class="date" text-anchor="middle">{span(cur_len, cur_start, cur_end)}</text>

  <text x="412.5" y="79" class="num" fill="{TEXT}" text-anchor="middle">{long_len}</text>
  <text x="412.5" y="115" class="label" fill="{TEXT}" text-anchor="middle">Longest Streak</text>
  <text x="412.5" y="137" class="date" text-anchor="middle">{span(long_len, long_start, long_end)}</text>
</svg>
"""


def render_extra(s: dict) -> str:
    best_count, best_day = s["best"]
    font = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"
    columns = [
        ("Active Days", f"{s['active']:,}", f"since {fmt(s['first'])}"),
        ("Average / Day", f"{s['average']:.1f}", "contributions"),
        ("Best Day", f"{best_count:,}", fmt(best_day)),
    ]
    cells = []
    for i, (label, value, sub) in enumerate(columns):
        x = 82.5 + i * 165
        cells.append(
            f'  <text x="{x}" y="88" class="num" fill="{TEXT}" text-anchor="middle">{value}</text>\n'
            f'  <text x="{x}" y="118" class="label" fill="{ACCENT}" text-anchor="middle">{label}</text>\n'
            f'  <text x="{x}" y="138" class="date" text-anchor="middle">{sub}</text>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195">
  <style>
    .num {{ font: 700 28px {font}; }}
    .label {{ font: 600 14px {font}; }}
    .date {{ font: 400 12px {font}; fill: {MUTED}; }}
  </style>
  <rect width="495" height="195" rx="4.5" fill="{BG}"/>
  <line x1="165" y1="28" x2="165" y2="167" stroke="{DIVIDER}"/>
  <line x1="330" y1="28" x2="330" y2="167" stroke="{DIVIDER}"/>
{chr(10).join(cells)}
</svg>
"""


if __name__ == "__main__":
    stats = streaks(fetch_days())
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "streak.svg").write_text(render(stats))
    (ASSETS / "extra-stats.svg").write_text(render_extra(stats))
    print(f"Wrote streak.svg and extra-stats.svg to {ASSETS}")
