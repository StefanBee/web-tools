import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';

const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const fixture=JSON.parse(readFileSync(new URL('./fixtures/espn-tor-orl.json',import.meta.url),'utf8'));
const source=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(source);new Function(source);
const from=source.indexOf('function clockRemaining(');
const to=source.indexOf('/* Player quarter numbers',from);
assert.ok(from>=0&&to>from);
const code=source.slice(from,to);
const roster=Array.from({length:5},(_,i)=>({id:'p'+i,name:'Player '+i,starter:false,dnp:false,min:'—'}));
roster.push({id:'b',name:'Bench Player',starter:false,dnp:false,min:'—'});
function setup(){
 const state={players:{away:roster,home:[]}};
 return new Function('env','const {state,allPlays,readPeriod,playType}=env;\n'+code+'\nreturn {playerPeriodMinutes,clockRemaining};')({
  state,allPlays:r=>r.plays,readPeriod:p=>p.period.number,playType:p=>p.type.text
 });
}
function ev(period,clock,kind,incoming,outgoing){
 const entry={period:{number:period},clock:clock,type:{text:kind},text:'',team:{id:'A'},participants:[],shootingPlay:kind==='Jump Shot'};
 if(incoming)entry.participants.push({athlete:{id:incoming}});
 if(outgoing)entry.participants.push({athlete:{id:outgoing}});
 if(kind==='Substitution')entry.text=incoming+' enters the game for '+(outgoing||'');
 return entry;
}
function game(period,displayClock='0:00',completed=true){
 return {away:{id:'A'},home:{id:'B'},status:{period,displayClock,type:{completed}}};
}
test('numeric ESPN clock.value and clock.displayValue are both usable',()=>{
 const {clockRemaining}=setup();
 assert.equal(clockRemaining({value:420}),420);
 assert.equal(clockRemaining({displayValue:'7:00',value:420}),420);
 assert.equal(clockRemaining(420),420);
 assert.equal(clockRemaining({displayValue:'',value:300}),300);
 assert.equal(clockRemaining(null),null);
});
test('Q2 historical minutes are recalculated after a game advances to Q4',()=>{
 const {playerPeriodMinutes:mins}=setup();
 const rows=[
  ev(2,{displayValue:'12:00'},'Start Period'),
  ev(2,{value:540},'Substitution','b','p0'),
  ev(2,{displayValue:'3:00'},'Substitution','p0','b'),
  ev(2,{displayValue:'0:00'},'End Period')
 ];
 assert.equal(mins({plays:rows},game(4),'away','p0',2),'6:00');
 assert.equal(mins({plays:rows},game(4),'away','b',2),'6:00');
});
test('out-of-order Q2 substitution corrections are replayed chronologically',()=>{
 const {playerPeriodMinutes:mins}=setup();
 const rows=[
  ev(2,{displayValue:'12:00'},'Start Period'),
  ev(2,{displayValue:'3:00'},'Substitution','p0','b'),
  ev(2,{displayValue:'9:00'},'Substitution','b','p0'),
  ev(2,{displayValue:'0:00'},'End Period')
 ];
 assert.equal(mins({plays:rows},game(3),'away','p0',2),'6:00');
});
test('an incomplete substitution for a different player does not erase Q2 MIN',()=>{
 const {playerPeriodMinutes:mins}=setup();
 const rows=[
  ev(2,{displayValue:'12:00'},'Start Period'),
  ev(2,{displayValue:'10:00'},'Substitution','b','p0'),
  ev(2,{displayValue:'8:00'},'Substitution','p3',null),
  ev(2,{displayValue:'3:00'},'Substitution','p0','b'),
  ev(2,{displayValue:'0:00'},'End Period')
 ];
 assert.equal(mins({plays:rows},game(3),'away','p0',2),'5:00');
 assert.equal(mins({plays:rows},game(3),'away','b',2),'7:00');
 assert.equal(mins({plays:rows},game(3),'away','p3',2),null);
});
test('player with no reliable Q2 timeline is unavailable rather than invented',()=>{
 const {playerPeriodMinutes:mins}=setup();
 const rows=[ev(2,{displayValue:'12:00'},'Start Period'),ev(2,{displayValue:'0:00'},'End Period')];
 assert.equal(mins({plays:rows},game(4),'away','p0',2),null);
});
test('the real saved ESPN fixture lacks clocks and cannot support exact Q2 minutes',()=>{
 const count=fixture.plays.filter(p=>p.period.number===2&&p.clock!=null).length;
 assert.equal(count,0,'the fixture has no clock data; do not infer minutes from play order');
});
test('player popup explains the cause when minutes remain unavailable',()=>{
 assert.match(source,/ESPN has no usable play-clock times for this period/);
 assert.match(source,/ESPN substitutions or playing-time evidence are incomplete for this period/);
});
