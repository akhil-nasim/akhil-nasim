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


FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"


def card(title: str, columns: list[tuple[str, str, str]], ring: int | None = None) -> str:
    """A 495x195 card laid out like the github-readme-stats cards: title top-left, three columns."""
    cells = []
    for i, (value, label, sub) in enumerate(columns):
        x = 82.5 + i * 165
        if i == ring:
            cells.append(
                f'  <g transform="translate({x}, 98)">\n'
                f'    <circle r="30" stroke="{ACCENT}" stroke-opacity="0.2" stroke-width="5"/>\n'
                f'    <circle r="30" stroke="{ACCENT}" stroke-width="5" stroke-dasharray="160 28.5"'
                f' stroke-linecap="round" transform="rotate(-62)"/>\n'
                f'    <path d="M0 -42 c3 4 6 7 6 11 a6 6 0 0 1 -12 0 c0 -3 1.5 -5 3 -7'
                f' c0 2 1.5 4 3 4 c0 -3 -1.5 -5 0 -8z" fill="{ACCENT}"/>\n'
                f'    <text y="8" class="num" text-anchor="middle">{value}</text>\n'
                f"  </g>"
            )
        else:
            cells.append(f'  <text x="{x}" y="107" class="num" text-anchor="middle">{value}</text>')
        cells.append(f'  <text x="{x}" y="150" class="label" text-anchor="middle">{label}</text>')
        cells.append(f'  <text x="{x}" y="170" class="sub" text-anchor="middle">{sub}</text>')
    body = "\n".join(cells)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195" fill="none">
  <style>
    .header {{ font: 600 18px {FONT}; fill: {ACCENT}; }}
    .num {{ font: 800 24px {FONT}; fill: {TEXT}; }}
    .label {{ font: 600 14px {FONT}; fill: {TEXT}; }}
    .sub {{ font: 400 12px {FONT}; fill: {MUTED}; }}
  </style>
  <rect x="0.5" y="0.5" width="494" height="194" rx="4.5" fill="{BG}"/>
  <text x="25" y="35" class="header">{title}</text>
{body}
</svg>
"""


def render(s: dict) -> str:
    cur_len, cur_start, cur_end = s["current"]
    long_len, long_start, long_end = s["longest"]
    return card(
        "My Contribution Streak",
        [
            (f"{s['total']:,}", "Total Contributions", f"{fmt(s['first'])} - Present"),
            (str(cur_len), "Current Streak", span(cur_len, cur_start, cur_end)),
            (str(long_len), "Longest Streak", span(long_len, long_start, long_end)),
        ],
        ring=1,
    )


def render_extra(s: dict) -> str:
    best_count, best_day = s["best"]
    return card(
        "My Activity",
        [
            (f"{s['active']:,}", "Active Days", f"since {fmt(s['first'])}"),
            (f"{s['average']:.1f}", "Average / Day", "contributions"),
            (f"{best_count:,}", "Best Day", fmt(best_day)),
        ],
    )


if __name__ == "__main__":
    stats = streaks(fetch_days())
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "streak.svg").write_text(render(stats))
    (ASSETS / "extra-stats.svg").write_text(render_extra(stats))
    print(f"Wrote streak.svg and extra-stats.svg to {ASSETS}")
