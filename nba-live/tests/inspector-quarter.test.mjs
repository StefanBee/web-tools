import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';

const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const fixture=JSON.parse(readFileSync(new URL('./fixtures/espn-tor-orl.json',import.meta.url),'utf8'));
const source=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(source);
new Function(source);

function section(start,end){
 const a=source.indexOf(start),b=source.indexOf(end,a+start.length);
 assert.ok(a!==-1&&b>a,start);
 return source.slice(a,b);
}
function setup(){
 const elems={};
 const document={activeElement:null};
 function el(id){
  if(!elems[id]){
   const obj={id,dataset:{},hidden:true,textContent:'',innerHTML:'',classList:{toggle(){}},
    focus(){document.activeElement=this},setAttribute(){},querySelectorAll(){return []}};
   elems[id]=obj;
  }
  return elems[id];
 }
 const g={away:{id:'28',abbr:'TOR',line:[]},home:{id:'19',abbr:'ORL',line:[]},status:{period:3}};
 const player={id:'2489663',name:'Kelly Olynyk',jersey:'41',pts:'10'};
 const state={inspector:null,raw:fixture,players:{away:[player],home:[]}};
 function game(){return g}
 function currentPeriod(){return String(Math.max(1,g.status.period))}
 function periodChoices(){return Array.from({length:Math.max(4,g.status.period)},(_,i)=>String(i+1)).concat(['ALL'])}
 function allPlayers(side){return side==='away'?[player]:[]}
 function $(id){return el(id)}
 function periodLabel(p){return p>4?'OT'+(p-4):'Q'+p}
 function esc(v){return String(v)}
 function playType(p){return (p.type||{}).text||''}
 function readPeriod(p){return (p.period||{}).number||p.period||0}
 function allPlays(raw){return raw.plays||[]}
 const code=[
  'const {state,game,currentPeriod,periodChoices,allPlayers,$,periodLabel,esc,playType,readPeriod,allPlays}=env;',
  'function focusRegion(){}',
  section('function madeAttempts(', '/* The summary already carries'),
  section('function playerPeriodTotals(', 'function scoringRun('),
  section('function renderInspector(){', '/* Reconstruct the live five'),
  'return {openInspector,selectInspectorPeriod,renderInspector};'
 ].join('\n');
 const app=new Function('env',code)({state,game,currentPeriod,periodChoices,allPlayers,$,periodLabel,esc,playType,readPeriod,allPlays});
 return {app,state,elems,g,player,fixture,el};
}
test('popup opens on current Q3',()=>{
 const {app,state,el}=setup();
 app.openInspector('away','2489663');
 assert.equal(state.inspector.period,3);
 assert.equal(state.inspector.followCurrent,true);
 assert.match(el('inspector-context').textContent,/Q3 · CURRENT/);
 assert.match(el('inspector-periods').innerHTML,/data-inspector-period="1"/);
 assert.match(el('inspector-periods').innerHTML,/data-inspector-period="4"/);
 assert.equal(el('inspector-overlay').hidden,false);
});
test('Q1–Q4 selection changes displayed stats and remains fixed across refreshes',()=>{
 const {app,state,g,el}=setup();
 app.openInspector('away','2489663');
 app.selectInspectorPeriod(1);
 assert.equal(state.inspector.period,1);
 assert.equal(state.inspector.followCurrent,false);
 const first=el('inspector-body').innerHTML;
 assert.match(el('inspector-context').textContent,/Q1 only/);
 app.selectInspectorPeriod(2);
 assert.equal(state.inspector.period,2);
 assert.notEqual(first,el('inspector-body').innerHTML);
 g.status.period=4;
 app.renderInspector();
 assert.equal(state.inspector.period,2);
 assert.match(el('inspector-context').textContent,/Q2 only/);
 app.selectInspectorPeriod(4);
 assert.equal(state.inspector.period,4);
 assert.match(el('inspector-context').textContent,/Q4 only/);
});
test('default follows quarter changes until manually selected',()=>{
 const {app,state,g,el}=setup();
 app.openInspector('away','2489663');
 g.status.period=4;
 app.renderInspector();
 assert.equal(state.inspector.period,4);
 assert.match(el('inspector-context').textContent,/Q4 · CURRENT/);
});
test('overtime appears automatically and missing period never fabricates stats',()=>{
 const {app,g,el,state}=setup();
 app.openInspector('away','2489663');
 g.status.period=5;
 app.renderInspector();
 assert.match(el('inspector-periods').innerHTML,/data-inspector-period="5"/);
 app.selectInspectorPeriod(5);
 assert.equal(state.inspector.period,5);
 assert.match(el('inspector-context').textContent,/OT1 only/);
 assert.match(el('inspector-body').innerHTML,/unavailable/i);
});
test('invalid quarter selections are ignored',()=>{
 const {app,state}=setup();
 app.openInspector('away','2489663');
 app.selectInspectorPeriod(7);
 assert.equal(state.inspector.period,3);
 app.selectInspectorPeriod(0);
 assert.equal(state.inspector.period,3);
});
test('numeric hotkeys, touch handler, accessible button state are present',()=>{
 assert.match(source,/selectInspectorPeriod\(Number\(e\.key\)\)/);
 assert.match(source,/inspector-periods'\)\.addEventListener\('click'/);
 assert.match(source,/aria-pressed/);
});
