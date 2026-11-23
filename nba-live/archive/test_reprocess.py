"""Offline reprocessing tests using a real 450-play ESPN NBA summary fixture."""
import gzip
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import collect
import reprocess

FIXTURE = Path(__file__).resolve().parent.parent/'tests'/'fixtures'/'espn-tor-orl.json'

def sample():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))

def event(raw):
    comps=[]
    for row in raw['header']['competitions'][0]['competitors']:
        comps.append(dict(homeAway=row['homeAway'], team={
            'id':row['team']['id'],
            'abbreviation': next(t['team']['abbreviation'] for t in raw['boxscore']['teams']
                                 if t['team']['id']==row['team']['id'])},
            score=row['score'],linescores=[{'value':0} for _ in range(4)]))
    return {'id':'401585607','date':'2026-11-16T00:00:00Z',
            'competitions':[{'competitors':comps}]}

class ReplayTests(unittest.TestCase):
    def test_real_fixture_all_team_metrics_reconcile(self):
        raw=sample()
        e=event(raw)
        p=collect.parse_player_games(raw,collect.teams_for(e))
        tp, pp, n=collect.derive_periods(e,raw,p)
        self.assertEqual(n,450)
        team_totals=reprocess.totals(tp,'team_id')
        for t in raw['boxscore']['teams']:
            id=t['team']['id']
            published=reprocess.official_team_stats(raw,id)
            for k in reprocess.TEAM_METRICS:
                if k in published:
                    self.assertEqual(team_totals[id][k],published[k],(id,k))
        player_totals=reprocess.totals(pp,'athlete_id')
        checked=0
        for player in p:
            if player['did_not_play']: continue
            for stat in collect.STATS:
                if player[stat] is None: continue
                self.assertEqual(player_totals[player['athlete_id']][stat],player[stat],
                                 (player['athlete_name'],stat))
                checked+=1
        self.assertGreater(checked,200)

    def test_replay_database_is_idempotent_and_preserves_scores(self):
        raw=sample()
        e=event(raw)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/collect.SEASON
            root.joinpath('raw','games').mkdir(parents=True)
            db=sqlite3.connect(root/'season.sqlite')
            db.row_factory=sqlite3.Row
            collect.ensure_schema(db)
            sha=collect.write_gz(root/'raw'/'games'/'401585607.json.gz',raw)
            collect.insert_game(db,e,raw,sha,'2026-11-23T00:00:00Z')
            db.close()
            self.assertEqual(reprocess.replay(Path(tmp)),0)
            db=sqlite3.connect(root/'season.sqlite')
            db.row_factory=sqlite3.Row
            original=[tuple(row) for row in db.execute('SELECT team_id,period,pts FROM team_periods ORDER BY team_id,period')]
            team_ok=db.execute("SELECT count(*) FROM stat_validations WHERE scope='team' AND status='mismatch'").fetchone()[0]
            player_ok=db.execute("SELECT count(*) FROM stat_validations WHERE scope='player' AND status='mismatch'").fetchone()[0]
            self.assertEqual(team_ok,0)
            self.assertEqual(player_ok,0)
            self.assertEqual(db.execute("SELECT count(*) FROM stat_validations").fetchone()[0]>200,True)
            db.close()
            self.assertEqual(reprocess.replay(Path(tmp)),0)
            db=sqlite3.connect(root/'season.sqlite')
            self.assertEqual([tuple(row) for row in db.execute('SELECT team_id,period,pts FROM team_periods ORDER BY team_id,period')],original)
            db.close()
            report=json.loads((root/'validation.json').read_text())
            self.assertEqual(report['games_validated'],1)
            self.assertEqual(report['games_with_mismatches'],0)

    def test_missing_raw_is_reported_without_damaging_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/collect.SEASON
            root.mkdir(parents=True)
            db=sqlite3.connect(root/'season.sqlite')
            collect.ensure_schema(db)
            db.close()
            self.assertEqual(reprocess.replay(Path(tmp)),0)
            data=json.loads((root/'validation.json').read_text())
            self.assertEqual(data['games_archived'],0)

if __name__=='__main__':
    unittest.main()
