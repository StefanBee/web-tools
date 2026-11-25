import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';

const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const source=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(source,'NBA Live inline script exists');
new Function(source);

const from=source.indexOf('function standingsMetric(');
const to=source.indexOf('function paletteActions(){',from);
assert.ok(from>=0&&to>from,'Found the standings logic');
const logic=source.slice(from,to);
function entry(name,rank,conference){
 return {team:{displayName:name},stats:[
  {name:'wins',displayValue:String(26-rank)},
  {name:'losses',displayValue:String(3+rank)},
  {name:'playoffSeed',displayValue:String(rank)},
  {name:'gamesBehind',displayValue:rank===1?'-':String((rank-1)/2)},
  {name:'Last Ten Games',displayValue:conference==='West'?'7-3':'6-4'}
 ]};
}
function fixture(){
 function entries(side){
  return Array.from({length:15},(_,i)=>
   entry(i===0?(side==='West'?'Minnesota Timberwolves':'Philadelphia 76ers'):side+' Team Full Name '+(i+1),i+1,side)
  ).reverse();
 }
 return {children:[
  {name:'Western Conference',standings:{entries:entries('West')}},
  {name:'Eastern Conference',standings:{entries:entries('East')}}
 ]};
}
function setup(){
 let requests=0;
 const els=new Map(),state={active:'teams'},standings={open:false,busy:false,error:'',data:null,updated:0,serial:0};
 function $(id){
  if(!els.has(id))els.set(id,{
   hidden:true,innerHTML:'',textContent:'',classList:{toggle(){}},focus(){},blur(){}
  });
  return els.get(id);
 }
 const app=new Function('env',
  'const {standings,$,get,esc,focusRegion,state}=env;\n'+logic+
  '\nreturn {parseStandings,standingsTable,drawStandings,openStandings,closeStandings};'
 )({standings,$,state,get:async()=>{requests++;return fixture()},esc:String,focusRegion(){}});
 return {app,standings,$,requests:()=>requests};
}
test('standings include both conferences and preserve full names',()=>{
 const {app}=setup(),data=app.parseStandings(fixture());
 assert.equal(data.West.length,15);
 assert.equal(data.East.length,15);
 assert.equal(data.West[0].name,'Minnesota Timberwolves');
 assert.equal(data.East[0].name,'Philadelphia 76ers');
 assert.equal(data.West[0].l10,'7-3');
 assert.equal(data.East[0].l10,'6-4');
 assert.equal(data.West[0].gb,'—');
 assert.equal(data.West[1].gb,'0.5');
});
test('render produces 30 compact rows and every full team name',()=>{
 const {app,standings,$}=setup();
 standings.open=true;
 standings.data=app.parseStandings(fixture());
 app.drawStandings();
 const output=$('standings-body').innerHTML;
 assert.equal((output.match(/<tr(?: class="cut")?>/g)||[]).length,30);
 assert.match(output,/Minnesota Timberwolves/);
 assert.match(output,/Philadelphia 76ers/);
 assert.match(output,/WESTERN CONFERENCE/);
 assert.match(output,/EASTERN CONFERENCE/);
 assert.match(output,/>W<\/th>/);
 assert.match(output,/>L10<\/th>/);
});
test('incomplete standings fail instead of inventing teams or statistics',()=>{
 const {app}=setup(),data=fixture();
 data.children[0].standings.entries.pop();
 assert.throws(()=>app.parseStandings(data),/Incomplete conference/);
 const missing=fixture();
 missing.children[0].standings.entries[0].team.displayName='';
 assert.throws(()=>app.parseStandings(missing),/Incomplete team/);
});
test('missing L10 shows dash and missing GB derives from official W/L',()=>{
 const {app}=setup(),data=fixture();
 const target=data.children[0].standings.entries[0];
 target.stats=target.stats.filter(s=>!['Last Ten Games','gamesBehind'].includes(s.name));
 const parsed=app.parseStandings(data);
 const row=parsed.West.find(r=>r.name===target.team.displayName);
 assert.equal(row.l10,'—');
 assert.notEqual(row.gb,'');
});
test('popup only fetches on demand and reuses fresh standings cache',async()=>{
 const {app,standings,$,requests}=setup();
 assert.equal(requests(),0);
 app.openStandings();
 assert.equal($('standings-overlay').hidden,false);
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(requests(),1);
 assert.equal(standings.data.West.length,15);
 app.closeStandings();
 assert.equal($('standings-overlay').hidden,true);
 app.openStandings();
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(requests(),1,'cached data should avoid an extra network request');
});
test('palette supports rankings and standings; Escape closes modal',()=>{
 assert.match(source,/label:'Rankings · NBA standings'/);
 assert.match(source,/kind:'COMMAND',run:openStandings/);
 assert.match(source,/standings\.open\)\s*\{\s*if\(e\.key==='Escape'\)/);
 assert.match(source,/\$\('standings-close'\)\.addEventListener\('click',closeStandings\)/);
});
