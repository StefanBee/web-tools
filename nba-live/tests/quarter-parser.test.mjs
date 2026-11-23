import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';

const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const fixture=JSON.parse(readFileSync(new URL('./fixtures/espn-tor-orl.json',import.meta.url),'utf8'));
const code=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(code,'Inline app script present');
new Function(code);
function extract(from,to){
 const a=code.indexOf(from),b=code.indexOf(to,a+from.length);
 assert.ok(a>=0&&b>a,`Parser section ${from}`);
 return code.slice(a,b);
}
const player=parsePlayerFallback();
function parsePlayerFallback(){
 const state={raw:fixture,players:{away:[],home:[]},period:'ALL'};
 const api=new Function('state','fixture',`
 var game=function(){return state.game};
 var number=function(v){return Number(v)||0};
 var playType=function(p){return String((p.type||{}).text||'')};
 var allPlays=function(r){return r.plays||[]};
 var readPeriod=function(p){return (p.period||{}).number||p.period||0};
 ${extract('function madeAttempts(', '/* The summary already carries')}
 ${extract('function playerPeriodTotals(', 'function scoringRun(')}
 return {derivePlays,playFacts,playerPeriodTotals};
 `)(state,fixture);
 return {state,api};
}
const official=Object.fromEntries(fixture.boxscore.teams.map(t=>[t.team.id,Object.fromEntries(t.statistics.map(x=>[x.name,x.displayValue]))]));
player.state.game={away:{id:fixture.boxscore.teams[0].team.id},home:{id:fixture.boxscore.teams[1].team.id}};
test('450 real ESPN plays reproduce official team shooting, rebounds, turnovers and fouls',()=>{
 const d=player.api.derivePlays(fixture,player.state.game,'ALL').teams;
 for(const [id,o] of Object.entries(official)){
  const a=d[id];
  assert.equal(a.fgm+'-'+a.fga,o['fieldGoalsMade-fieldGoalsAttempted'],id+' FG');
  assert.equal(a.tpm+'-'+a.tpa,o['threePointFieldGoalsMade-threePointFieldGoalsAttempted'],id+' 3PT');
  assert.equal(a.ftm+'-'+a.fta,o['freeThrowsMade-freeThrowsAttempted'],id+' FT');
  assert.equal(String(a.reb),o.totalRebounds,id+' REB');
  assert.equal(String(a.to),o.totalTurnovers,id+' TO');
  assert.equal(String(a.pf),o.fouls,id+' PF');
 }
});
test('real ESPN plays reproduce official player box scores',()=>{
 let checked=0;
 for(const team of fixture.boxscore.players){
  for(const group of team.statistics){
   for(const row of group.athletes){
    if(!row.stats?.length)continue;
    const o=Object.fromEntries(group.names.map((x,i)=>[x,row.stats[i]]));
    const s=player.api.playerPeriodTotals(fixture,row.athlete.id,'ALL');
    for(const [k,v] of Object.entries({PTS:'pts',REB:'reb',AST:'ast',TO:'to',STL:'stl',BLK:'blk'})){
     if(o[k]===undefined||o[k]==='')continue;
     assert.equal(s[v],Number(o[k]),row.athlete.displayName+' '+k);checked++;
    }
    for(const [k,m,a] of [['FG','fgm','fga'],['3PT','tpm','tpa'],['FT','ftm','fta']]){
     const x=String(o[k]||'').match(/^(\d+)-(\d+)$/);if(!x)continue;
     assert.equal(s[m],Number(x[1]),row.athlete.displayName+' '+k+' made');
     assert.equal(s[a],Number(x[2]),row.athlete.displayName+' '+k+' attempted');checked+=2;
    }
   }
  }
 }
 assert.ok(checked>200);
});
test('per-quarter field goals and 3PT add up to the full game',()=>{
 const all=player.api.derivePlays(fixture,player.state.game,'ALL').teams;
 for(const id of Object.keys(all)){
  const summed={fgm:0,fga:0,tpm:0,tpa:0,ftm:0,fta:0};
  for(let q=1;q<=4;q++){
   const part=player.api.derivePlays(fixture,player.state.game,q).teams[id];
   for(const k of Object.keys(summed))summed[k]+=part[k];
  }
  for(const [k,v] of Object.entries(summed))assert.equal(v,all[id][k],id+' '+k);
 }
});
test('no double count for duplicate ESPN play IDs',()=>{
 const more={...fixture,plays:fixture.plays.concat(fixture.plays[2])};
 assert.deepEqual(player.api.derivePlays(more,player.state.game,'ALL').teams,player.api.derivePlays(fixture,player.state.game,'ALL').teams);
});
