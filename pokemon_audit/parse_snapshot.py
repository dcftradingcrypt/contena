from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from rsc_utils import decode_rsc_text, extract_json_after_key, extract_string_after_key

BASE = Path('/mnt/data')
ROOT = BASE / 'formal_inputs' / 'formal_snapshot'
OUT = BASE / 'formal_parsed'
OUT.mkdir(parents=True, exist_ok=True)

MOVE_USAGE_THRESHOLD = 5.0
WIN_MOVE_THRESHOLD = 1.0
OTHER_THRESHOLD = 5.0


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def index_by_id(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(row['id']): row for row in rows if row.get('id') is not None}


def spread_points(value: str) -> list[int]:
    parts = value.split('-')
    if len(parts) != 6:
        raise ValueError(f'invalid training spread {value}')
    points = [int(part, 16) for part in parts]
    if any(point < 0 or point > 32 for point in points):
        raise ValueError(f'invalid point value in {value}: {points}')
    if sum(points) > 66:
        raise ValueError(f'training point sum exceeds 66: {value}: {points}')
    return points


def main() -> None:
    manifest = json.loads((ROOT / 'snapshot_manifest.json').read_text(encoding='utf-8'))
    top100 = read_csv(ROOT / 'top100.csv')
    if len(top100) != 100:
        raise RuntimeError(f'top100 count {len(top100)}')

    all_components: list[dict[str, Any]] = []
    opponents: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []

    for top in top100:
        rank = int(top['rank'])
        slug = top['slug']
        html_path = ROOT / 'raw_html' / 'details_en' / f'{rank:03d}_{slug}.html'
        html = html_path.read_text(encoding='utf-8')
        rsc = decode_rsc_text(html)
        updated_at = extract_string_after_key(rsc, 'updatedAt')
        detail = extract_json_after_key(rsc, 'singleDetail')
        lookup = extract_json_after_key(rsc, 'lookupData')
        moves = index_by_id(lookup.get('moves') or [])
        abilities = index_by_id(lookup.get('abilities') or [])
        items = index_by_id(lookup.get('items') or [])
        natures = index_by_id(lookup.get('natures') or [])
        pokemon_rows = lookup.get('pokemon') or []
        target = next((row for row in pokemon_rows if row.get('id') == detail.get('pokemon', {}).get('id') and row.get('form', 0) == detail.get('pokemon', {}).get('form', 0)), None) or next((row for row in pokemon_rows if row.get('key') == slug), None)
        name_en = (target or {}).get('name') or top.get('name_en') or slug
        types = (target or {}).get('types') or [x for x in top.get('types', '').split('|') if x]

        normal_move = {int(row['id']): float(row.get('usagePercent') or 0) for row in detail.get('moves') or []}
        win_move = {int(row['id']): float(row.get('usagePercent') or 0) for row in (detail.get('win') or {}).get('moves') or []}
        move_ids = sorted(set(normal_move) | set(win_move), key=lambda mid: (-normal_move.get(mid, 0), -win_move.get(mid, 0), mid))
        move_components: list[dict[str, Any]] = []
        for component_rank, move_id in enumerate(move_ids, 1):
            meta = moves.get(move_id)
            if meta is None:
                raise RuntimeError(f'move lookup missing rank={rank} slug={slug} id={move_id}')
            usage = normal_move.get(move_id, 0.0)
            win_usage = win_move.get(move_id, 0.0)
            selected = usage >= MOVE_USAGE_THRESHOLD or win_usage >= WIN_MOVE_THRESHOLD
            row = {
                'opponent_rank': rank, 'slug': slug, 'pokemon_ja': top['name_ja'], 'pokemon_en': name_en,
                'snapshot_jst': manifest['snapshot_jst'], 'category': 'move', 'component_rank': component_rank,
                'component_id': move_id, 'name': meta['name'], 'key': meta.get('key', ''),
                'usage_percent': usage, 'winning_usage_percent': win_usage, 'selected_by_threshold': selected,
                'type': meta.get('type', ''), 'move_category': meta.get('category', ''), 'power': meta.get('power', ''),
                'accuracy': meta.get('accuracy', ''), 'priority': meta.get('priority', 0), 'spread': '',
                'hp_points': '', 'attack_points': '', 'defense_points': '', 'sp_atk_points': '', 'sp_def_points': '', 'speed_points': '',
                'source_file': str(html_path.relative_to(BASE)), 'source_url': top['detail_url'],
            }
            move_components.append(row)
            all_components.append(row)

        category_specs = [
            ('held_item', detail.get('items') or [], items),
            ('ability', detail.get('abilities') or [], abilities),
            ('stat_alignment', detail.get('natures') or [], natures),
        ]
        grouped: dict[str, list[dict[str, Any]]] = {'move': move_components}
        for category, source_rows, lookup_index in category_specs:
            component_rows: list[dict[str, Any]] = []
            for component_rank, source in enumerate(source_rows, 1):
                component_id = int(source['id'])
                meta = lookup_index.get(component_id)
                if meta is None:
                    raise RuntimeError(f'{category} lookup missing rank={rank} id={component_id}')
                usage = float(source.get('usagePercent') or 0)
                row = {
                    'opponent_rank': rank, 'slug': slug, 'pokemon_ja': top['name_ja'], 'pokemon_en': name_en,
                    'snapshot_jst': manifest['snapshot_jst'], 'category': category, 'component_rank': component_rank,
                    'component_id': component_id, 'name': meta['name'], 'key': meta.get('key', ''),
                    'usage_percent': usage, 'winning_usage_percent': '', 'selected_by_threshold': usage >= OTHER_THRESHOLD,
                    'type': '', 'move_category': '', 'power': '', 'accuracy': '', 'priority': '', 'spread': '',
                    'hp_points': '', 'attack_points': '', 'defense_points': '', 'sp_atk_points': '', 'sp_def_points': '', 'speed_points': '',
                    'source_file': str(html_path.relative_to(BASE)), 'source_url': top['detail_url'],
                }
                component_rows.append(row)
                all_components.append(row)
            grouped[category] = component_rows

        training_components: list[dict[str, Any]] = []
        for component_rank, source in enumerate(detail.get('training') or [], 1):
            spread = str(source['spread'])
            points = spread_points(spread)
            usage = float(source.get('usagePercent') or 0)
            row = {
                'opponent_rank': rank, 'slug': slug, 'pokemon_ja': top['name_ja'], 'pokemon_en': name_en,
                'snapshot_jst': manifest['snapshot_jst'], 'category': 'stat_points', 'component_rank': component_rank,
                'component_id': spread, 'name': '', 'key': '', 'usage_percent': usage, 'winning_usage_percent': '',
                'selected_by_threshold': usage >= OTHER_THRESHOLD, 'type': '', 'move_category': '', 'power': '',
                'accuracy': '', 'priority': '', 'spread': spread,
                'hp_points': points[0], 'attack_points': points[1], 'defense_points': points[2],
                'sp_atk_points': points[3], 'sp_def_points': points[4], 'speed_points': points[5],
                'source_file': str(html_path.relative_to(BASE)), 'source_url': top['detail_url'],
            }
            training_components.append(row)
            all_components.append(row)
        grouped['stat_points'] = training_components

        top_four = sorted(move_components, key=lambda row: (-float(row['usage_percent']), int(row['component_rank'])))[:4]
        if len(top_four) != 4:
            raise RuntimeError(f'less than four moves for rank={rank} {slug}')
        if any(not bool(row['selected_by_threshold']) for row in top_four):
            raise RuntimeError(f'top-four move under threshold for rank={rank} {slug}: {top_four}')
        selected_parts: dict[str, dict[str, Any]] = {}
        for category in ['held_item', 'ability', 'stat_alignment', 'stat_points']:
            eligible = [row for row in grouped[category] if bool(row['selected_by_threshold'])]
            if not eligible:
                raise RuntimeError(f'no threshold-passing {category} for rank={rank} {slug}')
            selected_parts[category] = sorted(eligible, key=lambda row: (-float(row['usage_percent']), int(row['component_rank'])))[0]
        opponent = {
            'rank': rank, 'slug': slug, 'pokemon_id': detail.get('pokemon', {}).get('id'),
            'pokemon_form': detail.get('pokemon', {}).get('form', 0), 'pokemon_key': detail.get('pokemon', {}).get('key'),
            'pokemon_ja': top['name_ja'], 'pokemon_en': name_en, 'types': types, 'updated_at_en': updated_at,
            'snapshot_jst': manifest['snapshot_jst'], 'detail_url': top['detail_url'], 'source_file': str(html_path.relative_to(BASE)),
            'moves': [row['name'] for row in top_four], 'move_usage': [row['usage_percent'] for row in top_four],
            'eligible_attack_moves': [row['name'] for row in move_components if bool(row['selected_by_threshold']) and row['move_category'] != 'status'],
            'item': selected_parts['held_item']['name'], 'item_usage_percent': selected_parts['held_item']['usage_percent'],
            'ability': selected_parts['ability']['name'], 'ability_usage_percent': selected_parts['ability']['usage_percent'],
            'nature': selected_parts['stat_alignment']['name'], 'nature_usage_percent': selected_parts['stat_alignment']['usage_percent'],
            'spread': selected_parts['stat_points']['spread'], 'spread_usage_percent': selected_parts['stat_points']['usage_percent'],
            'hp_points': selected_parts['stat_points']['hp_points'], 'attack_points': selected_parts['stat_points']['attack_points'],
            'defense_points': selected_parts['stat_points']['defense_points'], 'sp_atk_points': selected_parts['stat_points']['sp_atk_points'],
            'sp_def_points': selected_parts['stat_points']['sp_def_points'], 'speed_points': selected_parts['stat_points']['speed_points'],
            'mega_usage': (detail.get('mega') or {}).get('use') or [], 'evidence_type': 'current_most_frequent_completion',
        }
        opponents.append(opponent)
        diagnostics.append({
            'rank': rank, 'slug': slug, 'move_count': len(move_components),
            'selected_move_count': sum(bool(row['selected_by_threshold']) for row in move_components),
            'item_count': len(grouped['held_item']), 'ability_count': len(grouped['ability']),
            'nature_count': len(grouped['stat_alignment']), 'spread_count': len(grouped['stat_points']),
            'fixed_moves': ' | '.join(opponent['moves']), 'fixed_item': opponent['item'],
            'fixed_ability': opponent['ability'], 'fixed_nature': opponent['nature'], 'fixed_spread': opponent['spread'],
        })

    if len(opponents) != 100 or {row['rank'] for row in opponents} != set(range(1, 101)):
        raise RuntimeError('opponent parse is not exactly ranks 1..100')
    write_csv(OUT / 'component_evidence.csv', all_components)
    write_csv(OUT / 'parse_diagnostics.csv', diagnostics)
    (OUT / 'opponent_usage.json').write_text(json.dumps({
        'schema_version': 1, 'snapshot_jst': manifest['snapshot_jst'],
        'thresholds': {'move_usage_percent': MOVE_USAGE_THRESHOLD, 'winning_move_percent': WIN_MOVE_THRESHOLD, 'item_ability_nature_spread_percent': OTHER_THRESHOLD},
        'opponents': opponents,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'opponents': len(opponents), 'components': len(all_components), 'snapshot_jst': manifest['snapshot_jst']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
