#!/usr/bin/env python3
"""Builds the profile activity card (dark and light SVG) from the public contribution calendar.

Usage: GITHUB_TOKEN=... python3 scripts/activity_card.py [--user adrian971029] [--out assets]
       python3 scripts/activity_card.py --calendar cal.json   # offline, from a saved GraphQL response
"""
import argparse
import datetime as dt
import json
import os
import urllib.request

QUERY = """query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""

THEMES = {
    "dark": dict(card="#151b23", border="#3d444d", grid="#262c36", ink="#f0f6fc", muted="#9198a1",
                 bar="#8B6AFF", accent=("#3DDC84", "#7F52FF")),
    "light": dict(card="#f6f8fa", border="#d1d9e0", grid="#e1e4e8", ink="#1f2328", muted="#59636e",
                  bar="#7F52FF", accent=("#1FA463", "#7F52FF")),
}
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def window(today):
    """The last 12 complete months: first day of the month a year back, to the end of last month."""
    end = today.replace(day=1) - dt.timedelta(days=1)
    start = dt.date(end.year - 1 + (end.month == 12), end.month % 12 + 1, 1)
    return start, end


def fetch(login, start, end):
    body = json.dumps({"query": QUERY, "variables": {
        "login": login, "from": f"{start}T00:00:00Z", "to": f"{end}T23:59:59Z"}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"bearer {os.environ['GITHUB_TOKEN']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def daily_counts(payload, start, end):
    weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}
    out, day = [], start
    while day <= end:
        out.append((day, days.get(day.isoformat(), 0)))
        day += dt.timedelta(days=1)
    return out


def stats(days):
    months = {}
    for day, n in days:
        months[(day.year, day.month)] = months.get((day.year, day.month), 0) + n
    streak = best = 0
    for _, n in days:
        streak = streak + 1 if n else 0
        best = max(best, streak)
    return dict(
        months=sorted(months.items()),
        total=sum(n for _, n in days),
        active=sum(1 for _, n in days if n),
        span=len(days),
        streak=best,
        best_day=max(n for _, n in days),
    )


def nice_step(top):
    for step in (5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000):
        if top / step <= 4:
            return step
    return 10000


def compact(n):
    if n < 1000:
        return f"{n}"
    return f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "K"


def column(x, y, w, h, r):
    """A column rounded at the data end and square at the baseline."""
    r = min(r, w / 2, h)
    return (f'<path d="M{x:.1f},{y + h:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} '
            f'H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} V{y + h:.1f} Z"/>')


def render(s, start, end, t):
    W, H = 840, 284
    px0, px1, py0, py1 = 318, 808, 52, 214
    months = s["months"]
    peak = max(n for _, n in months) or 1
    step = nice_step(peak)
    top = -(-peak // step) * step
    scale = (py1 - py0) / top
    slot = (px1 - px0) / len(months)
    bw = min(24, slot * 0.56)

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'role="img" aria-labelledby="t d">',
         f'<title id="t">Contributions, {MONTHS[start.month - 1]} {start.year} to {MONTHS[end.month - 1]} {end.year}</title>',
         '<desc id="d">' + "; ".join(f"{MONTHS[m - 1]} {y}: {n}" for (y, m), n in months) + "</desc>",
         f'<defs><linearGradient id="a" x1="0" x2="1"><stop offset="0" stop-color="{t["accent"][0]}"/>'
         f'<stop offset="1" stop-color="{t["accent"][1]}"/></linearGradient>'
         f'<clipPath id="c"><rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12"/></clipPath></defs>',
         f'<g font-family="{FONT}">',
         f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="{t["card"]}" stroke="{t["border"]}"/>',
         f'<rect x="0" y="0" width="{W}" height="3" fill="url(#a)" clip-path="url(#c)"/>']

    # Left panel: the headline number and three supporting figures.
    period = f"{MONTHS[start.month - 1]} {start.year} – {MONTHS[end.month - 1]} {end.year}"
    o += [f'<text x="32" y="50" font-size="15" font-weight="600" fill="{t["ink"]}">Contributions</text>',
          f'<text x="32" y="71" font-size="13" fill="{t["muted"]}">{period}</text>',
          f'<text x="30" y="128" font-size="52" font-weight="600" fill="{t["ink"]}">{s["total"]:,}</text>']
    rows = [("Active days", f'{s["active"]} of {s["span"]}'),
            ("Longest streak", f'{s["streak"]} days'),
            ("Busiest day", f'{s["best_day"]:,}')]
    for i, (label, value) in enumerate(rows):
        y = 168 + i * 26
        o += [f'<text x="32" y="{y}" font-size="13" fill="{t["muted"]}">{label}</text>',
              f'<text x="252" y="{y}" font-size="13" font-weight="600" fill="{t["ink"]}" text-anchor="end">{value}</text>']

    # Right panel: monthly columns over hairline gridlines.
    for v in range(0, top + 1, step):
        y = py1 - v * scale
        o += [f'<line x1="{px0}" x2="{px1}" y1="{y:.1f}" y2="{y:.1f}" stroke="{t["grid"]}" stroke-width="1"/>',
              f'<text x="{px0 - 10}" y="{y + 4:.1f}" font-size="11" fill="{t["muted"]}" text-anchor="end" '
              f'style="font-variant-numeric: tabular-nums">{compact(v)}</text>']
    o.append(f'<g fill="{t["bar"]}">')
    peak_at = max(range(len(months)), key=lambda i: months[i][1])
    for i, ((y_, m), n) in enumerate(months):
        cx = px0 + slot * (i + 0.5)
        if n:
            h = max(n * scale, 2)
            o.append(column(cx - bw / 2, py1 - h, bw, h, 4))
    o.append("</g>")
    for i, ((y_, m), n) in enumerate(months):
        cx = px0 + slot * (i + 0.5)
        o.append(f'<text x="{cx:.1f}" y="{py1 + 18}" font-size="11" fill="{t["muted"]}" text-anchor="middle">{MONTHS[m - 1]}</text>')
        if i == 0 or m == 1:
            o.append(f'<text x="{cx:.1f}" y="{py1 + 33}" font-size="11" fill="{t["muted"]}" text-anchor="middle">{y_}</text>')
    pn = months[peak_at][1]
    pcx = px0 + slot * (peak_at + 0.5)
    o.append(f'<text x="{pcx:.1f}" y="{py1 - pn * scale - 8:.1f}" font-size="12" font-weight="600" '
             f'fill="{t["ink"]}" text-anchor="middle">{pn:,}</text>')

    o += [f'<text x="32" y="{H - 22}" font-size="11" fill="{t["muted"]}">Includes private repositories</text>',
          "</g></svg>"]
    return "\n".join(o) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="adrian971029")
    ap.add_argument("--out", default="assets")
    ap.add_argument("--calendar", help="saved GraphQL response, instead of calling the API")
    ap.add_argument("--today", help="YYYY-MM-DD, defaults to today in UTC")
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.today) if a.today else dt.datetime.now(dt.timezone.utc).date()
    start, end = window(today)
    payload = json.load(open(a.calendar)) if a.calendar else fetch(a.user, start, end)
    s = stats(daily_counts(payload, start, end))
    os.makedirs(a.out, exist_ok=True)
    for name, theme in THEMES.items():
        with open(os.path.join(a.out, f"activity-{name}.svg"), "w") as f:
            f.write(render(s, start, end, theme))
    print(f"{start}..{end}: {s['total']} contributions, {s['active']} active days, streak {s['streak']}")


if __name__ == "__main__":
    main()
