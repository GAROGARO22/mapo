"""MAPZI background worker (runs on GitHub Actions schedule).

1) Pulls the map data from its link every run (default: every 15 min; change CRON in workflow).
2) Appends each detected change to today's "history file" -> history.json in this repo.
   At end of day, today's entry already contains ALL updates of that day (requirement #2).
3) The frontend reads history.json and shows the latest saved snapshot by default.
4) Time-machine navigation is done client-side over these daily files.
"""
import json, os, re, sys, urllib.request, datetime

MID = '1NZygQ5FhCvHG3ZH6Ddk3lbzAwnJum8M'
KML_URL = f'https://www.google.com/maps/d/kml?mid={MID}&forcekml=1'
EMBED_URL = f'https://www.google.com/maps/d/embed?mid={MID}&ehbc=2E312F'
REPO = os.environ.get('GITHUB_REPOSITORY', 'GAROGARO22/mapzi-archive')
TOKEN = os.environ['MAPZI_PAT']
BRANCH = 'main'
FILE = 'history.json'


def gh_get(path):
    req = urllib.request.Request(f'https://api.github.com/repos/{REPO}/contents/{path}?ref={BRANCH}',
                                 headers={'Authorization': f'Bearer {TOKEN}', 'Accept': 'application/vnd.github+json'})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def gh_put(path, data, message):
    cur = gh_get(path)
    body = {'message': message, 'branch': BRANCH,
            'content': __import__('base64').b64encode(json.dumps(data, ensure_ascii=False).encode()).decode()}
    if cur: body['sha'] = cur['sha']
    req = urllib.request.Request(f'https://api.github.com/repos/{REPO}/contents/{path}', method='PUT',
                                 data=json.dumps(body).encode(),
                                 headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json',
                                          'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req) as r:
        return r.status in (200, 201)


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; MapziWorker/1.0)'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode('utf-8', 'ignore')


def signature():
    """Extract place names + coordinates as a stable fingerprint."""
    try:
        t = fetch(KML_URL)
        names = sorted(re.findall(r'<name>([^<]{1,120})</name>', t))
        coords = sorted({c.strip() for c in re.findall(r'<coordinates>([^<]+)</coordinates>', t)})
        if names or coords:
            import hashlib
            blob = ';'.join(names) + '##' + '|'.join(coords)
            return hashlib.sha256(blob.encode()).hexdigest()[:16], len(names), names[:50]
    except Exception as e:
        print('KML failed:', e, file=sys.stderr)
    try:
        t = fetch(EMBED_URL)
        titles = sorted(set(re.findall(r'"title":"([^"]{1,120})"', t)))
        if titles:
            import hashlib
            return hashlib.sha256(';'.join(titles).encode()).hexdigest()[:16], len(titles), titles[:50]
    except Exception as e:
        print('Embed failed:', e, file=sys.stderr)
    return None, 0, []


def main():
    hist = gh_get(FILE)
    history = json.loads(__import__('base64').b64decode(hist['content']).decode()) if hist else {}
    sig, count, places = signature()
    if not sig:
        print('Could not read map — will retry next run.')
        return
    today = datetime.date.today().isoformat()
    day = history.get(today) or {'updates': [], 'latest': None, 'places': []}
    changed = day['latest'] != sig
    if changed:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        day['updates'].append({'t': now, 'sig': sig, 'count': count})
        if len(day['updates']) > 1000: day['updates'] = day['updates'][-1000:]
        day['latest'] = sig
        day['places'] = places
        history[today] = day
        # prune history older than 180 days
        cutoff = (datetime.date.today() - datetime.timedelta(days=180)).isoformat()
        for k in list(history.keys()):
            if k < cutoff: del history[k]
        ok = gh_put(FILE, history, f'history sync {today} ({len(day["updates"])} updates)')
        print('changed:', changed, 'saved:', ok, 'places:', count)
    else:
        print('no change. sig=', sig)


if __name__ == '__main__':
    main()
