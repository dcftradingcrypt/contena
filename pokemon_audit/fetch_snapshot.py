from __future__ import annotations

import concurrent.futures
import csv
import hashlib
import json
import random
import re
import shutil
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from rsc_utils import decode_rsc_text, extract_json_after_key, extract_string_after_key, parse_en_timestamp, parse_ja_timestamp

BASE = Path('/mnt/data')
ROOT = BASE / 'formal_inputs' / 'formal_snapshot'
TIER_URL = 'https://op.gg/ja/pokemon-champions/tier'
EN_DETAIL_BASE = 'https://op.gg/en/pokemon-champions/pokedex/'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36',
    'Accept-Language': 'ja,en;q=0.8',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
}
JST = timezone(timedelta(hours=9))
JA_TS_RE = re.compile(r'20\d{2}年\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{2}')
RANK_RE = re.compile(r'#\s*(\d{1,3})')


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get(url: str, attempts: int = 7) -> requests.Response:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            response = requests.get(url, headers=HEADERS, timeout=90)
            if response.status_code == 200 and len(response.content) > 20_000:
                return response
            last = RuntimeError(f'HTTP {response.status_code}, {len(response.content)} bytes')
        except Exception as exc:
            last = exc
        time.sleep(min(25.0, 1.4 * (2 ** attempt)) + random.random())
    raise RuntimeError(f'fetch failed: {url}: {last}')


def parse_tier(html: str) -> tuple[str, list[dict[str, object]]]:
    soup = BeautifulSoup(html, 'lxml')
    text = soup.get_text(' ', strip=True)
    stamps = JA_TS_RE.findall(text)
    if not stamps:
        raise RuntimeError('tier timestamp not found')
    timestamp = stamps[0]
    rows_by_rank: dict[int, dict[str, object]] = {}
    for anchor in soup.find_all('a', href=True):
        href = str(anchor.get('href') or '')
        if '/ja/pokemon-champions/pokedex/' not in href:
            continue
        match = RANK_RE.search(anchor.get_text(' ', strip=True))
        if not match:
            continue
        rank = int(match.group(1))
        if rank < 1 or rank > 100:
            continue
        slug = href.rstrip('/').split('/')[-1]
        images = anchor.find_all('img')
        name_ja = ''
        image_url = ''
        for image in images:
            alt = str(image.get('alt') or '').strip()
            src = str(image.get('src') or '').strip()
            if alt and not name_ja:
                name_ja = alt
            if src and 'pokemon/images/pokemon/' in src and not image_url:
                image_url = src.replace('&amp;', '&')
        if not name_ja:
            spans = [x.get_text(' ', strip=True) for x in anchor.find_all('span')]
            candidates = [x for x in spans if x and not x.startswith('#') and x not in {'=', '↑', '↓'}]
            name_ja = candidates[0] if candidates else slug
        row = {
            'rank': rank,
            'slug': slug,
            'name_ja': name_ja,
            'detail_url_en': EN_DETAIL_BASE + slug,
            'image_url': image_url,
        }
        existing = rows_by_rank.get(rank)
        if existing and existing['slug'] != slug:
            raise RuntimeError(f'duplicate rank {rank}: {existing["slug"]} vs {slug}')
        rows_by_rank[rank] = row
    if sorted(rows_by_rank) != list(range(1, 101)):
        missing = sorted(set(range(1, 101)) - set(rows_by_rank))
        raise RuntimeError(f'top100 incomplete: {len(rows_by_rank)} rows, missing={missing}')
    return timestamp, [rows_by_rank[i] for i in range(1, 101)]


def detail_metadata(html: str) -> dict[str, object]:
    rsc = decode_rsc_text(html)
    updated_at = extract_string_after_key(rsc, 'updatedAt')
    single_detail = extract_json_after_key(rsc, 'singleDetail')
    lookup_data = extract_json_after_key(rsc, 'lookupData')
    pokemon = single_detail.get('pokemon') or {}
    lookup_pokemon = lookup_data.get('pokemon') or []
    target = next((item for item in lookup_pokemon if item.get('id') == pokemon.get('id') and item.get('form', 0) == pokemon.get('form', 0)), None)
    if target is None:
        target = next((item for item in lookup_pokemon if item.get('key') == pokemon.get('key')), None)
    return {
        'updated_at_en': updated_at,
        'pokemon_id': pokemon.get('id'),
        'pokemon_form': pokemon.get('form', 0),
        'pokemon_key': pokemon.get('key'),
        'name_en': (target or {}).get('name', ''),
        'types': '|'.join((target or {}).get('types') or []),
        'single_detail_sha256': hashlib.sha256(json.dumps(single_detail, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f'no rows for {path}')
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_attempt(attempt: int) -> dict[str, object]:
    work = BASE / 'formal_inputs' / f'.snapshot_attempt_{attempt}'
    if work.exists():
        shutil.rmtree(work)
    details_dir = work / 'raw_html' / 'details_en'
    details_dir.mkdir(parents=True, exist_ok=True)

    tier_start = get(TIER_URL)
    timestamp_ja, top100 = parse_tier(tier_start.text)
    target_dt = parse_ja_timestamp(timestamp_ja)
    (work / 'raw_html' / 'tier_start.html').write_bytes(tier_start.content)

    def fetch_one(row: dict[str, object]) -> dict[str, object]:
        rank = int(row['rank'])
        slug = str(row['slug'])
        response = get(str(row['detail_url_en']))
        metadata = detail_metadata(response.text)
        detail_dt = parse_en_timestamp(str(metadata['updated_at_en']))
        if detail_dt != target_dt:
            raise RuntimeError(f'detail timestamp mismatch rank={rank} slug={slug}: {metadata["updated_at_en"]} != {timestamp_ja}')
        filename = f'{rank:03d}_{slug}.html'
        target = details_dir / filename
        target.write_bytes(response.content)
        return {
            **row,
            **metadata,
            'snapshot_jst': timestamp_ja,
            'bytes': len(response.content),
            'sha256': sha256_bytes(response.content),
            'filename': str(target.relative_to(work)),
        }

    captures: list[dict[str, object]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetch_one, row): row for row in top100}
        for future in concurrent.futures.as_completed(futures):
            captures.append(future.result())
    captures.sort(key=lambda row: int(row['rank']))

    tier_end = get(TIER_URL)
    timestamp_end, top100_end = parse_tier(tier_end.text)
    (work / 'raw_html' / 'tier_end.html').write_bytes(tier_end.content)
    start_sig = [(row['rank'], row['slug']) for row in top100]
    end_sig = [(row['rank'], row['slug']) for row in top100_end]
    if timestamp_end != timestamp_ja or end_sig != start_sig:
        raise RuntimeError(f'tier changed during capture: start={timestamp_ja}, end={timestamp_end}, same_top100={end_sig == start_sig}')
    if len(captures) != 100:
        raise RuntimeError(f'detail capture count {len(captures)}')

    by_rank = {int(row['rank']): row for row in captures}
    top_enriched = []
    for row in top100:
        capture = by_rank[int(row['rank'])]
        top_enriched.append({
            'rank': row['rank'],
            'slug': row['slug'],
            'name_ja': row['name_ja'],
            'name_en': capture['name_en'],
            'types': capture['types'],
            'snapshot_jst': timestamp_ja,
            'tier_url': TIER_URL,
            'detail_url': row['detail_url_en'],
            'image_url': row['image_url'],
        })
    write_csv(work / 'top100.csv', top_enriched)
    write_csv(work / 'detail_capture.csv', captures)

    manifest = {
        'schema_version': 1,
        'source': 'OP.GG Pokémon Champions',
        'tier_url': TIER_URL,
        'snapshot_jst': timestamp_ja,
        'snapshot_iso_jst': target_dt.replace(tzinfo=JST).isoformat(),
        'captured_at_jst': datetime.now(JST).replace(microsecond=0).isoformat(),
        'top100_count': len(top_enriched),
        'detail_count': len(captures),
        'start_end_tier_identical': True,
        'all_detail_timestamps_match': True,
        'tier_start_sha256': sha256_bytes(tier_start.content),
        'tier_end_sha256': sha256_bytes(tier_end.content),
        'detail_bytes': sum(int(row['bytes']) for row in captures),
        'attempt': attempt,
    }
    (work / 'snapshot_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'work': work, 'manifest': manifest}


def main() -> None:
    last: Exception | None = None
    for attempt in range(1, 4):
        try:
            result = run_attempt(attempt)
            if ROOT.exists():
                shutil.rmtree(ROOT)
            result['work'].rename(ROOT)
            print(json.dumps(result['manifest'], ensure_ascii=False))
            return
        except Exception as exc:
            last = exc
            print(f'attempt {attempt} failed: {exc}', flush=True)
            time.sleep(5 * attempt)
    raise RuntimeError(f'formal snapshot failed after retries: {last}')


if __name__ == '__main__':
    main()
