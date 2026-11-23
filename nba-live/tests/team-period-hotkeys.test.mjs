import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';

const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const source=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(source,'NBA Live script found');
new Function(source);

function section(start,end){
 const a=source.indexOf(start),b=source.indexOf(end,a+start.length);
 assert.ok(a>=0&&b>a,'Found '+start);
 return source.slice(a,b);
}
function setup(){
 let keydown,current='3';
 const inspectorKeys=[];
 class HTMLInputElement {}
 class HTMLSelectElement {}
 const state={active:'teams',period:'3',followCurrent:true,inspector:null,paletteOpen:false};
 const schedule={open:false};
 const document={addEventListener(type,listener){if(type==='keydown')keydown=listener}};
 const env={document,state,schedule,HTMLInputElement,HTMLSelectElement,
  currentPeriod(){return current},paintPeriods(){},renderTables(){},focusRegion(){},scrollToRegion(){},
  selectInspectorPeriod(n){inspectorKeys.push(n)},closeInspector(){},openPalette(){},closePalette(){},
  closeSchedule(){},moveSchedule(){},viewScheduledGame(){},paletteRun(){},drawPalette(){},
  moveCursor(){},changeSort(){},allPlayers(){return []},openInspector(){},
  $(){return {focus(){},querySelector(){return null}}}
 };
 const logic=section('function periodSelect(value){','/* Lightweight, lazy 7-day');
 const keys=section("document.addEventListener('keydown',function(e){","$('game-picker').addEventListener");
 new Function('env','const {'+Object.keys(env).join(',')+'}=env;\n'+logic+'\n'+keys)(env);
 assert.equal(typeof keydown,'function');
 return {state,schedule,inspectorKeys,Input:HTMLInputElement,
  setCurrent(quarter){current=quarter},
  key(key,overrides={}){
   let prevented=false;
   keydown({key,ctrlKey:false,metaKey:false,altKey:false,shiftKey:false,
    target:{isContentEditable:false},preventDefault(){prevented=true},...overrides});
   return prevented;
  }
 };
}

test('1–4 select pinned Q1–Q4 when the Team Statistics table is active',()=>{
 const app=setup();
 for(let n=1;n<=4;n++){
  assert.equal(app.key(String(n)),true);
  assert.equal(app.state.period,String(n));
  assert.equal(app.state.followCurrent,false);
 }
});
test('5 selects official full-game ALL and stops following the live quarter',()=>{
 const app=setup();
 assert.equal(app.key('5'),true);
 assert.equal(app.state.period,'ALL');
 assert.equal(app.state.followCurrent,false);
});
test('0 jumps to the current quarter and resumes automatic following',()=>{
 const app=setup();
 app.key('2');
 app.setCurrent('4');
 assert.equal(app.key('0'),true);
 assert.equal(app.state.period,'4');
 assert.equal(app.state.followCurrent,true);
 app.setCurrent('3');
 assert.equal(app.key('0'),true);
 assert.equal(app.state.period,'3');
});
test('shortcuts do not change team period in away/home tables',()=>{
 const app=setup();
 for(const region of ['away','home']){
  app.state.active=region;
  assert.equal(app.key('1'),false);
  assert.equal(app.key('5'),false);
  assert.equal(app.key('0'),false);
  assert.equal(app.state.period,'3');
 }
});
test('player inspector retains its own number shortcuts',()=>{
 const app=setup();
 app.state.inspector={};
 assert.equal(app.key('2'),true);
 assert.deepEqual(app.inspectorKeys,[2]);
 assert.equal(app.state.period,'3');
});
test('schedule, palette, typing and modified keys do not switch team period',()=>{
 const app=setup();
 app.schedule.open=true;app.key('2');app.schedule.open=false;
 app.state.paletteOpen=true;app.key('2');app.state.paletteOpen=false;
 for(const override of [{ctrlKey:true},{metaKey:true},{altKey:true},{shiftKey:true},
  {target:new app.Input()},{target:{isContentEditable:true}}]){
  assert.equal(app.key('2',override),false);
 }
 assert.equal(app.state.period,'3');
});
