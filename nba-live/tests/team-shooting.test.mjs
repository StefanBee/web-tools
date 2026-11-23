import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';

const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const f=JSON.parse(readFileSync(new URL('./fixtures/bos-gsw-shooting.json',import.meta.url),'utf8'));
const source=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(source,'Inline JavaScript is present');
new Function(source);

function section(from,to){
 const a=source.indexOf(from),b=source.indexOf(to,a+from.length);
 assert.ok(a>=0&&b>a,from);
 return source.slice(a,b);
}
const common=section('function madeAttempts(', 'function validateTeamPeriods(');
const rowsCode=section('function getTeamRows(){','function sortValue(');
function mockGame(period='ALL'){
 const a=f.teams.away,h=f.teams.home;
 const gameData={
  away:{id:a.id,abbr:a.abbr,score:a.pts,line:a.quarters.map(q=>({value:q.pts}))},
  home:{id:h.id,abbr:h.abbr,score:h.pts,line:h.quarters.map(q=>({value:q.pts}))}
 };
 const raw={boxscore:{teams:[a,h].map(t=>({team:{id:t.id},statistics:[
  {name:'fieldGoalsMade-fieldGoalsAttempted',displayValue:t.fg},
  {name:'threePointFieldGoalsMade-threePointFieldGoalsAttempted',displayValue:t.three},
  {name:'freeThrowsMade-freeThrowsAttempted',displayValue:t.ft}
 ]}))}};
 const state={period,raw,followCurrent:false,players:{away:[],home:[]},description:''};
 const api=new Function('env',[
   'const {state,game,$,derivePlays,validateTeamPeriods,periodLabel}=env;',
   common,rowsCode,
   'return {getTeamRows,teamBoxTotals,twoPointShots,madeAttempts};'
 ].join('\n'))({
  state,game:()=>gameData,
  $:()=>({set textContent(v){state.description=v}}),
  periodLabel:v=>'Q'+v,
  validateTeamPeriods:()=>Object.fromEntries([a.id,h.id].map(id=>[id,{fg:true,three:true,ft:true,reb:true,to:true,pf:true}])),
  derivePlays:(_raw,_g,q)=>{
   const get=t=>t.quarters.find(x=>x.period===q)||null;
   const by={};const teamPlays={};
   for(const t of [a,h]){
    const x=get(t);
    by[t.id]=x?{...x,reb:0,to:0,pf:0}:{fgm:0,fga:0,tpm:0,tpa:0,ftm:0,fta:0,reb:0,to:0,pf:0};
    teamPlays[t.id]=x?25:0;
   }
   return {teams:by,teamPlays,count:50};
  }
 });
 return {api,state};
}

test('ESPN ALL shooting is separate for BOS and GSW, with correct 2PT',()=>{
 const {api,state}=mockGame();
 const [bos,gs]=api.getTeamRows();
 assert.deepEqual([bos.name,bos.fg,bos.two,bos.three,bos.ft],['BOS','32-83','18-36','14-47','9-12']);
 assert.deepEqual([gs.name,gs.fg,gs.two,gs.three,gs.ft],['GS','33-83','19-38','14-45','8-10']);
 assert.match(state.description,/FG = 2PT \+ 3PT/);
});
test('real archived BOS-GSW Q1-Q4 shooting sums match ALL for each team',()=>{
 const result={away:{fgm:0,fga:0,tpm:0,tpa:0,ftm:0,fta:0,twom:0,twoa:0},
               home:{fgm:0,fga:0,tpm:0,tpa:0,ftm:0,fta:0,twom:0,twoa:0}};
 for(let q=1;q<=4;q++){
  const {api}=mockGame(q),periodRows=api.getTeamRows();
  periodRows.forEach((row,i)=>{
   const side=i?'home':'away';
   const fg=api.madeAttempts(row.fg),two=api.madeAttempts(row.two);
   const three=api.madeAttempts(row.three),ft=api.madeAttempts(row.ft);
   assert.ok(fg&&two&&three&&ft,side+' Q'+q+' has every shot category');
   assert.equal(fg.made,two.made+three.made,side+' Q'+q+' makes');
   assert.equal(fg.attempted,two.attempted+three.attempted,side+' Q'+q+' attempts');
   for(const [key,val] of [['fgm',fg.made],['fga',fg.attempted],['tpm',three.made],['tpa',three.attempted],
                           ['ftm',ft.made],['fta',ft.attempted],['twom',two.made],['twoa',two.attempted]])result[side][key]+=val;
  });
 }
 for(const side of ['away','home']){
  const t=f.teams[side],x=result[side];
  assert.equal(x.fgm+'-'+x.fga,t.fg,side+' FG');
  assert.equal(x.tpm+'-'+x.tpa,t.three,side+' 3PT');
  assert.equal(x.ftm+'-'+x.fta,t.ft,side+' FT');
  assert.equal(x.twom+'-'+x.twoa,side==='away'?'18-36':'19-38',side+' 2PT');
 }
});
test('BOS and GSW official team totals match sum of their own player box scores',()=>{
 for(const side of ['away','home']){
  const t=f.teams[side];
  for(const key of ['fg','three','ft']){
   const p=t.playerTotals[key];
   assert.equal(p.missing_players,0);
   assert.equal(p.made+'-'+p.attempted,t[key],side+' '+key);
  }
 }
});
test('2PT breakdown handles dashes and inconsistent records without inventing data',()=>{
 const {api}=mockGame();
 assert.equal(api.twoPointShots('32-83','14-47'),'18-36');
 assert.equal(api.twoPointShots('33-83','14-45'),'19-38');
 assert.equal(api.twoPointShots('32/83','14/47','/'),'18/36');
 assert.equal(api.twoPointShots(null,'14-47'),null);
 assert.equal(api.twoPointShots('2-3','4-5'),null);
});
test('team table includes explicit 2PT alongside FG, 3PT and FT',()=>{
 assert.match(source,/var TEAM_COLS=\[\['name','TEAM'\],\['pts','PTS'\],\['fg','FG'\],\['two','2PT'\]/);
 assert.match(source,/FG = 2PT \+ 3PT/);
});
