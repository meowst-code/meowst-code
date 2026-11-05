import html
import json
import math
import os
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

USER = os.environ.get("GH_USER", "meowst-code")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = "assets/profile-card.svg"

BG, BLUE, PURPLE, TEAL, TRACK = "#1a1b27", "#7aa2f7", "#bb9af7", "#2ac3a2", "#2a2f45"
FALLBACK = ["#7aa2f7", "#bb9af7", "#2ac3a2"]


def gql(query, variables=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "profile-card",
        },
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def fmt(d):
    return f"{d.strftime('%b')} {d.day}"

created = datetime.fromisoformat(
    gql("query($u:String!){user(login:$u){createdAt}}", {"u": USER})["user"]["createdAt"].replace("Z", "+00:00")
)
CAL = """query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){contributionsCollection(from:$f,to:$t){
contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""

now = datetime.now(timezone.utc)
today = now.date()
counts = {}
start = created
while start < now:
    end = min(start + timedelta(days=364), now)
    data = gql(CAL, {"u": USER, "f": start.isoformat(), "t": end.isoformat()})
    for w in data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
        for day in w["contributionDays"]:
            k = day["date"]
            counts[k] = max(counts.get(k, 0), day["contributionCount"])
    start = end + timedelta(days=1)

total = sum(counts.values())
active = sorted(date.fromisoformat(k) for k, v in counts.items() if v > 0 and date.fromisoformat(k) <= today)

runs = []
for dt in active:
    if runs and dt - runs[-1][1] == timedelta(days=1):
        runs[-1][1] = dt
    else:
        runs.append([dt, dt])

longest = max(runs, key=lambda r: (r[1] - r[0]).days) if runs else None
current = runs[-1] if runs and runs[-1][1] >= today - timedelta(days=1) else None


def length(r):
    return (r[1] - r[0]).days + 1 if r else 0


def span(r):
    return f"{fmt(r[0])} - {fmt(r[1])}" if r else "No active streak"


first_txt = f"{fmt(active[0])} - Present" if active else "No contributions yet"

LANG = """query($u:String!){user(login:$u){repositories(first:100,ownerAffiliations:OWNER,isFork:false){nodes{
languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}}}}"""
sizes, colors = defaultdict(int), {}
for repo in gql(LANG, {"u": USER})["user"]["repositories"]["nodes"]:
    for e in repo["languages"]["edges"]:
        sizes[e["node"]["name"]] += e["size"]
        colors[e["node"]["name"]] = e["node"]["color"]

langs = sorted(sizes.items(), key=lambda x: -x[1])[:3]
lang_total = sum(sizes.values()) or 1

R = 36
C = 2 * math.pi * R
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', sans-serif"


def text(x, y, s, size, color, weight="400"):
    return (
        f'<text x="{x}" y="{y}" text-anchor="middle" font-family="{FONT}" '
        f'font-size="{size}" font-weight="{weight}" fill="{color}">{html.escape(str(s))}</text>'
    )


parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="820" height="190" viewBox="0 0 820 190">',
    f'<rect width="820" height="190" rx="10" fill="{BG}"/>',
]

for x in (210, 410, 610):
    parts.append(f'<line x1="{x}" y1="35" x2="{x}" y2="155" stroke="#3b4261" stroke-width="1"/>')

parts += [
    text(110, 86, total, 34, BLUE, "700"),
    text(110, 135, "Total Contributions", 15, BLUE),
    text(110, 157, first_txt, 12, TEAL),
]

cx = 310
parts += [
    f'<circle cx="{cx}" cy="75" r="{R}" fill="none" stroke="{BLUE}" stroke-width="6"/>',
    text(cx, 86, length(current), 30, PURPLE, "700"),
    text(cx, 135, "Current Streak", 15, PURPLE, "700"),
    text(cx, 157, span(current), 12, TEAL),
]

parts += [
    text(510, 86, length(longest), 34, BLUE, "700"),
    text(510, 135, "Longest Streak", 15, BLUE),
    text(510, 157, span(longest), 12, TEAL),
]

cx, cy = 710, 75
parts.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{TRACK}" stroke-width="7"/>')
offset = 0.0
for i, (name, size) in enumerate(langs):
    ln = size / lang_total * C
    color = colors.get(name) or FALLBACK[i % 3]
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{color}" stroke-width="7" '
        f'stroke-dasharray="{ln:.2f} {C - ln:.2f}" stroke-dashoffset="{-offset:.2f}" '
        f'transform="rotate(-90 {cx} {cy})"/>'
    )
    offset += ln

top_name = langs[0][0] if langs else "None"
top_pct = f"{round(langs[0][1] / lang_total * 100)}%" if langs else "0%"
parts += [
    text(cx, 82, top_pct, 22, PURPLE, "700"),
    text(cx, 135, "Most Used", 15, PURPLE, "700"),
    text(cx, 157, top_name, 12, TEAL),
    "</svg>",
]

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(parts))
