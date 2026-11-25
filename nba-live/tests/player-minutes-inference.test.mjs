import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';

const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(script);
new Function(script);
const begin=script.indexOf('function clockRemaining(');
const end=script.indexOf('/* Player quarter numbers',begin);
assert.ok(begin>=0&&end>begin);
const code=script.slice(begin,end);
const roster=Array.from({length:5},(_,i)=>({id:'p'+i,name:'Player '+i,starter:false,dnp:false,min:'—'}));
roster.push({id:'b',name:'Bench Player',starter:false,dnp:false,min:'—'});
function make(rosterCopy=roster){
 const state={players:{away:rosterCopy,home:[]}};
 return new Function('env','const {state,allPlays,readPeriod,playType}=env;\n'+code+'\nreturn {playerPeriodMinutes,playerPeriodSeconds};')({
  state,allPlays:r=>r.plays,readPeriod:p=>p.period.number,playType:p=>p.type.text
 });
}
function play(period,clock,type,who,other){
 const p={period:{number:period},clock:clock===null?null:{displayValue:clock},
   type:{text:type},team:{id:'A'},text:'',participants:[],shootingPlay:type==='Jump Shot'};
 if(who)p.participants.push({athlete:{id:who}});
 if(other)p.participants.push({athlete:{id:other}});
 return p;
}
function sub(period,clock,incoming,outgoing){
 const p=play(period,clock,'Substitution',incoming,outgoing);
 p.text=(incoming||'')+' enters the game for '+(outgoing||'');
 return p;
}
function status(period=1,clock='0:00',completed=true){
 return {away:{id:'A'},home:{id:'B'},status:{period,displayClock:clock,type:{completed}}};
}
test('infers starter and bench MIN from first substitutions without starter flags',()=>{
 const {playerPeriodMinutes:mins}=make();
 const events=[play(1,'12:00','Start Period'),sub(1,'7:00','b','p0'),sub(1,'4:00','p0','b'),play(1,'0:00','End Period')];
 assert.equal(mins({plays:events},status(),'away','p0',1),'9:00');
 assert.equal(mins({plays:events},status(),'away','b',1),'3:00');
});
test('a positive on-court action establishes a no-substitution player',()=>{
 const {playerPeriodMinutes:mins}=make();
 const events=[play(1,'12:00','Start Period'),play(1,'6:00','Jump Shot','p0'),play(1,'0:00','End Period')];
 assert.equal(mins({plays:events},status(),'away','p0',1),'12:00');
 assert.equal(mins({plays:events},status(),'away','p1',1),null);
});
test('quarter lineup changes do not depend on the previous quarter',()=>{
 const {playerPeriodMinutes:mins}=make();
 const events=[play(1,'12:00','Start Period'),sub(1,'5:00','b','p0'),play(1,'0:00','End Period'),
  play(2,'12:00','Start Period'),play(2,'7:00','Jump Shot','p0'),play(2,'0:00','End Period')];
 assert.equal(mins({plays:events},status(2),'away','p0',2),'12:00');
 assert.equal(mins({plays:events},status(2),'away','b',2),null);
});
test('live minutes honor game clock and new ESPN events',()=>{
 const {playerPeriodMinutes:mins}=make();
 const events=[play(1,'12:00','Start Period'),sub(1,'8:00','b','p0')];
 assert.equal(mins({plays:events},status(1,'6:00',false),'away','b',1),'2:00');
 assert.equal(mins({plays:events},status(1,'6:00',false),'away','p0',1),'4:00');
 assert.equal(mins({plays:events},status(1,'8:30',false),'away','b',1),'0:00');
});
test('OT1 and OT2 are five minutes each',()=>{
 const {playerPeriodMinutes:mins}=make();
 const events=[play(5,'5:00','Start Period'),sub(5,'3:00','b','p0'),play(5,'0:00','End Period'),
  play(6,'5:00','Start Period'),play(6,'4:00','Jump Shot','p0'),play(6,'0:00','End Period')];
 assert.equal(mins({plays:events},status(6),'away','p0',5),'2:00');
 assert.equal(mins({plays:events},status(6),'away','b',5),'3:00');
 assert.equal(mins({plays:events},status(6),'away','p0',6),'5:00');
});
test('duplicate substitution records do not double-count rotations',()=>{
 const {playerPeriodMinutes:mins}=make();
 const events=[play(1,'12:00','Start Period'),sub(1,'9:00','b','p0'),sub(1,'9:00','b','p0'),play(1,'0:00','End Period')];
 assert.equal(mins({plays:events},status(),'away','p0',1),'3:00');
 assert.equal(mins({plays:events},status(),'away','b',1),'9:00');
});
test('incomplete or contradictory substitutions yield unavailable minutes',()=>{
 const {playerPeriodMinutes:mins}=make();
 const base=[play(1,'12:00','Start Period'),sub(1,'7:00','b','p0'),play(1,'0:00','End Period')];
 const broken=base.map(p=>({...p}));broken[1]={...broken[1],clock:null};
 assert.equal(mins({plays:broken},status(),'away','p0',1),null);
 const contradiction=[play(1,'12:00','Start Period'),sub(1,'8:00','b','p0'),sub(1,'4:00','b','p0'),play(1,'0:00','End Period')];
 assert.equal(mins({plays:contradiction},status(),'away','p0',1),null);
});
test('real official starter flags support a player with no play events',()=>{
 const known=roster.map(p=>({...p}));
 known.slice(0,5).forEach(p=>p.starter=true);
 const {playerPeriodMinutes:mins}=make(known);
 const events=[play(1,'12:00','Start Period'),play(1,'0:00','End Period')];
 assert.equal(mins({plays:events},status(),'away','p0',1),'12:00');
 assert.equal(mins({plays:events},status(),'away','b',1),'0:00');
});
test('minutes remain marked as estimates in the inspector',()=>{
 assert.match(script,/MIN is estimated from ESPN on-court events, timed substitutions and the game clock/);
 assert.match(script,/Estimated from starting lineups and timed ESPN substitutions/);
});
