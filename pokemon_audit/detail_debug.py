from __future__ import annotations

import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUT = Path('out')
OUT.mkdir(exist_ok=True)
URLS = {
    'ja': 'https://op.gg/ja/pokemon-champions/pokedex/garchomp',
    'en': 'https://op.gg/en/pokemon-champions/pokedex/garchomp',
}
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36',
    'Accept-Language': 'en,ja;q=0.7',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
}

for lang, url in URLS.items():
    r = requests.get(url, headers=HEADERS, timeout=90)
    r.raise_for_status()
    (OUT / f'garchomp_{lang}.html').write_bytes(r.content)
    soup = BeautifulSoup(r.text, 'lxml')
    tables = []
    for idx, table in enumerate(soup.find_all('table')):
        headings = []
        for prev in table.find_all_previous(['h1','h2','h3','h4','h5','h6','strong'], limit=8):
            txt = prev.get_text(' ', strip=True)
            if txt and txt not in headings:
                headings.append(txt)
        rows = []
        for tr in table.find_all('tr')[:12]:
            cells = [x.get_text(' ', strip=True) for x in tr.find_all(['th','td'])]
            alts = [img.get('alt','') for img in tr.find_all('img')]
            hrefs = [a.get('href','') for a in tr.find_all('a', href=True)]
            if cells or alts or hrefs:
                rows.append({'cells': cells, 'alts': alts, 'hrefs': hrefs})
        tables.append({'index': idx, 'headings': headings, 'rows': rows, 'html_prefix': str(table)[:3000]})
    text = soup.get_text(' ', strip=True)
    report = {
        'url': url,
        'status': r.status_code,
        'bytes': len(r.content),
        'title': soup.title.get_text(' ', strip=True) if soup.title else '',
        'tables': tables,
        'table_count': len(tables),
        'timestamps': re.findall(r'20\d{2}[/-]\d{1,2}[/-]\d{1,2}[^0-9]{0,10}\d{1,2}:\d{2}', text)[:20],
        'text_excerpt': text[0:20000],
    }
    (OUT / f'garchomp_{lang}_debug.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(lang, r.status_code, len(r.content), len(tables))
