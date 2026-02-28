import json, subprocess, urllib.request, urllib.parse, datetime, hashlib, xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
from pathlib import Path

CT = ZoneInfo('America/Chicago')
TODAY = datetime.datetime.now(CT).date().isoformat()
PIN = '0000'  # TODO: replace with Andy's chosen 4-digit PIN
PIN_HASH = hashlib.sha256(PIN.encode()).hexdigest()
OUT = Path('/Users/rivierehome/.openclaw/workspace/daily-update-site/index.html')


def sh(cmd):
    return subprocess.check_output(cmd, text=True).strip()


def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_text(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'ignore')


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


# Private summary (Gmail + Calendar)
calendar_summary = []
email_summary = []
try:
    c_raw = sh([
        'gog','calendar','events','--from',f'{TODAY}T00:00:00-06:00','--to',f'{TODAY}T23:59:59-06:00',
        '--account','arriviere@gmail.com','--json'
    ])
    c = json.loads(c_raw)
    events = c.get('events', c if isinstance(c, list) else [])
    for e in events[:12]:
        title = e.get('summary') or '(No title)'
        start = e.get('start') or e.get('startTime') or ''
        calendar_summary.append(f"{start} — {title}")
except Exception as ex:
    calendar_summary = [f'Calendar fetch failed: {ex}']

try:
    g_raw = sh(['gog','gmail','messages','search','in:inbox is:unread -category:promotions -category:updates','--max','10','--account','arriviere@gmail.com','--json'])
    g = json.loads(g_raw)
    msgs = g.get('messages', [])
    for m in msgs[:8]:
        email_summary.append(f"{m.get('date','')} — {m.get('from','')} — {m.get('subject','')}")
    if not email_summary:
        email_summary = ['No unread important/personal inbox items found.']
except Exception as ex:
    email_summary = [f'Gmail fetch failed: {ex}']

# Headlines
try:
    reuters = rss_items('https://feeds.reuters.com/reuters/topNews', 5)
except Exception:
    reuters = [('Reuters headlines unavailable right now','https://www.reuters.com')]

try:
    nyt = rss_items('https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml', 5)
except Exception:
    nyt = [('NYT headlines unavailable right now','https://www.nytimes.com')]

# APOD
apod = {'title': 'Astronomy Picture of the Day', 'url': '', 'image': '', 'desc': ''}
try:
    a = fetch_json('https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY')
    apod = {
        'title': a.get('title','APOD'),
        'url': a.get('url',''),
        'image': a.get('hdurl') or a.get('url') or '',
        'desc': a.get('explanation','')[:500] + ('...' if len(a.get('explanation',''))>500 else '')
    }
except Exception:
    pass

# JWST image (NASA Images API)
jwst = {'title':'James Webb Space Telescope image','url':'','image':''}
try:
    q = urllib.parse.quote('James Webb Space Telescope')
    d = fetch_json(f'https://images-api.nasa.gov/search?q={q}&media_type=image')
    items = d.get('collection',{}).get('items',[])
    if items:
        first = items[0]
        title = first.get('data',[{}])[0].get('title','JWST Image')
        page = first.get('href','')
        image = ''
        if first.get('links'):
            image = first['links'][0].get('href','')
        jwst = {'title':title,'url':page,'image':image}
except Exception:
    pass

# Cool fact
fact = 'Honey never spoils. Archaeologists have found edible honey in ancient tombs.'
try:
    f = fetch_json('https://uselessfacts.jsph.pl/api/v2/facts/random?language=en')
    fact = f.get('text', fact)
except Exception:
    pass

# TV update (Cubs game + national games glimpse)
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
except Exception as ex:
    tv = [f'TV fetch failed: {ex}']


def li(lines):
    return ''.join(f'<li>{x}</li>' for x in lines)

def links(items):
    return ''.join(f"<li><a href='{u}' target='_blank' rel='noreferrer'>{t}</a></li>" for t,u in items)

html = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Daily Update</title>
<style>
body{{font-family:Inter,Arial,sans-serif;background:#0f1220;color:#eef2ff;margin:0}} .wrap{{max-width:1050px;margin:0 auto;padding:20px}}
.card{{background:#171b2f;border:1px solid #2a3159;border-radius:12px;padding:14px;margin:12px 0}}
h1{{margin:0 0 8px}} h2{{margin:0 0 10px;color:#8cc6ff}} a{{color:#9bd2ff}} .grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.pin{{display:flex;gap:8px;align-items:center}} input{{padding:8px;border-radius:8px;border:1px solid #3a4478;background:#10162b;color:#fff}}
button{{padding:8px 12px;border-radius:8px;border:none;background:#2e6dff;color:white;cursor:pointer}}
.small{{color:#a6b2da;font-size:12px}}
@media (max-width:900px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><div class='wrap'>
<h1>Daily Update</h1><div class='small'>Updated: {datetime.datetime.now(CT).strftime('%Y-%m-%d %I:%M %p CT')}</div>

<div class='card'>
<h2>🔒 Private Brief (Email + Calendar)</h2>
<div class='pin'><input id='pin' maxlength='4' placeholder='Enter 4-digit PIN'><button onclick='unlock()'>Unlock</button></div>
<div id='private' style='display:none'>
  <h3>Calendar Summary</h3><ul>{li(calendar_summary)}</ul>
  <h3>Email Summary</h3><ul>{li(email_summary)}</ul>
</div>
<div id='pinmsg' class='small'></div>
</div>

<div class='grid'>
  <div class='card'><h2>📰 Reuters Headlines</h2><ul>{links(reuters)}</ul></div>
  <div class='card'><h2>🗞️ NYT Headlines</h2><ul>{links(nyt)}</ul></div>
</div>

<div class='card'><h2>📺 TV Update</h2><ul>{li(tv)}</ul></div>

<div class='grid'>
  <div class='card'><h2>🔭 Astronomy Picture of the Day</h2><p><b>{apod['title']}</b></p>{f"<img src='{apod['image']}' style='max-width:100%;border-radius:8px'>" if apod['image'] else ''}<p>{apod['desc']}</p>{f"<a href='{apod['url']}' target='_blank'>Open source</a>" if apod['url'] else ''}</div>
  <div class='card'><h2>✨ James Webb Pick</h2><p><b>{jwst['title']}</b></p>{f"<img src='{jwst['image']}' style='max-width:100%;border-radius:8px'>" if jwst['image'] else ''}{f"<p><a href='{jwst['url']}' target='_blank'>NASA collection</a></p>" if jwst['url'] else ''}</div>
</div>

<div class='card'><h2>🧠 Cool Fact of the Day</h2><p>{fact}</p></div>

</div>
<script>
const PIN_HASH = '{PIN_HASH}';
async function sha256(text){{
  const data = new TextEncoder().encode(text);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2,'0')).join('');
}}
async function unlock(){{
  const v = document.getElementById('pin').value.trim();
  const h = await sha256(v);
  if(h === PIN_HASH){{
    document.getElementById('private').style.display='block';
    document.getElementById('pinmsg').innerText='Unlocked';
  }} else {{
    document.getElementById('pinmsg').innerText='Wrong PIN';
  }}
}}
</script></body></html>"""

OUT.write_text(html)
print(str(OUT))
