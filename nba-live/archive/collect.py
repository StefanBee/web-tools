#!/usr/bin/env python3
"""Archive completed ESPN NBA games to a queryable SQLite season database.

stdlib only. Data goes to a separate Git branch, never the live website bundle.
Run: python nba-live/archive/collect.py --data-dir /path/to/nba-season-data
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta
import gzip
import hashlib
import io
import json
import logging
from pathlib import Path
import random
import re
import sqlite3
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

API = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/'
SEASON = '2026-27'
START = date(2026, 10, 20)
ET = ZoneInfo('America/New_York')
LOG = logging.getLogger('nba.archive')
STATS = ('pts', 'fgm', 'fga', 'tpm', 'tpa', 'ftm', 'fta', 'reb', 'ast', 'to', 'pf', 'stl', 'blk')
SHOT_STATS = ('fgm', 'fga', 'tpm', 'tpa', 'ftm', 'fta')


def fetch_json(path: str, params: dict[str, str], *, retries: int = 4) -> dict:
    url = API + path + '?' + urlencode(params)
    for attempt in range(retries):
        try:
            req = Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; NBASeasonArchive/1.0; personal statistics archive)',
                'Accept': 'application/json',
            })
            with urlopen(req, timeout=22) as reply:
                result = json.load(reply)
                if not isinstance(result, dict):
                    raise ValueError('Expected an object from ESPN')
                return result
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            if attempt == retries - 1:
                raise RuntimeError(f'Unable to fetch {path} {params}: {exc}') from exc
            delay = min(2 ** attempt * 2, 20) + random.random()
            LOG.warning('ESPN request failed (%s); retrying in %.1fs', exc, delay)
            time.sleep(delay)
    raise AssertionError('unreachable')


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript('''
      PRAGMA foreign_keys=ON;
      CREATE TABLE IF NOT EXISTS games (
        id TEXT PRIMARY KEY, season TEXT NOT NULL, date TEXT NOT NULL,
        away_team_id TEXT NOT NULL, home_team_id TEXT NOT NULL,
        away_abbr TEXT NOT NULL, home_abbr TEXT NOT NULL,
        away_score INTEGER, home_score INTEGER, periods INTEGER NOT NULL,
        play_count INTEGER NOT NULL, source_sha256 TEXT NOT NULL,
        archived_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_games_date ON games(date);
      CREATE TABLE IF NOT EXISTS team_games (
        game_id TEXT NOT NULL, team_id TEXT NOT NULL, abbr TEXT NOT NULL,
        side TEXT NOT NULL, points INTEGER, stats_json TEXT NOT NULL,
        PRIMARY KEY(game_id,team_id), FOREIGN KEY(game_id) REFERENCES games(id)
      );
      CREATE INDEX IF NOT EXISTS idx_team_games_team ON team_games(team_id,game_id);
      CREATE TABLE IF NOT EXISTS team_periods (
        game_id TEXT NOT NULL, team_id TEXT NOT NULL, abbr TEXT NOT NULL,
        period INTEGER NOT NULL, period_label TEXT NOT NULL,
        pts INTEGER, fgm INTEGER, fga INTEGER, tpm INTEGER, tpa INTEGER,
        ftm INTEGER, fta INTEGER, reb INTEGER, ast INTEGER, tov INTEGER,
        pf INTEGER, stl INTEGER, blk INTEGER,
        play_count INTEGER NOT NULL, quality TEXT NOT NULL,
        PRIMARY KEY(game_id,team_id,period),
        FOREIGN KEY(game_id) REFERENCES games(id)
      );
      CREATE INDEX IF NOT EXISTS idx_team_periods_query ON team_periods(team_id,period);
      CREATE INDEX IF NOT EXISTS idx_team_periods_rank ON team_periods(period,reb);
      CREATE TABLE IF NOT EXISTS player_games (
        game_id TEXT NOT NULL, athlete_id TEXT NOT NULL, team_id TEXT NOT NULL,
        athlete_name TEXT NOT NULL, jersey TEXT, did_not_play INTEGER NOT NULL,
        min TEXT, pts INTEGER, reb INTEGER, ast INTEGER,
        fgm INTEGER, fga INTEGER, tpm INTEGER, tpa INTEGER,
        ftm INTEGER, fta INTEGER, plus_minus INTEGER,
        stl INTEGER, blk INTEGER, tov INTEGER, pf INTEGER,
        raw_stats_json TEXT NOT NULL,
        PRIMARY KEY(game_id,athlete_id),
        FOREIGN KEY(game_id) REFERENCES games(id)
      );
      CREATE INDEX IF NOT EXISTS idx_player_games_player ON player_games(athlete_id,game_id);
      CREATE INDEX IF NOT EXISTS idx_player_games_team ON player_games(team_id,game_id);
      CREATE TABLE IF NOT EXISTS player_periods (
        game_id TEXT NOT NULL, athlete_id TEXT NOT NULL, team_id TEXT NOT NULL,
        period INTEGER NOT NULL, pts INTEGER, fgm INTEGER, fga INTEGER,
        tpm INTEGER, tpa INTEGER, ftm INTEGER, fta INTEGER, reb INTEGER,
        ast INTEGER, tov INTEGER, pf INTEGER, stl INTEGER, blk INTEGER,
        quality TEXT NOT NULL,
        PRIMARY KEY(game_id,athlete_id,period),
        FOREIGN KEY(game_id,athlete_id) REFERENCES player_games(game_id,athlete_id)
      );
      CREATE INDEX IF NOT EXISTS idx_player_periods_query ON player_periods(athlete_id,period);
      CREATE TABLE IF NOT EXISTS scanned_dates (
        date TEXT PRIMARY KEY, scanned_at TEXT NOT NULL, event_count INTEGER NOT NULL
      );
      CREATE TABLE IF NOT EXISTS pending_games (
        id TEXT PRIMARY KEY, date TEXT NOT NULL, reason TEXT NOT NULL
      );
    ''')


def compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def write_gz(path: Path, value: object) -> str:
    data = compact_json(value).encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or gzip.decompress(path.read_bytes()) != data:
        # gzip header has a fixed timestamp, keeping repeated runs git-friendly.
        with path.open('wb') as dst:
            with gzip.GzipFile(filename='', fileobj=dst, mode='wb', compresslevel=9, mtime=0) as out:
                out.write(data)
    return hashlib.sha256(data).hexdigest()


def get_plays(raw: dict) -> list[dict]:
    plays = raw.get('plays', [])
    if isinstance(plays, dict):
        plays = plays.get('plays', [])
    return plays if isinstance(plays, list) else []


def numeric(value: object) -> int | None:
    try:
        if value is None or str(value).strip() in ('', '—', '-'): return None
        return int(float(str(value).strip().replace('+', '')))
    except (ValueError, TypeError):
        return None


def made_attempted(value: object) -> tuple[int | None, int | None]:
    values = re.split(r'\s*[-/]\s*', str(value or ''))
    return (numeric(values[0]), numeric(values[1])) if len(values) == 2 else (None, None)


def period_of(play: dict) -> int:
    p = play.get('period') or {}
    return numeric(p.get('number') if isinstance(p, dict) else p) or 0


def actor_id(play: dict) -> str:
    p = play.get('participants') or []
    if not p or not isinstance(p, list) or not isinstance(p[0], dict): return ''
    a = p[0]
    return str((a.get('athlete') or {}).get('id') or a.get('athleteId') or a.get('id') or '')


def event_type(play: dict) -> str:
    typ = play.get('type') or {}
    return str(typ.get('text') or typ.get('name') or '') if isinstance(typ, dict) else str(typ)


def event_stats(play: dict) -> dict[str, int]:
    """Explicitly heuristic: do not label these as official box-score splits."""
    txt = str(play.get('text') or '')
    full = txt + ' ' + event_type(play)
    free = bool(re.search(r'free[\s-]?throw', full, re.I))
    three = bool(re.search(r'\b3[\s-]?(?:pt|point)\b|three[\s-]?point', full, re.I))
    nonshot = bool(re.search(r'\b(?:rebound|turnover|steals?|blocks?|blocked|foul|substitution)\b', full, re.I))
    shot = not free and (play.get('shootingPlay') is True or (not nonshot and (three or bool(re.search(r'\b(?:jumper|jump shot|layup|dunk|hook shot|tip shot|field goal|finger roll)\b', full, re.I)))))
    made = bool(play.get('scoringPlay')) or bool(re.search(r'\b(?:makes|made)\b', txt, re.I))
    # A scoring play is not necessarily a basket (e.g. technical FT).
    return {
        'pts': numeric(play.get('scoreValue')) if play.get('scoringPlay') else 0,
        'fgm': int(shot and made), 'fga': int(shot),
        'tpm': int(shot and three and made), 'tpa': int(shot and three),
        'ftm': int(free and made), 'fta': int(free),
        'reb': int(bool(re.search(r'\brebound\b', full, re.I))),
        'to': int(bool(re.search(r'\bturnover\b', full, re.I))),
        'pf': int(bool(re.search(r'\bfoul\b', full, re.I)) and not bool(re.search(r'foul shot', full, re.I))),
        'ast': int(bool(re.search(r'\bassist\b', full, re.I))),
        'stl': int(bool(re.search(r'\bsteal\b', full, re.I))),
        'blk': int(bool(re.search(r'\bblock\b', full, re.I))),
    }


def teams_for(event: dict) -> dict[str, dict] | None:
    comp = (event.get('competitions') or [{}])[0]
    by = {c.get('homeAway'): c for c in comp.get('competitors', [])}
    if 'home' not in by or 'away' not in by: return None
    return by


def final_event(event: dict) -> bool:
    status = (event.get('status') or {}).get('type') or {}
    return bool(status.get('completed') or status.get('state') == 'post')


def season_event(event: dict) -> bool:
    # ESPN regular season: type 2; NBA Cup group games are regular-season games.
    typ = (event.get('season') or {}).get('type')
    return typ is None or numeric(typ) == 2


def parse_player_games(raw: dict, teams: dict[str, dict]) -> list[dict]:
    allowed = {str(c['team']['id']) for c in teams.values()}
    players: list[dict] = []
    seen = set()
    for group in (raw.get('boxscore') or {}).get('players') or []:
        team_id = str((group.get('team') or {}).get('id') or '')
        if team_id not in allowed: continue
        for stats_group in group.get('statistics') or []:
            labels = stats_group.get('names') or stats_group.get('labels') or []
            for entry in stats_group.get('athletes') or []:
                athlete = entry.get('athlete') or {}
                athlete_id = str(athlete.get('id') or '')
                if not athlete_id or athlete_id in seen: continue
                seen.add(athlete_id)
                values = entry.get('stats') or []
                stat = {str(label).upper(): val for label, val in zip(labels, values)}
                def read(*keys):
                    for key in keys:
                        if key in stat and stat[key] not in ('', None): return stat[key]
                    return None
                fgm, fga = made_attempted(read('FG'))
                tpm, tpa = made_attempted(read('3PT', '3P'))
                ftm, fta = made_attempted(read('FT'))
                players.append(dict(
                    athlete_id=athlete_id, team_id=team_id,
                    athlete_name=athlete.get('displayName') or athlete.get('fullName') or athlete_id,
                    jersey=str(athlete.get('jersey') or entry.get('jersey') or ''),
                    did_not_play=int(bool(entry.get('didNotPlay') or athlete.get('didNotPlay') or not values)),
                    min=str(read('MIN') or ''), pts=numeric(read('PTS')),
                    reb=numeric(read('REB', 'TOT')), ast=numeric(read('AST')),
                    fgm=fgm, fga=fga, tpm=tpm, tpa=tpa, ftm=ftm, fta=fta,
                    plus_minus=numeric(read('+/-', 'PM', 'PLUSMINUS')),
                    stl=numeric(read('STL')), blk=numeric(read('BLK')),
                    tov=numeric(read('TO', 'TOV')), pf=numeric(read('PF')),
                    raw_stats_json=compact_json(stat),
                ))
    return players


def official_points(competitor: dict, period: int) -> int | None:
    lines = competitor.get('linescores') or []
    if len(lines) < period: return None
    line = lines[period - 1]
    if isinstance(line, dict): return numeric(line.get('value', line.get('displayValue')))
    return numeric(line)


def derive_periods(event: dict, raw: dict, players: list[dict]) -> tuple[list[dict], list[dict], int]:
    """Compute all periods, retaining NULL when play data is missing.

    Exact period scoring is taken from ESPN's scoreboard line scores.
    Other per-period statistics are best-effort play-by-play reconstructions.
    """
    teams = teams_for(event)
    assert teams
    plays = get_plays(raw)
    valid_team_ids = {str(c['team']['id']) for c in teams.values()}
    counts: dict[tuple[str, int], dict] = defaultdict(lambda: defaultdict(int))
    player_counts: dict[tuple[str, int], dict] = defaultdict(lambda: defaultdict(int))
    play_counts: dict[int, int] = defaultdict(int)
    per_team_plays: dict[tuple[str, int], int] = defaultdict(int)
    players_by_id = {p['athlete_id']: p for p in players}
    for play in plays:
        period = period_of(play)
        if period <= 0 or period > 20: continue
        play_counts[period] += 1
        team_id = str((play.get('team') or {}).get('id') or play.get('teamId') or '')
        stat = event_stats(play)
        if team_id in valid_team_ids:
            per_team_plays[(team_id, period)] += 1
            for key, value in stat.items(): counts[(team_id, period)][key] += value or 0
        # Only credit the *primary actor* for field goals/FTs/rebounds/turnovers.
        # Secondary assists/steals/blocks may be in the prose; cannot rely on team labels.
        aid = actor_id(play)
        if aid in players_by_id:
            key = (aid, period)
            for field in ('pts', 'fgm', 'fga', 'tpm', 'tpa', 'ftm', 'fta', 'reb', 'to', 'pf'):
                player_counts[key][field] += stat[field] or 0
        prose = str(play.get('text') or '')
        for field, verb in (('ast', 'assists?'), ('stl', 'steals?'), ('blk', 'blocks?')):
            # Reproduce the live inspector's name-based secondary credit only.
            if not re.search(r'\b'+verb+r'\b', prose, re.I): continue
            for player in players:
                base = re.sub(r'\s+(?:Jr\.?|Sr\.?|II|III|IV)$', '', player['athlete_name'], flags=re.I)
                if re.search(r'(?:^|[^a-z])'+re.escape(base)+r'\s+'+verb+r'\b', prose, re.I):
                    player_counts[(player['athlete_id'], period)][field] += 1
    max_period = max([4, *play_counts.keys(),
                      *(len(c.get('linescores') or []) for c in teams.values())])
    max_period = min(20, max_period)
    result_teams: list[dict] = []
    result_players: list[dict] = []
    for side, competitor in teams.items():
        team = competitor['team']; team_id = str(team['id'])
        for period in range(1, max_period + 1):
            count = per_team_plays[(team_id, period)]
            observed = play_counts.get(period, 0) > 0
            stats = counts[(team_id, period)]
            result_teams.append(dict(
                team_id=team_id, abbr=team.get('abbreviation') or '', period=period,
                period_label=f'Q{period}' if period <= 4 else f'OT{period-4}',
                pts=official_points(competitor, period),
                fgm=stats['fgm'] if observed else None, fga=stats['fga'] if observed else None,
                tpm=stats['tpm'] if observed else None, tpa=stats['tpa'] if observed else None,
                ftm=stats['ftm'] if observed else None, fta=stats['fta'] if observed else None,
                reb=stats['reb'] if observed else None, ast=stats['ast'] if observed else None,
                tov=stats['to'] if observed else None, pf=stats['pf'] if observed else None,
                stl=stats['stl'] if observed else None, blk=stats['blk'] if observed else None,
                play_count=count,
                quality='derived' if observed else 'no_play_by_play',
            ))
    for player in players:
        if player['did_not_play']: continue
        for period in range(1, max_period+1):
            observed = play_counts.get(period, 0) > 0
            stats = player_counts[(player['athlete_id'], period)]
            result_players.append(dict(
                athlete_id=player['athlete_id'], team_id=player['team_id'], period=period,
                **{k: (stats[k] if observed else None) for k in STATS},
                quality='derived' if observed else 'no_play_by_play',
            ))
    return result_teams, result_players, len(plays)


def insert_game(db: sqlite3.Connection, event: dict, raw: dict, sha: str, now: str) -> None:
    team_map = teams_for(event)
    if not team_map: raise ValueError('Missing game competitors')
    teams = team_map
    players = parse_player_games(raw, teams)
    tperiods, pperiods, play_count = derive_periods(event, raw, players)
    gid = str(event['id'])
    away, home = teams['away'], teams['home']
    score = lambda team: numeric(team.get('score'))
    if play_count == 0:
        LOG.warning('%s has no play-by-play; storing NULL for derived quarter stats', gid)
    with db:
        for table in ('player_periods', 'team_periods', 'player_games', 'team_games'):
            db.execute(f'DELETE FROM {table} WHERE game_id=?', (gid,))
        db.execute('''INSERT INTO games(id,season,date,away_team_id,home_team_id,away_abbr,home_abbr,
                  away_score,home_score,periods,play_count,source_sha256,archived_at)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                  season=excluded.season,date=excluded.date,away_team_id=excluded.away_team_id,
                  home_team_id=excluded.home_team_id,away_abbr=excluded.away_abbr,home_abbr=excluded.home_abbr,
                  away_score=excluded.away_score,home_score=excluded.home_score,periods=excluded.periods,
                  play_count=excluded.play_count,source_sha256=excluded.source_sha256,archived_at=excluded.archived_at''',
                   (gid, SEASON, event.get('date') or '', str(away['team']['id']), str(home['team']['id']),
                    away['team'].get('abbreviation') or '', home['team'].get('abbreviation') or '',
                    score(away), score(home), max(t['period'] for t in tperiods), play_count, sha, now))
        for side, comp in teams.items():
            tid = str(comp['team']['id'])
            team_stats = next((g.get('statistics') or [] for g in (raw.get('boxscore') or {}).get('teams') or []
                               if str((g.get('team') or {}).get('id') or '') == tid), [])
            db.execute('INSERT INTO team_games VALUES (?,?,?,?,?,?)',
                       (gid, tid, comp['team'].get('abbreviation') or '', side,
                        score(comp), compact_json(team_stats)))
        for t in tperiods:
            db.execute('''INSERT INTO team_periods
                (game_id,team_id,abbr,period,period_label,pts,fgm,fga,tpm,tpa,ftm,fta,reb,ast,tov,pf,stl,blk,play_count,quality)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                       (gid, *(t.get(k) for k in ('team_id','abbr','period','period_label','pts','fgm','fga','tpm','tpa','ftm','fta','reb','ast','tov','pf','stl','blk','play_count','quality'))))
        for p in players:
            db.execute('''INSERT INTO player_games
               (game_id,athlete_id,team_id,athlete_name,jersey,did_not_play,min,pts,reb,ast,
                fgm,fga,tpm,tpa,ftm,fta,plus_minus,stl,blk,tov,pf,raw_stats_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                       (gid, *(p.get(k) for k in ('athlete_id','team_id','athlete_name','jersey','did_not_play','min','pts','reb','ast','fgm','fga','tpm','tpa','ftm','fta','plus_minus','stl','blk','tov','pf','raw_stats_json'))))
        for p in pperiods:
            db.execute('''INSERT INTO player_periods
                (game_id,athlete_id,team_id,period,pts,fgm,fga,tpm,tpa,ftm,fta,reb,ast,tov,pf,stl,blk,quality)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                       (gid, *(p.get(k) for k in ('athlete_id','team_id','period','pts','fgm','fga','tpm','tpa','ftm','fta','reb','ast','to','pf','stl','blk','quality'))))
        db.execute('DELETE FROM pending_games WHERE id=?', (gid,))


def date_range(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def run(args: argparse.Namespace) -> int:
    root = args.data_dir / SEASON
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / 'season.sqlite')
    db.row_factory = sqlite3.Row
    ensure_schema(db)
    # DELETE mode means only the SQLite file must be committed (no -wal/-shm).
    db.execute('PRAGMA journal_mode=DELETE')
    db.execute('PRAGMA busy_timeout=60000')
    today = args.today or datetime.now(ET).date()
    start = START if not args.from_date else max(START, args.from_date)
    scanned = {row['date'] for row in db.execute('SELECT date FROM scanned_dates')}
    # Recheck the last several NBA calendar days; overnight finalization can be late.
    refresh_start = today - timedelta(days=args.refresh_days)
    dates = [d for d in date_range(start, today)
             if args.force or d >= refresh_start or d.isoformat() not in scanned]
    LOG.info('Season %s: %s through %s; scanning %s scoreboard days', SEASON, start, today, len(dates))
    errors = []
    due: dict[str, dict] = {}
    now = datetime.now(ZoneInfo('UTC')).isoformat(timespec='seconds')
    for d in dates:
        key = d.strftime('%Y%m%d')
        try:
            board = fetch_json('scoreboard', {'dates': key, 'limit':'100'})
            events = [e for e in board.get('events') or [] if season_event(e) and teams_for(e)]
            write_gz(root / 'raw' / 'scoreboards' / (key+'.json.gz'), board)
            with db:
                db.execute('INSERT OR REPLACE INTO scanned_dates VALUES (?,?,?)', (d.isoformat(), now, len(events)))
            for event in events:
                if final_event(event): due[str(event['id'])] = (event, d.isoformat())
        except Exception as exc:
            LOG.error('Scoreboard %s: %s', key, exc)
            errors.append(f'board:{key}')
        if args.delay: time.sleep(args.delay)
    # Revisit previously failed final games, even if their scoreboard day is not scanned again.
    # Old entries are discovered from the cached original scoreboard rather than ignored.
    for row in db.execute('SELECT id,date FROM pending_games'):
        key = row['date'].replace('-', '')
        path = root / 'raw' / 'scoreboards' / (key+'.json.gz')
        if not path.exists(): continue
        try:
            board = json.loads(gzip.decompress(path.read_bytes()))
            for event in board.get('events') or []:
                if str(event.get('id')) == row['id'] and final_event(event): due[row['id']] = (event, row['date'])
        except (ValueError, OSError) as exc:
            LOG.warning('Corrupt board cache %s: %s', key, exc)
    archived = 0
    skipped = 0
    for gid, (event, board_date) in due.items():
        existing = db.execute('SELECT play_count FROM games WHERE id=?', (gid,)).fetchone()
        # A final game with zero plays is retried for more complete ESPN data.
        if existing and existing['play_count'] > 0 and not args.force:
            skipped += 1
            continue
        if args.max_games and archived >= args.max_games:
            # Keep backlog from being dropped on the next incremental scan.
            with db:
                db.execute('INSERT OR REPLACE INTO pending_games VALUES (?,?,?)',
                           (gid, board_date, 'queued'))
            continue
        try:
            raw = fetch_json('summary', {'event': gid})
            # Raw input is written before committing derived data, never the other way round.
            sha = write_gz(root / 'raw' / 'games' / (gid+'.json.gz'), raw)
            insert_game(db, event, raw, sha, now)
            archived += 1
            if archived % 10 == 0:
                LOG.info('Archived %s games...', archived)
        except Exception as exc:
            LOG.error('Game %s: %s', gid, exc)
            errors.append(f'game:{gid}')
            with db:
                db.execute('INSERT OR REPLACE INTO pending_games VALUES (?,?,?)',
                           (gid, board_date, str(exc)[:180]))
        if args.delay: time.sleep(args.delay)
    game_count = db.execute('SELECT count(*) FROM games').fetchone()[0]
    period_count = db.execute('SELECT count(*) FROM team_periods').fetchone()[0]
    pending_count = db.execute('SELECT count(*) FROM pending_games').fetchone()[0]
    summary = dict(season=SEASON, updated_at=now, games=game_count, team_periods=period_count,
                   newly_archived=archived, unchanged=skipped, pending_games=pending_count,
                   scoreboard_errors=len([e for e in errors if e.startswith('board:')]),
                   note='Period stats other than score are estimates reconstructed from ESPN plays; raw source retained.')
    (root/'manifest.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    db.execute('PRAGMA optimize')
    db.commit()
    db.close()
    LOG.info('Archive: %s', summary)
    # Missing games should be visible as failure but successful data is committed by workflow.
    return 1 if errors or pending_count else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True, type=Path,
                        help='Root of the separate nba-season-data Git branch checkout')
    parser.add_argument('--today', type=date.fromisoformat, help='Testing/recovery cutoff (YYYY-MM-DD)')
    parser.add_argument('--from-date', type=date.fromisoformat, help='Force starting date (default season opener)')
    parser.add_argument('--refresh-days', type=int, default=4,
                        help='Scoreboard days to recheck regularly')
    parser.add_argument('--force', action='store_true', help='Re-fetch and recalculate every game')
    parser.add_argument('--max-games', type=int, default=0, help='Limit summaries fetched per run (0 unlimited)')
    parser.add_argument('--delay', type=float, default=0.18, help='Seconds between requests')
    parser.add_argument('-v','--verbose', action='store_true')
    return parser.parse_args()


if __name__ == '__main__':
    a = parse_args()
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    sys.exit(run(a))
