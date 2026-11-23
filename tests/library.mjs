import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source = fs.readFileSync(new URL('../src/library.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}}).outputText;
const {canUpdate, keepChecked, syncSummary} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
const base = {version:'1', error:null, missing:false, update:null};
const previous = {unmanaged:[], matching:{matched:2, unmatched:[], modified:[]}, addons:[
  {...base, id:1, name:'Syndicator', fileId:10, update:'291', blocked:true, download:{fileName:'S.zip', page:'p1'}},
  {...base, id:2, name:'Baganator', fileId:20, update:'862', blocked:true, download:{fileName:'B.zip', page:'p2', authorRelease:true}},
]};
const next = {unmanaged:[], addons:[{...base, id:1, name:'Syndicator', fileId:11}, {...base, id:2, name:'Baganator', fileId:20}]};
const merged = keepChecked(previous, next);
assert.equal(merged.addons[0].update, null, 'the installed addon loses its stale update');
assert.equal(merged.addons[0].blocked, true, 'the CurseForge download restriction is remembered');
assert.equal(merged.addons[0].download, undefined, 'the previous release source is discarded');
assert.deepEqual(merged.addons[1].download, previous.addons[1].download, 'untouched addons keep their download info');
assert.equal(merged.matching.matched, 2);
assert.deepEqual(previous.addons.filter(canUpdate).map(a => a.id), [2], 'Update all includes the author release');
assert.equal(canUpdate({...previous.addons[1], update:null}), false);
assert.equal(canUpdate({...previous.addons[0], blocked:false}), true);
assert.match(syncSummary(previous), /2 updates available.*1 requires a manual ZIP download/);
assert.match(syncSummary({...previous, addons:[previous.addons[0]]}), /1 update available/);
assert.doesNotMatch(syncSummary(merged), /manual ZIP/);

const local = {...previous.addons[0], download:{...previous.addons[0].download, localRelease:true}};
assert.equal(canUpdate(local), true, 'Update all includes a verified ZIP in Downloads');
assert.equal(canUpdate({...local, update:null}), false);
const localSummary = syncSummary({...previous, addons:[local]});
assert.match(localSummary, /1 update available/);
assert.doesNotMatch(localSummary, /manual ZIP/);

const rechecked = {...previous, addons: previous.addons.map(addon => ({
  ...addon, download: {...addon.download, authorRelease: !addon.download.authorRelease}
}))};
assert.deepEqual(keepChecked(previous, rechecked).addons.filter(canUpdate).map(a => a.id), [1], 'a fresh check replaces availability');
assert.deepEqual(keepChecked(previous, {...next, path:'/other/AddOns'}).addons.filter(canUpdate), []);
console.log('Library tests passed.');
