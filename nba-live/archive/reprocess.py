#!/usr/bin/env python3
"""Offline replay of archived ESPN NBA play-by-play into season SQLite.

No network access: reads original compressed summaries, updates only derived
per-period rows and per-metric validation tables, keeps original box scores.
Run after collect.py, or independently:
  python nba-live/archive/reprocess.py --data-dir /path/to/nba-season-data
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import json
import logging
from pathlib import Path
import sqlite3
import sys

from collect import (
    SEASON, STATS, compact_json, derive_periods, ensure_schema,
    made_attempted, numeric, parse_player_games,
)

LOG = logging.getLogger('nba.archive.replay')
PARSER_VERSION = 'structured-2026-11-23-v2-heaves-fouls'
TEAM_METRICS = ('fgm', 'fga', 'tpm', 'tpa', 'ftm', 'fta',
                'reb', 'ast', 'to', 'pf', 'stl', 'blk')
PLAYER_METRICS = STATS


def official_team_stats(raw: dict, team_id: str) -> dict[str, int]:
    teams = (raw.get('boxscore') or {}).get('teams') or []
    row = next((t for t in teams if str((t.get('team') or {}).get('id')) == team_id), None)
    if row is None: return {}
    by = {str(s.get('name') or s.get('label') or '').lower().replace('-', ''):
          s.get('displayValue', s.get('value'))
          for s in row.get('statistics') or []}
    out: dict[str, int] = {}
    for source, made, attempted in (
        ('fieldgoalsmadefieldgoalsattempted', 'fgm', 'fga'),
        ('threepointfieldgoalsmadethreepointfieldgoalsattempted', 'tpm', 'tpa'),
        ('freethrowsmadefreethrowsattempted', 'ftm', 'fta')):
        if source in by:
            m, a = made_attempted(by[source])
            if m is not None: out[made] = m
            if a is not None: out[attempted] = a
    for source, target in (
        ('totalrebounds', 'reb'), ('assists', 'ast'),
        ('totalturnovers', 'to'), ('fouls', 'pf'),
        ('steals', 'stl'), ('blocks', 'blk')):
        v = numeric(by.get(source))
        if v is not None: out[target] = v
    return out


def restored_event(db: sqlite3.Connection, game: sqlite3.Row) -> dict:
    """Keep previously archived official period points; never recompute scores."""
    prior: dict[str, dict[int, int]] = defaultdict(dict)
    for r in db.execute('SELECT team_id,period,pts FROM team_periods WHERE game_id=?', (game['id'],)):
        if r['pts'] is not None: prior[r['team_id']][r['period']] = r['pts']
    comps = []
    for side in ('away', 'home'):
        tid = game[side + '_team_id']
        lines = [({'value': prior[tid][period]} if period in prior[tid] else {})
                 for period in range(1, game['periods'] + 1)]
        comps.append(dict(homeAway=side,team=dict(id=tid,abbreviation=game[side + '_abbr']),
                          score=game[side + '_score'], linescores=lines))
    return {'id':game['id'],'date':game['date'],
            'competitions':[{'competitors':comps}]}


def totals(periods: list[dict], entity_key: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in periods:
        eid = row[entity_key]
        for k in STATS:
            # SQLite team periods call turnovers "tov", player periods call them "to".
            value = row.get('tov') if k == 'to' and entity_key == 'team_id' else row.get(k)
            if value is not None: out[eid][k] += value
    return out


def validate_entity(game_id: str, scope: str, entity_id: str,
                    observed: dict[str, int], official: dict[str, int],
                    metrics: tuple[str, ...]) -> list[tuple]:
    return [(game_id, scope, entity_id, stat, official[stat],
             observed.get(stat, 0), 'matched' if official[stat] == observed.get(stat, 0) else 'mismatch')
            for stat in metrics if official.get(stat) is not None]


def replay_one(db: sqlite3.Connection, game: sqlite3.Row, raw: dict) -> tuple[int, int]:
    event = restored_event(db, game)
    comps = event['competitions'][0]['competitors']
    by = {c['homeAway']:c for c in comps}
    players = parse_player_games(raw, by)
    teams, pperiods, count = derive_periods(event, raw, players)
    team_totals = totals(teams, 'team_id')
    player_totals = totals(pperiods, 'athlete_id')
    checks: list[tuple] = []
    for c in comps:
        team_id = c['team']['id']
        published = official_team_stats(raw, team_id)
        checks.extend(validate_entity(game['id'], 'team', team_id,
                                      team_totals[team_id], published, TEAM_METRICS))
    for p in players:
        if p['did_not_play']: continue
        pid = p['athlete_id']
        official = dict(p, to=p.get('tov'))
        checks.extend(validate_entity(game['id'], 'player', pid,
                                      player_totals[pid], official, PLAYER_METRICS))
    mismatches: dict[tuple[str, str], int] = defaultdict(int)
    matched: dict[tuple[str, str], int] = defaultdict(int)
    for _gid, scope, entity_id, _metric, _official, _observed, status in checks:
        target = matched if status == 'matched' else mismatches
        target[(scope, entity_id)] += 1
    def quality(scope: str, entity_id: str, prior: str) -> str:
        if prior == 'no_play_by_play' or count == 0:return 'no_play_by_play'
        if mismatches[(scope, entity_id)]:return 'mismatch'
        if matched[(scope, entity_id)]:return 'reconciled'
        return 'derived'
    with db:
        # Delete dependents first, and retain official full-game player/team rows.
        db.execute('DELETE FROM player_periods WHERE game_id=?', (game['id'],))
        db.execute('DELETE FROM team_periods WHERE game_id=?', (game['id'],))
        db.execute('DELETE FROM stat_validations WHERE game_id=?', (game['id'],))
        for t in teams:
            q = quality('team', t['team_id'], t['quality'])
            db.execute('''INSERT INTO team_periods
              (game_id,team_id,abbr,period,period_label,pts,fgm,fga,tpm,tpa,ftm,fta,reb,ast,tov,pf,stl,blk,play_count,quality)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
              (game['id'], *(t.get(k) for k in ('team_id','abbr','period','period_label','pts',
                'fgm','fga','tpm','tpa','ftm','fta','reb','ast','tov','pf','stl','blk','play_count')), q))
        for p in pperiods:
            q = quality('player', p['athlete_id'], p['quality'])
            db.execute('''INSERT INTO player_periods
              (game_id,athlete_id,team_id,period,pts,fgm,fga,tpm,tpa,ftm,fta,reb,ast,tov,pf,stl,blk,quality)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
              (game['id'], *(p.get(k) for k in ('athlete_id','team_id','period','pts',
               'fgm','fga','tpm','tpa','ftm','fta','reb','ast','to','pf','stl','blk')),q))
        db.executemany('''INSERT INTO stat_validations
          (game_id,scope,entity_id,metric,official,observed,status)
          VALUES (?,?,?,?,?,?,?)''', checks)
    return len(checks),sum(r[-1] == 'mismatch' for r in checks)


def report(db: sqlite3.Connection, root: Path, processed: int,
           missing: list[str], errors: list[str]) -> dict:
    counts: dict[str, dict[str, dict[str, int]]] = {'team':{},'player':{}}
    for row in db.execute('''SELECT scope,metric,status,count(*) AS count
                              FROM stat_validations GROUP BY scope,metric,status'''):
        metric = counts[row['scope']].setdefault(row['metric'],{'matched':0,'mismatch':0})
        metric[row['status']] = row['count']
    total_games = db.execute('SELECT count(*) FROM games').fetchone()[0]
    checked_games = db.execute('SELECT count(DISTINCT game_id) FROM stat_validations').fetchone()[0]
    mismatched_games = db.execute("SELECT count(DISTINCT game_id) FROM stat_validations WHERE status='mismatch'").fetchone()[0]
    team_mismatches = db.execute("SELECT count(*) FROM stat_validations WHERE scope='team' AND status='mismatch'").fetchone()[0]
    player_mismatches = db.execute("SELECT count(*) FROM stat_validations WHERE scope='player' AND status='mismatch'").fetchone()[0]
    # Preserve complete per-game mismatch details without flooding the manifest.
    details = [dict(game_id=r['game_id'],scope=r['scope'],entity_id=r['entity_id'],
                    metric=r['metric'],official=r['official'],observed=r['observed'])
               for r in db.execute('''SELECT game_id,scope,entity_id,metric,official,observed
                                      FROM stat_validations WHERE status='mismatch'
                                      ORDER BY game_id,scope,entity_id,metric''')]
    result = dict(season=SEASON,parser_version=PARSER_VERSION,
                  updated_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                  games_archived=total_games, games_reprocessed=processed,
                  games_validated=checked_games,
                  games_with_mismatches=mismatched_games,
                  games_without_mismatches=max(0,checked_games-mismatched_games),
                  team_metric_mismatches=team_mismatches,
                  player_metric_mismatches=player_mismatches,
                  metric_reconciliation=counts,
                  missing_raw=missing,errors=errors,
                  discrepancies=details,
                  note='A matching full-game total does not prove every per-period split is correct; live ESPN feed can be corrected.')
    (root/'validation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    manifest = root/'manifest.json'
    if manifest.exists():
        obj = json.loads(manifest.read_text(encoding='utf-8'))
        obj['validation'] = {k:result[k] for k in ('parser_version','games_validated','games_with_mismatches',
                                                  'team_metric_mismatches','player_metric_mismatches')}
        manifest.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return result


def replay(data_dir: Path) -> int:
    root = data_dir / SEASON
    db_path = root/'season.sqlite'
    if not db_path.is_file():
        LOG.error('Archive database does not exist: %s', db_path)
        return 1
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    ensure_schema(db)
    db.execute('PRAGMA journal_mode=DELETE')
    processed = 0
    missing: list[str] = []
    errors: list[str] = []
    for game in list(db.execute('SELECT * FROM games ORDER BY date,id')):
        gid = game['id']
        raw_path = root/'raw'/'games'/f'{gid}.json.gz'
        if not raw_path.exists():
            missing.append(gid)
            continue
        try:
            raw = json.loads(gzip.decompress(raw_path.read_bytes()))
            replay_one(db, game, raw)
            processed += 1
        except Exception as exc:
            LOG.error('Reprocessing game %s: %s', gid, exc)
            errors.append(f'{gid}: {exc}')
        if processed % 50 == 0 and processed:
            LOG.info('Reprocessed %d games', processed)
    summary = report(db,root,processed,missing,errors)
    db.execute('PRAGMA optimize')
    db.commit()
    db.close()
    LOG.info('Validation: %d/%d games, %d games with mismatches, %d team and %d player metric mismatches',
             summary['games_validated'],summary['games_archived'],summary['games_with_mismatches'],
             summary['team_metric_mismatches'],summary['player_metric_mismatches'])
    return 1 if missing or errors else 0


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',required=True,type=Path)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    return replay(args.data_dir)


if __name__ == '__main__':
    sys.exit(main())
