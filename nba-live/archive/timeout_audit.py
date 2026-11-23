#!/usr/bin/env python3
"""Audit charged timeout play events against stored ESPN NBA summaries."""
import gzip
import json
import re
import sys
from pathlib import Path
from collect import SEASON,get_plays,event_type

root=Path(sys.argv[1])/SEASON
target_id='401910035'
target=root/'raw'/'games'/f'{target_id}.json.gz'
if not target.exists():
    raise SystemExit('BOS @ GSW source not archived: '+str(target))
raw=json.loads(gzip.decompress(target.read_bytes()))
plays=get_plays(raw)
def is_timeout(p):
    return re.search(r'time[\s-]?out', str(p.get('text',''))+' '+event_type(p),re.I) is not None
def is_non_team(p):
    t=str(p.get('text',''))+' '+event_type(p)
    return re.search(r'(?:official|mandatory|media|television|tv|referee|commercial)[\s-]*(?:team[\s-]*)?time[\s-]?out|time[\s-]?out[\s-]*(?:official|mandatory|media|tv)',t,re.I) is not None
events=[]
counts={}
for i,p in enumerate(plays):
    if not is_timeout(p):continue
    team=str((p.get('team') or {}).get('id') or p.get('teamId') or '')
    period=(p.get('period') or {}).get('number',p.get('period'))
    typ=p.get('type') or {}
    obj={'index':i,'id':p.get('id'),'sequenceNumber':p.get('sequenceNumber'),
         'period':period,'clock':(p.get('clock') or {}).get('displayValue'),
         'team_id':team,'type_id':typ.get('id'),
         'type':event_type(p),'text':p.get('text'),
         'non_team_regex':is_non_team(p)}
    events.append(obj)
    if team and not is_non_team(p):
        counts[team]=counts.get(team,0)+1
head=raw.get('header') or {}
competition=(head.get('competitions') or [{}])[0]
competitors=[{'id':str((c.get('team') or {}).get('id')),
              'abbr':(c.get('team') or {}).get('abbreviation'),
              'homeAway':c.get('homeAway'),'timeouts':c.get('timeouts'),
              'timeOuts':c.get('timeOuts')}
             for c in competition.get('competitors') or []]
data={'event':target_id,'plays':len(plays),'event_count':len(events),
      'counts_current_parser':counts,'competitors':competitors,'events':events}
(root/'timeout-audit.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'events':len(events),'counts':counts,'teams':competitors},indent=2))
