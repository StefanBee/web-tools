import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';

const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const source=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(source,'App JavaScript found');
new Function(source);
const from=source.indexOf('function scheduleScrollDelta(');
const to=source.indexOf('function drawSchedule(',from);
assert.ok(from>=0&&to>from,'Schedule scroll helper exists');
const scheduleScrollDelta=new Function(source.slice(from,to)+'return scheduleScrollDelta;')();
assert.match(source.slice(to,source.indexOf('async function loadSchedule(',to)),/list\.scrollTop\+=scheduleScrollDelta\(/);

test('highlighted schedule row stays put while safely visible',()=>{
 assert.equal(scheduleScrollDelta('nearest',200,240,150,400),0);
 assert.equal(scheduleScrollDelta('nearest',150,190,150,400),0);
});
test('upward navigation reveals a row obscured by the sticky date heading',()=>{
 assert.equal(scheduleScrollDelta('nearest',131,175,150,400),-19);
 assert.equal(scheduleScrollDelta('nearest',-30,10,150,400),-180);
});
test('downward navigation reveals the selected row',()=>{
 assert.equal(scheduleScrollDelta('nearest',390,430,150,400),30);
});
test('initial schedule selection aligns below the date heading',()=>{
 assert.equal(scheduleScrollDelta('start',300,340,150,400),150);
});
