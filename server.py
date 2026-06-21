from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import feedparser
import trafilatura
import concurrent.futures
import os
import requests as req_lib

app = Flask(__name__, static_folder='.')
CORS(app)

@app.route('/')
def index():
    return send_from_directory('.', 'app.html')

SOURCES = [
    # Tiếng Việt
    {'url': 'https://vnexpress.net/rss/games.rss',                        'name': 'VnExpress Game',  'lang': 'vi'},
    {'url': 'https://gamek.vn/rss',                                       'name': 'GameK',           'lang': 'vi'},
    # Tiếng Anh
    {'url': 'https://feeds.ign.com/ign/all',                              'name': 'IGN',             'lang': 'en'},
    {'url': 'https://www.pcgamer.com/rss/',                               'name': 'PC Gamer',        'lang': 'en'},
    {'url': 'https://www.eurogamer.net/?format=rss',                      'name': 'Eurogamer',       'lang': 'en'},
    {'url': 'https://www.gamespot.com/feeds/mashup/',                     'name': 'GameSpot',        'lang': 'en'},
    {'url': 'https://www.rockpapershotgun.com/feed',                      'name': 'Rock Paper Shotgun', 'lang': 'en'},
    {'url': 'https://www.polygon.com/rss/index.xml',                      'name': 'Polygon',         'lang': 'en'},
    {'url': 'https://kotaku.com/rss',                                     'name': 'Kotaku',          'lang': 'en'},
    {'url': 'https://www.vg247.com/feed',                                 'name': 'VG247',           'lang': 'en'},
    {'url': 'https://www.gamesradar.com/feeds/articletype/news/',         'name': 'GamesRadar',      'lang': 'en'},
]

def fetch_full_content(url):
    try:
        downloaded = trafilatura.fetch_url(url, timeout=10)
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        return (text or '').strip()[:2000]
    except:
        return ''

def parse_source(src):
    try:
        feed = feedparser.parse(src['url'], agent='Mozilla/5.0', request_headers={'Connection': 'close'})
        items = []
        for e in feed.entries[:10]:
            thumb = ''
            if hasattr(e, 'media_thumbnail') and e.media_thumbnail:
                thumb = e.media_thumbnail[0].get('url', '')
            elif hasattr(e, 'enclosures') and e.enclosures:
                thumb = e.enclosures[0].get('href', '')
            items.append({
                'title':       e.get('title', ''),
                'link':        e.get('link', ''),
                'description': e.get('summary', '')[:300],
                'pubDate':     e.get('published', ''),
                'thumbnail':   thumb,
                'source':      src['name'],
                'lang':        src.get('lang', 'en'),
                'content':     '',
            })

        # lấy nội dung đầy đủ song song
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            links   = [i['link'] for i in items]
            results = list(ex.map(fetch_full_content, links))
        for i, content in enumerate(results):
            items[i]['content'] = content

        return items
    except Exception as ex:
        print(f"Lỗi {src['name']}: {ex}")
        return []

@app.route('/news')
def get_all():
    src_name = request.args.get('source', 'all')
    results = []

    if src_name == 'all':
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            futures = {ex.submit(parse_source, src): src for src in SOURCES}
            for future in concurrent.futures.as_completed(futures, timeout=30):
                try:
                    results.extend(future.result())
                except Exception as e:
                    print(f"Lỗi nguồn {futures[future]['name']}: {e}")
    else:
        src = next((s for s in SOURCES if s['name'] == src_name), None)
        if src:
            results = parse_source(src)

    # bỏ trùng tiêu đề
    seen = set()
    unique = []
    for item in results:
        key = item['title'][:40].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return jsonify({'items': unique, 'total': len(unique)})

@app.route('/sources')
def get_sources():
    return jsonify([s['name'] for s in SOURCES])

@app.route('/ping')
def ping():
    return jsonify({'status': 'ok'})

@app.route('/proxy/anthropic', methods=['POST'])
def proxy_anthropic():
    key = os.environ.get('ANTHROPIC_KEY', '')
    r = req_lib.post('https://api.anthropic.com/v1/messages',
        headers={'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
        json=request.get_json())
    return jsonify(r.json()), r.status_code

@app.route('/proxy/pexels')
def proxy_pexels():
    key = os.environ.get('PEXELS_KEY', '')
    q   = request.args.get('query', '')
    r   = req_lib.get(f'https://api.pexels.com/v1/search?query={q}&per_page=6',
        headers={'Authorization': key})
    return jsonify(r.json()), r.status_code

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
