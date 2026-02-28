import json, subprocess, urllib.request, urllib.parse, datetime, xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
from pathlib import Path

CT = ZoneInfo('America/Chicago')
NOW = datetime.datetime.now(CT)
TODAY = NOW.date().isoformat()
OUT = Path('/Users/rivierehome/.openclaw/workspace/daily-update-site/index.html')


def run(cmd):
    return subprocess.check_output(cmd, text=True)


def fetch_text(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'ignore')


def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def rss_items(url, limit=5):
    xml = fetch_text(url)
    root = ET.fromstring(xml)
    items = []
    for it in root.findall('.//item')[:limit]:
        title = (it.findtext('title') or '').strip()
        link = (it.findtext('link') or '').strip()
        if title and link:
            items.append((title, link))
    return items


# --- Email privacy summary (counts only) ---
unread_count = 0
starred_count = 0
try:
    unread = json.loads(run([
        'gog','gmail','messages','search','in:inbox is:unread -category:promotions -category:updates',
        '--max','500','--account','arriviere@gmail.com','--json'
    ]))
    unread_count = len(unread.get('messages', []))
except Exception:
    pass

try:
    starred = json.loads(run([
        'gog','gmail','messages','search','in:inbox is:starred',
        '--max','500','--account','arriviere@gmail.com','--json'
    ]))
    starred_count = len(starred.get('messages', []))
except Exception:
    pass

# --- Calendar privacy summary (block map only: work/personal busy) ---
work_blocks = set()
personal_blocks = set()

# 6am-10pm CT block slots (hourly)
slots = [f'{h:02d}:00' for h in range(6, 23)]


def classify_event(e):
    text = ' '.join([
        str(e.get('calendarId','')),
        str(e.get('sourceCalendarId','')),
        str(e.get('organizer','')),
        str(e.get('summary','')),
    ]).lower()
    if 'inquirly' in text or 'affiliate' in text or 'meeting' in text or 'work' in text:
        return 'work'
    return 'personal'


def mark_blocks(start_iso, end_iso, kind):
    try:
        # Normalize rough ISO strings
        s = datetime.datetime.fromisoformat(start_iso.replace('Z', '+00:00')).astimezone(CT)
        e = datetime.datetime.fromisoformat(end_iso.replace('Z', '+00:00')).astimezone(CT)
    except Exception:
        return
    cur = s.replace(minute=0, second=0, microsecond=0)
    if e <= cur:
        e = cur + datetime.timedelta(hours=1)
    while cur < e:
        label = f'{cur.hour:02d}:00'
        if 6 <= cur.hour <= 22:
            if kind == 'work':
                work_blocks.add(label)
            else:
                personal_blocks.add(label)
        cur += datetime.timedelta(hours=1)


try:
    c = json.loads(run([
        'gog','calendar','events',
        '--from',f'{TODAY}T00:00:00-06:00',
        '--to',f'{TODAY}T23:59:59-06:00',
        '--account','arriviere@gmail.com','--json'
    ]))
    events = c.get('events', c if isinstance(c, list) else [])
    for e in events:
        kind = classify_event(e)
        # try common keys
        s = e.get('start') or e.get('startTime') or e.get('startDateTime')
        t = e.get('end') or e.get('endTime') or e.get('endDateTime')
        if s and t:
            mark_blocks(str(s), str(t), kind)
except Exception:
    pass

# --- Headlines ---
try:
    reuters = rss_items('https://feeds.reuters.com/reuters/topNews', 6)
except Exception:
    reuters = [('Reuters headlines unavailable', 'https://www.reuters.com')]

try:
    nyt = rss_items('https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml', 6)
except Exception:
    nyt = [('NYT headlines unavailable', 'https://www.nytimes.com')]

# --- Quotes of the day ---
philosophy_quote = "The happiness of your life depends upon the quality of your thoughts. — Marcus Aurelius"
biblical_quote = "Be strong and courageous. Do not be afraid; do not be discouraged, for the Lord your God will be with you wherever you go. — Joshua 1:9"
science_quote = "Somewhere, something incredible is waiting to be known. — Carl Sagan"

try:
    q = fetch_json('https://zenquotes.io/api/random')
    if isinstance(q, list) and q:
        philosophy_quote = f"{q[0].get('q','')} — {q[0].get('a','')}"
except Exception:
    pass

# --- APOD + JWST + fact ---
apod = {'title':'Astronomy Picture of the Day','url':'','image':'','desc':''}
try:
    a = fetch_json('https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY')
    apod = {
        'title': a.get('title','APOD'),
        'url': a.get('url',''),
        'image': a.get('hdurl') or a.get('url') or '',
        'desc': (a.get('explanation','')[:380] + '...') if len(a.get('explanation','')) > 380 else a.get('explanation','')
    }
except Exception:
    pass

jwst = {'title':'James Webb Space Telescope image','url':'','image':''}
try:
    q = urllib.parse.quote('James Webb Space Telescope')
    d = fetch_json(f'https://images-api.nasa.gov/search?q={q}&media_type=image')
    items = d.get('collection',{}).get('items',[])
    if items:
        it = items[0]
        jwst['title'] = it.get('data',[{}])[0].get('title','JWST Image')
        jwst['url'] = it.get('href','')
        if it.get('links'):
            jwst['image'] = it['links'][0].get('href','')
except Exception:
    pass

fact = 'Octopuses have three hearts and blue blood.'
try:
    f = fetch_json('https://uselessfacts.jsph.pl/api/v2/facts/random?language=en')
    fact = f.get('text', fact)
except Exception:
    pass

# TV update
tv = []
try:
    s = fetch_json('https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId=112&date=' + TODAY + '&hydrate=broadcasts(all)')
    for d in s.get('dates',[]):
        for g in d.get('games',[]):
            away = g.get('teams',{}).get('away',{}).get('team',{}).get('name','')
            home = g.get('teams',{}).get('home',{}).get('team',{}).get('name','')
            dt = g.get('gameDate','')
            bcasts = g.get('broadcasts',[])
            channels = sorted({b.get('name','') for b in bcasts if b.get('name')})
            tv.append(f"{away} @ {home} — {dt} — {', '.join(channels) if channels else 'TV TBD'}")
    if not tv:
        tv = ['No Cubs game on today.']
except Exception:
    tv = ['TV data unavailable right now.']


def render_headlines(items):
    return ''.join(f"<li><a href='{u}' target='_blank' rel='noreferrer'>{t}</a></li>" for t, u in items)


def render_blocks():
    rows = []
    for s in slots:
        state = []
        if s in work_blocks:
            state.append('<span class="pill work">Work busy</span>')
        if s in personal_blocks:
            state.append('<span class="pill personal">Personal busy</span>')
        if not state:
            state = ['<span class="pill free">Open</span>']
        rows.append(f"<tr><td>{s}</td><td>{' '.join(state)}</td></tr>")
    return ''.join(rows)


html = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Daily Update</title>
<style>
body{{font-family:Inter,Arial,sans-serif;background:#0f1220;color:#eef2ff;margin:0}} .wrap{{max-width:1100px;margin:0 auto;padding:20px}}
.card{{background:#171b2f;border:1px solid #2a3159;border-radius:12px;padding:14px;margin:12px 0}}
h1{{margin:0 0 8px}} h2{{margin:0 0 10px;color:#8cc6ff}} a{{color:#9bd2ff}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}} table{{width:100%;border-collapse:collapse}} th,td{{border:1px solid #2e365f;padding:8px;font-size:13px;text-align:left}}
.small{{color:#a6b2da;font-size:12px}} .pill{{display:inline-block;padding:3px 8px;border-radius:999px;font-size:11px;margin-right:6px}}
.work{{background:#244f88}} .personal{{background:#7b3f7c}} .free{{background:#38405e}}
@media (max-width:900px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><div class='wrap'>
<h1>Daily Update (Privacy Mode)</h1>
<div class='small'>Updated: {NOW.strftime('%Y-%m-%d %I:%M %p CT')} · Sensitive details intentionally hidden</div>

<div class='card'>
  <h2>📬 Email Snapshot (Counts Only)</h2>
  <p><b>Unread emails:</b> {unread_count}</p>
  <p><b>Starred emails:</b> {starred_count}</p>
</div>

<div class='card'>
  <h2>🗓️ Daily Schedule Blocks (No event details)</h2>
  <table><thead><tr><th>Time (CT)</th><th>Status</th></tr></thead><tbody>{render_blocks()}</tbody></table>
</div>

<div class='grid'>
  <div class='card'><h2>📰 Reuters Headlines</h2><ul>{render_headlines(reuters)}</ul></div>
  <div class='card'><h2>🗞️ NYT Headlines</h2><ul>{render_headlines(nyt)}</ul></div>
</div>

<div class='card'><h2>📺 TV Update</h2><ul>{''.join(f'<li>{x}</li>' for x in tv)}</ul></div>

<div class='grid'>
  <div class='card'><h2>🔭 Astronomy Picture of the Day</h2><p><b>{apod['title']}</b></p>{f"<img src='{apod['image']}' style='max-width:100%;border-radius:8px'>" if apod['image'] else ''}<p>{apod['desc']}</p>{f"<a href='{apod['url']}' target='_blank'>Open source</a>" if apod['url'] else ''}</div>
  <div class='card'><h2>✨ James Webb Pick</h2><p><b>{jwst['title']}</b></p>{f"<img src='{jwst['image']}' style='max-width:100%;border-radius:8px'>" if jwst['image'] else ''}{f"<p><a href='{jwst['url']}' target='_blank'>NASA collection</a></p>" if jwst['url'] else ''}</div>
</div>

<div class='grid'>
  <div class='card'><h2>🧭 Philosophy Quote of the Day</h2><p>{philosophy_quote}</p></div>
  <div class='card'><h2>✝️ Biblical Quote of the Day</h2><p>{biblical_quote}</p></div>
</div>
<div class='card'><h2>🔬 Science Quote of the Day</h2><p>{science_quote}</p></div>
<div class='card'><h2>🧠 Cool Fact of the Day</h2><p>{fact}</p></div>
</div></body></html>"""

OUT.write_text(html)
print(str(OUT))
