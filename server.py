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
    {'url': 'https://vnexpress.net/rss/games.rss',    'name': 'VnExpress Game'},
    {'url': 'https://gamek.vn/rss',                   'name': 'GameK'},
    {'url': 'https://feeds.ign.com/ign/all',          'name': 'IGN'},
    {'url': 'https://www.pcgamer.com/rss/',           'name': 'PC Gamer'},
    {'url': 'https://www.eurogamer.net/?format=rss',  'name': 'Eurogamer'},
]

def fetch_full_content(url):
    try:
        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        return (text or '').strip()[:2000]
    except:
        return ''

def parse_source(src):
    try:
        feed = feedparser.parse(src['url'])
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
        for src in SOURCES:
            results.extend(parse_source(src))
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
