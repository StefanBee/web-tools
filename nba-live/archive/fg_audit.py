#!/usr/bin/env python3
"""Audit full-game and per-period shooting from saved BOS vs GSW ESPN summary."""
from __future__ import annotations
from collections import defaultdict
import gzip,json,sqlite3,sys
from pathlib import Path
from collect import SEASON, made_attempted, parse_player_games, teams_for, derive_periods
from reprocess import restored_event, official_team_stats

root=Path(sys.argv[1])/SEASON
game_id='401910035'
db=sqlite3.connect(root/'season.sqlite')
db.row_factory=sqlite3.Row
game=db.execute("SELECT * FROM games WHERE id=?",(game_id,)).fetchone()
if game is None: raise SystemExit("Game not found")
raw=json.loads(gzip.decompress((root/'raw'/'games'/f'{game_id}.json.gz').read_bytes()))
event=restored_event(db,game)
teams=teams_for(event)
players=parse_player_games(raw,teams)
quarter_team,quarter_players,count=derive_periods(event,raw,players)
rows={}
for side in ('away','home'):
    tid=game[side+'_team_id']
    box=next((b for b in raw.get('boxscore',{}).get('teams',[]) if str(b.get('team',{}).get('id'))==tid),None)
    native={s.get('name'):s.get('displayValue') for s in (box or {}).get('statistics',[])}
    group=[p for p in players if p['team_id']==tid and not p['did_not_play']]
    totals={}
    for source,m,a in [('fg','fgm','fga'),('three','tpm','tpa'),('ft','ftm','fta')]:
        vals=[p.get(m) for p in group];attempts=[p.get(a) for p in group]
        totals[source]={'made':sum(v for v in vals if v is not None),
                        'attempted':sum(v for v in attempts if v is not None),
                        'missing_players':sum(v is None or w is None for v,w in zip(vals,attempts))}
    period_rows=[{k:t[k] for k in ('period','pts','fgm','fga','tpm','tpa','ftm','fta','quality')}
                 for t in quarter_team if t['team_id']==tid]
    period_sums={key:sum(t[key] or 0 for t in period_rows) for key in ('fgm','fga','tpm','tpa','ftm','fta')}
    rows[side]={'team_id':tid,'abbr':game[side+'_abbr'],
                'native_espn_boxscore':native,'official_normalized':official_team_stats(raw,tid),
                'summed_players':totals,'derived_quarters':period_rows,
                'summed_quarters':period_sums}
out={'game_id':game_id,'play_count':count,'teams':rows,
     'note':'Team/native and summed player stats are separate ESPN views. Per-quarter numbers are derived.'}
(root/'fg-audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({'game':game_id,'teams':{s:{'abbr':x['abbr'],'nativeFG':x['native_espn_boxscore'].get('fieldGoalsMade-fieldGoalsAttempted'),
                'playerFG':x['summed_players']['fg'],'playFG':(x['summed_quarters']['fgm'],x['summed_quarters']['fga'])} for s,x in rows.items()}},indent=2))
