import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';

const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(script);
new Function(script);
const from=script.indexOf('function clockRemaining(');
const to=script.indexOf('/* Player quarter numbers',from);
assert.ok(from>=0&&to>from);
const code=script.slice(from,to);
const starters=Array.from({length:5},(_,i)=>({id:'p'+i,starter:true,dnp:false}));
const bench={id:'b',starter:false,dnp:false};
function event(period,time,type,incoming,outgoing){
 const value={period:{number:period},clock:time===null?null:{displayValue:time},type:{text:type},team:{id:'A'}};
 if(incoming)value.participants=outgoing?[{athlete:{id:incoming}},{athlete:{id:outgoing}}]:[{athlete:{id:incoming}}];
 return value;
}
function game(){return {away:{id:'A'},home:{id:'B'},status:{period:5,displayClock:'0:00',type:{completed:true}}}}
function plays(){
 return [
  event(1,'12:00','Start Period'),
  event(1,'6:00','Substitution','b','p0'),
  event(1,'2:00','Substitution','p0','b'),
  event(1,'0:00','End Period'),
  event(2,'12:00','Start Period'),
  event(2,'10:00','Substitution','b','p0'),
  event(2,'5:00','Substitution','p0','b'),
  event(2,'0:00','End Period'),
  event(3,'12:00','Start Period'),event(3,'0:00','End Period'),
  event(4,'12:00','Start Period'),event(4,'0:00','End Period'),
  event(5,'5:00','Start Period'),
  event(5,'3:00','Substitution','b','p0'),
  event(5,'1:00','Substitution','p0','b'),
  event(5,'0:00','End Period')
 ];
}
function setup(players=starters.concat(bench)){
 const state={players:{away:players,home:[]}};
 const fn=new Function('env',
  'const {state,allPlays,readPeriod,playType}=env;\n'+code+'\nreturn playerPeriodMinutes;'
 )({state,allPlays:r=>r.plays,readPeriod:p=>p.period.number,playType:p=>p.type.text});
 return (playsData,player,period,g=game())=>fn({plays:playsData},g,'away',player,period);
}
test('Q1 starter plays eight minutes and bench replacement four',()=>{
 const calc=setup(),events=plays();
 assert.equal(calc(events,'p0',1),'8:00');
 assert.equal(calc(events,'b',1),'4:00');
});
test('each quarter resets independently; a period with no player evidence is unknown',()=>{
 const calc=setup(),events=plays();
 assert.equal(calc(events,'p0',2),'7:00');
 assert.equal(calc(events,'b',2),'5:00');
 assert.equal(calc(events,'p0',3),null);
 assert.equal(calc(events,'b',3),null);
});
test('overtime uses five-minute periods',()=>{
 const calc=setup(),events=plays();
 assert.equal(calc(events,'p0',5),'3:00');
 assert.equal(calc(events,'b',5),'2:00');
});
test('live quarter uses the running game clock, not the full twelve minutes',()=>{
 const calc=setup();
 const events=plays().filter(p=>p.period.number===1&&p.clock.displayValue!=='0:00');
 const g=game();g.status={period:1,displayClock:'1:00',type:{state:'in'}};
 assert.equal(calc(events,'p0',1,g),'7:00');
});
test('missing starters can be inferred, but missing timing or identity remains unavailable',()=>{
 const events=plays();
 assert.equal(setup(starters.slice(0,4).concat(bench))(events,'p0',1),'8:00');
 const noClock=plays();noClock[1].clock=null;
 assert.equal(setup()(noClock,'p0',1),null);
 const missingSub=plays();missingSub[1].participants=[];
 assert.equal(setup()(missingSub,'p0',1),null);
});
test('activity by a player after they were subbed out reveals an incomplete rotation',()=>{
 const events=plays();
 const shot=event(1,'5:00','Jump Shot','p0');
 shot.shootingPlay=true;
 events.splice(2,0,shot);
 assert.equal(setup()(events,'p0',1),null);
});
test('popup includes a clearly qualified MIN tile',()=>{
 assert.ok(script.includes("['MIN',mins===null?'—':mins,'min']"));
 assert.match(script,/Estimated from starting lineups and timed ESPN substitutions/);
 assert.ok(script.includes('Quarter +/− is not available reliably.'));
});
