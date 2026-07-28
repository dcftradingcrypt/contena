from __future__ import annotations

import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUT = Path('out')
OUT.mkdir(exist_ok=True)
URL = 'https://op.gg/ja/pokemon-champions/tier'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36',
    'Accept-Language': 'ja,en;q=0.7',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
}

r = requests.get(URL, headers=HEADERS, timeout=90)
r.raise_for_status()
(OUT / 'tier.html').write_bytes(r.content)

soup = BeautifulSoup(r.text, 'lxml')
anchors = []
for a in soup.find_all('a', href=True):
    href = str(a.get('href'))
    if '/pokemon-champions/pokedex/' not in href:
        continue
    text = a.get_text(' ', strip=True)
    alts = [str(img.get('alt', '')).strip() for img in a.find_all('img')]
    anchors.append({'href': href, 'text': text, 'alts': alts, 'html': str(a)[:1000]})

text = soup.get_text(' ', strip=True)
timestamps = re.findall(r'2026[^\n]{0,80}?\d{1,2}:\d{2}', text)
summary = {
    'status': r.status_code,
    'bytes': len(r.content),
    'title': soup.title.get_text(' ', strip=True) if soup.title else '',
    'anchor_count': len(anchors),
    'anchors_first_120': anchors[:120],
    'timestamps': timestamps[:20],
    'text_prefix': text[:5000],
}
(OUT / 'debug.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': r.status_code, 'bytes': len(r.content), 'anchor_count': len(anchors), 'timestamps': timestamps[:5]}, ensure_ascii=False))
