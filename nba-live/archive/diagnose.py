#!/usr/bin/env python3
"""Explain archive-vs-box-score differences using saved ESPN play records."""
import gzip
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from collect import SEASON, get_plays, event_type

root=Path(sys.argv[1])/SEASON
db=sqlite3.connect(root/'season.sqlite')
db.row_factory=sqlite3.Row
samples=[]
summary=Counter()
bad={r['game_id']:{'fga':r['official'],'delta':r['observed']-r['official']}
     for r in db.execute("SELECT * FROM stat_validations WHERE scope='team' AND metric='fga' AND status='mismatch'")}
for game_id in sorted({r['game_id'] for r in db.execute(
    "SELECT game_id FROM stat_validations WHERE scope='team' AND metric='fga' AND status='mismatch'")}):
    path=root/'raw'/'games'/f'{game_id}.json.gz'
    if not path.exists():continue
    raw=json.loads(gzip.decompress(path.read_bytes()))
    plays=get_plays(raw)
    problems={r['entity_id']:dict(r) for r in db.execute(
        "SELECT * FROM stat_validations WHERE game_id=? AND scope='team' AND metric='fga' AND status='mismatch'",(game_id,))}
    fouls={r['entity_id']:dict(r) for r in db.execute(
        "SELECT * FROM stat_validations WHERE game_id=? AND scope='team' AND metric='pf' AND status='mismatch'",(game_id,))}
    example={'id':game_id,'teams':{},'shots_near_fouls':[],'fouls':[]}
    for t,diff in problems.items():
        candidate=0
        for i,p in enumerate(plays):
            if str((p.get('team') or {}).get('id'))!=t:continue
            if p.get('shootingPlay') is not True or p.get('scoringPlay') or p.get('pointsAttempted') not in (2,3):continue
            period=(p.get('period') or {}).get('number')
            clock=(p.get('clock') or {}).get('displayValue')
            neighbors=[]
            for j in range(max(0,i-2),min(len(plays),i+5)):
                if j==i:continue
                q=plays[j]
                if (q.get('period') or {}).get('number')!=period:continue
                kind=event_type(q)
                if 'foul' in kind.lower() and (q.get('clock') or {}).get('displayValue')==clock:
                    neighbors.append({'offset':j-i,'type':kind,'text':q.get('text'),'foul_team':(q.get('team') or {}).get('id')})
            if neighbors:
                candidate+=1
                if len(example['shots_near_fouls'])<25:
                    example['shots_near_fouls'].append({'team':t,'period':period,'clock':clock,'type':event_type(p),
                                                         'text':p.get('text'),'pointsAttempted':p.get('pointsAttempted'),'neighbors':neighbors})
        summary['teams_with_fga_mismatch']+=1
        summary['total_extra_fga']+=diff['observed']-diff['official']
        summary['missed_shots_with_fouls_at_same_clock']+=candidate
        if candidate:summary['teams_with_possible_fouled_shots']+=1
        example['teams'][t]={'observed_fga':diff['observed'],'official_fga':diff['official'],'delta':diff['observed']-diff['official'],
                             'same_clock_fouled_shots':candidate}
    if len(samples)<8:
        for p in plays:
            kind=event_type(p)
            if 'foul' in kind.lower() and len(example['fouls'])<55:
                example['fouls'].append({'period':(p.get('period') or {}).get('number'),'clock':(p.get('clock') or {}).get('displayValue'),
                                         'team':(p.get('team') or {}).get('id'),'type':kind,'text':p.get('text')})
        for k,v in fouls.items():
            example['teams'].setdefault(k,{})['foul_delta']=v['observed']-v['official']
        samples.append(example)
result={'summary':dict(summary),'examples':samples}
(root/'diagnostics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('Diagnostic summary',json.dumps(result['summary']))
