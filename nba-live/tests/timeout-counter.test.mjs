import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';

const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const fixture=JSON.parse(readFileSync(new URL('./fixtures/bos-gsw-timeouts.json',import.meta.url),'utf8'));
const source=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(source,'App JavaScript found');
new Function(source);
const from=source.indexOf('function playType(p){');
const to=source.indexOf('function liveStateLabel(g,raw){',from);
assert.ok(from>0&&to>from);
const logic=source.slice(from,to);
function makeApi(raw){
 return new Function('raw','g',[
  'function allPlays(){return raw.plays;}',
  'function readPeriod(p){return (p.period||{}).number||0;}',
  logic,
  'return {timeoutPlay,nonTeamTimeout,calculateTimeouts,latestTimeout};'
 ].join('\n'))(raw,fixture.teams);
}
const api=makeApi(fixture);
test('Nov 22 BOS at GSW: only six dedicated timeout plays each, not 8/7',()=>{
 const result=api.calculateTimeouts(fixture,fixture.teams);
 assert.equal(result.complete,true);
 assert.equal(result.counts.REG['9'],6,'GSW used six Full Timeout events');
 assert.equal(result.counts.REG['2'],6,'BOS used six Full Timeout events');
 assert.equal(Object.keys(result.counts).join(','),'REG');
});
test('successful coach challenges retaining their timeout are not charged events',()=>{
 const challenges=fixture.plays.filter(p=>/Coach.s Challenge/i.test(p.type.text));
 assert.equal(challenges.length,3);
 for(const p of challenges){
  assert.match(p.text,/retain their timeout/i);
  assert.equal(api.timeoutPlay(p),false);
 }
 assert.equal(api.timeoutPlay({type:{text:'Full Timeout'},text:'Warriors Full timeout'}),true);
 assert.equal(api.timeoutPlay({type:{text:'Short Timeout'},text:'Warriors Short timeout'}),true);
});
test('official timeout, descriptive mention, and duplicate ID are not charged',()=>{
 const dup=fixture.plays.find(p=>p.type.text==='Full Timeout'&&p.team.id==='9');
 const extra=[
  dup,
  {id:'official',period:{number:4},team:{id:'9'},type:{text:'Official Timeout'},text:'OFFICIAL TIMEOUT'},
  {id:'review',period:{number:4},team:{id:'9'},type:{text:"Coach's Challenge (Overturned)"},text:'Warriors retain their timeout'},
  {id:'caption',period:{number:4},team:{id:'9'},type:{text:'Instant Replay'},text:'Warriors retain their timeout'}
 ];
 const totals=makeApi({...fixture,plays:[...fixture.plays,...extra]}).calculateTimeouts(null,fixture.teams);
 assert.equal(totals.counts.REG['9'],6);
});
test('overtime timeouts have a separate 2-timeout allowance bucket',()=>{
 const overtime={...fixture,plays:[...fixture.plays,{id:'ot-1',period:{number:5},team:{id:'9'},type:{text:'Full Timeout'},text:'Warriors Full timeout'}]};
 const totals=makeApi(overtime).calculateTimeouts(null,fixture.teams);
 assert.equal(totals.counts.REG['9'],6);
 assert.equal(totals.counts['5']['9'],1);
});
test('types with no timeout but mention it in prose are not classified as timeout',()=>{
 assert.equal(api.timeoutPlay({type:{text:'Ref-Initiated Review'},text:'Warriors get timeout back'}),false);
 assert.equal(api.timeoutPlay({type:{text:"Coach's Challenge (Overturned)"},text:'Warriors retain their timeout'}),false);
 assert.equal(api.timeoutPlay({type:{text:'Full Timeout'},text:'Golden State Full timeout'}),true);
});
