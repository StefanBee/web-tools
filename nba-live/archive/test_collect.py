"""Offline tests: run `python -m unittest discover -s nba-live/archive -v`."""
import contextlib
from datetime import date
import gzip
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import collect


def fake_event():
    return {
        'id': '401999001', 'date': '2026-11-20T23:30Z', 'season': {'type': 2},
        'status': {'type': {'completed': True, 'state': 'post'}},
        'competitions': [{'competitors': [
            {'homeAway':'away','team':{'id':'1','abbreviation':'ATL'},'score':'17',
             'linescores':[{'value':5},{'value':3},{'value':4},{'value':5}]},
            {'homeAway':'home','team':{'id':'2','abbreviation':'DET'},'score':'9',
             'linescores':[{'value':0},{'value':2},{'value':4},{'value':3}]},
        ]}]
    }


def fake_summary():
    return {'boxscore':{'players':[{
        'team':{'id':'1'},'statistics':[{'names':['MIN','PTS','REB','AST','FG','3PT','FT','+/-','STL','BLK','TO','PF'],
        'athletes':[{'athlete':{'id':'11','displayName':'Test Player','jersey':'7'},
        'stats':['32','17','4','3','6-12','1-3','4-4','+8','1','0','2','2']}]}]
    }], 'teams':[{'team':{'id':'1'},'statistics':[{'name':'rebounds','displayValue':'20'}]}]},
    'plays':[
        {'id':'1','period':{'number':4},'team':{'id':'1'},'participants':[{'athlete':{'id':'11'}}],
         'text':'Test Player makes 3-pt jumper','type':{'text':'3-pt jump shot'},
         'shootingPlay':True,'scoringPlay':True,'scoreValue':3},
        {'id':'2','period':{'number':4},'team':{'id':'1'},'participants':[{'athlete':{'id':'11'}}],
         'text':'Test Player defensive rebound','type':{'text':'Defensive Rebound'}},
        {'id':'3','period':{'number':4},'team':{'id':'2'},'participants':[],
         'text':'Someone misses jumper','type':{'text':'Jump Shot'},'shootingPlay':True},
    ]}


class ArchiveTests(unittest.TestCase):
    def test_scoring_and_rebounds(self):
        teams, players, plays = collect.derive_periods(fake_event(), fake_summary(), collect.parse_player_games(fake_summary(), collect.teams_for(fake_event())))
        self.assertEqual(plays, 3)
        q4 = next(p for p in teams if p['period']==4 and p['team_id']=='1')
        self.assertEqual(q4['pts'], 5)  # official scoreboard, not estimated from plays (3)
        self.assertEqual(q4['tpm'], 1)
        self.assertEqual(q4['tpa'], 1)
        self.assertEqual(q4['reb'], 1)
        player = next(p for p in players if p['period']==4)
        self.assertEqual(player['pts'], 3)
        self.assertEqual(player['reb'], 1)
        self.assertIsNone(next(p for p in teams if p['period']==2)['reb'])

    def test_database_and_raw_reproducibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = sqlite3.connect(root/'season.sqlite')
            collect.ensure_schema(db)
            event, summary = fake_event(), fake_summary()
            sha = collect.write_gz(root/'raw'/'games'/'401999001.json.gz', summary)
            collect.insert_game(db, event, summary, sha, '2026-11-23T00:00:00Z')
            self.assertEqual(db.execute('SELECT count(*) FROM team_periods').fetchone()[0], 8)
            self.assertEqual(db.execute('SELECT count(*) FROM player_periods').fetchone()[0], 4)
            self.assertEqual(db.execute("SELECT reb FROM team_periods WHERE game_id='401999001' AND team_id='1' AND period=4").fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM player_games').fetchone()[0], 1)
            # Idempotent overwrite doesn't duplicate stats.
            collect.insert_game(db, event, summary, sha, '2026-11-23T00:00:00Z')
            self.assertEqual(db.execute('SELECT count(*) FROM games').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM team_periods').fetchone()[0], 8)
            original = gzip.decompress((root/'raw'/'games'/'401999001.json.gz').read_bytes())
            collect.write_gz(root/'raw'/'games'/'401999001.json.gz', summary)
            self.assertEqual(original, gzip.decompress((root/'raw'/'games'/'401999001.json.gz').read_bytes()))
            db.close()

    def test_backfill_and_incremental(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board = {'events':[fake_event()]}
            calls = []
            def mock_fetch(path, params):
                calls.append((path,params))
                return board if path=='scoreboard' else fake_summary()
            args = type('Args', (), {'data_dir':root, 'today':date(2026, 10, 20), 'from_date':None,
                                     'refresh_days':4, 'force':False, 'max_games':0, 'delay':0})
            with patch.object(collect, 'fetch_json', side_effect=mock_fetch):
                self.assertEqual(collect.run(args), 0)
                self.assertEqual(collect.run(args), 0)
            self.assertEqual(len([x for x in calls if x[0]=='summary']), 1)
            self.assertTrue((root/collect.SEASON/'season.sqlite').exists())
            manifest=json.loads((root/collect.SEASON/'manifest.json').read_text())
            self.assertEqual(manifest['games'], 1)
            self.assertEqual(manifest['team_periods'], 8)

    def test_missing_plays_not_fabricated(self):
        raw=fake_summary()
        raw['plays']=[]
        teams,players,n=collect.derive_periods(fake_event(),raw,collect.parse_player_games(raw,collect.teams_for(fake_event())))
        self.assertEqual(n,0)
        self.assertIsNone(teams[0]['reb'])
        self.assertEqual(teams[0]['pts'],5)
        self.assertIsNone(players[0]['reb'])

if __name__ == '__main__': unittest.main()
