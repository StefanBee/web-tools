import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';

const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');

test('Team Statistics fills split-screen widths below the mobile breakpoint',()=>{
 // A fixed 453px width previously left a gap to the right in 650–749px windows.
 assert.match(html,/\.data\.team-data\{width:100%;min-width:453px\}/);
 assert.doesNotMatch(html,/\.data\.team-data\{width:453px;min-width:453px\}/);
});

test('narrow phones keep horizontal scroll and sticky team names',()=>{
 assert.match(html,/\.scroll\{width:100%;overflow-x:auto/);
 assert.match(html,/\.data\.team-data th:first-child,\.data\.team-data td:first-child\{position:sticky;left:0/);
});

test('player tables keep their existing responsive dimensions',()=>{
 assert.match(html,/\.data:not\(\.team-data\)\{width:710px;min-width:710px\}/);
});
