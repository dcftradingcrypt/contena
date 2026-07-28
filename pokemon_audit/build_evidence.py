from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import Any

BASE = Path('/mnt/data')
PARSED = BASE / 'formal_parsed'
OUT = BASE / 'formal_audit_data'
OUT.mkdir(parents=True, exist_ok=True)
BATTLE_REPO = BASE / 'battledata_repo'


def idnorm(value: str) -> str:
    value = unicodedata.normalize('NFKC', str(value)).lower()
    return re.sub(r'[^a-z0-9]+', '', value)


def add_key(index: dict[str, tuple[Path, dict[str, Any]]], key: Any, value: tuple[Path, dict[str, Any]]) -> None:
    if key is None:
        return
    normalized = idnorm(str(key))
    if normalized:
        index.setdefault(normalized, value)


def build_index() -> tuple[dict[str, tuple[Path, dict[str, Any]]], dict[str, str]]:
    index: dict[str, tuple[Path, dict[str, Any]]] = {}
    root = BATTLE_REPO / 'data' / 'api' / 'pokemon'
    if not root.exists():
        raise FileNotFoundError(root)
    for path in root.glob('*.json'):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        value = (path, data)
        for key in [path.stem, data.get('slug'), data.get('showdownId'), data.get('showdownName'), data.get('name'), data.get('battleName')]:
            add_key(index, key, value)
        summary = data.get('summary') or {}
        for form in summary.get('forms') or []:
            for key in [form.get('slug'), form.get('form_name'), form.get('saved_name'), form.get('title')]:
                add_key(index, key, value)
    aliases: dict[str, str] = {}
    lookup = BATTLE_REPO / 'data' / 'api' / 'lookup.json'
    if lookup.exists():
        raw = json.loads(lookup.read_text(encoding='utf-8')).get('aliases') or {}
        aliases = {idnorm(k): str(v) for k, v in raw.items()}
    return index, aliases


def resolve_record(opponent: dict[str, Any], index: dict[str, tuple[Path, dict[str, Any]]], aliases: dict[str, str]) -> tuple[Path, dict[str, Any], str]:
    raw_candidates = [opponent.get('slug'), opponent.get('pokemon_key'), opponent.get('pokemon_en')]
    slug = str(opponent.get('slug') or '')
    raw_candidates.extend([
        slug.replace('-alolan', '-alola'), slug.replace('-galarian', '-galar'), slug.replace('-hisuian', '-hisui'),
        slug.replace('alolan-', ''), slug.replace('galarian-', ''), slug.replace('hisuian-', ''),
    ])
    for raw in raw_candidates:
        key = idnorm(str(raw or ''))
        if not key:
            continue
        if key in index:
            path, data = index[key]
            return path, data, f'direct:{raw}'
        alias = aliases.get(key)
        if alias and idnorm(alias) in index:
            path, data = index[idnorm(alias)]
            return path, data, f'alias:{raw}->{alias}'
    raise KeyError(f"mapping not found rank={opponent.get('rank')} slug={opponent.get('slug')} english={opponent.get('pokemon_en')}")


def csv_write(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f'empty rows for {path}')
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    usage = json.loads((PARSED / 'opponent_usage.json').read_text(encoding='utf-8'))
    index, aliases = build_index()
    repo_commit = subprocess.check_output(['git', '-C', str(BATTLE_REPO), 'rev-parse', 'HEAD'], text=True).strip()
    build_rows: list[dict[str, Any]] = []
    output_opponents: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    for opponent in usage['opponents']:
        path, record, match_method = resolve_record(opponent, index, aliases)
        engine_species = record.get('showdownName') or record.get('name') or record.get('battleName')
        showdown_id = record.get('showdownId') or record.get('slug')
        if not engine_species:
            raise RuntimeError(f'engine species missing in {path}')
        fixed_moves = list(opponent['moves'])
        if len(fixed_moves) != 4:
            raise RuntimeError(f'fixed move count != 4 rank={opponent["rank"]}')
        rank = int(opponent['rank'])
        snapshot_token = re.sub(r'[^0-9]+', '', usage['snapshot_jst'])
        build_id = f'M4_{snapshot_token}_R{rank:03d}_MOSTFREQ'
        build = {
            'build_id': build_id, 'opponent_rank': rank, 'slug': opponent['slug'],
            'pokemon_ja': opponent['pokemon_ja'], 'pokemon_en': opponent['pokemon_en'],
            'engine_species': engine_species, 'showdown_id': showdown_id,
            'moves': fixed_moves, 'eligible_moves': fixed_moves,
            'move_1': fixed_moves[0], 'move_2': fixed_moves[1], 'move_3': fixed_moves[2], 'move_4': fixed_moves[3],
            'item': opponent['item'], 'ability': opponent['ability'], 'nature': opponent['nature'], 'spread': opponent['spread'],
            'hp_points': int(opponent['hp_points']), 'attack_points': int(opponent['attack_points']),
            'defense_points': int(opponent['defense_points']), 'sp_atk_points': int(opponent['sp_atk_points']),
            'sp_def_points': int(opponent['sp_def_points']), 'speed_points': int(opponent['speed_points']),
            'evidence_type': 'current_most_frequent_completion', 'snapshot_jst': usage['snapshot_jst'],
            'source_url': opponent['detail_url'], 'source_file': opponent['source_file'],
            'mapping_file': str(path.relative_to(BATTLE_REPO)), 'mapping_commit': repo_commit, 'mapping_method': match_method,
            'item_usage_percent': opponent['item_usage_percent'], 'ability_usage_percent': opponent['ability_usage_percent'],
            'nature_usage_percent': opponent['nature_usage_percent'], 'spread_usage_percent': opponent['spread_usage_percent'],
            'move_usage_percent': ' | '.join(str(v) for v in opponent['move_usage']),
        }
        build_rows.append(build)
        output_opponents.append({
            'rank': rank, 'slug': opponent['slug'], 'pokemon_ja': opponent['pokemon_ja'], 'pokemon_en': opponent['pokemon_en'],
            'engine_species': engine_species, 'showdown_id': showdown_id, 'moves': fixed_moves, 'build_id': build_id,
        })
        mapping_rows.append({
            'rank': rank, 'slug': opponent['slug'], 'pokemon_en': opponent['pokemon_en'],
            'engine_species': engine_species, 'showdown_id': showdown_id, 'mapping_method': match_method,
            'mapping_file': str(path.relative_to(BATTLE_REPO)),
        })

    if len(build_rows) != 100 or len({row['opponent_rank'] for row in build_rows}) != 100:
        raise RuntimeError('build evidence is not exactly one build for each rank 1..100')
    if any(sum(int(row[key]) for key in ['hp_points','attack_points','defense_points','sp_atk_points','sp_def_points','speed_points']) > 66 for row in build_rows):
        raise RuntimeError('invalid stat point sum')

    csv_write(OUT / 'build_evidence.csv', build_rows)
    csv_write(OUT / 'species_mapping.csv', mapping_rows)
    data = {
        'schema_version': 1, 'snapshot_jst': usage['snapshot_jst'], 'thresholds': usage['thresholds'],
        'mapping_repository': 'Gheist23/pokemonbattledata', 'mapping_commit': repo_commit,
        'opponents': output_opponents, 'builds': build_rows,
    }
    (OUT / 'opponent_builds.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (OUT / 'component_evidence.csv').write_bytes((PARSED / 'component_evidence.csv').read_bytes())
    digest = hashlib.sha256((OUT / 'opponent_builds.json').read_bytes()).hexdigest()
    print(json.dumps({'builds': len(build_rows), 'mapping_commit': repo_commit, 'sha256': digest}, ensure_ascii=False))


if __name__ == '__main__':
    main()
